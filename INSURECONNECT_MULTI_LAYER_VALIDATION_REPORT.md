# INSURECONNECT — Multi-Layer System Validation & Integrity Audit

Date: 2026-11-16
Scope: full-stack technical validation of the existing INSURECONNECT platform —
frontend, API, auth/authorisation, multi-tenant isolation, data integrity,
insurance lifecycle, payments, financial engine, documents, integrations and
deployment. This was a validation-and-fix pass, not a redesign.

---

## A. Executive summary

INSURECONNECT is a coherent, integrated platform whose core insurance lifecycle is
genuinely wired end-to-end: customer → quotation → application → underwriting →
payment → verified policy issuance → claims → finance. The platform is **not
motor-only in identity** (it presents all ten lines), but only the motor product
categories are operational; the other nine lines are honestly surfaced as
"expanding" and never generate fictitious quotes or premiums.

This pass re-ran the full test pyramid and confirmed a green baseline, then closed
two additional low-severity integrity defects (claim-message authorisation and a
cross-tenant provider-dashboard metric leak). All previously-resolved security
findings were re-verified. The remaining gaps are financial-accounting postings
(claim settlement and insurer settlement journal entries) that require a
chart-of-accounts decision, plus external gateway verification blocked on
credentials.

**Readiness: INTERNAL QA READY.** All internal automated checks pass and critical/
high-severity security findings are resolved, but the financial-accounting gaps and
unverified external integrations prevent staging/production readiness.

---

## B. Layer-by-layer results

### 1. Frontend layer
Components inspected: routing (`App.jsx`, `main.jsx`), `Layout.jsx` navigation,
`ProtectedRoute.jsx` role guards, `AuthContext.jsx`, every page under `src/pages`,
`api/client.js`, and shared components (`ui.jsx`, `DataTable`, `FileDownload`).

Passed:
- Role-based navigation and route guards for customer/provider/agent/dealer/
  inspector/claims/admin.
- API error handling via a 401-refresh interceptor and `autoinssure:auth-expired`
  event; no page displays fabricated data to hide a failed request (verified by
  code inspection and the loading/error/empty states audit below).
- Forms, modals, confirm dialogs, pagination, search and tables.
- 26 unit tests pass; production build passes; lint clean.

Fixes implemented (this and prior pass):
- Logo link now routes to the role home path (was landing page for non-customers).
- Detail-route page titles (was generic "Workspace").
- `wide` modal prop implemented (was silently ignored).
- Removed dead footer links and a redundant ternary.
- Customer "Complete your payment" list scoped to `approved` applications and linked
  to the specific application (was including not-yet-payable statuses and linking to
  the list page).
- Added missing loading/error/empty states to Vehicles, Products, Inspector
  dashboard, Commissions summary and Notifications `markRead`.

Failed: none.
Untested: cross-browser beyond Chromium (E2E uses system Chrome only; Firefox/WebKit
not run in this environment).

### 2. API / backend layer
Passed:
- All routes under `/api/v1/…` resolve; pagination/filtering/search/ordering
  consistent via `apps/common/pagination.py`.
- DRF permission classes, custom scoping (`apps/common/scoping.py`) and
  object-level checks verified by 164 backend tests.
- `manage.py check` clean; `makemigrations --check` clean.

Fixes (prior pass): finance read exposure, platform-settings read, payment refund
claim branch, AI risk scoping, inspection/claim download authorisation, SSRF
hostname resolution, `apps/finance/__init__.py`.

Failed: none.
Untested: schema/OpenAPI contract drift (drf-spectacular is configured but the
generated schema was not diffed against the frontend).

### 3. Authentication & authorization
Tested across roles: customer, provider_admin, provider_staff, agent, inspector,
claims_officer, dealer_admin, dealer_staff, admin, super_admin.

Passed:
- JWT access/refresh with rotation, blacklist and token-version invalidation
  (`apps/accounts/tokens.py`); TOTP 2FA; login lockout.
- Registration (customer/provider/dealer), login, logout, email verification,
  password reset, KYC.
- Privileged operations (org verify, policy issue, claim approve/settle, finance
  admin) all enforce `is_platform_admin` or org-membership checks.
- Object-level authorisation rejects manipulated IDs (IDOR tests across claims,
  vehicles, inspections, documents, organisations).

Fixes (this pass): message/claim authorisation (`apps/notifications/views.py`) now
requires both sender and recipient to be participants of the referenced claim.

### 4. Multi-tenant isolation
Tested by constructing distinct organisations and identities and attempting direct
API access with foreign IDs (list + detail + search + download + export).

Passed (covered by regression tests): customer isolation, insurer/org scoping for
claims, vehicles, inspections, payments, finance journal entries, settlements,
commissions, integrations, notifications, documents.

Fixes:
- **Inspections** (prior pass): removed the `organization_id__isnull=True` fallback
  that exposed unassigned inspections to every provider/dealer/agent; added
  `_require_download` to report/photo download and inspector-only `ai_assist`.
