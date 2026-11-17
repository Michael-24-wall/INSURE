from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.claims.models import Claim
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


class AIServiceTests(TestCase):
    def setUp(self):
        self.customer = make_user("aicustomer@example.com")
        self.provider = make_user("aiprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org = make_org("AI Insurance")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        self.insurer = make_insurer(self.org, "AI Insurance")
        self.product = make_product(self.insurer, code="AI-COMP")
        self.policy = create_policy(self.customer, self.insurer, self.product)
        self.claim = Claim.objects.create(
            claim_number="CLM-AI-1",
            policy=self.policy,
            customer=self.customer,
            claim_type="accident",
            incident_date=timezone.now().date() - timedelta(days=1),
            location="Nairobi",
            description="Test claim",
            amount_claimed=10000,
            status=Claim.Status.SUBMITTED,
        )
        self.client_auth = auth_client(self.customer)

    def test_assistant(self):
        resp = self.client_auth.post(
            "/api/v1/ai/assistant/", {"question": "How do I file a claim?"}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("claim", resp.json()["answer"].lower())
        self.assertTrue(resp.json()["disclaimer"])

    def test_document_classification(self):
        upload = SimpleUploadedFile("police_report.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        resp = self.client_auth.post("/api/v1/ai/document-classify/", {"file": upload}, format="multipart")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["category"], "police_report")
        self.assertTrue(resp.json()["requires_human_review"])

    def test_duplicate_document_detection(self):
        resp = self.client_auth.get(f"/api/v1/ai/duplicates/{self.claim.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["checked"], 0)

    def test_risk_indicators_permissions(self):
        customer_resp = self.client_auth.get("/api/v1/ai/risk-indicators/")
        self.assertEqual(customer_resp.status_code, 403)
        provider_resp = auth_client(self.provider).get("/api/v1/ai/risk-indicators/")
        self.assertEqual(provider_resp.status_code, 200)
        self.assertIn("flags", provider_resp.json())

    def test_customer_cannot_read_other_claim_duplicates(self):
        other = make_user("aiother@example.com")
        resp = auth_client(other).get(f"/api/v1/ai/duplicates/{self.claim.id}/")
        self.assertEqual(resp.status_code, 403)

    def test_payment_risk_indicators_scoped_to_insurer(self):
        from apps.ai_services.services import suspicious_payment_indicators
        from apps.payments.models import Payment

        from apps.common.tests_utils import make_vehicle

        other_org = make_org("Other AI Insurer")
        other_insurer = make_insurer(other_org, "Other AI Insurer")
        other_vehicle = make_vehicle(self.customer, reg="KDB 002B")
        other_policy = create_policy(
            self.customer, other_insurer, make_product(other_insurer, code="AI-OTHER"), other_vehicle
        )

        Payment.objects.create(
            user=self.customer, policy=self.policy, amount=100, method="bank", status="failed"
        )
        Payment.objects.create(
            user=self.customer, policy=other_policy, amount=100, method="bank", status="failed"
        )

        scoped = suspicious_payment_indicators(insurer_ids=[self.insurer.id])
        self.assertEqual(scoped["failed_payments"], 1)
