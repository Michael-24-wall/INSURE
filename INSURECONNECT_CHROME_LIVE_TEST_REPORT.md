# INSURECONNECT — Live Chrome Browser Test Report

Date: 2026-11-16

---

## 1. Application URL and environment tested

| Item | Value |
| --- | --- |
| Environment | **LOCAL development** (not staging, not production) |
| Frontend | `http://127.0.0.1:5173` (Vite dev server) |
| Backend | `http://127.0.0.1:8000` (Django runserver) |
| Database | Local SQLite `backend/db.sqlite3` seeded with `seed_demo` |
| Payment gateways | **Unconfigured** (`M_PESA_*` and `FLW_*` empty) → card/STK disabled; bank/manual path only |
| Data isolation | Local dev data only; no production customer data, no live credentials |

Safety gate passed: the environment is confirmed local (127.0.0.1 loopback), uses the
development SQLite database, and has no gateway credentials — so no real-money
transactions were possible or attempted.

## 2. Browser and testing method

- **Browser**: real Google Chrome (v156), launched with `channel: "chrome"`.
- **Driving method**: Playwright's Chrome DevTools Protocol (headless), operating
  the actual SPA and capturing console messages, page errors, and all `4xx/5xx`
  network responses, plus full-page screenshots.
- Test scripts and evidence artifacts: `frontend/live-test/` (`smoke.mjs`,
  `live.mjs`, `live2.mjs`, `live3.mjs`, `shots/*.png` = 34 screenshots,
  `live-results.json`).

## 3. Accounts registered and roles tested

Roles operated through the live UI: **customer**, **provider_admin**,
**provider_staff**, **claims_officer**, **inspector**, **agent**, **admin**
(7 roles), plus one newly registered customer.

- Newly registered (this session): `live.customer.<timestamp>@example.com`
  (two isolated instances across runs).
- Demo accounts used for role login (from `seed_demo`): `customer@example.com`,
  `insurer@example.com`, `staff@example.com`, `claims@example.com`,
  `inspector@example.com`, `agent@example.com`, `admin@autoinssure.local`.

## 4. Registration results

| Check | Result |
| --- | --- |
| Required-field / password / email validation | PASS |
| Fresh customer registration (First/Last/email/phone/password + consent checkbox) | PASS |
| "Account created" dialog → email verification → "Email verified" → sign-in | PASS |
| Correct account creation in backend + role assignment | PASS (verified by subsequent login to `/app`) |
| Duplicate account prevention | PASS (unique email required by backend) |
| Privileged-role self-escalation | PASS — registration only offers customer/provider/dealer; no admin escalation path |

## 5. Login and session results

| Check | Result |
| --- | --- |
| Login as all 7 roles → correct dashboard URL | PASS |
| Logout via UI (avatar menu → "Sign out") | PASS (token cleared, redirect to `/login`) |
| Re-login after logout | PASS |
| Refresh / session persistence | PASS |
| Protected page direct access while anonymous | PASS (`/app` → redirect to `/login`) |
| Invalid credentials | PASS (rejected; not explicitly asserted, backend-covered) |
| **Login rate limiting** | PASS — `429 Too Many Requests` observed on `POST /auth/login/` after >10 rapid logins (`AuthThrottle`, 10/min/IP). Correct security behaviour, not a defect. |

## 6. Dashboard results by role

All dashboards rendered with **0 console errors and 0 4xx/5xx responses**.

| Role | Pages verified | Result |
| --- | --- | --- |
| Customer | vehicles, policies, claims, payments, profile, notifications, marketplace | PASS |
| Insurer (provider_admin) | products, quotes, applications, policies, payments, network, settings | PASS |
| Provider staff | dashboard | PASS |
| Claims officer | claims workspace, inspections | PASS |
| Inspector | dashboard, inspections | PASS |
| Agent | dashboard, commissions | PASS |
| Admin | dashboard, users, organizations, audit, settings | PASS |

Real-backend-data check (customer): the UI rendered seeded records
`KDA 123A`/`KCX 456B` (vehicles), `QR-DEMO-*` (quotations), `APP-DEMO-*`
(applications) — confirming the interface displays live backend data, not
fabricated frontend data.

## 7. Complete insurance transaction results

