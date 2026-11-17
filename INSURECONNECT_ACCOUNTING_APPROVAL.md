# INSURECONNECT — Accounting Approval (Claim & Insurer Settlement)

Date: 2026-11-17
Status: **PROPOSALS PREPARED — AWAITING APPROVAL. NOT IMPLEMENTED.**

## Current chart of accounts (single currency KES)

| Code | Name | Type |
| --- | --- | --- |
| 1000 | Bank / Cash | asset |
| 2000 | Premiums Collected - Unearned | liability |
| 3000 | Premium Revenue | revenue |
| 4000 | Commission Expense | expense |
| 5000 | Commission Payable | liability |
| 6000 | Platform Revenue | revenue |
| 7000 | Platform Fee Receivable | asset |

Verified premium flow (DO NOT alter): payment → Debit `1000` / Credit `2000`;
issuance → Debit `2000` / Credit `3000`. Commission pay → Debit `5000` / Credit `1000`.

`JournalEntry` already has `claim` and `settlement` foreign keys (ready for these postings).

## A. Claim settlement

Posting point: the existing `ClaimViewSet.settle` action (currently records
`settled_amount`/`settlement_reference` and transitions to `SETTLED` with **no** journal entry).

| | Option A — Trust/agency (RECOMMENDED) | Option B — Expense model |
| --- | --- | --- |
| New account | `8100` Claims Payable (liability) | `8200` Claims Expense (expense) |
| On `Claim.settle(amount A)` | Debit `8100` A · Credit `1000` A | Debit `8200` A · Credit `1000` A |
| Meaning | Platform holds insurer funds in trust and disburses claims | Platform bears claim cost as its own expense |

## B. Insurer settlement

| | Option A — Trust/agency (RECOMMENDED) | Option B — Revenue model |
| --- | --- | --- |
| New account | `8000` Insurer Settlements Payable (liability) | — |
| On settlement `instruct`/creation (A) | Debit `3000` A · Credit `8000` A | (no entry) |
| On `settle` (funds remitted) (A) | Debit `8000` A · Credit `1000` A | Debit `3000` A · Credit `1000` A |
| `reconcile` | status only (no posting) | status only (no posting) |

## Impact of Option A vs Option B

- **Option A** treats the platform as an intermediary holding funds in trust; the
  insurer's share moves from premium revenue to a payable, then to cash on remittance.
  This matches the existing `Settlement` model (`amount_due` owed to insurer) and
  `create_settlement_from_verified_payments`.
- **Option B** treats premium as the platform's own revenue and remittances as a
  revenue reduction; it requires no new payable account but does not reflect the
  insurer liability before remittance.

## Proposed controls (once a model is approved)

- Idempotent posting (one entry per settlement reference, guarded by the existing
  unique `JournalEntry.reference`).
- Balanced, single-currency entries via `post_journal_entry`.
- Transactional atomicity (wrap status + posting in `@transaction.atomic`).
- Reversal via the existing `reverse_journal_entry`.
- `reconcile` never posts.
- Settlement records remain **"Recorded — journal posting pending"** until a posting
  exists; never marked financially complete without it.

## Decision required from you

1. Select **Option A** or **Option B** for claim settlement.
2. Select **Option A** or **Option B** for insurer settlement.
3. Confirm the account codes/names for any new accounts.

Until then, no settlement journal code is written and no settlement is reported as
financially complete.
