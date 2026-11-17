import shutil
import tempfile
from urllib.parse import urlparse

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.common.tests_utils import add_member, auth_client, make_org, make_user
from apps.insurance.models import Insurer
from apps.organizations.models import Membership, Organization


class ProviderRegistrationTests(TestCase):
    def test_provider_registration_creates_pending_org(self):
        resp = self.client.post(
            "/api/v1/auth/register/provider/",
            {
                "email": "newinsurer@example.com",
                "password": "Strong@12345",
                "first_name": "New",
                "last_name": "Insurer",
                "organization_name": "New Mutual Insurance",
                "registration_number": "REG-999",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        org = Organization.objects.get(name="New Mutual Insurance")
        self.assertEqual(org.status, Organization.Status.PENDING)
        user = User.objects.get(email="newinsurer@example.com")
        self.assertTrue(Membership.objects.filter(user=user, organization=org, role=Membership.Role.OWNER).exists())


class VerificationTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", role=User.Role.ADMIN)
        self.provider = make_user("provider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org = make_org("Pending Insurer", status=Organization.Status.PENDING)
        add_member(self.provider, self.org, Membership.Role.OWNER)

    def test_admin_verification_creates_insurer_profile(self):
        client = auth_client(self.admin)
        resp = client.post(f"/api/v1/organizations/{self.org.id}/verify/", {"action": "verify"}, content_type="application/json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, Organization.Status.VERIFIED)
        self.assertTrue(Insurer.objects.filter(organization=self.org).exists())

    def test_provider_cannot_verify_org(self):
        client = auth_client(self.provider)
        resp = client.post(f"/api/v1/organizations/{self.org.id}/verify/", {"action": "verify"}, content_type="application/json")
        self.assertEqual(resp.status_code, 403)

    def test_provider_cannot_delete_organization(self):
        client = auth_client(self.provider)
        resp = client.delete(f"/api/v1/organizations/{self.org.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Organization.objects.filter(pk=self.org.pk).exists())

    def test_reject_org(self):
        client = auth_client(self.admin)
        resp = client.post(
            f"/api/v1/organizations/{self.org.id}/verify/",
            {"action": "reject", "reason": "Documents incomplete"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, Organization.Status.REJECTED)


class MembershipIsolationTests(TestCase):
    def setUp(self):
        self.provider = make_user("owner@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org_a = make_org("Org A")
        self.org_b = make_org("Org B")
        add_member(self.provider, self.org_a, Membership.Role.OWNER)
        self.agent_user = make_user("agent2@example.com")

    def test_provider_only_sees_own_organizations(self):
        client = auth_client(self.provider)
        resp = client.get("/api/v1/organizations/")
        self.assertEqual(resp.status_code, 200)
        names = [o["name"] for o in resp.json()["results"]]
        self.assertIn("Org A", names)
        self.assertNotIn("Org B", names)

    def test_provider_cannot_read_other_org(self):
        client = auth_client(self.provider)
        self.assertEqual(client.get(f"/api/v1/organizations/{self.org_b.id}/").status_code, 404)

    def test_add_member_updates_role(self):
        client = auth_client(self.provider)
        resp = client.post(
            f"/api/v1/organizations/{self.org_a.id}/members/",
            {"email": self.agent_user.email, "role": "agent"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.agent_user.refresh_from_db()
        self.assertEqual(self.agent_user.role, User.Role.AGENT)
        self.assertTrue(hasattr(self.agent_user, "agent_profile"))


class OrganizationDocumentAccessTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.provider = make_user("orgdoc@example.com", role=User.Role.PROVIDER_ADMIN)
        self.other_provider = make_user("otherorgdoc@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org = make_org("Document Org")
        self.other_org = make_org("Other Document Org")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        add_member(self.other_provider, self.other_org, Membership.Role.OWNER)
        self.client_auth = auth_client(self.provider)
        self.other_client = auth_client(self.other_provider)

    def upload(self):
        return self.client_auth.post(
            f"/api/v1/organizations/{self.org.id}/documents/",
            {
                "document_type": "Tax compliance certificate",
                "file": SimpleUploadedFile("tax.pdf", b"%PDF-1.4 tax", content_type="application/pdf"),
            },
            format="multipart",
        )

    def test_organization_document_download_is_scoped_and_audited(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        body = uploaded.json()
        self.assertNotIn("file", body)
        path = urlparse(body["download_url"]).path
        downloaded = self.client_auth.get(path)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded["Cache-Control"], "private, no-store")
        self.assertTrue(AuditLog.objects.filter(action="organization.document_downloaded").exists())
        self.assertEqual(self.other_client.get(path).status_code, 404)
