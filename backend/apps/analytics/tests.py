from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.common.tests_utils import (
    add_member,
    auth_client,
    create_policy,
    make_insurer,
    make_org,
    make_product,
    make_user,
)
from apps.insurance.models import QuotationRequest
from apps.organizations.models import Membership


class DashboardTests(TestCase):
    def setUp(self):
        self.admin = make_user("dashadmin@example.com", role=User.Role.ADMIN)
        self.customer = make_user("dashcustomer@example.com")
        self.provider = make_user("dashprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org = make_org("Dashboard Insurance")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        self.insurer = make_insurer(self.org, "Dashboard Insurance")
        self.product = make_product(self.insurer, code="DASH-COMP")
        self.policy = create_policy(self.customer, self.insurer, self.product)

    def test_admin_dashboard(self):
        client = auth_client(self.admin)
        resp = client.get("/api/v1/admin/dashboard/")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        for key in ["users", "organizations", "marketplace", "claims", "finance"]:
            self.assertIn(key, data)
        self.assertGreaterEqual(data["marketplace"]["policies"], 1)
        self.assertGreaterEqual(data["users"]["total"], 3)

    def test_customer_dashboard(self):
        client = auth_client(self.customer)
        resp = client.get("/api/v1/analytics/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["role"], "customer")
        self.assertGreaterEqual(resp.json()["data"]["active_policies"], 1)

    def test_provider_dashboard(self):
        client = auth_client(self.provider)
        resp = client.get("/api/v1/analytics/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["role"], "provider_admin")
        self.assertGreaterEqual(resp.json()["data"]["products"], 1)

    def test_provider_dashboard_open_requests_scoped_to_insurer(self):
        from apps.analytics.services import provider_dashboard

        fresh = make_user("dashfresh@example.com", role=User.Role.PROVIDER_ADMIN)
        fresh_org = make_org("Fresh Dashboard Insurer")
        add_member(fresh, fresh_org, Membership.Role.OWNER)
        make_insurer(fresh_org, "Fresh Dashboard Insurer")

        other_org = make_org("Other Dashboard Insurer")
        other_insurer = make_insurer(other_org, "Other Dashboard Insurer")

        QuotationRequest.objects.create(
            request_number="QR-DASH-OTHER",
            customer=self.customer,
            vehicle=self.policy.vehicle,
            insurer=other_insurer,
            coverage_type=self.product.category,
            sum_insured=self.policy.vehicle.estimated_value,
            status=QuotationRequest.Status.PENDING,
            desired_start_date=timezone.now().date(),
            expires_at=timezone.now() + timedelta(days=14),
        )
        QuotationRequest.objects.create(
            request_number="QR-DASH-OPEN",
            customer=self.customer,
            vehicle=self.policy.vehicle,
            coverage_type=self.product.category,
            sum_insured=self.policy.vehicle.estimated_value,
            status=QuotationRequest.Status.PENDING,
            desired_start_date=timezone.now().date(),
            expires_at=timezone.now() + timedelta(days=14),
        )

        data = provider_dashboard(fresh)
        # Visible to any provider: the seed open-marketplace request (selected)
        # from setUp plus the new open request. The directed request to the
        # *other* insurer must be excluded.
        self.assertEqual(data["open_quotation_requests"], 2)

    def test_customer_cannot_access_admin_dashboard(self):
        client = auth_client(self.customer)
        self.assertEqual(client.get("/api/v1/admin/dashboard/").status_code, 403)

    def test_platform_settings_admin_only_write(self):
        customer_client = auth_client(self.customer)
        self.assertEqual(customer_client.get("/api/v1/admin/settings/").status_code, 403)
        self.assertEqual(customer_client.put(
            "/api/v1/admin/settings/",
            {"key": "x", "value": 1},
            content_type="application/json",
        ).status_code, 403)
        admin_client = auth_client(self.admin)
        resp = admin_client.put(
            "/api/v1/admin/settings/",
            {"key": "maintenance_mode", "value": False},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        listing = admin_client.get("/api/v1/admin/settings/")
        self.assertIn("maintenance_mode", listing.json())

    def test_csv_exports(self):
        admin_client = auth_client(self.admin)
        resp = admin_client.get("/api/v1/admin/exports/policies/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        customer_client = auth_client(self.customer)
        self.assertEqual(customer_client.get("/api/v1/admin/exports/policies/").status_code, 403)

    def test_financial_report(self):
        client = auth_client(self.admin)
        resp = client.get("/api/v1/analytics/reports/financial/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("by_method", resp.json())

    def test_audit_logs_endpoint(self):
        client = auth_client(self.admin)
        resp = client.get("/api/v1/admin/audit-logs/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)
