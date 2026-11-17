import shutil
import tempfile
from datetime import timedelta
from urllib.parse import urlparse

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.claims.models import Claim, ClaimStatusHistory
from apps.common.tests_utils import (
    add_member,
    auth_client,
    create_policy,
    make_insurer,
    make_org,
    make_product,
    make_user,
)
from apps.organizations.models import Membership


class ClaimLifecycleTests(TestCase):
    def setUp(self):
        self.customer = make_user("claimant@example.com")
        self.other = make_user("otherclaimant@example.com")
        self.provider = make_user("claimprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.officer = make_user("officer@example.com", role=User.Role.CLAIMS_OFFICER)
        self.inspector = make_user("claiminspector@example.com", role=User.Role.INSPECTOR)
        self.org = make_org("Claims Insurance")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        add_member(self.officer, self.org, Membership.Role.CLAIMS)
        add_member(self.inspector, self.org, Membership.Role.INSPECTOR)
        self.insurer = make_insurer(self.org, "Claims Insurance")
        self.product = make_product(self.insurer, code="CLM-COMP", rate="5.0000")
        self.policy = create_policy(self.customer, self.insurer, self.product)
        self.client_auth = auth_client(self.customer)
        self.provider_client = auth_client(self.provider)
        self.officer_client = auth_client(self.officer)

    def create_claim(self, amount="250000.00", incident=None):
        incident = incident or (timezone.now().date() - timedelta(days=5))
        return self.client_auth.post(
            "/api/v1/claims/",
            {
                "policy": str(self.policy.id),
                "claim_type": "accident",
                "incident_date": incident.isoformat(),
                "location": "Mombasa Road",
                "description": "Rear-ended at traffic lights.",
                "police_report_number": "OB/123/2026",
                "amount_claimed": amount,
            },
            content_type="application/json",
        )

    def test_full_claim_lifecycle(self):
        resp = self.create_claim()
        self.assertEqual(resp.status_code, 201, resp.content)
        claim_id = resp.json()["id"]
        self.assertEqual(resp.json()["status"], "submitted")

        assigned = self.provider_client.post(
            f"/api/v1/claims/{claim_id}/assign-officer/",
            {"officer": str(self.officer.id)},
            content_type="application/json",
        )
        self.assertEqual(assigned.status_code, 200, assigned.content)
        self.assertEqual(assigned.json()["officer"], str(self.officer.id))

        reviewed = self.officer_client.post(f"/api/v1/claims/{claim_id}/review/")
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertEqual(reviewed.json()["status"], "under_review")

        scheduled = self.officer_client.post(
            f"/api/v1/claims/{claim_id}/schedule-inspection/",
            {
                "inspector": str(self.inspector.id),
                "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "location": "Industrial Area",
            },
            content_type="application/json",
        )
        self.assertEqual(scheduled.status_code, 201, scheduled.content)
        self.assertEqual(scheduled.json()["status"], "inspection_scheduled")

        assessed = self.officer_client.post(f"/api/v1/claims/{claim_id}/assess/")
        self.assertEqual(assessed.status_code, 200, assessed.content)
        self.assertEqual(assessed.json()["status"], "assessment")

        approved = self.officer_client.post(
            f"/api/v1/claims/{claim_id}/approve/",
            {"approved_amount": "200000.00", "notes": "Assessed at 200k"},
            content_type="application/json",
        )
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertEqual(approved.json()["status"], "approved")
        self.assertEqual(approved.json()["approved_amount"], "200000.00")

        settled = self.officer_client.post(
            f"/api/v1/claims/{claim_id}/settle/",
            {"settled_amount": "200000.00", "settlement_reference": "EFT-7788"},
            content_type="application/json",
        )
        self.assertEqual(settled.status_code, 200, settled.content)
        self.assertEqual(settled.json()["status"], "settled")

        claim = Claim.objects.get(pk=claim_id)
        self.assertEqual(claim.status, Claim.Status.SETTLED)
        self.assertGreaterEqual(ClaimStatusHistory.objects.filter(claim=claim).count(), 6)

    def test_inspector_cannot_approve_claim(self):
        claim = self.create_claim().json()
        self.provider_client.post(f"/api/v1/claims/{claim['id']}/review/")
        inspector_client = auth_client(self.inspector)
        resp = inspector_client.post(
            f"/api/v1/claims/{claim['id']}/approve/",
            {"approved_amount": "1000.00"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Claim.objects.get(pk=claim["id"]).status, Claim.Status.UNDER_REVIEW)

    def test_claim_fields_cannot_be_patched(self):
        claim = self.create_claim().json()
        resp = self.officer_client.patch(
            f"/api/v1/claims/{claim['id']}/",
            {"approved_amount": "999999.00"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 405)

    def test_settle_before_approval_rejected(self):
        claim = self.create_claim().json()
        resp = self.officer_client.post(
            f"/api/v1/claims/{claim['id']}/settle/",
            {"settled_amount": "1000.00", "settlement_reference": "X"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_rejection_requires_reason_and_records_status(self):
        claim = self.create_claim().json()
        self.officer_client.post(f"/api/v1/claims/{claim['id']}/review/")
        no_reason = self.officer_client.post(
            f"/api/v1/claims/{claim['id']}/reject/", {}, content_type="application/json"
        )
        self.assertEqual(no_reason.status_code, 400)
        rejected = self.officer_client.post(
            f"/api/v1/claims/{claim['id']}/reject/",
            {"notes": "Policy did not cover the driver."},
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status"], "rejected")

    def test_claim_outside_policy_period_rejected(self):
        future = timezone.now().date() + timedelta(days=900)
        resp = self.create_claim(incident=future)
        self.assertEqual(resp.status_code, 400)

    def test_claim_amount_above_sum_insured_rejected(self):
        resp = self.create_claim(amount="999999999.00")
        self.assertEqual(resp.status_code, 400)

    def test_claimant_isolation(self):
        claim = self.create_claim().json()
        other = auth_client(self.other)
        self.assertEqual(other.get(f"/api/v1/claims/{claim['id']}/").status_code, 404)
        self.assertEqual(other.get("/api/v1/claims/").json()["count"], 0)

    def test_non_member_officer_cannot_review(self):
        claim = self.create_claim().json()
        outsider = make_user("outsider@example.com", role=User.Role.CLAIMS_OFFICER)
        resp = auth_client(outsider).post(f"/api/v1/claims/{claim['id']}/review/")
        self.assertIn(resp.status_code, (403, 404))

    def test_customer_cannot_submit_claim_for_other_policy(self):
        other_policy = create_policy(self.other, self.insurer, self.product)
        resp = self.client_auth.post(
            "/api/v1/claims/",
            {
                "policy": str(other_policy.id),
                "claim_type": "accident",
                "incident_date": (timezone.now().date() - timedelta(days=1)).isoformat(),
                "location": "Nairobi",
                "description": "Test",
                "amount_claimed": "1000.00",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_claim_transition_returns_400(self):
        claim = self.create_claim().json()
        resp = self.officer_client.post(
            f"/api/v1/claims/{claim['id']}/approve/",
            {"approved_amount": "1000.00", "notes": "Skipped review"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Claim.objects.get(pk=claim["id"]).status, Claim.Status.SUBMITTED)

    def test_customer_respond_to_info_request(self):
        claim = self.create_claim().json()
        self.officer_client.post(f"/api/v1/claims/{claim['id']}/review/")
        self.officer_client.post(
            f"/api/v1/claims/{claim['id']}/request-info/",
            {"notes": "Upload the police abstract"},
            content_type="application/json",
        )
        self.assertEqual(Claim.objects.get(pk=claim["id"]).status, Claim.Status.INFO_REQUIRED)

        resp = self.client_auth.post(
            f"/api/v1/claims/{claim['id']}/respond/",
            {"notes": "Abstract uploaded"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["status"], "under_review")

    def test_respond_requires_info_required_state(self):
        claim = self.create_claim().json()
        resp = self.client_auth.post(
            f"/api/v1/claims/{claim['id']}/respond/",
            {"notes": "Premature response"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class ClaimDocumentAccessTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.customer = make_user("claimdoc@example.com")
        self.other = make_user("otherclaimdoc@example.com")
        self.org = make_org("Claim Document Insurer")
        self.insurer = make_insurer(self.org, "Claim Document Insurer")
        self.product = make_product(self.insurer, code="CLMDOC")
        self.policy = create_policy(self.customer, self.insurer, self.product)
        self.client_auth = auth_client(self.customer)
        self.other_client = auth_client(self.other)

    def create_claim(self):
        response = self.client_auth.post(
            "/api/v1/claims/",
            {
                "policy": str(self.policy.id),
                "claim_type": "accident",
                "incident_date": (timezone.now().date() - timedelta(days=2)).isoformat(),
                "location": "Thika Road",
                "description": "Windscreen damage",
                "amount_claimed": "45000.00",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def upload(self, claim_id):
        return self.client_auth.post(
            f"/api/v1/claims/{claim_id}/documents/",
            {
                "document_type": "photo",
                "file": SimpleUploadedFile("damage.jpg", b"image-bytes", content_type="image/jpeg"),
            },
            format="multipart",
        )

    def test_claim_document_download_is_scoped_and_audited(self):
        claim = self.create_claim()
        uploaded = self.upload(claim["id"])
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        body = uploaded.json()
        self.assertNotIn("file", body)
        path = urlparse(body["download_url"]).path
        downloaded = self.client_auth.get(path)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded["Cache-Control"], "private, no-store")
        self.assertTrue(AuditLog.objects.filter(action="claim.document_downloaded").exists())
        self.assertEqual(self.other_client.get(path).status_code, 404)

    def test_claim_document_download_requires_insurer_org_membership(self):
        claim = self.create_claim()
        uploaded = self.upload(claim["id"])
        path = urlparse(uploaded.json()["download_url"]).path

        same_insurer = make_user("sameinsurer@example.com", role=User.Role.PROVIDER_STAFF)
        add_member(same_insurer, self.org, Membership.Role.STAFF)
        self.assertEqual(auth_client(same_insurer).get(path).status_code, 200)

        other_insurer = make_user("otherinsurer@example.com", role=User.Role.PROVIDER_STAFF)
        other_org = make_org("Other Claim Insurer")
        add_member(other_insurer, other_org, Membership.Role.STAFF)
        self.assertEqual(auth_client(other_insurer).get(path).status_code, 404)
