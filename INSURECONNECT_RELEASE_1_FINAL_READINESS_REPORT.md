# INSURECONNECT — Release 1.0 Final Readiness & Staging Preparation

Date: 2026-11-17
Prior state: full transactional acceptance passed
(`INSURECONNECT_FULL_TRANSACTIONAL_ACCEPTANCE_REPORT.md`).

This report consolidates the verified state and the remaining conditions for a
controlled staging release. No production data, live credentials or real-money
transactions are involved.

---

## 1. Verified capabilities

All of the following were verified end-to-end (unit, integration, real-Chrome
browser, and direct database inspection):

- **Registration & authentication** — customer/provider/dealer registration, email
  verification, login, logout, session persistence, JWT rotation + blacklist +
  token-version invalidation, TOTP 2FA, account lockout, login rate limiting (429).
- **Organisation membership & permissions** — role-based access, org verification,
  tenant isolation (cross-tenant reads/IDs rejected with 403/404).
- **Customer dashboard** — real backend data (vehicles/quotes/applications/policies/
  claims/payments), marketplace, category discovery (motor "Live", nine lines
  "Expanding").
- **Insurer dashboard** — products, quote requests, applications, underwriting,
  payments, policies, finance, business network.
- **Quotation → application → underwriting** — request, comparison, select, submit,
  approve/reject/info flows with valid state guards.
- **Payment verification** — initiate (bank path; card/STK fail-closed without
  credentials), manual verify, idempotency, duplicate-callback protection, no
  auto-success from callbacks.
- **Policy issuance** — verified-payment-gated, authorised-only, duplicate-issuance
  prevention, certificate generation + authenticated download.
- **Claims** — submit, evidence upload, request-info/respond, approve/reject, status
  history, participant authorisation.
- **Premium & commission accounting** — balanced double-entry ledger, refund
  reversals, currency correctness, policy↔payment linkage.
- **Cross-tenant security** — isolation, IDOR, document download, webhook fail-closed,
  SSRF (literal + DNS-rebinding + redirect), PII minimisation, file magic-byte check.

## 2. Final regression evidence

```bash
# Backend (backend/)
python manage.py check                         # clean
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test --parallel 4             # 174 tests OK

# Frontend (frontend/)
npm run lint                                   # clean
npm test -- --run                              # 26 tests passed
npm run build                                  # passed (code-split; one chunk >500 kB, non-blocking)
npm run test:e2e                               # 6 passed (1.1m)
```

The complete customer→policy→claim transaction was re-verified in real Chrome
(previous report) and remains green under the full suite.

## 3. Remaining blockers

| # | Blocker | Severity | Blocked by |
| --- | --- | --- | --- |
| 1 | Live Daraja + Flutterwave sandbox verification | High | External sandbox credentials |
| 2 | Claim-settlement journal posting | Medium (accounting) | Chart-of-accounts approval |
| 3 | Insurer-settlement journal posting | Medium (accounting) | Chart-of-accounts approval |
| 4 | Private object storage | Medium (infra) | Object-storage credentials |
| 5 | SMS notifications | Low | Provider configuration |
| 6 | Full extension↔magic file-content match | Low | (optional hardening) |

## 4. External credentials required

Documented in `PAYMENT_GATEWAY_SANDBOX.md`. Summary:

- **M-Pesa Daraja (sandbox):** `M_PESA_CONSUMER_KEY`, `M_PESA_CONSUMER_SECRET`,
  `M_PESA_SHORTCODE`, `M_PESA_PASSKEY`, `M_PESA_ENV=sandbox`, public HTTPS
  `M_PESA_CALLBACK_URL` (→ `/api/v1/payments/mpesa/callback/`), and
  `M_PESA_ALLOWED_IPS` (Safaricom egress ranges). STK query is the authoritative
  confirmation; callbacks are idempotent via `WebhookEvent`.
- **Flutterwave (sandbox):** `FLW_SECRET_KEY`, `FLW_PUBLIC_KEY`, `FLW_ENV=sandbox`,
  `FLW_WEBHOOK_HASH` (constant-time `verif-hash` check), `CARD_REDIRECT_URL`.
  `verify_by_reference` is authoritative; webhooks are idempotent.
- **Fail-closed:** with `DEBUG=false`, missing `M_PESA_ALLOWED_IPS` /
  `FLW_WEBHOOK_HASH` reject all callbacks.

