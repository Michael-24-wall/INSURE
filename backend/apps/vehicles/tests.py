import shutil
import tempfile
from urllib.parse import urlparse

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.common.tests_utils import (
    add_member,
    auth_client,
    create_policy,
    make_insurer,
    make_org,
    make_product,
    make_user,
    make_vehicle,
)
from apps.organizations.models import Membership


class VehicleTests(TestCase):
    def setUp(self):
        self.customer = make_user("owner@example.com")
        self.other = make_user("other@example.com")
        self.client_auth = auth_client(self.customer)

    def payload(self, reg="KDD 222B"):
        return {
            "registration_number": reg,
            "make": "Mazda",
            "model": "CX-5",
            "manufacturing_year": 2021,
            "chassis_number": "JMZKF123456",
            "engine_cc": 2000,
            "category": "suv",
            "fuel_type": "petrol",
            "usage": "private",
            "estimated_value": "3500000.00",
        }

    def test_create_and_list_own_vehicle(self):
        resp = self.client_auth.post("/api/v1/vehicles/", self.payload(), content_type="application/json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["owner"], str(self.customer.id))
        listing = self.client_auth.get("/api/v1/vehicles/")
        self.assertEqual(listing.json()["count"], 1)

    def test_registration_is_normalized(self):
        resp = self.client_auth.post("/api/v1/vehicles/", self.payload("kdd 999z"), content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["registration_number"], "KDD999Z")

    def test_duplicate_registration_for_same_owner_rejected(self):
        self.client_auth.post("/api/v1/vehicles/", self.payload(), content_type="application/json")
        resp = self.client_auth.post("/api/v1/vehicles/", self.payload(), content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_customer_isolation(self):
        vehicle = make_vehicle(self.customer)
        other_client = auth_client(self.other)
        self.assertEqual(other_client.get(f"/api/v1/vehicles/{vehicle.id}/").status_code, 404)
        resp = other_client.patch(
            f"/api/v1/vehicles/{vehicle.id}/", {"color": "Red"}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 404)

    def test_future_year_rejected(self):
        data = self.payload()
        data["manufacturing_year"] = 2101
        resp = self.client_auth.post("/api/v1/vehicles/", data, content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_soft_delete(self):
        vehicle = make_vehicle(self.customer)
        resp = self.client_auth.delete(f"/api/v1/vehicles/{vehicle.id}/")
        self.assertEqual(resp.status_code, 204)
        vehicle.refresh_from_db()
        self.assertIsNotNone(vehicle.deleted_at)
        self.assertEqual(self.client_auth.get(f"/api/v1/vehicles/{vehicle.id}/").status_code, 404)


class VehicleProviderAccessTests(TestCase):
    def test_provider_with_policy_access_cannot_edit_vehicle(self):
        customer = make_user("vehiclepolicyowner@example.com")
        vehicle = make_vehicle(customer, reg="KDP 777P")
        provider = make_user("vehicleprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        org = make_org("Vehicle Access Insurance")
        add_member(provider, org, Membership.Role.OWNER)
        insurer = make_insurer(org, "Vehicle Access Insurance")
        product = make_product(insurer, code="VEH-ACCESS")
        create_policy(customer, insurer, product, vehicle)

        client = auth_client(provider)
        self.assertEqual(client.get(f"/api/v1/vehicles/{vehicle.id}/").status_code, 200)
        resp = client.patch(
            f"/api/v1/vehicles/{vehicle.id}/",
            {"registration_number": "KDP 888P"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.registration_number, "KDP 777P")


class VehicleDocumentAccessTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.customer = make_user("docowner@example.com")
        self.other = make_user("docother@example.com")
        self.vehicle = make_vehicle(self.customer)
        self.client_auth = auth_client(self.customer)
        self.other_client = auth_client(self.other)

    def upload(self):
        return self.client_auth.post(
            f"/api/v1/vehicles/{self.vehicle.id}/documents/",
            {
                "document_type": "logbook",
                "file": SimpleUploadedFile("logbook.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            },
            format="multipart",
        )

    def test_document_response_hides_storage_path_and_download_is_audited(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        body = uploaded.json()
        self.assertNotIn("file", body)
        self.assertIn("download_url", body)
        self.assertEqual(body["filename"], "logbook.pdf")

        path = urlparse(body["download_url"]).path
        downloaded = self.client_auth.get(path)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded["Cache-Control"], "private, no-store")
        self.assertTrue(AuditLog.objects.filter(action="vehicle.document_downloaded").exists())

    def test_other_customer_cannot_download_document(self):
        body = self.upload().json()
        path = urlparse(body["download_url"]).path
        self.assertEqual(self.other_client.get(path).status_code, 404)

    def test_anonymous_download_is_rejected(self):
        body = self.upload().json()
        path = urlparse(body["download_url"]).path
        self.assertEqual(self.client.get(path).status_code, 401)

    def test_executable_content_is_rejected(self):
        resp = self.client_auth.post(
            f"/api/v1/vehicles/{self.vehicle.id}/documents/",
            {
                "document_type": "logbook",
                "file": SimpleUploadedFile("malware.pdf", b"\x7fELF binary", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not an allowed document type", resp.json()["error"]["message"])
