# INSURECONNECT — Accounting Consistency Review

Date: 2026-11-17
Purpose: document the **actual** accounting behaviour and its internal
inconsistencies for accountant/legal review. **No accounts, migrations, journal
postings, or transactions were changed.** Settlement records remain
**"Recorded — journal posting pending."**

---

## 1. Complete accounting lifecycle (as implemented)

The following is traced from the code, not from documentation. Every posting is
listed with its source location in §2.

1. **Customer pays premium** (`complete_payment`, `apps/payments/services.py:148-163`)
   → Dr 1000 Bank/Cash · Cr 2000 Premiums Unearned.
2. **Policy issued** (`issue_policy`, `apps/insurance/services.py:216-222`)
   → Dr 2000 · Cr 3000 "Premium Revenue" (comment: *"premium is earned when the
   policy is issued"*).
3. **Commission accrued** on issuance (`_create_agent_commission` /
   `_create_dealer_commission`, `apps/insurance/services.py:283-284`)
   → Dr 4000 Commission Expense · Cr 5000 Commission Payable.
4. **Commission paid** (`CommissionViewSet.pay`, `apps/payments/views.py:276-277`)
   → Dr 5000 · Cr 1000.
5. **Refund** (`create_refund`, `apps/payments/services.py:224-233`)
   → Dr 2000 · Cr 1000.
6. **Platform fee** → **no journal posting exists** (accounts 6000/7000 are dormant).
7. **Insurer settlement** (`SettlementViewSet.settle`/`reconcile`,
   `apps/finance/views.py`) → **no journal posting**; only `Settlement` model status/
   amounts are updated.
8. **Claim settlement** (`ClaimViewSet.settle`, `apps/claims/views.py:237-254`) →
   **no journal posting**; only `Claim.settled_amount`/`settlement_reference` are set.

## 2. Every journal posting and source location

| # | Trigger | Entry | Source |
| --- | --- | --- | --- |
| 1 | Premium receipt | Dr 1000 / Cr 2000 | `apps/payments/services.py:152-154` |
| 2 | Policy issuance | Dr 2000 / Cr 3000 | `apps/insurance/services.py:219-220` |
| 3 | Commission accrual | Dr 4000 / Cr 5000 | `apps/insurance/services.py:283-284` |
| 4 | Commission pay | Dr 5000 / Cr 1000 | `apps/payments/views.py:276-277` |
| 5 | Premium refund | Dr 2000 / Cr 1000 | `apps/payments/services.py:228-229` |
| — | Platform fee | (none) | — |
| — | Insurer settlement | (none) | — |
| — | Claim settlement | (none) | — |

## 3. Who owns the premium at each stage (verified behaviour)

- **On receipt:** cash is debited to the platform's own `1000 Bank/Cash`; a liability
  `2000 Premiums Collected-Unearned` is credited. The cash is in the **platform's
  account**. "Unearned" is ambiguous: it could be a liability to the customer (to
  provide cover) or to the insurer (funds held in trust).
- **On issuance:** `2000` is debited and `3000 Premium Revenue` is credited, i.e. the
  premium is recognised as the **platform's own revenue**. At this point the ledger
  does **not** record any amount owed to the insurer (no `8000`); the insurer's
  receivable exists only in the application-level `Settlement` model.
- **Conclusion:** under the implemented ledger, the **platform is treated as the
  principal** that earns the premium. There is no ledger representation of a
  trust/agency relationship to the insurer.

## 4. Is account 3000 consistently revenue, or used as clearing?

**Consistently revenue — never clearing.** `3000` is only ever **credited**
(`apps/insurance/services.py:220`) and read as a credit total
(`apps/finance/services.py:316-343`). There is **no debit** to 3000 anywhere in the
codebase. A clearing account would be debited and credited; 3000 is not.

Implication: Option A's proposed **Debit 3000** on insurer settlement would be the
first-ever debit to 3000 — i.e. a **revenue reversal**, not a clearing movement. Under
the current definition, that entry belongs to the *revenue* model (Option B), not to a
trust/agency model.

## 5. Contradictory assumptions in the models

| Source | Statement | Implied model |
| --- | --- | --- |
| `LedgerAccount` 3000 name/type | "Premium Revenue" / revenue | principal |
| `issue_policy` comment | "premium is earned when the policy is issued" | principal |
| `PlatformFee` docstring | "the platform never holds or distributes insurance premiums itself" | agent/trust |
| `Settlement` docstring | "Amounts owed to an insurer" | agent/trust |
| `create_settlement_from_verified_payments` | computes insurer receivable from premiums − refunds | agent/trust |

The **ledger is principal; the model documentation is agent/trust.** These are
irreconcilable as written and must be resolved before any settlement posting is added.

## 6. Dashboards / reports that could misrepresent

1. **`financial_dashboard.commission_expense_recorded`** (`apps/finance/services.py:344-355`)
   sums **credit** entries on account 4000. Commission accrual **debits** 4000, so this
   figure is always **0** — commission expense is under-reported. (Should sum debits.)
2. **`financial_dashboard.premium_earned_recognized`** (`apps/finance/services.py:332-343`)
   reports the full premium (credit on 3000) as platform revenue. Under a trust/agency
   model this would misstate insurer premiums as platform income.
3. **`financial_dashboard.outstanding_settlements`** is derived from the `Settlement`
   table (`amount_due − amount_settled`), which has **no corresponding ledger posting**.
   Once settlement postings exist, this dashboard figure and the ledger could diverge.
4. **`premium_tracking_summary`** reports `premium`/`collected`/`refunded` at policy
   level (from `Payment`, not the ledger) — accurate for cash, but silent on insurer
   liability and platform revenue classification.

## 7. Effect of the two accounting models on existing records and reporting

**Principal (current behaviour):**
- Premium = platform revenue (3000). Commission = platform expense (4000). Insurer
  settlement would be a cost/expense or a revenue reduction when remitted.
- `premium_earned_recognized` is meaningful as revenue; `commission_expense_recorded`
  must be fixed (debit, not credit).
- No historical adjustment needed — this is what the ledger already does.

**Trust/agency (Option A):**
- Premium is the insurer's funds, not platform revenue. The existing `Dr 2000 / Cr 3000`
  issuance entry would misclassify premium as platform revenue.
- `3000` would need to be **redefined** (or the issuance posting changed) so premium is
  not P&L. Insurer settlement becomes `Dr 3000 (or replacement clearing) / Cr 8000`
  then `Dr 8000 / Cr 1000`. Claims become `Dr 8100 / Cr 1000` (if the platform is the
  payer) or memo-only (if the insurer pays directly).
- Reporting changes materially: premium must be excluded from platform revenue;
  insurer liabilities (8000/8100) must be reported.

## 8. Would changing the model require a migration or historical adjustment?

- **Changing to trust/agency (Option A):** yes. The existing issuance posting already
  credited `3000 Premium Revenue` for all issued policies. Converting would require
  either (a) a chart-of-accounts change (redefine 3000 or add a trust liability) plus
  a **historical reclassification** of posted entries, or (b) prospective-only adoption
  with a documented cut-over and a reconciling adjustment. This is an accounting
  migration decision. **Not performed.**
- **Staying principal:** no migration; only fix the `commission_expense_recorded`
  calculation (debit vs credit) and decide insurer-settlement treatment.

Neither migration nor adjustment was performed.

## 9. Ledger unchanged

Verified: no account, migration, journal entry, or financial record was added, edited,
or deleted during this review. The chart of accounts remains exactly
`1000/2000/3000/4000/5000/6000/7000`, and all settlement records remain
**"Recorded — journal posting pending."**

---

## Required scenarios (illustrative, KES)

Figures are **illustrative**. "Verified" marks behaviour already in the system;
"Assumed" marks the proposed model behaviour (not implemented).

**Inputs:** premium 100,000; commission 10,000; platform fee 5,000; insurer net
settlement 85,000; separate insurer-funded claim payout (assume 20,000).

### Principal model (matches current ledger — VERIFIED for steps 1–4)

| Step | Entry | Debit | Credit | Status |
| --- | --- | --- | --- | --- |
| Premium receipt | 1000 / 2000 | 100,000 | 100,000 | VERIFIED |
| Issuance | 2000 / 3000 | 100,000 | 100,000 | VERIFIED |
| Commission accrual | 4000 / 5000 | 10,000 | 10,000 | VERIFIED |
| Commission paid | 5000 / 1000 | 10,000 | 10,000 | VERIFIED |
| Platform fee | (none) | — | — | NOT IMPLEMENTED |
| Insurer settlement remit | 3000 / 1000 | 85,000 | 85,000 | ASSUMED (revenue reduction) |
| Claim payout | expense / 1000 | 20,000 | 20,000 | ASSUMED |

### Trust/agency model (Option A — ASSUMED, not implemented)

| Step | Entry | Debit | Credit | Status |
| --- | --- | --- | --- | --- |
| Premium receipt | 1000 / 2000 | 100,000 | 100,000 | VERIFIED |
| Issuance | 2000 / (trust/clearing) | 100,000 | 100,000 | ASSUMED (3000 redefined or replaced) |
| Commission accrual | 4000 / 5000 | 10,000 | 10,000 | VERIFIED |
| Commission paid | 5000 / 1000 | 10,000 | 10,000 | VERIFIED |
| Insurer settlement — instruct | 3000(clearing) / 8000 | 85,000 | 85,000 | ASSUMED |
| Insurer settlement — remit | 8000 / 1000 | 85,000 | 85,000 | ASSUMED |
| Claim payout (platform payer) | 8100 / 1000 | 20,000 | 20,000 | ASSUMED |

If the insurer pays the claimant directly, the claim payout is **memo-only** (no 1000
movement). This depends on the legal/contractual arrangement.

---

## Who must confirm what (before a model is approved)

**Accountant:**
1. Is the platform **agent/trustee or principal** for premiums (ledger vs docstrings)?
2. If agent, must `3000` be redefined/replaced, and is the issuance posting correct?
3. What is the platform's **revenue**: commission/fee only, or premium too?
4. Confirm the **platform-fee** model and whether dormant `6000/7000` should be used.
5. Confirm **commission** is a platform cost vs netted from the insurer settlement.
6. Fix `commission_expense_recorded` (debit vs credit) regardless of model.
7. Determine **revenue recognition / derecognition** triggers and **tax/VAT** treatment.

**Legal adviser:**
8. Does premium legally enter the **platform's own account**, or must it be segregated
   (client/trust money)? Are there client-money / segregation obligations?
9. Is the platform the **payer of record** for claims, or does the insurer pay directly?
10. Do the insurer partnership agreements support an agency (trust) relationship?

**Insurer partners:**
11. Confirm the **net settlement basis** (premium − refunds − commission − fee) and the
    settlement cadence.
12. Confirm **who funds claim payouts** and the claim settlement flow (insurer-funded
    vs platform-disbursed).

Until these are confirmed, the model cannot be approved and no settlement journal
posting may be implemented.
