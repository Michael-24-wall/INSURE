from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.common.tests_utils import (
    add_member,
    auth_client,
    create_submitted_application,
    make_insurer,
    make_org,
    make_product,
    make_user,
)
from apps.insurance.models import Policy
from apps.integrations.models import WebhookEvent
from apps.organizations.models import Membership
from apps.payments.models import Payment, Refund, Transaction
from apps.payments.services import PaymentError, verify_card_payment


class PaymentFlowTests(TestCase):
    def setUp(self):
        self.customer = make_user("payer@example.com")
        self.other_customer = make_user("nonpayer@example.com")
        self.provider = make_user("payprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.other_provider = make_user("otherprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org = make_org("Payer Insurance")
        self.other_org = make_org("Other Insurance")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        add_member(self.other_provider, self.other_org, Membership.Role.OWNER)
        self.insurer = make_insurer(self.org, "Payer Insurance")
        self.product = make_product(self.insurer, code="PAY-COMP", rate="5.0000")
        self.application = create_submitted_application(self.customer, self.insurer, self.product)
        self.client_auth = auth_client(self.customer)
        self.provider_client = auth_client(self.provider)

    def initiate(self, method="bank", key=None):
        headers = {}
        if key:
            headers["HTTP_IDEMPOTENCY_KEY"] = key
        return self.client_auth.post(
            "/api/v1/payments/initiate/",
            {"application": str(self.application.id), "method": method, "phone": "0712345678"},
            content_type="application/json",
            **headers,
        )

    def test_bank_payment_pending_then_manual_verification(self):
        resp = self.initiate()
        self.assertEqual(resp.status_code, 201, resp.content)
        payment = resp.json()["payment"]
        self.assertEqual(payment["status"], "pending")
        self.assertEqual(Decimal(payment["amount"]), self.application.quotation.premium)

        verify = self.provider_client.post(
            f"/api/v1/payments/{payment['id']}/verify/",
            {"provider_reference": "BANK-REF-777"},
            content_type="application/json",
        )
        self.assertEqual(verify.status_code, 200, verify.content)
        self.assertEqual(verify.json()["status"], "succeeded")
        self.assertTrue(verify.json()["receipt_number"])
        self.assertTrue(Transaction.objects.filter(payment_id=payment["id"], status="succeeded").exists())

    @override_settings(M_PESA_ALLOWED_IPS=["127.0.0.1"])
    def test_unverified_mpesa_payment_never_auto_succeeds(self):
        resp = self.initiate(method="mpesa")
        self.assertEqual(resp.status_code, 201, resp.content)
        payment_id = resp.json()["payment"]["id"]
        callback = self.client.post(
            "/api/v1/payments/mpesa/callback/",
            {
                "Body": {
                    "stkCallback": {
                        "CheckoutRequestID": "unconfigured-checkout",
                        "ResultCode": 0,
                        "ResultDesc": "Success",
                        "CallbackMetadata": {"Item": [{"Name": "Amount", "Value": 1}]},
                    }
                }
            },
            content_type="application/json",
        )
        self.assertEqual(callback.status_code, 200)
        payment = Payment.objects.get(pk=payment_id)
        self.assertNotEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertTrue(WebhookEvent.objects.filter(provider="mpesa").exists())

    def test_mpesa_callback_fails_closed_without_allowlist(self):
        resp = self.client.post(
            "/api/v1/payments/mpesa/callback/", {"Body": {}}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_card_callback_fails_closed_without_signature_config(self):
        resp = self.client.post(
            "/api/v1/payments/card/callback/", {"data": {}}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_idempotency_key_reuses_payment(self):
        first = self.initiate(key="idem-123")
        second = self.initiate(key="idem-123")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["payment"]["id"], second.json()["payment"]["id"])
        self.assertEqual(Payment.objects.count(), 1)

    def test_idempotency_key_cannot_return_another_users_payment(self):
        first = self.initiate(key="shared-key")
        self.assertEqual(first.status_code, 201)
        other_application = create_submitted_application(self.other_customer, self.insurer, self.product)
        other_client = auth_client(self.other_customer)
        second = other_client.post(
            "/api/v1/payments/initiate/",
            {"application": str(other_application.id), "method": "bank"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="shared-key",
        )
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Payment.objects.count(), 1)

    def test_commission_amount_cannot_be_patched(self):
        resp = self.provider_client.patch(
            "/api/v1/payments/commissions/00000000-0000-0000-0000-000000000000/",
            {"amount": "999999.00"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 405)

    def test_duplicate_premium_payment_blocked_after_success(self):
        payment = self.initiate().json()["payment"]
        self.provider_client.post(
            f"/api/v1/payments/{payment['id']}/verify/",
            {"provider_reference": "BANK-1"},
            content_type="application/json",
        )
        again = self.initiate()
        self.assertEqual(again.status_code, 400)

    def test_refund_flow_and_limits(self):
        payment = self.initiate().json()["payment"]
        self.provider_client.post(
            f"/api/v1/payments/{payment['id']}/verify/",
            {"provider_reference": "BANK-2"},
            content_type="application/json",
        )
        refund = self.provider_client.post(
            f"/api/v1/payments/{payment['id']}/refund/",
            {"amount": "1000.00", "reason": "Customer cancelled"},
            content_type="application/json",
        )
        self.assertEqual(refund.status_code, 201, refund.content)
        self.assertTrue(Refund.objects.filter(payment_id=payment["id"], status="completed").exists())
        over = self.provider_client.post(
            f"/api/v1/payments/{payment['id']}/refund/",
            {"amount": "99999999.00", "reason": "Too much"},
            content_type="application/json",
        )
        self.assertEqual(over.status_code, 400)

    def test_customer_cannot_verify_payment(self):
        payment = self.initiate().json()["payment"]
        resp = self.client_auth.post(
            f"/api/v1/payments/{payment['id']}/verify/",
            {"provider_reference": "FAKE"},
            content_type="application/json",
        )
        self.assertIn(resp.status_code, (403, 404))
        self.assertEqual(Payment.objects.get(pk=payment["id"]).status, Payment.Status.PENDING)

    def test_other_provider_cannot_verify(self):
        payment = self.initiate().json()["payment"]
        other = auth_client(self.other_provider)
        resp = other.post(
            f"/api/v1/payments/{payment['id']}/verify/",
            {"provider_reference": "X"},
            content_type="application/json",
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_customer_cannot_initiate_for_other_application(self):
        client = auth_client(self.other_customer)
        resp = client.post(
            "/api/v1/payments/initiate/",
            {"application": str(self.application.id), "method": "bank"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_receipt_only_after_success(self):
        payment = self.initiate().json()["payment"]
        before = self.client_auth.get(f"/api/v1/payments/{payment['id']}/receipt/")
        self.assertEqual(before.status_code, 400)
        self.provider_client.post(
            f"/api/v1/payments/{payment['id']}/verify/",
            {"provider_reference": "BANK-3"},
            content_type="application/json",
        )
        after = self.client_auth.get(f"/api/v1/payments/{payment['id']}/receipt/")
        self.assertEqual(after.status_code, 200)
        self.assertIn("receipt_number", after.json())


class PaymentAutomationTests(TestCase):
    def setUp(self):
        self.customer = make_user("autopay@example.com")
        self.org = make_org("Auto Insurer")
        self.insurer = make_insurer(self.org, "Auto Insurer")
        self.product = make_product(self.insurer, code="AUTO-COMP")
        self.application = create_submitted_application(self.customer, self.insurer, self.product)

    def test_card_payment_requires_gateway(self):
        resp = auth_client(self.customer).post(
            "/api/v1/payments/initiate/",
            {"application": str(self.application.id), "method": "card"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_timeout_stale_bank_payment(self):
        payment = Payment.objects.create(
            user=self.customer,
            purpose=Payment.Purpose.PREMIUM,
            application=self.application,
            amount=self.application.quotation.premium,
            method=Payment.Method.BANK,
            status=Payment.Status.PENDING,
        )
        Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(days=10))

        from apps.payments.tasks import timeout_stale_payments

        failed = timeout_stale_payments()
        self.assertGreaterEqual(failed, 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)

    @override_settings(M_PESA_ALLOWED_IPS=["1.2.3.4"])
    def test_mpesa_callback_rejects_non_allowlisted_ip(self):
        resp = self.client.post(
            "/api/v1/payments/mpesa/callback/",
            {"Body": {"stkCallback": {"CheckoutRequestID": "x", "ResultCode": 0}}},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    @override_settings(M_PESA_ALLOWED_IPS=["127.0.0.1"])
    def test_mpesa_callback_accepts_allowlisted_ip(self):
        resp = self.client.post(
            "/api/v1/payments/mpesa/callback/",
            {"Body": {"stkCallback": {"CheckoutRequestID": "x", "ResultCode": 0}}},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    @override_settings(M_PESA_ALLOWED_IPS=["10.0.0.5"], M_PESA_TRUST_FORWARDED_FOR=False)
    def test_mpesa_callback_rejects_spoofed_forwarded_for(self):
        resp = self.client.post(
            "/api/v1/payments/mpesa/callback/",
            {"Body": {"stkCallback": {"CheckoutRequestID": "x", "ResultCode": 0}}},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR="10.0.0.5",
        )
        self.assertEqual(resp.status_code, 403)

    @override_settings(M_PESA_ALLOWED_IPS=["10.0.0.5"], M_PESA_TRUST_FORWARDED_FOR=True)
    def test_mpesa_callback_accepts_trusted_proxy_forwarded_for(self):
        resp = self.client.post(
            "/api/v1/payments/mpesa/callback/",
            {"Body": {"stkCallback": {"CheckoutRequestID": "x", "ResultCode": 0}}},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR="10.0.0.5",
        )
        self.assertEqual(resp.status_code, 200)

    @override_settings(FLW_WEBHOOK_HASH="test-webhook-secret")
    def test_card_callback_rejects_invalid_or_missing_signature(self):
        payload = {"data": {"tx_ref": "card-ref-1", "status": "successful"}}
        missing = self.client.post(
            "/api/v1/payments/card/callback/", payload, content_type="application/json"
        )
        wrong = self.client.post(
            "/api/v1/payments/card/callback/",
            payload,
            content_type="application/json",
            HTTP_VERIF_HASH="wrong-secret",
        )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(wrong.status_code, 403)
        self.assertFalse(WebhookEvent.objects.filter(provider="flutterwave").exists())

    @override_settings(FLW_WEBHOOK_HASH="test-webhook-secret")
    def test_card_callback_accepts_valid_signature_and_is_idempotent(self):
        payload = {"data": {"tx_ref": "card-ref-2", "status": "successful"}}
        for _ in range(2):
            resp = self.client.post(
                "/api/v1/payments/card/callback/",
                payload,
                content_type="application/json",
                HTTP_VERIF_HASH="test-webhook-secret",
            )
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            WebhookEvent.objects.filter(provider="flutterwave", event_id="card:card-ref-2").count(), 1
        )

    @override_settings(
        M_PESA_CONSUMER_KEY="test-key",
        M_PESA_CONSUMER_SECRET="test-secret",
        M_PESA_SHORTCODE="123456",
        M_PESA_PASSKEY="test-passkey",
        M_PESA_ALLOWED_IPS=["127.0.0.1"],
    )
    @patch("apps.payments.services.MpesaDarajaClient.query")
    def test_stk_callback_rejects_query_amount_mismatch(self, query):
        query.return_value = {"ResultCode": "0", "Amount": 1, "MpesaReceiptNumber": "REC-1"}
        payment = Payment.objects.create(
            user=self.customer,
            purpose=Payment.Purpose.PREMIUM,
            application=self.application,
            amount=self.application.quotation.premium,
            method=Payment.Method.MPESA,
            status=Payment.Status.PROCESSING,
            checkout_request_id="checkout-amount-mismatch",
        )
        resp = self.client.post(
            "/api/v1/payments/mpesa/callback/",
            {
                "Body": {
                    "stkCallback": {
                        "CheckoutRequestID": payment.checkout_request_id,
                        "ResultCode": 0,
                        "ResultDesc": "Success",
                        "CallbackMetadata": {"Item": [{"Name": "Amount", "Value": str(payment.amount)}]},
                    }
                }
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        self.assertNotEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertTrue(WebhookEvent.objects.filter(provider="mpesa", error__icontains="amount").exists())

    @override_settings(
        M_PESA_CONSUMER_KEY="test-key",
        M_PESA_CONSUMER_SECRET="test-secret",
        M_PESA_SHORTCODE="123456",
        M_PESA_PASSKEY="test-passkey",
        M_PESA_ALLOWED_IPS=["127.0.0.1"],
    )
    @patch("apps.payments.services.MpesaDarajaClient.query")
    def test_stk_callback_success_marks_payment_without_issuing_policy(self, query):
        payment = Payment.objects.create(
            user=self.customer,
            purpose=Payment.Purpose.PREMIUM,
            application=self.application,
            amount=self.application.quotation.premium,
            method=Payment.Method.MPESA,
            status=Payment.Status.PROCESSING,
            checkout_request_id="checkout-policy-boundary",
        )
        query.return_value = {
            "ResultCode": "0",
            "Amount": str(payment.amount),
            "MpesaReceiptNumber": "REC-POLICY",
        }
        resp = self.client.post(
            "/api/v1/payments/mpesa/callback/",
            {
                "Body": {
                    "stkCallback": {
                        "CheckoutRequestID": payment.checkout_request_id,
                        "ResultCode": 0,
                        "ResultDesc": "Success",
                        "CallbackMetadata": {"Item": [{"Name": "Amount", "Value": str(payment.amount)}]},
                    }
                }
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(Policy.objects.filter(application=self.application).count(), 0)

    @override_settings(FLW_WEBHOOK_HASH="test-webhook-secret", FLW_SECRET_KEY="test-secret")
    @patch("apps.payments.services.FlutterwaveCardGateway.verify")
    def test_card_callback_success_marks_payment_without_issuing_policy(self, verify):
        verify.return_value = {
            "data": {
                "status": "successful",
                "amount": str(self.application.quotation.premium),
                "currency": "KES",
                "flw_ref": "FLW-POLICY",
            }
        }
        payment = Payment.objects.create(
            user=self.customer,
            purpose=Payment.Purpose.PREMIUM,
            application=self.application,
            amount=self.application.quotation.premium,
            method=Payment.Method.CARD,
            status=Payment.Status.PROCESSING,
            reference="card-policy-ref",
        )
        resp = self.client.post(
            "/api/v1/payments/card/callback/",
            {"data": {"tx_ref": payment.reference, "status": "successful"}},
            content_type="application/json",
            HTTP_VERIF_HASH="test-webhook-secret",
        )
        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(Policy.objects.filter(application=self.application).count(), 0)

    @override_settings(FLW_SECRET_KEY="test-secret")
    @patch("apps.payments.services.FlutterwaveCardGateway.verify")
    def test_card_verification_rejects_amount_mismatch(self, verify):
        verify.return_value = {
            "data": {"status": "successful", "amount": 1, "currency": "KES", "flw_ref": "FLW-1"}
        }
        payment = Payment.objects.create(
            user=self.customer,
            purpose=Payment.Purpose.PREMIUM,
            application=self.application,
            amount=self.application.quotation.premium,
            method=Payment.Method.CARD,
            status=Payment.Status.PROCESSING,
        )
        with self.assertRaises(PaymentError):
            verify_card_payment(payment.id)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PROCESSING)
