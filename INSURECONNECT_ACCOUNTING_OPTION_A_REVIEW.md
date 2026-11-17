# INSURECONNECT — Accounting Option A (Trust/Agency) Review

Date: 2026-11-17
Purpose: prepare Option A for **professional accountant review only**.
**No journal postings, accounts, migrations, or transactions were created.**
Settlement status remains **"Recorded — journal posting pending."**

---

## 1. Files inspected

| File | Content inspected |
| --- | --- |
| `backend/apps/finance/migrations/0002_seed_default_ledger_accounts.py` | Chart of accounts seed (codes/names/types) |
| `backend/apps/finance/models.py` | `LedgerAccount`, `JournalEntry`, `LedgerEntry`, `Settlement`, `PlatformFee` docstrings |
| `backend/apps/finance/services.py` | `post_journal_entry`, `account_balance`, `financial_dashboard` (account 3000/4000 usage), `create_settlement_from_verified_payments` |
| `backend/apps/payments/services.py` | `complete_payment` (Dr 1000 / Cr 2000), `create_refund` (Dr 2000 / Cr 1000) |
| `backend/apps/insurance/services.py` | `issue_policy` (Dr 2000 / Cr 3000), `_create_agent_commission` (Dr 4000 / Cr 5000) |
| `backend/apps/payments/views.py` | `CommissionViewSet.pay` (Dr 5000 / Cr 1000) |
| Runtime DB query | Confirmed 8000/8100/8200 do **not** exist; 8200 unused anywhere |

## 2. Current chart of accounts (verified)

| Code | Name | Type | Actual use |
| --- | --- | --- | --- |
| 1000 | Bank / Cash | asset | Dr on premium receipt; Cr on refund/commission pay |
| 2000 | Premiums Collected - Unearned | liability | Cr on premium receipt; Dr on issuance & refund |
| 3000 | Premium Revenue | revenue | Cr on issuance ("premium is earned…") |
| 4000 | Commission Expense | expense | Dr on commission accrual |
| 5000 | Commission Payable | liability | Cr on accrual; Dr on commission pay |
| 6000 | Platform Revenue | revenue | **dormant — never posted** |
| 7000 | Platform Fee Receivable | asset | **dormant — never posted** |

## 3. Meaning of accounts 1000, 2000, 3000 (as implemented)

- **1000 Bank / Cash (asset)** — the platform's cash. Premium receipts debit it; refunds
  and commission payments credit it.
- **2000 Premiums Collected - Unearned (liability)** — premium received but not yet
  earned. Credited on receipt, debited (released) on policy issuance and refund.
- **3000 Premium Revenue (revenue)** — credited on issuance with the code comment
  *"premium is earned when the policy is issued"*. `financial_dashboard` computes
  `premium_earned` as the sum of credit entries on 3000.

> **Verification result: account 3000 is currently defined and used as the
> platform's own REVENUE (a principal-style recognition), not as a trust/clearing
> account.** This is the central issue for Option A — see §8.

## 4. Account 8000 — Insurer Settlements Payable (proposed)

- Code: `8000`
- Name: `Insurer Settlements Payable`
- Type: `liability`
- Currency: `KES` (match existing single-currency accounts)
- Purpose: amounts collected from customers on behalf of an insurer and owed to that
  insurer, until remitted.
- **Does not exist** — would be added as a new seeded account (subject to approval).

## 5. Account 8100 — Claims Payable

- **Does not exist.** No account named "Claims Payable" or code `8100` is present.
- Proposal: add `8100` Claims Payable (liability) — the amount due to a claimant once
  a claim is settled, until the funds are actually disbursed.

## 6. Account 8200

- **Does not exist and is not used anywhere** in code, migrations, or the database.
- `8200` is free; in the prior Option B it was proposed as "Claims Expense". Under the
  selected Option A it is **not required** and should remain unused.

## 7. Proposed debit / credit entries (Option A — trust/agency)

### Claim settlement (on actual disbursement, `Claim.settle`)

| Account | Direction | Amount |
| --- | --- | --- |
| 8100 Claims Payable | Debit | A |
| 1000 Bank / Cash | Credit | A |

> Posting point to be confirmed: the current `ClaimViewSet.settle` records
> `settled_amount`/`settlement_reference` and transitions to `SETTLED` immediately.
> The accountant must confirm whether the *settlement event* equals the *cash
> disbursement event*, or whether the payable should be recognised first and the cash
> credit posted later. **No posting before funds are actually remitted.**

### Insurer settlement — instruction/creation (recognise the liability)

| Account | Direction | Amount |
| --- | --- | --- |
| 3000 (see §8 caveat) | Debit | A |
| 8000 Insurer Settlements Payable | Credit | A |

### Insurer settlement — actual remittance

| Account | Direction | Amount |
| --- | --- | --- |
| 8000 Insurer Settlements Payable | Debit | A |
| 1000 Bank / Cash | Credit | A |

