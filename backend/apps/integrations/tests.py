from unittest import mock

from django.test import TestCase

from apps.accounts.models import User
from apps.common.tests_utils import add_member, auth_client, make_org, make_user
from apps.integrations.adapters import outbound_url_error
from apps.integrations.models import Integration
from apps.organizations.models import Membership


class IntegrationTests(TestCase):
    def setUp(self):
        self.provider = make_user("intprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.other_provider = make_user("intother@example.com", role=User.Role.PROVIDER_ADMIN)
        self.customer = make_user("intcustomer@example.com")
        self.org = make_org("Integration Insurance")
        self.other_org = make_org("Other Integration Insurance")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        add_member(self.other_provider, self.other_org, Membership.Role.OWNER)
        self.client_auth = auth_client(self.provider)

    def create_integration(self):
        return self.client_auth.post(
            "/api/v1/integrations/",
            {
                "organization": str(self.org.id),
                "name": "Core Policy API",
                "provider_type": "rest",
                "base_url": "https://insurer.example.test",
                "auth_type": "api_key",
                "credentials": "super-secret-key",
                "is_enabled": True,
                "config": {"health_path": "/health"},
            },
            content_type="application/json",
        )

    def test_create_stores_credentials_encrypted(self):
        resp = self.create_integration()
        self.assertEqual(resp.status_code, 201, resp.content)
        integration = Integration.objects.get(pk=resp.json()["id"])
        self.assertNotEqual(integration.credentials_encrypted, "super-secret-key")
        self.assertEqual(integration.get_credentials(), "super-secret-key")
        self.assertNotIn("credentials", resp.json())

    def test_test_endpoint_reports_failure_without_network_success(self):
        resp = self.create_integration()
        integration_id = resp.json()["id"]
        integration = Integration.objects.get(pk=integration_id)
        integration.is_enabled = False
        integration.save(update_fields=["is_enabled"])
        test = self.client_auth.post(f"/api/v1/integrations/{integration_id}/test/")
        self.assertEqual(test.status_code, 400)
        self.assertFalse(test.json()["success"])

    def test_other_provider_cannot_access(self):
        resp = self.create_integration()
        other_client = auth_client(self.other_provider)
        self.assertEqual(other_client.get(f"/api/v1/integrations/{resp.json()['id']}/").status_code, 404)

    def test_customer_forbidden(self):
        customer_client = auth_client(self.customer)
        self.assertEqual(customer_client.get("/api/v1/integrations/").status_code, 403)

    def test_private_and_local_urls_rejected(self):
        for url in (
            "http://127.0.0.1:8000/health",
            "http://localhost/health",
            "http://10.0.0.5/health",
            "http://169.254.169.254/latest/meta-data",
            "file:///etc/passwd",
        ):
            resp = self.client_auth.post(
                "/api/v1/integrations/",
                {
                    "organization": str(self.org.id),
                    "name": f"Unsafe {url}",
                    "provider_type": "rest",
                    "base_url": url,
                },
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 400, (url, resp.content))

    def test_hostname_resolving_to_private_ip_is_blocked(self):
        with mock.patch(
            "apps.integrations.adapters.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("169.254.169.254", 0))],
        ):
            self.assertIsNotNone(outbound_url_error("https://rebind.example.test/health"))
        with mock.patch(
            "apps.integrations.adapters.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            self.assertIsNone(outbound_url_error("https://public.example.test/health"))

    def test_unresolvable_hostname_is_not_rejected(self):
        with mock.patch(
            "apps.integrations.adapters.socket.getaddrinfo",
            side_effect=OSError("nodename nor servname provided"),
        ):
            self.assertIsNone(outbound_url_error("https://does-not-resolve.example.test/health"))

    def test_connection_guard_rejects_private_resolved_ip(self):
        from apps.integrations.adapters import IntegrationCallError, _resolve_public_address

        with mock.patch(
            "apps.integrations.adapters.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.0.0.5", 443))],
        ):
            with self.assertRaises(IntegrationCallError):
                _resolve_public_address("rebind.example.test", 443)

    def test_connection_guard_accepts_public_resolved_ip(self):
        from apps.integrations.adapters import _resolve_public_address

        with mock.patch(
            "apps.integrations.adapters.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
        ):
            resolved = _resolve_public_address("example.com", 443)
            self.assertEqual(resolved[4], ("93.184.216.34", 443))

    def test_opener_rejects_redirects(self):
        from apps.integrations.adapters import IntegrationCallError, _NoRedirectHandler, _validating_opener

        handler_names = {type(h).__name__ for h in _validating_opener().handlers}
        self.assertIn("_NoRedirectHandler", handler_names)
        self.assertNotIn("HTTPRedirectHandler", handler_names)
        with self.assertRaises(IntegrationCallError):
            _NoRedirectHandler().redirect_request(None, None, 302, "Found", {}, "http://internal.example/")

    def test_non_insurer_org_rejected(self):
        agency = make_org("Some Agency", org_type="agency")
        add_member(self.provider, agency, Membership.Role.OWNER)
        resp = self.client_auth.post(
            "/api/v1/integrations/",
            {
                "organization": str(agency.id),
                "name": "Agency API",
                "provider_type": "rest",
                "base_url": "https://agency.example.test",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