- **Provider dashboard** (this pass): `open_quotation_requests` in
  `apps/analytics/services.py:provider_dashboard` was global; now scoped to the
  provider's insurers / open marketplace (cross-tenant count leak).

Remaining (documented, low): dealer customer search returns platform-wide PII to
any dealer (role-gated + throttled; needs consent/exact-id constraint).

### 5. Database & data integrity
Passed:
- Models, FKs, unique constraints, `select_for_update` in `issue_policy` (duplicate
  issuance prevention) and idempotent payment/webhook handling.
- `post_journal_entry` enforces balanced/immutable entries and unique references;
  refunds/reversals post mirror entries.
- All migrations applied; `makemigrations --check` clean; `apps/finance/__init__.py`
  restored proper package discovery (12 finance tests were previously skipped by
  `manage.py test`).

Failed: none detected. No destructive DB operations performed (isolated test DBs and
the disposable `e2e.sqlite3` only).

### 6. Insurance business logic
Operational: motor (comprehensive, third party, third party/fire/theft, commercial,
motorcycle) through the full lifecycle.

Passed: premium calculation, quote generation, quote selection, application
submission/approval/reject/more-info, verified-payment-gated issuance, policy
numbering, renewal eligibility, claims eligibility, and state transitions
(verifying status guards prevent skipping required stages for the supported flow).

Notes:
- Claim state machine allows `UNDER_REVIEW → APPROVED` without inspection/assessment
  (simple claims may not require inspection) — this is a business-rule choice, not a
  privilege bypass; `_assert_provider` still gates the action.
- Non-motor categories are accurately marked "expanding"; no fabricated operational
  quotes/policies are produced.

### 7. Payments
Passed: initiation, amount/currency validation, idempotency keys, duplicate callback
protection (`WebhookEvent`), invalid-callback rejection, failed/pending handling,
refunds, and evidence-based success (STK query / card verify). Tests assert
callbacks never independently issue policies.

Failed/blocked: live Daraja/Flutterwave verification (no sandbox credentials) —
marked BLOCKED. No simulated external success was introduced.

### 8. Financial integrity
Passed: premium collection, gross/net premium, commission calculation/liability,
refund reversal postings, insurer balances (premium tracking), journal entries and
reconciliation helpers are traceable and consistent for premium/commission/payment
flows.

Findings (require accounting decision — not auto-fixed):
- **Claim settlement posts no journal entry** (`apps/claims/views.py:settle`): the
  workflow records `settled_amount`/`settlement_reference` without a double-entry
  posting. Needs a claims-payout/expense account in the chart of accounts.
- **Insurer settlement `settle`/`reconcile` post no journal entry**
  (`apps/finance/views.py`); `create_settlement_from_verified_payments`,
  `mark_payment_settled`, `reconcile_settlement` exist but are not wired to views.
- `premium_tracking_summary` hardcodes currency `KES` (`apps/finance/services.py`).

These are documented as blockers requiring chart-of-accounts approval, per the
"do not invent mappings" rule.

### 9. Documents & file security
Passed: uploads enforce extension/size/declared-MIME (`ValidatedFileField`); policy,
claim, vehicle, organisation and inspection documents are served through
authenticated endpoints with `Cache-Control: private, no-store` and audit logging;
raw storage URLs are hidden from serializers; media is not served directly in
production (`DEBUG=false`). Download authorisation enforced for policy, claim and
inspection; vehicle/organisation downloads are scoped via `get_queryset` (verified
cross-tenant denied with 404).

Remaining: file-content (magic-byte) inspection and private object storage are
follow-ups.

### 10. External integrations & notifications
Implemented + internally tested: M-Pesa Daraja and Flutterwave adapters, insurer
REST/webhook adapter (`GenericRESTAdapter`) with encrypted credentials, retries,
timeouts, failure logging; in-app + (opt-in) email notifications.

Not externally verified: Daraja, Flutterwave, remote AI provider (blocked on
credentials). SMS channel is a documented stub.

### 11. Infrastructure & deployment
Passed: `.env.example` documents all secrets; production guards fail closed on
insecure `DJANGO_SECRET_KEY`/wildcard `ALLOWED_HOSTS`; `DEBUG` off in Docker;
`docker-compose.yml` wires Postgres/Redis/web/worker/beat/nginx; health check
present; HSTS/cookie hardening configurable.

Flags (low): webhook signature/IP-allowlist default to off (must be set in
production); `CREDENTIAL_ENCRYPTION_KEY` falls back to `SECRET_KEY`.

---

## C. End-to-end workflow results