### Reconciliation

Status-only. **No posting.** (`Settlement.reconcile` must not create a journal entry.)

## 8. Accounting assumptions — principal vs agent (the key question)

Two signals in the codebase conflict:

- **Implemented ledger (principal):** premium is recognised as the platform's own
  `3000 Premium Revenue` on issuance. Under this reading the platform is a **principal**
  that earns premium and pays commissions/claims as its own expense.
- **Documented intent (agent):** `PlatformFee` states *"the platform never holds or
  distributes insurance premiums itself"* and `Settlement` records *"amounts owed to an
  insurer"* — an **agent/trust** reading where premium belongs to the insurer.

**Implication for Option A:** the proposed insurer-settlement entry **Debit 3000 /
Credit 8000** only makes sense under the *agent* reading, where 3000 is a trust/clearing
account (insurer funds collected on the insurer's behalf), not the platform's revenue.

If 3000 remains the platform's *own revenue* (principal), then "Debit 3000" on insurer
settlement is effectively a revenue reversal — which is the Option B (revenue) model,
not Option A. These two models cannot both be true for the same 3000.

**Do not alter the existing premium/commission ledger** until the accountant resolves
whether the platform is agent or principal and, if agent, whether 3000 must be
redefined/renamed (e.g. "Premiums collected on behalf of insurers") or replaced by a
liability account.

## 9. Questions for the accountant

1. Is INSURECONNECT acting as **agent/trustee** or **principal** with respect to
   customer premiums? (The ledger says principal; the model docstrings say agent.)
2. If agent: should account **3000 be redefined** from "Premium Revenue" to a trust/
   clearing liability? This changes revenue recognition and the `financial_dashboard`
   "premium earned" figure.
3. Is the **platform's own revenue** correctly the commission/fee only (4000/6000),
   with premium excluded from the P&L?
4. Are premiums actually **collected into the platform's own bank account** (legal
   ownership) or into a segregated client/trust account? (Determines whether 1000 should
   even reflect premium, and whether client-money segregation rules apply.)
5. Claim settlement: is the platform the **payer of record**, or does the insurer pay
   the claimant directly (platform records only)? Determines whether 1000 is credited.
6. Does the insurer's receivable include **refunds and chargebacks** netted out? Confirm
   the `create_settlement_from_verified_payments` netting (premiums − refunds).
7. Are **commissions** (4000/5000) the platform's cost or the insurer's cost (netted from
   the insurer settlement)? Currently commission is the platform's expense — confirm.
8. Are the **dormant accounts 6000/7000** (Platform Revenue / Fee Receivable) intended to
   be used, and what is the platform's actual fee model?
9. What are the **revenue recognition** and **derecognition** triggers under the chosen
   model (policy issuance vs premium collection vs settlement)?
10. **Tax/VAT** treatment of premiums held in trust vs recognised revenue.
11. **Client-money / trust-account regulatory** obligations if premiums are held in trust.

## 10. Reconciliation example (synthetic, KES)

Scenario: customer premium 100,000; agent commission 10,000; platform fee 5,000;
insurer's net = 85,000.

| Step | Entry | Debit | Credit |
| --- | --- | --- | --- |
| 1 | Premium receipt | 1000 Bank | 100,000 | — |
| | | 2000 Unearned | — | 100,000 |
| 2 | Policy issuance (current) | 2000 Unearned | 100,000 | — |
| | | 3000 (trust/clearing — see §8) | — | 100,000 |
| 3 | Commission accrual | 4000 Comm Expense | 10,000 | — |
| | | 5000 Comm Payable | — | 10,000 |
| 4 | Insurer settlement — instruct (net of fee) | 3000 | 85,000 | — |
| | | 8000 Insurer Settlements Payable | — | 85,000 |
| 5 | Commission paid | 5000 | 10,000 | — |
| | | 1000 | — | 10,000 |
| 6 | Insurer settlement — remit | 8000 | 85,000 | — |
| | | 1000 | — | 85,000 |
| 7 | Claim settlement (approved 20,000) | 8100 Claims Payable | 20,000 | — |
| | | 1000 | — | 20,000 |

Reconciliation of 8000: credit 85,000 (step 4) − debit 85,000 (step 6) = **0** — no
residual payable. Reconciliation of 1000: 100,000 − 10,000 − 85,000 − 20,000 = −15,000,
representing the platform's retained fee/commission margin (subject to the fee model
in question 8).

> These figures are illustrative only; they depend on the accountant's answers to
> §9 (notably the agent/principal determination and the platform-fee model) and must
> not be treated as approved.

---

## Status

**BLOCKED BY APPROVAL.** No journal postings were implemented, no accounts or
migrations were created, no financial transactions were generated, and the existing
premium/commission ledger was not modified. Settlement records continue to show
**"Recorded — journal posting pending."**
