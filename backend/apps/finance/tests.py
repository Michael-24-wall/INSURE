from decimal import Decimal

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
    make_vehicle,
)
from apps.finance.models import LedgerAccount, LedgerEntry, Settlement
from apps.finance.services import (
    create_settlement_from_verified_payments,
    financial_dashboard,
    post_journal_entry,
    premium_tracking_summary,
    reverse_journal_entry,
)
from apps.organizations.models import Membership, Organization
from apps.payments.models import Commission, Payment, Refund


class FinancialOperationsTests(TestCase):
    def setUp(self):
        self.admin = make_user("financeadmin@example.com", role=User.Role.ADMIN)
        self.customer = make_user("financecustomer@example.com")
        self.provider = make_user("financeprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org = make_org("Finance Insurance")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        self.insurer = make_insurer(self.org, "Finance Insurance")
        self.product = make_product(self.insurer, code="FIN-COMP", rate="5.0000")
        self.vehicle = make_vehicle(self.customer)
        self.customer_client = auth_client(self.customer)
        self.provider_client = auth_client(self.provider)
        self.admin_client = auth_client(self.admin)

    def test_financial_dashboard_requires_platform_access(self):
        customer_resp = self.customer_client.get("/api/v1/finance/dashboard/")
        self.assertEqual(customer_resp.status_code, 200, customer_resp.content)
        self.assertEqual(customer_resp.json()["scope"], "customer")

        provider_resp = self.provider_client.get("/api/v1/finance/dashboard/")
        self.assertEqual(provider_resp.status_code, 200, provider_resp.content)
        self.assertEqual(provider_resp.json()["scope"], "insurer")
        self.assertEqual(provider_resp.json()["insurer_id"], str(self.insurer.id))

    def test_admin_financial_dashboard_reports_collections_and_settlements(self):
        resp = self.admin_client.get("/api/v1/finance/dashboard/")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertIn("gross_premium_collected", data)
        self.assertIn("net_premium_collected", data)
        self.assertIn("refunded", data)
        self.assertIn("premium_earned_recognized", data)
        self.assertIn("commissions_outstanding", data)
        self.assertIn("settlements", data)

    def test_customer_financial_dashboard_is_scoped_to_own_payments(self):
        policy = create_policy(self.customer, self.insurer, self.product, self.vehicle)
        Payment.objects.create(
            user=self.customer,
            purpose=Payment.Purpose.PREMIUM,
            policy=policy,
            application=policy.application,
            amount=Decimal("12500.00"),
            method=Payment.Method.BANK,
            status=Payment.Status.SUCCEEDED,
            verified_at=timezone.now(),
            verified_by=self.provider,
            receipt_number="RCPT-FIN-001",
        )
        resp = self.customer_client.get("/api/v1/finance/dashboard/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["gross_premium_collected"], "12500.00")
        self.assertEqual(resp.json()["payment_count"], 1)

    def test_net_collected_subtracts_completed_refunds(self):
        policy = create_policy(self.customer, self.insurer, self.product, self.vehicle)
        payment = Payment.objects.create(
            user=self.customer,
            purpose=Payment.Purpose.PREMIUM,
            policy=policy,
            application=policy.application,
            amount=Decimal("12500.00"),
            method=Payment.Method.BANK,
            status=Payment.Status.SUCCEEDED,
            verified_at=timezone.now(),
            verified_by=self.provider,
            receipt_number="RCPT-FIN-002",
        )
        Refund.objects.create(
            payment=payment,
            amount=Decimal("2500.00"),
            reason="Duplicate premium charged",
            status=Refund.Status.COMPLETED,
            reference="REF-FIN-001",
            completed_at=timezone.now(),
        )
        resp = self.provider_client.get("/api/v1/finance/dashboard/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["gross_premium_collected"], "12500.00")
        self.assertEqual(resp.json()["net_premium_collected"], "10000.00")
        self.assertEqual(resp.json()["refunded"], "2500.00")

    def test_premium_tracking_uses_payment_currency(self):
        policy = create_policy(self.customer, self.insurer, self.product, self.vehicle)
        Payment.objects.create(
            user=self.customer,
            policy=policy,
            purpose=Payment.Purpose.PREMIUM,
            amount=policy.premium,
            method=Payment.Method.BANK,
            status=Payment.Status.SUCCEEDED,
            currency="USD",
            verified_at=timezone.now(),
        )
        summary = premium_tracking_summary(policy, self.customer.full_name)
        self.assertEqual(summary["currency"], "USD")

    def test_premium_tracking_endpoint_is_scoped(self):
        policy = create_policy(self.customer, self.insurer, self.product, self.vehicle)
        own_resp = self.customer_client.get(f"/api/v1/finance/premium-tracking/{policy.id}/")
        self.assertEqual(own_resp.status_code, 200, own_resp.content)
        self.assertEqual(own_resp.json()["policy"], policy.policy_number)
        self.assertEqual(own_resp.json()["premium"], "100000.00")

        other = make_user("financeothercustomer@example.com")
        other_client = auth_client(other)
        self.assertEqual(other_client.get(f"/api/v1/finance/premium-tracking/{policy.id}/").status_code, 403)

        provider_resp = self.provider_client.get(f"/api/v1/finance/premium-tracking/{policy.id}/")
        self.assertEqual(provider_resp.status_code, 200, provider_resp.content)

        other_provider = make_user("financeotherprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        add_member(other_provider, make_org("Finance Insurance B"), Membership.Role.OWNER)
        other_provider_client = auth_client(other_provider)
        self.assertEqual(
            other_provider_client.get(f"/api/v1/finance/premium-tracking/{policy.id}/").status_code,
            403,
        )

    def test_ledger_balances_endpoint_returns_chart_of_accounts(self):
        resp = self.admin_client.get("/api/v1/finance/ledger/balances/")
        self.assertEqual(resp.status_code, 200, resp.content)
        balances = resp.json()
        self.assertIsInstance(balances, list)
        self.assertTrue(any(row["account"] == "1000" for row in balances))

    def test_ledger_balances_are_platform_admin_scoped(self):
        self.assertEqual(self.customer_client.get("/api/v1/finance/ledger/balances/").status_code, 403)

    def test_chart_of_accounts_and_config_endpoints_are_admin_scoped(self):
        for path in (
            "/api/v1/finance/ledger/accounts/",
            "/api/v1/finance/exchange-rates/",
            "/api/v1/finance/currency-configs/",
            "/api/v1/finance/platform-fees/",
        ):
            self.assertEqual(self.customer_client.get(path).status_code, 403, path)
            self.assertEqual(self.provider_client.get(path).status_code, 403, path)
            self.assertEqual(self.admin_client.get(path).status_code, 200, path)

    def test_settlement_lifecycle_updates_outstanding_balance(self):
        settlement = Settlement.objects.create(
            reference="SET-FIN-001",
            insurer=self.insurer,
            amount_due=Decimal("15000.00"),
            status=Settlement.Status.PENDING,
        )
        create_resp = self.provider_client.post(
            "/api/v1/finance/settlements/",
            {
                "insurer": str(self.insurer.id),
                "amount_due": "15000.00",
                "settlement_instructions": "Bank transfer to insurer collection account.",
            },
            content_type="application/json",
        )
        # A manually supplied reference is optional; the endpoint may generate one.
        self.assertEqual(create_resp.status_code, 201, create_resp.content)

        pending = Settlement.objects.filter(insurer=self.insurer).order_by("-created_at").first()
        self.assertEqual(pending.amount_due, Decimal("15000.00"))
        self.assertEqual(pending.outstanding, Decimal("15000.00"))

        instruct = self.provider_client.post(f"/api/v1/finance/settlements/{pending.id}/instruct/", {}, content_type="application/json")
        self.assertEqual(instruct.status_code, 200, instruct.content)
        settle = self.provider_client.post(f"/api/v1/finance/settlements/{pending.id}/settle/", {}, content_type="application/json")
        self.assertEqual(settle.status_code, 200, settle.content)
        reconcile = self.admin_client.post(f"/api/v1/finance/settlements/{pending.id}/reconcile/", {}, content_type="application/json")
        self.assertEqual(reconcile.status_code, 200, reconcile.content)
        self.assertEqual(reconcile.json()["status"], "reconciled")

    def test_settlement_auto_creation_uses_verified_payments(self):
        settlement = create_settlement_from_verified_payments(self.insurer)
        self.assertIsNone(settlement)

    def test_settlement_auto_creation_ignores_other_insurers_refunds(self):
        policy = create_policy(self.customer, self.insurer, self.product, self.vehicle)
        payment = Payment.objects.create(
            user=self.customer,
            purpose=Payment.Purpose.PREMIUM,
            policy=policy,
            application=policy.application,
            amount=Decimal("1000.00"),
            method=Payment.Method.BANK,
            status=Payment.Status.SUCCEEDED,
            verified_at=timezone.now(),
            receipt_number="RCPT-FIN-SET-1",
        )
        Refund.objects.create(
            payment=payment,
            amount=Decimal("100.00"),
            reason="Partial refund",
            status=Refund.Status.COMPLETED,
            reference="REF-FIN-SET-1",
            completed_at=timezone.now(),
        )

        other_org = make_org("Other Finance Insurance")
        other_insurer = make_insurer(other_org, "Other Finance Insurance")
        other_product = make_product(other_insurer, code="FIN-OTHER", rate="5.0000")
        other_customer = make_user("financeother@example.com")
        other_policy = create_policy(other_customer, other_insurer, other_product)
        other_payment = Payment.objects.create(
            user=other_customer,
            purpose=Payment.Purpose.PREMIUM,
            policy=other_policy,
            application=other_policy.application,
            amount=Decimal("5000.00"),
            method=Payment.Method.BANK,
            status=Payment.Status.SUCCEEDED,
            verified_at=timezone.now(),
            receipt_number="RCPT-FIN-SET-2",
        )
        Refund.objects.create(
            payment=other_payment,
            amount=Decimal("5000.00"),
            reason="Full refund for other insurer",
            status=Refund.Status.COMPLETED,
            reference="REF-FIN-SET-2",
            completed_at=timezone.now(),
        )

        settlement = create_settlement_from_verified_payments(self.insurer)
        self.assertIsNotNone(settlement)
        self.assertEqual(settlement.amount_due, Decimal("900.00"))

    def test_settlement_cannot_be_patched(self):
        settlement = Settlement.objects.create(
            reference="SET-FIN-LOCK",
            insurer=self.insurer,
            amount_due=Decimal("15000.00"),
            status=Settlement.Status.PENDING,
        )
        resp = self.provider_client.patch(
            f"/api/v1/finance/settlements/{settlement.id}/",
            {"amount_due": "1.00"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 405)


class CommissionReportingTests(TestCase):
    def setUp(self):
        self.admin = make_user("commrepadmin@example.com", role=User.Role.ADMIN)
        self.customer = make_user("commrepcustomer@example.com")
        self.provider = make_user("commrepprovider@example.com", role=User.Role.PROVIDER_ADMIN)
        self.org = make_org("Commission Reporting Insurance")
        add_member(self.provider, self.org, Membership.Role.OWNER)
        self.insurer = make_insurer(self.org, "Commission Reporting Insurance")
        self.product = make_product(self.insurer, code="COMMREP-COMP")
        self.policy = create_policy(self.customer, self.insurer, self.product)

    def _accrue(self, amount, reference):
        return post_journal_entry(
            reference=reference,
            description=f"Commission accrual {reference}",
            lines=[
                {"account": "4000", "direction": "debit", "amount": amount, "reference": reference},
                {"account": "5000", "direction": "credit", "amount": amount, "reference": reference},
            ],
            currency="KES",
            posted_by=self.admin,
            policy=self.policy,
        )

    def _pay(self, amount, reference):
        return post_journal_entry(
            reference=reference,
            description=f"Commission payment {reference}",
            lines=[
                {"account": "5000", "direction": "debit", "amount": amount, "reference": reference},
                {"account": "1000", "direction": "credit", "amount": amount, "reference": reference},
            ],
            currency="KES",
            posted_by=self.admin,
        )

    def _expense(self):
        return financial_dashboard(self.admin)["commission_expense_recorded"]

    def test_commission_accrual_debits_account_4000(self):
        entry = self._accrue(Decimal("1000.00"), "COMM-ACC-1")
        line = entry.entries.get(account__code="4000")
        self.assertEqual(line.direction, LedgerEntry.Direction.DEBIT)
        self.assertEqual(line.amount, Decimal("1000.00"))
        self.assertEqual(self._expense(), "1000.00")

    def test_commission_payment_debits_account_5000_without_increasing_expense(self):
        self._accrue(Decimal("1000.00"), "COMM-ACC-2")
        payment = self._pay(Decimal("1000.00"), "COMM-PAY-2")
        line = payment.entries.get(account__code="5000")
        self.assertEqual(line.direction, LedgerEntry.Direction.DEBIT)
        self.assertEqual(line.amount, Decimal("1000.00"))
        self.assertFalse(payment.entries.filter(account__code="4000").exists())
        self.assertEqual(self._expense(), "1000.00")

    def test_multiple_commission_accruals_are_summed(self):
        self._accrue(Decimal("1000.00"), "COMM-ACC-3")
        self._accrue(Decimal("500.00"), "COMM-ACC-4")
        self.assertEqual(self._expense(), "1500.00")

    def test_commission_reversal_nets_against_original_expense(self):
        entry = self._accrue(Decimal("1000.00"), "COMM-ACC-5")
        reversal = reverse_journal_entry("REV-COMM-ACC-5", entry, "test reversal", self.admin)
        line = reversal.entries.get(account__code="4000")
        self.assertEqual(line.direction, LedgerEntry.Direction.CREDIT)
        self.assertEqual(line.amount, Decimal("1000.00"))
        self.assertEqual(self._expense(), "0.00")

    def test_empty_commission_is_zero(self):
        self.assertFalse(LedgerEntry.objects.filter(account__code="4000").exists())
        self.assertEqual(Commission.objects.count(), 0)
        self.assertEqual(self._expense(), "0.00")

    def test_commission_expense_isolates_account_4000(self):
        # Policy issuance posts 2000/3000 and payment posts 5000/1000; only 4000 is expense.
        self._accrue(Decimal("1000.00"), "COMM-ACC-6")
        self._pay(Decimal("1000.00"), "COMM-PAY-6")
        self.assertTrue(LedgerEntry.objects.filter(account__code="3000").exists())
        self.assertTrue(
            LedgerEntry.objects.filter(account__code="5000", direction=LedgerEntry.Direction.DEBIT).exists()
        )
        self.assertEqual(self._expense(), "1000.00")

    def test_commission_expense_does_not_mix_foreign_currency_accounts(self):
        # Accounts carry one currency, so a USD commission-like posting on other
        # accounts must not be valued into the KES commission-expense figure.
        usd_expense = LedgerAccount.objects.create(
            code="4100", name="Commission Expense (USD)", type=LedgerAccount.Type.EXPENSE, currency="USD"
        )
        usd_payable = LedgerAccount.objects.create(
            code="5100", name="Commission Payable (USD)", type=LedgerAccount.Type.LIABILITY, currency="USD"
        )
        post_journal_entry(
            reference="COMM-USD-1",
            description="USD commission accrual",
            lines=[
                {"account": usd_expense, "direction": "debit", "amount": Decimal("250.00"), "reference": "COMM-USD-1"},
                {"account": usd_payable, "direction": "credit", "amount": Decimal("250.00"), "reference": "COMM-USD-1"},
            ],
            currency="USD",
            posted_by=self.admin,
        )
        self._accrue(Decimal("1000.00"), "COMM-ACC-8")
        self.assertEqual(self._expense(), "1000.00")

    def test_commission_expense_is_all_time_and_ignores_date_filter(self):
        # commission_expense_recorded is a cumulative ledger total (like
        # premium_earned_recognized). Dashboard start/end narrow cash-flow metrics only.
        self._accrue(Decimal("1000.00"), "COMM-ACC-7")
        dashboard = financial_dashboard(self.admin, start="2099-01-01", end="2099-12-31")
        self.assertEqual(dashboard["commission_expense_recorded"], "1000.00")
