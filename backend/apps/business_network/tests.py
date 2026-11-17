import base64
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.common.tests_utils import add_member, auth_client, make_insurer, make_org, make_product, make_user
from apps.organizations.models import Membership, Organization
from apps.vehicles.models import Vehicle

from .models import (
    CustomerConsent,
    DealerBranch,
    DealerVehicle,
    Partnership,
    PartnershipCommissionTerms,
    PartnershipRequest,
)
from .services import (
    compute_dealer_commission,
    create_partnership_request,
    grant_consent,
    respond_to_partnership_request,
)


class BusinessNetworkTests(TestCase):
    def setUp(self):
        self.admin = make_user("bnadmin@example.com", role=User.Role.ADMIN)
        self.customer = make_user("bncustomer@example.com")

        # insurer
        self.insurer_org = make_org("BN Insurer", org_type=Organization.Type.INSURER)
        self.provider = make_user("bnprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        add_member(self.provider, self.insurer_org, Membership.Role.OWNER)
        self.insurer = make_insurer(self.insurer_org, "BN Insurer")

        # dealer
        self.dealer_org = make_org("BN Motors", org_type=Organization.Type.DEALER)
        self.dealer = make_user("bndealer@example.com", role=User.Role.DEALER_ADMIN)
        add_member(self.dealer, self.dealer_org, Membership.Role.OWNER)

        # another dealer (for isolation tests)
        self.dealer2_org = make_org("Other Motors", org_type=Organization.Type.DEALER)
        self.dealer2 = make_user("bndealer2@example.com", role=User.Role.DEALER_ADMIN)
        add_member(self.dealer2, self.dealer2_org, Membership.Role.OWNER)

        self.dealer_client = auth_client(self.dealer)
        self.provider_client = auth_client(self.provider)
        self.admin_client = auth_client(self.admin)

    def _verify(self, org):
        org.status = Organization.Status.VERIFIED
        org.verified_at = timezone.now()
        org.save(update_fields=["status", "verified_at"])

    def _make_inventory(self, dealership=None, **kwargs):
        return DealerVehicle.objects.create(
            dealership=dealership or self.dealer_org,
            make=kwargs.get("make", "Toyota"),
            model=kwargs.get("model", "Hilux"),
            year=kwargs.get("year", 2022),
            asking_price=kwargs.get("asking_price", Decimal("2500000.00")),
            **{k: v for k, v in kwargs.items() if k not in ("make", "model", "year", "asking_price")},
        )


class PartnershipFlowTests(BusinessNetworkTests):
    def test_partnership_list_serializes(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "Let's partner", self.dealer)
        respond_to_partnership_request(req, "approve", self.provider)

        resp = self.dealer_client.get("/api/v1/business-network/partnerships/", {"page_size": 100})
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["results"][0]
        self.assertEqual(result["insurer_id"], str(self.insurer.id))
        self.assertEqual(result["dealership_id"], str(self.dealer_org.id))
        self.assertEqual(result["dealership_name"], "BN Motors")

    def test_dealer_sends_request_and_insurer_approves(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "Let's partner", self.dealer)
        self.assertEqual(req.status, PartnershipRequest.Status.PENDING)

        partnership = respond_to_partnership_request(req, "approve", self.provider)
        self.assertEqual(partnership.status, Partnership.Status.ACTIVE)
        self.assertEqual(partnership.insurer, self.insurer)
        self.assertEqual(partnership.dealership, self.dealer_org)

    def test_duplicate_request_blocked(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        create_partnership_request(self.dealer_org, self.insurer_org, "x", self.dealer)
        with self.assertRaises(ValueError):
            create_partnership_request(self.dealer_org, self.insurer_org, "again", self.dealer)

    def test_duplicate_active_partnership_blocked(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "x", self.dealer)
        respond_to_partnership_request(req, "approve", self.provider)
        req2 = create_partnership_request(self.insurer_org, self.dealer_org, "reverse", self.provider)
        with self.assertRaises(ValueError):
            respond_to_partnership_request(req2, "approve", self.dealer)

    def test_reject_and_more_info(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "x", self.dealer)
        respond_to_partnership_request(req, "more_info", self.provider, "Need more docs")
        self.assertEqual(req.status, PartnershipRequest.Status.MORE_INFO)

    def test_suspend_and_terminate(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "x", self.dealer)
        p = respond_to_partnership_request(req, "approve", self.provider)
        from .services import suspend_partnership, terminate_partnership

        suspend_partnership(p, self.provider, "Regulatory review")
        self.assertEqual(p.status, Partnership.Status.SUSPENDED)
        terminate_partnership(p, self.provider, "Ended")
        self.assertEqual(p.status, Partnership.Status.TERMINATED)


class InventoryIsolationTests(BusinessNetworkTests):
    def test_dealer_manages_own_inventory(self):
        v = self._make_inventory()
        resp = self.dealer_client.get("/api/v1/business-network/inventory/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

        # mark sold
        sold = self.dealer_client.post(f"/api/v1/business-network/inventory/{v.id}/mark-sold/")
        self.assertEqual(sold.status_code, 200)
        v.refresh_from_db()
        self.assertEqual(v.status, DealerVehicle.Status.SOLD)

    def test_other_dealer_cannot_see_or_modify(self):
        v = self._make_inventory()
        other = auth_client(self.dealer2)
        self.assertEqual(other.get("/api/v1/business-network/inventory/").json()["count"], 0)
        self.assertEqual(other.get(f"/api/v1/business-network/inventory/{v.id}/").status_code, 404)
        self.assertEqual(other.patch(f"/api/v1/business-network/inventory/{v.id}/", {"make": "Hacked"}, content_type="application/json").status_code, 404)

    def test_branch_management(self):
        branch = DealerBranch.objects.create(dealership=self.dealer_org, name="Nairobi Branch")
        resp = self.dealer_client.get("/api/v1/business-network/branches/")
        self.assertEqual(resp.json()["count"], 1)
        other = auth_client(self.dealer2)
        self.assertEqual(other.get("/api/v1/business-network/branches/").json()["count"], 0)


class DealerTransactionTests(BusinessNetworkTests):
    def test_dealer_quotation_request_with_consent_and_attribution(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "x", self.dealer)
        respond_to_partnership_request(req, "approve", self.provider)

        inv = self._make_inventory()
        make_product(self.insurer)
        resp = self.dealer_client.post(
            "/api/v1/business-network/dealer/quotations/",
            {
                "inventory_vehicle": str(inv.id),
                "insurer": str(self.insurer.id),
                "customer": str(self.customer.id),
                "coverage_type": "comprehensive",
                "sum_insured": "2500000.00",
                "desired_start_date": (timezone.now().date() + timedelta(days=3)).isoformat(),
                "data_categories": ["name", "contact", "vehicle"],
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertIsNotNone(data["request"]["dealership"])
        self.assertIsNotNone(data["request"]["partnership"])
        self.assertIsNotNone(data["consent"]["id"])

        from apps.insurance.models import Quotation, QuotationRequest

        qreq = QuotationRequest.objects.get(pk=data["request"]["id"])
        self.assertEqual(qreq.dealership, self.dealer_org)
        self.assertEqual(qreq.partnership.insurer, self.insurer)
        self.assertTrue(qreq.consent_id)
        self.assertEqual(Quotation.objects.filter(request=qreq).count(), 1)

        # customer got a Vehicle created
        self.assertTrue(Vehicle.objects.filter(owner=self.customer).exists())

    def test_dealer_quotation_requires_active_partnership(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        inv = self._make_inventory()
        resp = self.dealer_client.post(
            "/api/v1/business-network/dealer/quotations/",
            {
                "inventory_vehicle": str(inv.id),
                "insurer": str(self.insurer.id),
                "customer": str(self.customer.id),
                "coverage_type": "comprehensive",
                "sum_insured": "2500000.00",
                "desired_start_date": (timezone.now().date() + timedelta(days=3)).isoformat(),
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class DealerCustomerSearchTests(BusinessNetworkTests):
    def _active_partnership(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "Let's partner", self.dealer)
        return respond_to_partnership_request(req, "approve", self.provider)

    def test_dealer_searches_customers_by_email(self):
        self._active_partnership()
        resp = self.dealer_client.get("/api/v1/business-network/dealer/customers/", {"search": "bncustomer"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["id"], str(self.customer.id))
        # No consent yet: phone is minimised.
        self.assertEqual(resp.json()[0]["email"], "bncustomer@example.com")
        self.assertEqual(resp.json()[0]["phone"], "")

    def test_search_requires_active_partnership(self):
        self._verify(self.dealer_org)
        resp = self.dealer_client.get("/api/v1/business-network/dealer/customers/", {"search": "bncustomer"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_phone_returned_only_with_consent(self):
        self._active_partnership()
        self.customer.phone = "+254700000000"
        self.customer.save(update_fields=["phone"])
        grant_consent(self.customer, self.dealer_org, self.insurer)
        resp = self.dealer_client.get("/api/v1/business-network/dealer/customers/", {"search": "bncustomer"})
        self.assertEqual(resp.json()[0]["phone"], "+254700000000")

    def test_search_requires_minimum_term(self):
        self._active_partnership()
        resp = self.dealer_client.get("/api/v1/business-network/dealer/customers/", {"search": "b"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_non_dealer_cannot_search_customers(self):
        resp = self.provider_client.get("/api/v1/business-network/dealer/customers/", {"search": "bncustomer"})
        self.assertEqual(resp.status_code, 403)


class InsurerDiscoverTests(BusinessNetworkTests):
    def test_dealer_lists_verified_insurers(self):
        self._verify(self.insurer_org)
        resp = self.dealer_client.get("/api/v1/business-network/insurers/", {"page_size": 100})
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["organization_id"], str(self.insurer_org.id))
        self.assertEqual(results[0]["name"], "BN Insurer")


class CommissionTests(BusinessNetworkTests):
    def test_insurer_adds_commission_terms_via_api(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "x", self.dealer)
        p = respond_to_partnership_request(req, "approve", self.provider)
        resp = self.provider_client.post(
            f"/api/v1/business-network/partnerships/{p.id}/commission-terms/",
            {"commission_type": "percentage", "rate": "12.50"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["rate"], "12.50")
        self.assertEqual(p.commission_terms.count(), 1)

    def test_commission_terms_calculation(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "x", self.dealer)
        p = respond_to_partnership_request(req, "approve", self.provider)
        PartnershipCommissionTerms.objects.create(
            partnership=p, commission_type=PartnershipCommissionTerms.Type.PERCENTAGE, rate=Decimal("10.00")
        )
        rate, amount = compute_dealer_commission(p, None, Decimal("100000.00"))
        self.assertEqual(rate, Decimal("10.00"))
        self.assertEqual(amount, Decimal("10000.00"))

    def test_fixed_commission(self):
        self._verify(self.insurer_org)
        self._verify(self.dealer_org)
        req = create_partnership_request(self.dealer_org, self.insurer_org, "x", self.dealer)
        p = respond_to_partnership_request(req, "approve", self.provider)
        PartnershipCommissionTerms.objects.create(
            partnership=p, commission_type=PartnershipCommissionTerms.Type.FIXED, fixed_amount=Decimal("5000.00")
        )
        rate, amount = compute_dealer_commission(p, None, Decimal("100000.00"))
        self.assertEqual(amount, Decimal("5000.00"))


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGMU9+pmYGBgYgADAArGAPAkkoMKAAAAAElFTkSuQmCC"
)


class DealerVehiclePhotoTests(BusinessNetworkTests):
    def setUp(self):
        super().setUp()
        self._media_root = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=self._media_root)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self._media_root, ignore_errors=True)

    def _upload(self, client, vehicle, name="vehicle.png", content=PNG_BYTES, content_type="image/png", is_primary=False):
        payload = {"image": SimpleUploadedFile(name, content, content_type=content_type)}
        if is_primary:
            payload["is_primary"] = "true"
        return client.post(f"/api/v1/business-network/inventory/{vehicle.id}/photos/", payload, format="multipart")

    def test_dealer_uploads_primary_photo(self):
        vehicle = self._make_inventory()
        resp = self._upload(self.dealer_client, vehicle, is_primary=True)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(vehicle.photos.count(), 1)
        photo = vehicle.photos.get()
        self.assertTrue(photo.is_primary)
        self.assertTrue(resp.json()["photos"][0]["image"])

    def test_uploaded_primary_replaces_previous_primary(self):
        vehicle = self._make_inventory()
        self.assertEqual(self._upload(self.dealer_client, vehicle, is_primary=True).status_code, 201)
        self.assertEqual(self._upload(self.dealer_client, vehicle, name="second.png", is_primary=True).status_code, 201)
        self.assertEqual(vehicle.photos.filter(is_primary=True).count(), 1)
        self.assertEqual(vehicle.photos.get(is_primary=True).order, 1)

    def test_upload_rejects_non_image(self):
        vehicle = self._make_inventory()
        resp = self._upload(
            self.dealer_client, vehicle, name="notes.txt", content=b"not an image", content_type="text/plain"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(vehicle.photos.count(), 0)

    def test_other_dealer_cannot_upload_photo(self):
        vehicle = self._make_inventory()
        resp = self._upload(auth_client(self.dealer2), vehicle)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(vehicle.photos.count(), 0)


class DealerRegistrationTests(BusinessNetworkTests):
    def test_dealer_registration_endpoint(self):
        resp = self.client.post(
            "/api/v1/auth/register/dealer/",
            {
                "email": "dealernew@example.com",
                "password": "Strong@12345",
                "first_name": "Amina",
                "last_name": "Dealer",
                "organization_name": "New Age Motors Ltd",
                "trading_name": "New Age Motors",
                "county": "Nairobi",
                "country": "Kenya",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["organization"]["type"], "dealer")
        org = Organization.objects.get(name="New Age Motors Ltd")
        self.assertEqual(org.organization_type, Organization.Type.DEALER)
        self.assertEqual(org.status, Organization.Status.PENDING)
