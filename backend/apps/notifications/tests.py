from django.test import TestCase

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


class MessageAuthorizationTests(TestCase):
    def setUp(self):
        self.customer = make_user("msgcustomer@example.com")
        self.provider = make_user("msgprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org = make_org("Message Insurer")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        self.insurer = make_insurer(self.org, "Message Insurer")
        self.product = make_product(self.insurer, code="MSG-COMP")
        self.policy = create_policy(self.customer, self.insurer, self.product)
        self.claim = Claim.objects.create(
            claim_number="CLM-MSG-1",
            policy=self.policy,
            customer=self.customer,
            claim_type="accident",
            incident_date="2026-01-01",
            location="Nairobi",
            description="Test claim for messaging validation.",
            amount_claimed=1000,
            status=Claim.Status.SUBMITTED,
        )
        self.customer_client = auth_client(self.customer)
        self.provider_client = auth_client(self.provider)

    def message(self, client, recipient, claim=None):
        payload = {"recipient": str(recipient.id), "subject": "Hi", "body": "Body"}
        if claim is not None:
            payload["claim"] = str(claim.id)
        return client.post("/api/v1/notifications/messages/", payload, content_type="application/json")

    def test_customer_can_message_insurer_about_claim(self):
        resp = self.message(self.customer_client, self.provider, claim=self.claim)
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_non_participant_cannot_message_about_claim(self):
        outsider = make_user("msgoutsider@example.com")
        resp = self.message(auth_client(outsider), self.provider, claim=self.claim)
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_customer_cannot_message_non_participant(self):
        outsider = make_user("msgnonpart@example.com")
        resp = self.message(self.customer_client, outsider, claim=self.claim)
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_customer_cannot_message_self(self):
        resp = self.message(self.customer_client, self.customer, claim=self.claim)
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_unrelated_user_cannot_read_messages(self):
        created = self.message(self.customer_client, self.provider, claim=self.claim)
        self.assertEqual(created.status_code, 201, created.content)
        message_id = created.json()["id"]

        outsider = make_user("msgreader@example.com")
        self.assertEqual(auth_client(outsider).get(f"/api/v1/notifications/messages/{message_id}/").status_code, 404)
        self.assertEqual(self.provider_client.get(f"/api/v1/notifications/messages/{message_id}/").status_code, 200)