These integrations are **implemented and internally tested but not externally
verified** — do not report them as operational until sandbox tests pass.

## 5. Accounting approvals required (exact proposals — NOT implemented)

Current chart of accounts (single currency KES):
`1000` Bank/Cash, `2000` Premiums Collected-Unearned, `3000` Premium Revenue,
`4000` Commission Expense, `5000` Commission Payable, `6000` Platform Revenue,
`7000` Platform Fee Receivable. `JournalEntry` already carries `claim` and
`settlement` foreign keys.

**Claim settlement** (requires one new account):

| Option | New account | On `Claim.settle` (amount A) |
| --- | --- | --- |
| A — trust/agency (recommended) | `8100` Claims Payable (liability) | Debit `8100` A · Credit `1000` A |
| B — expense model | `8200` Claims Expense (expense) | Debit `8200` A · Credit `1000` A |

**Insurer settlement** (requires one new account):

| Step | Option A (trust/agency, recommended) | Option B (revenue model) |
| --- | --- | --- |
| On settlement `instruct`/creation | Debit `3000` A · Credit `8000` Insurer Settlements Payable A | (no entry) |
| On `settle` (funds remitted) | Debit `8000` A · Credit `1000` A | Debit `3000` A · Credit `1000` A |

`reconcile` is a status-only step (no posting). Until one mapping is approved and
implemented, claim/insurer settlement must be reported as **"recorded, journal
posting pending"** — never as financially complete.

## 6. Security requirements

- **Private object storage (proposal, not implemented):** adopt `django-storages`
  S3 backend with a **private** bucket; serve every document through the existing
  authenticated `protected_file_response` stream (`Cache-Control: private, no-store`,
  `X-Content-Type-Options: nosniff`). Never expose public storage URLs or signed
  URLs for confidential documents.
- **File-content validation:** already rejects executable magic bytes
  (ELF/PE/Mach-O/shebang) in `apps/common/fields.py`. Full extension↔magic
  consistency is a documented follow-up (avoiding false rejections).
- **Upload/download authorization:** object-level checks on all document endpoints
  (policy, claim, vehicle, organisation, inspection); media not served directly in
  production. Verified by 174 backend tests + real-browser negative tests.

## 7. Deployment prerequisites (staging checklist)

Prepared artifacts: `backend/.env.staging.example`, `docker-compose.staging.yml`.

- [ ] Separate staging database (`autoinssure_staging`) + separate volumes/project.
- [ ] Secrets: `DJANGO_SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY`,
      `STAGING_DB_PASSWORD` (no real secrets committed).
- [ ] `DJANGO_DEBUG=False`, explicit `DJANGO_ALLOWED_HOSTS`.
- [ ] HTTPS at the edge; `SECURE_SSL_REDIRECT`/`SESSION_COOKIE_SECURE`/
      `CSRF_COOKIE_SECURE`/HSTS on.
- [ ] Explicit `CORS_ALLOWED_ORIGINS` + `CSRF_TRUSTED_ORIGINS`.
- [ ] `KYC_REQUIRED_FOR_POLICY_ISSUANCE=True`.
- [ ] Webhook verification: `M_PESA_ALLOWED_IPS` + `FLW_WEBHOOK_HASH` (fail-closed).
- [ ] Private media storage (S3) + authenticated download.
- [ ] Run `manage.py migrate`; `collectstatic`.
- [ ] Sandbox-only gateway credentials; no live payment keys.
- [ ] Seed synthetic/test data only — never production customer data.
- [ ] Logging (request-id structured logging), error reporting (optional Sentry),
      health checks (`/health/`).
- [ ] Backup/restore procedure documented for `staging_postgres_data` volume.

## 8. Final staging recommendation

**READY FOR STAGING** — for a controlled, non-production staging environment.

Rationale:
- All automated checks pass (174 backend, 26 frontend, 6 E2E, clean
  lint/build/check/migrations) and the full customer→policy→claim transaction is
  verified in real Chrome with correct backend records.
- Security hardening (webhook fail-closed, SSRF, PII minimisation, file-content,
  tenant isolation) is implemented and regression-tested.
- Staging configuration (separate DB, secrets, HTTPS, KYC, webhook verification) is
  prepared but not deployed.

**NOT PRODUCTION READY.** Production additionally requires: (1) live Daraja/
Flutterwave sandbox verification, (2) approved and implemented claim- and
insurer-settlement journal postings, and (3) private object storage.

No commit, push, or deployment was performed.
