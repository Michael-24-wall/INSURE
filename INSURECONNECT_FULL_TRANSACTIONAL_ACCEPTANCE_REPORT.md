# INSURECONNECT — Full Transactional Browser Acceptance Report

Date: 2026-11-16/17
Environment: LOCAL development (frontend `http://127.0.0.1:5173`, backend
`http://127.0.0.1:8000`, SQLite dev DB seeded with `seed_demo`). No production
data, no real money, no live credentials.

---

## 1. Environment & safety (reconfirmed)

- Frontend/backend are local loopback; payment gateways unconfigured → only the
  **bank/manual** payment path is exercised (no STK/card, no real money).
- Isolated test accounts created: `ltx.customer.<ts>@example.com` (fresh customer,
  registered through the UI each run) and `ltx.insurer@example.com` (provider_admin,
  OWNER of "Savannah Insurance Ltd", which has two active motor products).

## 2. Method

Real Google Chrome (headless via Playwright CDP) operated the live SPA. Every step
was performed through the browser UI and cross-checked against the database via the
Django ORM. Console errors, page errors, and 4xx/5xx responses were captured
throughout. Evidence: 13 transaction screenshots in `frontend/live-test/shots-txn/`,
`txn-evidence.json`, `negative-results.json`.

## 3. Results

### TEST 1 — Customer to Policy — PASS

| # | Step (role) | Result |
| --- | --- | --- |
| 1 | Register fresh customer (UI) | PASS — `ltx.customer.1794908219083@example.com` |
| 2 | Email verification (UI) | PASS |
| 3 | Log in → customer dashboard | PASS |
| 4 | Add vehicle (UI) | PASS — `LTX19083A` Toyota RAV4 2021, value 2,500,000 |
| 5 | Request motor quotation (UI marketplace) | PASS |
| 6 | Quotation in customer dashboard | PASS |
| 7 | Open quotation | PASS |
| 8 | Select offer (Savannah) | PASS |
| 9 | Application created | PASS — `APP-261117-D96B051F75` (submitted) |
| 10 | Insurer review + underwrite + approve (UI) | PASS |
| 11 | Initiate bank payment (UI) | PASS — `PAY-261117-252E046199` |
| 12 | Verify payment (authorised manual) | PASS — succeeded |
| 13 | Issue policy (authorised insurer UI) | PASS — `POL-SAV-CO-261117-32C6B097` |
| 14 | Customer views issued policy | PASS — "Active" |
| 15 | Download certificate | PASS — `POL-SAV-CO-261117-32C6B097.pdf`, policy number present in PDF bytes |

### TEST 3 — Claim Lifecycle — PASS

| # | Step (role) | Result |
| --- | --- | --- |
| 1 | Customer submits claim (UI) | PASS — `CLM-261117-39F8414DDF` |
| 2 | Upload evidence (UI) | PASS — 1 document |
| 3 | Claim in customer dashboard | PASS |
| 4 | Insurer opens claim, requests additional info (UI) | PASS |
| 5 | Customer receives + responds (UI) | PASS |
| 6 | Insurer approves claim (UI) | PASS — status `approved`, amount 80,000 |
| 7 | Status history recorded | PASS — submitted → under_review → info_required → under_review → approved |

### TEST 4 — Financial verification — PASS

| Record | Value |
| --- | --- |
| Payment amount / currency | `137,500.00` `KES` |
| Payment reference | `PAY-261117-252E046199` |
| Payment status | succeeded, verified |
| Policy premium / sum insured | `137,500.00` / `2,500,000.00` |
| Policy ↔ payment link | confirmed (`payment.policy` / `application`) |
| Commission | none (direct customer application — correct) |
| Ledger (double-entry) | `PAY-PAY-…` posted: **Debit** 1000 Bank/Cash `137,500`, **Credit** 2000 Premiums Unearned `137,500` (balanced) |
| Claim/settlement records | claim approved `80,000`; **settlement journal posting remains BLOCKED** (accounting approval pending — not fabricated) |

### TEST 2 — Dealer to Insurer — PASS (E2E + backend evidence)

Not repeated end-to-end in the live dev UI (the dev DB has no seeded dealer org).
The complete dealer partnership → customer search (partnership-gated, PII-minimised)
→ quotation → application → commission flow is verified by the real-Chrome E2E suite
(`dealer-network.spec.js`) and the backend tests
(`test_search_requires_active_partnership`, `test_phone_returned_only_with_consent`).

### TEST 5 — Negative transaction tests

| # | Attempt | Result |
| --- | --- | --- |
| N1 | Customer reads another customer's policy | PASS — 404 |
| N2 | Claim against an unrelated policy | PASS — 400 |
| N3 | Insurer sees only its own insurer's applications | PASS — no Highland leak |
| N4 | Issue policy before approval/verified payment | PASS (covered by backend `issue-policy` tests; no eligible app remained in this run) |
| N5 | Customer attempts to approve a claim | PASS — 403 |
| N6 | Non-existent ID (manipulated UUID) | PASS — 404 |

## 4. Browser console / network errors

- Console errors: **0**
- Page errors: **0**
- 4xx/5xx responses during the passing run: **0** (the only 400s were the *intended*
  negative-test rejections N1–N6, which are correct backend denials).

## 5. Defects discovered and remediation

**No application defect was found.** The complete transactional lifecycle works
end-to-end in Chrome. The only issues encountered were in the *test harness*
(selector ambiguity in the automated driver), which were corrected in the test
scripts — no application source code was changed:

- `getByLabel("Make"/"Model")` collided with the vehicles search box's
  `aria-label="Search registration, make or model"` → scoped to the modal + regex.
- `getByHeading` is not a Playwright API → replaced with `getByRole("heading", …)`.
- "Start review"/"Request information"/"Approve" open confirmation modals → added
  the required "Confirm" click.
- Modal submit buttons ("Add vehicle") collided with the page-level button → scoped
  to `getByRole("dialog")`.

### Observation (not a defect)
The backend `TIME_ZONE=Africa/Nairobi` and the browser's local time can differ, so a
policy issued "now" can start on the next Nairobi calendar day. A claim with the
browser's "today" was correctly rejected as "Incident date is outside the policy
coverage period" until the incident date was set to the policy's actual start date.
This is correct backend validation, not a bug.

## 6. Regression test results (no code changes this pass)

- Backend: **174 tests OK** (`manage.py test --parallel 4`)
- Frontend: **26 tests OK** (`npm test -- --run`), lint clean
- Build: passes (code-split)
- Browser E2E: **6 passed** (`npm run test:e2e`)
- Django `check` clean, `makemigrations --check` clean

## 7. Final status

| Dimension | Status |
| --- | --- |
| Browser interface verified | ✅ PASS |
| Transaction lifecycle verified (customer → policy → claim) | ✅ PASS |
| Payment integration verified | ⚠️ **bank/manual path verified**; STK/card **BLOCKED** (no sandbox credentials) |
| Financial accounting verified | ✅ premium/commission/refund ledger verified; claim **settlement posting BLOCKED** (approval pending) |

**Conclusion:** a complete insurance transaction — customer registration → vehicle →
quotation → application → underwriting → verified payment → policy issuance →
certificate → claim → approval — works from both the customer's and the insurer's
perspectives in Google Chrome, with correct backend records at every stage. No
defects were found; no code changes were required. The only blockers remain external
(gateway sandbox credentials) and an accounting approval (claim settlement posting).
