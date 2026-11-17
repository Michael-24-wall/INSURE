# INSURECONNECT — Release 1.0 Staging Readiness

Date: 2026-11-16
Prior state: INTERNAL QA READY (multi-layer validation complete).
Objective: harden the outstanding items and determine whether the system is ready
for a controlled staging environment.

---

## 1. Findings and root causes

| # | Area | Finding | Root cause |
| --- | --- | --- | --- |
| 1 | Webhooks | M-Pesa callback accepted any source when `M_PESA_ALLOWED_IPS` was empty; Flutterwave callback accepted any `verif-hash` when `FLW_WEBHOOK_HASH` was empty. | `_ip_allowed`/`_signature_valid` returned `True` as a fallback when the credential was unset. |
| 2 | SSRF | `outbound_url_error` validated the hostname at check time but `urllib.request.urlopen` re-resolved at connect time. | No pinned resolution between validation and connection (DNS-rebinding TOCTOU). |
| 3 | PII | Dealer customer search returned full `email` + `phone` to any dealership, with no relationship check. | `DealerCustomerSearchView` did not require an active partnership or consent. |
| 4 | Claims accounting | Claim `settle` recorded `settled_amount`/`settlement_reference` with no journal entry. | No claims-payout account existed; accounting decision pending. |
| 5 | Settlement accounting | `Settlement.settle`/`reconcile` updated status/amounts with no journal entry; helper functions unwired. | No settlement-payable account; accounting decision pending. |
| 6 | Currency | `premium_tracking_summary` hardcoded `"KES"`. | Assumption baked into the summary; `Policy` has no currency field (currency lives on `Payment`). |
| 7 | Documents | Uploads enforced extension/size/declared-MIME only; no content inspection; files on local disk. | `ValidatedFileField` had no magic-byte check; `FileSystemStorage` only. |
| 8 | Gateways | Daraja/Flutterwave not verified against live sandbox. | No sandbox credentials available. |
| 9 | SMS | `SmsChannel.send` is a documented no-op. | No SMS provider configured. |
| 10 | Bundle | Single 1.88 MB JS bundle; `three` and `recharts` loaded eagerly. | No `manualChunks`/lazy loading. |

---

## 2. Proposed corrections (with accounting approvals separated)

Items 4 and 5 require chart-of-accounts decisions and are **not implemented** — see
"Outstanding approvals" for the proposal. All other items were implemented as
described below.

---

## 3. Changes implemented

### 3.1 Webhook fail-closed (item 1)
`apps/payments/views.py`:
- `MpesaCallbackView._ip_allowed` now returns `False` when `M_PESA_ALLOWED_IPS` is
  empty and `DEBUG` is off (logs a rejection); it still validates against the
  allowlist (and `X-Forwarded-For` only when trusted) when configured.
- `CardCallbackView._signature_valid` now returns `False` when `FLW_WEBHOOK_HASH`
  is empty and `DEBUG` is off; when set, it uses constant-time `hmac.compare_digest`.

Behaviour: production rejects unsigned/unallowlisted callbacks; the authoritative
re-verification (Daraja STK query / Flutterwave `verify`) remains intact.

Tests added (`apps/payments/tests.py`): fail-closed for M-Pesa (no allowlist) and
Flutterwave (no hash), in addition to the existing valid/invalid/replay/duplicate
signature and IP-allowlist tests. Test callbacks now explicitly configure
`M_PESA_ALLOWED_IPS=["127.0.0.1"]`.

### 3.2 SSRF TOCTOU (item 2)
`apps/integrations/adapters.py`:
- `_resolve_public_address(host, port)` resolves once and rejects if **any**
  resolved address is not globally routable.
- `_ValidatingHTTPConnection` / `_ValidatingHTTPSConnection` connect to the validated
  IP while preserving TLS SNI/certificate verification against the original host.
- `_validating_opener()` omits the default redirect handler so redirects to an
  internal address are not silently followed.
- `GenericRESTAdapter.request` now uses the validating opener; connection-time
  validation failures are recorded in `IntegrationLog` and re-raised.

Tests added (`apps/integrations/tests.py`): private resolved IP rejected, public
resolved IP accepted at the connection guard.

