from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.common.tests_utils import (
    add_member,
    auth_client,
    make_insurer,
    make_org,
    make_product,
    make_user,
    make_vehicle,
)
from apps.insurance.models import Application, Policy, Product, Quotation, QuotationRequest
from apps.organizations.models import Membership, Organization
from apps.payments.models import Payment


class MarketplaceTests(TestCase):
    def setUp(self):
        self.customer = make_user("buyer@example.com")
        self.other = make_user("otherbuyer@example.com")
        self.provider = make_user("prova@example.com", role=User.Role.PROVIDER_ADMIN)
        self.provider_b = make_user("provb@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org_a = make_org("Alpha Insurance")
        self.org_b = make_org("Beta Insurance")
        self.unverified = make_org("Gamma Insurance", status=Organization.Status.PENDING)
        add_member(self.provider, self.org_a, Membership.Role.OWNER)
        add_member(self.provider_b, self.org_b, Membership.Role.OWNER)
        self.insurer_a = make_insurer(self.org_a, "Alpha Insurance")
        self.insurer_b = make_insurer(self.org_b, "Beta Insurance")
        self.insurer_unverified = make_insurer(self.unverified, "Gamma Insurance")
        self.product_a = make_product(self.insurer_a, code="ALP-COMP", rate="5.0000")
        self.product_b = make_product(self.insurer_b, code="BET-COMP", rate="6.0000")
        self.product_unverified = make_product(self.insurer_unverified, code="GAM-COMP", rate="1.0000")
        self.vehicle = make_vehicle(self.customer)
        self.client_auth = auth_client(self.customer)

    def create_request(self, category=Product.Category.COMPREHENSIVE):
        return self.client_auth.post(
            "/api/v1/quotation-requests/",
            {
                "vehicle": str(self.vehicle.id),
                "coverage_type": category,
                "sum_insured": "2000000.00",
                "desired_start_date": (timezone.now().date() + timedelta(days=2)).isoformat(),
                "notes": "Please compare comprehensive options.",
            },
            content_type="application/json",
        )

    def test_quotation_engine_only_uses_verified_insurers(self):
        resp = self.create_request()
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data["status"], "quoted")
        self.assertEqual(data["quotation_count"], 2)
        insurer_ids = {q["insurer"] for q in data["quotations"]}
        self.assertEqual(insurer_ids, {str(self.insurer_a.id), str(self.insurer_b.id)})
        self.assertNotIn(str(self.insurer_unverified.id), insurer_ids)
        self.assertTrue(all(q["source"] == "internal" for q in data["quotations"]))

    def test_lowest_premium_selection_and_full_policy_flow(self):
        resp = self.create_request()
        quotes = sorted(resp.json()["quotations"], key=lambda q: Decimal(q["premium"]))
        chosen = quotes[0]
        self.assertEqual(chosen["insurer"], str(self.insurer_a.id))

        select = self.client_auth.post(f"/api/v1/quotations/{chosen['id']}/select/")
        self.assertEqual(select.status_code, 200, select.content)

        app_resp = self.client_auth.post(
            "/api/v1/applications/", {"quotation": chosen["id"]}, content_type="application/json"
        )
        self.assertEqual(app_resp.status_code, 201, app_resp.content)
        app_id = app_resp.json()["id"]

        submit = self.client_auth.post(f"/api/v1/applications/{app_id}/submit/")
        self.assertEqual(submit.status_code, 200, submit.content)

        provider_client = auth_client(self.provider)
        early_issue = provider_client.post(f"/api/v1/applications/{app_id}/issue-policy/", {}, content_type="application/json")
        self.assertEqual(early_issue.status_code, 400)

        approve = provider_client.post(
            f"/api/v1/applications/{app_id}/approve/", {}, content_type="application/json"
        )
        self.assertEqual(approve.status_code, 200, approve.content)

        pay_resp = self.client_auth.post(
            "/api/v1/payments/initiate/",
            {"application": app_id, "method": "bank"},
            content_type="application/json",
        )
        self.assertIn(pay_resp.status_code, (200, 201), pay_resp.content)
        payment = pay_resp.json()["payment"]
        self.assertEqual(payment["status"], "pending")
        self.assertEqual(payment["amount"], chosen["premium"])

        verify = provider_client.post(
            f"/api/v1/payments/{payment['id']}/verify/",
            {"provider_reference": "BANK-TRX-001"},
            content_type="application/json",
        )
        self.assertEqual(verify.status_code, 200, verify.content)
        self.assertEqual(verify.json()["status"], "succeeded")

        issue = provider_client.post(
            f"/api/v1/applications/{app_id}/issue-policy/",
            {"provider_reference": "POLICY-EXT-1"},
            content_type="application/json",
        )
        self.assertEqual(issue.status_code, 201, issue.content)
        self.assertEqual(issue.json()["status"], "active")
        self.assertEqual(issue.json()["insurer"], str(self.insurer_a.id))

        policy = Policy.objects.get(application_id=app_id)
        self.assertEqual(policy.customer_id, self.customer.id)

        duplicate = provider_client.post(f"/api/v1/applications/{app_id}/issue-policy/", {}, content_type="application/json")
        self.assertEqual(duplicate.status_code, 400)

        self.assertEqual(self.client_auth.get("/api/v1/policies/").json()["count"], 1)
        other_client = auth_client(self.other)
        self.assertEqual(other_client.get("/api/v1/policies/").json()["count"], 0)

    def test_other_insurer_cannot_issue_policy(self):
        resp = self.create_request()
        chosen = next(q for q in resp.json()["quotations"] if q["insurer"] == str(self.insurer_a.id))
        self.client_auth.post(f"/api/v1/quotations/{chosen['id']}/select/")
        app = self.client_auth.post(
            "/api/v1/applications/", {"quotation": chosen["id"]}, content_type="application/json"
        ).json()
        client_b = auth_client(self.provider_b)
        resp = client_b.post(f"/api/v1/applications/{app['id']}/issue-policy/", {}, content_type="application/json")
        self.assertIn(resp.status_code, (403, 404))

    def test_customer_isolation_on_requests(self):
        resp = self.create_request()
        req_id = resp.json()["id"]
        other_client = auth_client(self.other)
        self.assertEqual(other_client.get(f"/api/v1/quotation-requests/{req_id}/").status_code, 404)
        self.assertEqual(other_client.get(f"/api/v1/quotations/{resp.json()['quotations'][0]['id']}/").status_code, 404)

    def test_expired_quote_cannot_be_selected(self):
        resp = self.create_request()
        quote = Quotation.objects.get(pk=resp.json()["quotations"][0]["id"])
        quote.valid_until = timezone.now() - timedelta(days=1)
        quote.save(update_fields=["valid_until"])
        selected = self.client_auth.post(f"/api/v1/quotations/{quote.id}/select/")
        self.assertEqual(selected.status_code, 400)

    def test_provider_cannot_see_competitor_quotes_on_shared_request(self):
        resp = self.create_request()
        req_id = resp.json()["id"]
        provider_client = auth_client(self.provider)
        quotes = provider_client.get(f"/api/v1/quotation-requests/{req_id}/quotations/")
        self.assertEqual(quotes.status_code, 200, quotes.content)
        insurer_ids = {q["insurer"] for q in quotes.json()}
        self.assertEqual(insurer_ids, {str(self.insurer_a.id)})
        self.assertTrue(all(q["insurer"] == str(self.insurer_a.id) for q in quotes.json()))

        customer_quotes = self.client_auth.get(f"/api/v1/quotation-requests/{req_id}/quotations/")
        self.assertEqual(customer_quotes.status_code, 200)
        self.assertEqual(len(customer_quotes.json()), 2)

    def test_provider_can_submit_quote_for_new_product(self):
        resp = self.create_request()
        req_id = resp.json()["id"]
        new_product = make_product(self.insurer_a, code="ALP-COMP-2", rate="4.5000")
        provider_client = auth_client(self.provider)
        quote = provider_client.post(
            "/api/v1/quotations/",
            {
                "request": req_id,
                "product": str(new_product.id),
                "premium": "85000.00",
                "excess_amount": "10000.00",
                "notes": "Manual insurer quotation",
            },
            content_type="application/json",
        )
        self.assertEqual(quote.status_code, 201, quote.content)
        self.assertEqual(quote.json()["source"], "provider_api")

        # A provider from a different insurer cannot quote using Alpha's product.
        other_provider = auth_client(self.provider_b)
        dup = other_provider.post(
            "/api/v1/quotations/",
            {
                "request": req_id,
                "product": str(new_product.id),
                "premium": "90000.00",
                "excess_amount": "10000.00",
            },
            content_type="application/json",
        )
        self.assertEqual(dup.status_code, 403)

    def test_provider_product_crud_scoped_to_own_insurer(self):
        client_b = auth_client(self.provider_b)
        resp = client_b.post(
            "/api/v1/products/",
            {
                "insurer": str(self.insurer_a.id),
                "name": "Hijack Product",
                "code": "HIJ-1",
                "category": "comprehensive",
                "base_premium_rate": "5.0000",
                "minimum_premium": "5000.00",
                "excess_amount": "10000.00",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["insurer"], str(self.insurer_b.id))

    def test_customer_cannot_create_product(self):
        resp = self.client_auth.post(
            "/api/v1/products/",
            {
                "insurer": str(self.insurer_a.id),
                "name": "Nope",
                "code": "NOPE",
                "category": "comprehensive",
                "base_premium_rate": "5.0000",
                "minimum_premium": "5000.00",
                "excess_amount": "10000.00",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_application_converts_request_and_auto_commissions(self):
        from apps.accounts.models import AgentProfile
        from apps.insurance.models import QuotationRequest
        from apps.payments.models import Commission

        agent = make_user("agentattr@example.com", role=User.Role.AGENT)
        AgentProfile.objects.create(user=agent, commission_rate=Decimal("12.00"))

        resp = self.create_request()
        chosen = next(q for q in resp.json()["quotations"] if q["insurer"] == str(self.insurer_a.id))
        self.client_auth.post(f"/api/v1/quotations/{chosen['id']}/select/")
        app = self.client_auth.post(
            "/api/v1/applications/", {"quotation": chosen["id"]}, content_type="application/json"
        ).json()

        req = QuotationRequest.objects.get(pk=resp.json()["id"])
        self.assertEqual(req.status, QuotationRequest.Status.CONVERTED)

        Application.objects.filter(pk=app["id"]).update(agent=agent)
        self.client_auth.post(f"/api/v1/applications/{app['id']}/submit/")
        auth_client(self.provider).post(
            f"/api/v1/applications/{app['id']}/approve/", {}, content_type="application/json"
        )
        pay = self.client_auth.post(
            "/api/v1/payments/initiate/",
            {"application": app["id"], "method": "bank"},
            content_type="application/json",
        ).json()["payment"]
        auth_client(self.provider).post(
            f"/api/v1/payments/{pay['id']}/verify/",
            {"provider_reference": "BANK-COM-1"},
            content_type="application/json",
        )
        issue = auth_client(self.provider).post(
            f"/api/v1/applications/{app['id']}/issue-policy/",
            {},
            content_type="application/json",
        )
        self.assertEqual(issue.status_code, 201, issue.content)

        commission = Commission.objects.get(policy__application_id=app["id"])
        self.assertEqual(commission.agent_id, agent.id)
        self.assertEqual(commission.rate, Decimal("12.00"))
        self.assertGreater(commission.amount, Decimal("0"))

    @override_settings(KYC_REQUIRED_FOR_POLICY_ISSUANCE=True)
    def test_policy_issuance_requires_kyc(self):
        from apps.accounts.models import CustomerProfile

        resp = self.create_request()
        chosen = next(q for q in resp.json()["quotations"] if q["insurer"] == str(self.insurer_a.id))
        self.client_auth.post(f"/api/v1/quotations/{chosen['id']}/select/")
        app = self.client_auth.post(
            "/api/v1/applications/", {"quotation": chosen["id"]}, content_type="application/json"
        ).json()
        self.client_auth.post(f"/api/v1/applications/{app['id']}/submit/")
        auth_client(self.provider).post(
            f"/api/v1/applications/{app['id']}/approve/", {}, content_type="application/json"
        )
        pay = self.client_auth.post(
            "/api/v1/payments/initiate/",
            {"application": app["id"], "method": "bank"},
            content_type="application/json",
        ).json()["payment"]
        auth_client(self.provider).post(
            f"/api/v1/payments/{pay['id']}/verify/",
            {"provider_reference": "BANK-KYC-1"},
            content_type="application/json",
        )

        issue = auth_client(self.provider).post(
            f"/api/v1/applications/{app['id']}/issue-policy/", {}, content_type="application/json"
        )
        self.assertEqual(issue.status_code, 400)

        CustomerProfile.objects.filter(user=self.customer).update(kyc_status="verified")
        issue_after = auth_client(self.provider).post(
            f"/api/v1/applications/{app['id']}/issue-policy/", {}, content_type="application/json"
        )
        self.assertEqual(issue_after.status_code, 201, issue_after.content)

    def test_agent_can_create_application_for_customer(self):
        agent = make_user("salesagent@example.com", role=User.Role.AGENT)
        resp = self.create_request()
        chosen = next(q for q in resp.json()["quotations"] if q["insurer"] == str(self.insurer_a.id))
        self.client_auth.post(f"/api/v1/quotations/{chosen['id']}/select/")

        app = auth_client(agent).post(
            "/api/v1/applications/agent-create/",
            {"quotation": chosen["id"], "customer": str(self.customer.id)},
            content_type="application/json",
        )
        self.assertEqual(app.status_code, 201, app.content)
        self.assertEqual(app.json()["customer"], str(self.customer.id))
        self.assertEqual(Application.objects.get(pk=app.json()["id"]).agent_id, agent.id)

    def test_agent_create_rejects_mismatched_customer(self):
        agent = make_user("salesagent2@example.com", role=User.Role.AGENT)
        resp = self.create_request()
        chosen = resp.json()["quotations"][0]
        app = auth_client(agent).post(
            "/api/v1/applications/agent-create/",
            {"quotation": chosen["id"], "customer": str(self.other.id)},
            content_type="application/json",
        )
        self.assertEqual(app.status_code, 400)

    def test_application_requires_selected_or_valid_quote(self):
        resp = self.create_request()
        quote = resp.json()["quotations"][0]
        # Quote is in 'received' state; application creation is allowed, but
        # cannot submit an expired quote.
        app = self.client_auth.post(
            "/api/v1/applications/", {"quotation": quote["id"]}, content_type="application/json"
        )
        self.assertEqual(app.status_code, 201, app.content)
        q = Quotation.objects.get(pk=quote["id"])
        q.valid_until = timezone.now() - timedelta(days=1)
        q.save(update_fields=["valid_until"])
        submit = self.client_auth.post(f"/api/v1/applications/{app.json()['id']}/submit/")
        self.assertEqual(submit.status_code, 400)




class DealerInsurerWorkflowTests(TestCase):
    def setUp(self):
        from apps.business_network.models import CustomerConsent, Partnership

        self.customer = make_user("workflowbuyer@example.com")
        self.dealer_user = make_user("dealeradmin@example.com", role=User.Role.DEALER_ADMIN)
        self.other_dealer_user = make_user("otherdealer@example.com", role=User.Role.DEALER_ADMIN)
        self.provider_a = make_user("workflowprova@example.com", role=User.Role.PROVIDER_ADMIN)
        self.provider_b = make_user("workflowprovb@example.com", role=User.Role.PROVIDER_ADMIN)

        self.insurer_org_a = make_org("Workflow Alpha")
        self.insurer_org_b = make_org("Workflow Beta")
        add_member(self.provider_a, self.insurer_org_a, Membership.Role.OWNER)
        add_member(self.provider_b, self.insurer_org_b, Membership.Role.OWNER)
        self.insurer_a = make_insurer(self.insurer_org_a, "Workflow Alpha")
        self.insurer_b = make_insurer(self.insurer_org_b, "Workflow Beta")
        self.product_a = make_product(self.insurer_a, code="WF-ALP", rate="5.0000")
        self.product_b = make_product(self.insurer_b, code="WF-BET", rate="6.0000")

        self.dealer_org = make_org("Workflow Dealer", org_type=Organization.Type.DEALER)
        add_member(self.dealer_user, self.dealer_org, Membership.Role.OWNER)
        self.other_dealer_org = make_org("Other Workflow Dealer", org_type=Organization.Type.DEALER)
        add_member(self.other_dealer_user, self.other_dealer_org, Membership.Role.OWNER)

        self.vehicle = make_vehicle(self.customer, reg="KWF 001A")
        self.partnership = Partnership.objects.create(
            insurer=self.insurer_a,
            dealership=self.dealer_org,
            status=Partnership.Status.ACTIVE,
            effective_date=timezone.now().date(),
        )
        self.consent = CustomerConsent.objects.create(
            customer=self.customer, dealership=self.dealer_org, insurer=self.insurer_a
        )
        self.dealer_client = auth_client(self.dealer_user)
        self.provider_a_client = auth_client(self.provider_a)
        self.provider_b_client = auth_client(self.provider_b)
        self.customer_client = auth_client(self.customer)

    def make_dealer_request(self, expires_at=None):
        from apps.insurance.services import generate_quotes

        req = QuotationRequest.objects.create(
            request_number=f"QR-WF-{QuotationRequest.objects.count()}",
            customer=self.customer,
            vehicle=self.vehicle,
            insurer=self.insurer_a,
            coverage_type=Product.Category.COMPREHENSIVE,
            sum_insured=Decimal("2000000.00"),
            desired_start_date=timezone.now().date() + timedelta(days=2),
            dealership=self.dealer_org,
            partnership=self.partnership,
            consent=self.consent,
            expires_at=expires_at or (timezone.now() + timedelta(days=14)),
        )
        generate_quotes(req, insurer_ids=[self.insurer_a.id])
        return req

    def test_dealer_request_visible_only_to_target_insurer_and_dealer(self):
        req = self.make_dealer_request()

        provider_a_detail = self.provider_a_client.get(f"/api/v1/quotation-requests/{req.id}/")
        self.assertEqual(provider_a_detail.status_code, 200, provider_a_detail.content)
        self.assertEqual(provider_a_detail.json()["insurer"], str(self.insurer_a.id))

        self.assertEqual(self.provider_a_client.get("/api/v1/quotation-requests/").json()["count"], 1)
        self.assertEqual(self.provider_b_client.get("/api/v1/quotation-requests/").json()["count"], 0)
        self.assertEqual(self.provider_b_client.get(f"/api/v1/quotation-requests/{req.id}/").status_code, 404)

        self.assertEqual(self.dealer_client.get("/api/v1/quotation-requests/").json()["count"], 1)
        self.assertEqual(
            auth_client(self.other_dealer_user).get(f"/api/v1/quotation-requests/{req.id}/").status_code, 404
        )
        self.assertEqual(self.customer_client.get(f"/api/v1/quotation-requests/{req.id}/").status_code, 200)

    def test_insurer_review_information_and_rejection_flow(self):
        req = self.make_dealer_request()

        review = self.provider_a_client.post(f"/api/v1/quotation-requests/{req.id}/start-review/")
        self.assertEqual(review.status_code, 200, review.content)
        self.assertEqual(review.json()["status"], "under_review")
        req.refresh_from_db()
        self.assertEqual(req.reviewed_by_id, self.provider_a.id)

        missing = self.provider_a_client.post(
            f"/api/v1/quotation-requests/{req.id}/request-info/", {}, content_type="application/json"
        )
        self.assertEqual(missing.status_code, 400)

        info = self.provider_a_client.post(
            f"/api/v1/quotation-requests/{req.id}/request-info/",
            {"notes": "Please upload the vehicle logbook."},
            content_type="application/json",
        )
        self.assertEqual(info.status_code, 200, info.content)
        self.assertEqual(info.json()["status"], "more_info")
        self.assertIn("logbook", info.json()["insurer_notes"])

        self.assertEqual(
            self.provider_b_client.post(f"/api/v1/quotation-requests/{req.id}/start-review/").status_code, 404
        )

        rejected = self.provider_a_client.post(
            f"/api/v1/quotation-requests/{req.id}/reject/",
            {"notes": "Vehicle falls outside our underwriting guidelines."},
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 200, rejected.content)
        self.assertEqual(rejected.json()["status"], "rejected")
        self.assertTrue(req.quotations.exists())
        self.assertTrue(all(q.status == Quotation.Status.REJECTED for q in req.quotations.all()))

        dealer_view = self.dealer_client.get(f"/api/v1/quotation-requests/{req.id}/")
        self.assertEqual(dealer_view.json()["status"], "rejected")

    def test_insurer_can_prepare_quotation_charges_and_expiry(self):
        req = self.make_dealer_request()
        quote = req.quotations.first()
        expiry = timezone.now() + timedelta(days=21)

        update = self.provider_a_client.patch(
            f"/api/v1/quotations/{quote.id}/",
            {
                "premium": "80000.00",
                "taxes": "5000.00",
                "fees": "1000.00",
                "other_charges": "500.00",
                "excess_amount": "15000.00",
                "coverage_limits": {"Own damage": "2000000", "Third party": "1000000"},
                "deductibles": {"Own damage": "15000"},
                "terms": "Cover is valid within Kenya.",
                "valid_until": expiry.isoformat(),
            },
            content_type="application/json",
        )
        self.assertEqual(update.status_code, 200, update.content)
        data = update.json()
        self.assertEqual(Decimal(data["total_payable"]), Decimal("86500.00"))
        self.assertEqual(data["coverage_limits"]["Third party"], "1000000")
        self.assertEqual(data["status"], "received")

        quote.refresh_from_db()
        self.assertEqual(quote.taxes, Decimal("5000.00"))
        self.assertEqual(quote.total_payable, Decimal("86500.00"))

        hijack = self.provider_b_client.patch(
            f"/api/v1/quotations/{quote.id}/", {"premium": "1.00"}, content_type="application/json"
        )
        self.assertEqual(hijack.status_code, 404)

    def test_dealer_clarify_select_and_apply(self):
        req = self.make_dealer_request()
        quote = req.quotations.first()

        clarify = self.dealer_client.post(
            f"/api/v1/quotation-requests/{req.id}/clarify/",
            {"notes": "Can you include windscreen cover?"},
            content_type="application/json",
        )
        self.assertEqual(clarify.status_code, 200, clarify.content)
        self.assertIn("windscreen", clarify.json()["clarification_note"])

        selected = self.dealer_client.post(f"/api/v1/quotations/{quote.id}/select/")
        self.assertEqual(selected.status_code, 200, selected.content)
        self.assertEqual(selected.json()["status"], "selected")
        req.refresh_from_db()
        self.assertEqual(req.status, QuotationRequest.Status.SELECTED)

        apply_resp = self.dealer_client.post(
            "/api/v1/applications/dealer-create/",
            {"quotation": str(quote.id)},
            content_type="application/json",
        )
        self.assertEqual(apply_resp.status_code, 201, apply_resp.content)
        app_data = apply_resp.json()
        self.assertEqual(app_data["status"], "submitted")
        self.assertEqual(app_data["customer"], str(self.customer.id))
        self.assertIsNone(app_data["policy_id"])

        application = Application.objects.get(pk=app_data["id"])
        self.assertEqual(application.dealership_id, self.dealer_org.id)
        self.assertEqual(application.partnership_id, self.partnership.id)
        req.refresh_from_db()
        self.assertEqual(req.status, QuotationRequest.Status.CONVERTED)

        duplicate = self.dealer_client.post(
            "/api/v1/applications/dealer-create/",
            {"quotation": str(quote.id)},
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 400)

        self.assertEqual(self.dealer_client.get("/api/v1/applications/").json()["count"], 1)
        self.assertEqual(self.provider_a_client.get("/api/v1/applications/").json()["count"], 1)
        self.assertEqual(self.provider_b_client.get("/api/v1/applications/").json()["count"], 0)
        self.assertEqual(
            auth_client(self.other_dealer_user).get(f"/api/v1/quotations/{quote.id}/").status_code, 404
        )

        other_apply = auth_client(self.other_dealer_user).post(
            "/api/v1/applications/dealer-create/",
            {"quotation": str(quote.id)},
            content_type="application/json",
        )
        self.assertEqual(other_apply.status_code, 403)

        self.assertTrue(Quotation.objects.filter(pk=quote.id, status=Quotation.Status.SELECTED).exists())

    def test_expired_dealer_request_blocks_selection_and_application(self):
        req = self.make_dealer_request(expires_at=timezone.now() - timedelta(days=1))
        quote = req.quotations.first()

        selected = self.dealer_client.post(f"/api/v1/quotations/{quote.id}/select/")
        self.assertEqual(selected.status_code, 400)

        apply_resp = self.dealer_client.post(
            "/api/v1/applications/dealer-create/",
            {"quotation": str(quote.id)},
            content_type="application/json",
        )
        self.assertEqual(apply_resp.status_code, 400)

    def test_multiple_insurers_respond_to_open_request(self):
        from apps.insurance.services import generate_quotes

        req = QuotationRequest.objects.create(
            request_number="QR-WF-OPEN",
            customer=self.customer,
            vehicle=self.vehicle,
            coverage_type=Product.Category.COMPREHENSIVE,
            sum_insured=Decimal("2000000.00"),
            desired_start_date=timezone.now().date() + timedelta(days=2),
            expires_at=timezone.now() + timedelta(days=14),
        )
        generate_quotes(req)
        quote_a = req.quotations.get(insurer=self.insurer_a)
        quote_b = req.quotations.get(insurer=self.insurer_b)

        info = self.provider_a_client.post(
            f"/api/v1/quotations/{quote_a.id}/request-info/",
            {"notes": "Confirm the vehicle's parking location."},
            content_type="application/json",
        )
        self.assertEqual(info.status_code, 200, info.content)
        self.assertEqual(info.json()["status"], "more_info")

        restore = self.provider_a_client.patch(
            f"/api/v1/quotations/{quote_a.id}/",
            {"notes": "Information provided."},
            content_type="application/json",
        )
        self.assertEqual(restore.status_code, 200, restore.content)
        quote_a.refresh_from_db()
        self.assertEqual(quote_a.status, Quotation.Status.RECEIVED)

        decline = self.provider_b_client.post(
            f"/api/v1/quotations/{quote_b.id}/reject/",
            {"notes": "We cannot cover this vehicle."},
            content_type="application/json",
        )
        self.assertEqual(decline.status_code, 200, decline.content)
        self.assertEqual(decline.json()["status"], "rejected")

        provider_a_quotes = self.provider_a_client.get(
            f"/api/v1/quotation-requests/{req.id}/quotations/"
        ).json()
        self.assertEqual({q["insurer"] for q in provider_a_quotes}, {str(self.insurer_a.id)})

        chosen = self.customer_client.post(f"/api/v1/quotations/{quote_a.id}/select/")
        self.assertEqual(chosen.status_code, 200, chosen.content)
        quote_b.refresh_from_db()
        self.assertEqual(quote_b.status, Quotation.Status.REJECTED)
        req.refresh_from_db()
        self.assertEqual(req.status, QuotationRequest.Status.SELECTED)