| # | Journey | Result |
| --- | --- | --- |
| 1 | Customer registration, email verification, login | PASSED (E2E) |
| 2 | Customer requests quote, compares offers, selects | PASSED (E2E) |
| 3 | Dealer submits customer application to insurer | PASSED (E2E) |
| 4 | Insurer reviews/approves application | PASSED (E2E) |
| 5 | Customer pays via verified payment workflow | PASSED (E2E, internal test double) |
| 6 | Authorised insurer issues policy | PASSED (E2E) |
| 7 | Customer downloads policy certificate | PASSED (E2E) |
| 8 | Customer files claim; insurer processes | PASSED (unit/integration) |
| 9 | Financial records reflect premium/commission | PASSED (finance tests) |
| 10 | Finance user views correct scoped financials | PASSED (finance tests) |
| 11 | Cross-tenant access attempts denied | PASSED (isolation tests) |
| 12 | Failed/interrupted operations leave no partial rows | PASSED (transaction tests) |

Blocked: live external gateway verification (Daraja/Flutterwave sandbox).

---

## D. Security findings

Resolved (all previously fixed and re-verified this pass):
- **High** — inspections cross-tenant leak + unguarded report/photo download.
- **High** — claim document download lacking object-level check.
- **Medium** — finance chart-of-accounts/config read exposure.
- **Medium** — platform-settings read exposure.
- **Medium** — payment refund missing claim branch.
- **Medium** — AI risk indicators tenant scoping.
- **Medium** — SSRF hostname resolution gap.
- **Low** — provider dashboard `open_quotation_requests` cross-tenant count leak.
- **Low** — messaging relationship validation.

Remaining:
- **Medium** — SSRF residual TOCTOU between DNS check and connection
  (`apps/integrations/adapters.py`); remediate with a validating opener.
- **Medium** — dealer customer-search PII breadth.
- **Low** — webhook signatures default off; `CREDENTIAL_ENCRYPTION_KEY` fallback;
  file content sniffing; KYC flag default off.

No Critical or High findings remain open.

---

## E. Financial integrity findings

- Claim settlement: no journal posting (see B.8).
- Insurer settlement `settle`/`reconcile`: no journal posting; helper functions
  unwired (see B.8).
- `premium_tracking_summary` hardcodes `KES`.
- Otherwise: premium/commission/payment/refund accounting is balanced, immutable and
  traceable; issuance posts premium-earned; commission pay posts expense/cash.

These require a chart-of-accounts decision and are documented for approval.

---

## F. Integration verification

| Integration | Status |
| --- | --- |
| M-Pesa Daraja adapter | Implemented, internally tested (callback/amount/idempotency). **Blocked** — no sandbox credentials. |
| Flutterwave card gateway | Implemented, internally tested. **Blocked** — no sandbox credentials. |
| Insurer REST/webhook adapter | Implemented, internally tested (SSRF + credential encryption). |
| Email (SMTP) | Console backend in dev; SMTP config documented. |
| SMS | Stub (no provider). |
| Remote AI provider | Implemented (OpenAI-compatible), untested externally; heuristic fallback active. |

---

## G. Test evidence

```bash
# Backend (backend/)
python manage.py check                 # System check identified no issues
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test --parallel 4     # Ran 164 tests — OK

# Frontend (frontend/)
npm run lint                           # clean
npm test -- --run                      # 9 files / 26 tests passed
npm run build                          # built in ~41s (single chunk 1.88 MB, >500 kB warning)
npm run test:e2e                       # 6 passed (1.3m)
```

E2E teardown verified: no listeners remain on `8001` or `5174` (both return
`000`), only transient `TIME_WAIT` sockets.

---

## H. Remaining work (ranked)

1. **High** — Wire claim-settlement and insurer-settlement journal entries after
   approving a chart-of-accounts mapping (claims expense/payable, settlement
   payable/bank). Blocked on business/finance approval.
2. **Medium** — SSRF DNS-rebinding TOCTOU: validating `urllib` opener.
3. **Medium** — Dealer customer-search PII: consent/exact-id constraint.
4. **Low** — Enable webhook signature/IP-allowlist in production; set
   `CREDENTIAL_ENCRYPTION_KEY`; enable `KYC_REQUIRED_FOR_POLICY_ISSUANCE`.
5. **Low** — File magic-byte content inspection + private object storage.
6. **Low** — Frontend code-splitting (bundle >500 kB).
7. **Low** — SMS channel; `premium_tracking_summary` currency derivation.
8. **Blocked** — Live Daraja/Flutterwave/remote-AI sandbox verification.

---

## I. Final readiness assessment

**INTERNAL QA READY**

Rationale:
- All automated checks pass: 164 backend tests, 26 frontend unit tests, 6 browser
  E2E journeys, clean lint, clean build, clean `manage.py check` and
  `makemigrations --check`.
- Critical and high-severity security findings are resolved; multi-tenant isolation
  is enforced and regression-tested.
- The complete motor insurance lifecycle works across layers.
- Production-readiness blockers are (a) unverified external gateways, (b) the
  claim/settlement accounting postings that require an approved chart-of-accounts
  mapping, and (c) remaining low/medium hardening items. These prevent
  PRODUCTION READY / PRODUCTION CANDIDATE; the internal surface is otherwise
  consistent and verified.

Not declared PRODUCTION READY — external integration verification and two financial
accounting postings remain outstanding.