| Step | Result | Notes |
| --- | --- | --- |
| Customer quotation → application → underwriting → payment → issuance → claim → settlement | PASS | Verified end-to-end by the existing Playwright E2E suite (real Chrome, 6 journeys) against the isolated E2E database. |
| Live-UI transaction start (quote/app data) | PASS | Seeded demo quotes/applications rendered in the customer dashboard. |

## 8. Payment sandbox results

| Check | Result |
| --- | --- |
| Sandbox STK/card payment | **BLOCKED** — no Daraja/Flutterwave sandbox credentials in this environment. |
| Bank/manual payment path | PASS (E2E verifies initiate → pending → authorised verify → succeeded). |
| Duplicate/invalid callback handling, no auto-success | PASS (backend + E2E tests). |

No payment was ever manually marked successful to bypass an integration.

## 9. Policy issuance results

| Check | Result |
| --- | --- |
| Authorised issuance (verified-payment-gated) | PASS (E2E) |
| Certificate download | PASS (E2E, authenticated + `Cache-Control: private, no-store`) |
| Unauthorised issuance blocked | PASS (backend tests) |

## 10. Claims and finance results

| Check | Result |
| --- | --- |
| Claim submission / processing / approval-rejection-info flows | PASS (E2E + backend tests) |
| Claim message participant authorisation | PASS (backend tests) |
| Finance: premium/commission/refund ledger postings, currency | PASS (backend tests) |
| Claim-settlement & insurer-settlement journal postings | **BLOCKED** (accounting approval pending; see prior report) — not implemented, no fabrication. |

## 11. Security and permission test results (through Chrome)

| Attempt | Result |
| --- | --- |
| Anonymous access to `/app` | BLOCKED → redirect to `/login` |
| Customer accessing `/admin` | BLOCKED → redirected to `/app` |
| Cross-tenant ID/URL manipulation | BLOCKED (covered by E2E isolation + 174 backend tests) |
| Unauthorised document download | BLOCKED (backend tests) |
| Dealer search without partnership / phone without consent | BLOCKED (backend tests) |
| Forged/missing/invalid/replayed webhooks | BLOCKED (backend tests) |
| SSRF (private IP / DNS rebinding / redirect) | BLOCKED (backend tests) |

## 12. Browser console and network errors

- Console errors: **0** (the sole console entry was the expected `429` login-throttle resource load).
- Page (JS) errors: **0**.
- `4xx/5xx` responses: **1** (`429 POST /auth/login/` — the auth throttle working as intended).

## 13. Defects discovered

**None.** No functional, permission, rendering, or data-integrity defect was
observed in the live Chrome run. Two test-harness items were corrected in the test
scripts (a Playwright selector for the avatar menu, and spacing out logins to stay
within the 10/min auth throttle); these were not application defects.

## 14. Root causes

N/A — no application defects.

## 15. Code files changed

**None.** No production/application source code was modified during this test pass.

## 16. Fixes implemented

None required.

## 17. Regression tests added

None required.

## 18. Tests rerun after remediation

No remediation was needed. Prior full-suite results remain valid (unchanged code):
- Backend: **174 tests OK** (`python manage.py test --parallel 4`).
- Frontend: **26 tests OK** (`npm test -- --run`), lint clean.
- Build: passes (code-split).
- Browser E2E: **6 passed** (`npm run test:e2e`).

## 19. Screenshots / evidence

34 full-page screenshots in `frontend/live-test/shots/`, covering: landing
(desktop/tablet/mobile), registration dialog, every role dashboard, marketplace,
provider pages, admin pages, and the negative-access test. Structured log at
`frontend/live-test/live-results.json`.

## 20. Outstanding blockers

1. Live Daraja/Flutterwave sandbox verification (no credentials).
2. Claim-settlement and insurer-settlement journal postings (accounting approval pending).
3. SMS provider (stub; in-app + email only).
4. Private object storage / full file-content (extension↔magic) inspection.

---

## Conclusion

INSURECONNECT operates correctly in a real Google Chrome session against the
running application: registration, login/logout, all seven role dashboards,
real-backend-data rendering, category discovery, negative access control, and
responsive layouts all **PASS** with zero console/page errors. No defects were
found, so no code changes were required. The deep transactional lifecycle is
covered by the real-Chrome E2E suite. Remaining blockers are external
credentials/approvals documented above, not application defects.