### 3.3 Dealer customer-search PII minimisation (item 3)
`apps/business_network/views.py` `DealerCustomerSearchView`:
- Requires an **active partnership** (`Partnership.status == ACTIVE`) before any
  result is returned (platform admin exempt).
- Returns `phone` only when the customer has **granted consent** to the dealership
  (`CustomerConsent.status == GRANTED`); otherwise `phone` is empty. `email` is
  retained because it is the lookup identifier the dealer needs to initiate a
  quotation (which then records consent).

Tests added (`apps/business_network/tests.py`): search requires active partnership;
phone returned only with consent; email returned without consent.

### 3.4 Currency correctness (item 6)
`apps/finance/services.py` `premium_tracking_summary` now derives currency from the
policy's succeeded premium `Payment.currency` and only falls back to a new
`settings.DEFAULT_CURRENCY` (default `KES`) when no payment exists. Added
`DEFAULT_CURRENCY` to `config/settings.py` and `backend/.env.example`.

Test added (`apps/finance/tests.py`): USD payment surfaces `currency == "USD"`.

### 3.5 File-content inspection (item 7)
`apps/common/fields.py` `ValidatedFileField` now rejects uploads whose leading bytes
match a known executable/script signature (ELF, PE/MZ, Mach-O, shebang) regardless
of extension or declared MIME. Full extension↔magic consistency is a documented
follow-up (avoiding false rejection of valid documents).

Test added (`apps/vehicles/tests.py`): executable payload rejected with `400`.

### 3.6 Frontend bundle code splitting (item 10)
`frontend/vite.config.js` adds `manualChunks` for `react`, `query`, `charts`,
`three`. `VehicleScene` (Three.js) is lazy-loaded in `InspectionDetail.jsx` and
`AdminDashboard` (recharts) is lazy-loaded in `App.jsx` behind a `Suspense`
fallback.

Result: initial main bundle reduced from **1.88 MB** to **~352 KB** (`index`) plus
`react` 165 KB and `query` 74 KB; `three` (844 KB) and `charts` (423 KB) are now
deferred to their respective routes.

### 3.7 Environment documentation (items 1, 6)
`backend/.env.example` now documents `FLW_WEBHOOK_HASH` and `DEFAULT_CURRENCY`, and
marks `M_PESA_ALLOWED_IPS` / `FLW_WEBHOOK_HASH` as required in production
(fail-closed).

---

## 4. Tests and evidence

```bash
# Backend (backend/)
python manage.py check                 # System check identified no issues
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test --parallel 4     # Ran 172 tests — OK

# Frontend (frontend/)
npm run lint                           # clean
npm test -- --run                      # 9 files / 26 tests passed
npm run build                          # built; code-split chunks emitted
npm run test:e2e                       # 6 passed (59.6s)
```

Targeted suites exercised this pass: payments (webhook fail-closed), integrations
(SSRF connection guard), business_network (PII), finance (currency), vehicles
(file content), analytics/notifications (prior pass). E2E teardown verified: no
listeners remain on `8001`/`5174`.

No production data, live credentials or production transactions were used; all
changes are additive and isolated.

---

## 5. Outstanding approvals (financial accounting)

Not implemented — require chart-of-accounts / business approval. Current chart of
accounts (single-currency KES, seeded in `finance/migrations/0002_*`):

| Code | Name | Type |
| --- | --- | --- |
| 1000 | Bank / Cash | asset |
| 2000 | Premiums Collected - Unearned | liability |
| 3000 | Premium Revenue | revenue |
| 4000 | Commission Expense | expense |
| 5000 | Commission Payable | liability |
| 6000 | Platform Revenue | revenue |
| 7000 | Platform Fee Receivable | asset |

`JournalEntry` already carries `claim` and `settlement` FKs, so the models are ready
for these postings once accounts are agreed.

### 5.1 Claim settlement journal posting
Proposal A (recommended): add `8000` "Claims Payable" (liability) — treat collected
premiums as held in trust for the insurer. On `Claim.settle`:
- Debit `8000` Claims Payable, Credit `1000` Bank/Cash for the settled amount.

Proposal B (alternative, no GL): keep settlement as a memo on the claim because
claim payouts are the insurer's obligation and the platform does not disburse.

Decision required: whether the platform holds insurer funds and therefore records
claim payouts on its own ledger, and the exact account code/name.

### 5.2 Insurer settlement journal posting
Proposal: add `8100` "Insurer Settlements Payable" (liability). On `Settlement`
creation/`instruct`: Debit `3000` Premium Revenue (insurer net share), Credit `8100`
Insurer Settlements Payable. On `settle`: Debit `8100`, Credit `1000` Bank/Cash.
`reconcile` records no new posting (status only).

Decision required: confirm the revenue-reduction-vs-payable split and the exact
account codes; then wire `create_settlement_from_verified_payments`,
`mark_payment_settled` and `reconcile_settlement`.

---

## 6. External dependencies

| Dependency | Status |
| --- | --- |
| M-Pesa Daraja sandbox | Implemented + internally tested; **blocked** on sandbox credentials. |
| Flutterwave sandbox | Implemented + internally tested; **blocked** on sandbox credentials. |
| SMS provider | **Blocked** — no provider; channel is a documented stub. |
| Private object storage (S3-compatible) | Proposed; **blocked** on bucket/credentials (see 7). |
| Remote AI provider (vision/OCR) | Optional; heuristic fallback active. |

---

## 7. Staging deployment prerequisites

1. **Secrets**: set `DJANGO_SECRET_KEY` (strong), `CREDENTIAL_ENCRYPTION_KEY`,
   `DJANGO_DEBUG=False`, explicit `DJANGO_ALLOWED_HOSTS`, production
   `CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS`.
2. **Webhooks**: set `M_PESA_ALLOWED_IPS` (Safaricom egress ranges) and
   `FLW_WEBHOOK_HASH` (otherwise callbacks are rejected — fail-closed).
3. **Database**: PostgreSQL via `DATABASE_URL`; run `manage.py migrate`.
4. **Storage**: provision private object storage (S3-compatible) and set
   `DEFAULT_FILE_STORAGE`/`MEDIA_ROOT`; keep authenticated streaming downloads.
5. **Cache/tasks**: Redis (`REDIS_URL`/`CACHE_URL`/`CELERY_BROKER_URL`) and
   `CELERY_TASK_ALWAYS_EAGER=False`; run worker + beat.
6. **TLS**: terminate HTTPS at the edge; set `SECURE_SSL_REDIRECT=True`,
   `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, HSTS values.
7. **Static**: `collectstatic` (WhiteNoise) and the nginx SPA build (`docker compose`).
8. **Private storage proposal (item 7)**: adopt `django-storages` S3 backend with a
   private bucket; serve all documents through the existing authenticated
   `protected_file_response` stream (no public URLs). This is a dependency addition
   requiring justification and credentials — not installed in this pass.

---

## 8. Remaining production blockers

1. **Financial accounting approvals** — claim and insurer settlement journal
   postings (section 5). Required before production, not for staging.
2. **Live gateway verification** — Daraja/Flutterwave sandbox.
3. **Private object storage** — infrastructure + credentials.
4. **SMS provider** — optional channel (in-app + email are sufficient for staging).
5. Minor: full extension↔magic file consistency, `premium_tracking` fallback
   currency validation per deployment.

---

## 9. Final readiness

**READY FOR STAGING** — for the purpose of controlled, non-production staging.

Rationale:
- All automated checks pass (172 backend tests, 26 frontend tests, 6 E2E journeys,
  clean lint/build/check/migrations).
- Webhook fail-closed, SSRF TOCTOU, dealer PII minimisation, currency correctness,
  file-content inspection and bundle code-splitting are implemented and tested.
- The two financial-accounting postings are the only implemented-code gaps; they
  require chart-of-accounts approval and can be deferred past staging because they
  do not affect the correctness of existing premium/commission/payment/refund
  postings.
- Staging is explicitly NOT production: live gateway verification and private object
  storage remain outstanding and must be completed before any production cutover.

**Not PRODUCTION READY.** Staging may proceed; production readiness additionally
requires the financial-accounting approvals and live gateway/object-storage
verification above.
