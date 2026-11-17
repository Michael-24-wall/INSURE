# INSURECONNECT — Independent Staging Acceptance & Regression Verification

Date: 2026-11-16
Method: independent code inspection + fresh test execution + adversarial tests.
No reliance on the previous readiness report — every fix was re-verified against
the implementation and the live test suite.

---

## 1. Code references for each verified fix

| # | Fix | Verified location | Verdict |
| --- | --- | --- | --- |
| 1 | M-Pesa webhook fail-closed + IP allowlist | `apps/payments/views.py:294-314` (`MpesaCallbackView._ip_allowed`) | Verified |
| 2 | Flutterwave signature fail-closed | `apps/payments/views.py:324-349` (`CardCallbackView._signature_valid`, `hmac.compare_digest`) | Verified |
| 3 | Callback replay/duplicate protection | `apps/payments/services.py:268-335` (`WebhookEvent` idempotency), `handle_stk_callback`, `verify_card_payment` | Verified |
| 4 | SSRF DNS resolution + pinned connections | `apps/integrations/adapters.py:62-88` (`_resolve_public_address`), `:90-105` (`_ValidatingHTTP/HTTPSConnection.connect`) | Verified |
| 5 | Redirect restriction | `apps/integrations/adapters.py:108-124` (`_NoRedirectHandler`, `_validating_opener`) | **Fixed this pass** — see finding F1 |
| 6 | Dealer customer-search partnership + PII/consent | `apps/business_network/views.py:480-534` (`DealerCustomerSearchView`) | Verified |
| 7 | Premium tracking currency derivation | `apps/finance/services.py:453-470`, `config/settings.py` `DEFAULT_CURRENCY` | Verified |
| 8 | File magic-byte validation | `apps/common/fields.py:24-44` (`DANGEROUS_MAGIC`, `_has_dangerous_magic`), `:86-87` | Verified |
| 9 | Frontend lazy loading / code splitting | `vite.config.js` (`manualChunks`), `App.jsx` (lazy `AdminDashboard`), `InspectionDetail.jsx` (lazy `VehicleScene`) | Verified |
| 10 | Claim-message participant + recipient authorisation | `apps/notifications/views.py:51-68` (`_is_claim_participant`, `perform_create`) | Verified |

### Finding F1 (fixed during this verification)
The prior report claimed "redirects are not followed". Independent inspection
showed `urllib.request.build_opener` silently re-adds the default
`HTTPRedirectHandler`, so redirects *were* still followed (though re-validated at
connection time). This pass added `_NoRedirectHandler` and re-verified the opener
now rejects redirects deterministically. This is the one genuine defect found by
independent verification; all other claims held.

---

## 2. Exact test commands and results

```bash
# Backend (backend/)
python manage.py check                 # System check identified no issues
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test --parallel 4     # Ran 174 tests — OK

# Frontend (frontend/)
npm run lint                           # clean
npm test -- --run                      # 9 files / 26 tests passed
npm run build                          # built; code-split chunks emitted
npm run test:e2e                       # 6 passed (1.5m)
```

Bundle evidence: initial entry `index` **352.78 KB** (gzip 77.52 KB); `three`
844 KB and `charts` 423 KB are deferred; `react` 165 KB + `query` 74 KB shared.

---

## 3. Adversarial test results

| Adversarial attempt | Result | Evidence |
| --- | --- | --- |
| Access another organisation's records | BLOCKED (404/403) | claims/vehicles/inspections/finance/documents/organizations isolation tests |
| Access unrelated claims | BLOCKED | `apps/claims/tests.py` tenant-isolation + officer tests |
| Access unrelated claim messages | BLOCKED | `apps/notifications/tests.py` (non-participant 403; unrelated reader 404) |
| Forged webhook callback | BLOCKED | `apps/payments/tests.py` fail-closed + signature tests |
| Missing webhook signature | BLOCKED (403) | `test_card_callback_fails_closed_without_signature_config` |
| Invalid webhook signature | BLOCKED (403) | `test_card_callback_rejects_invalid_or_missing_signature` |
| Replayed payment callback | Idempotent (no double-post) | `test_card_callback_accepts_valid_signature_and_is_idempotent`, STK `WebhookEvent` guard |
| SSRF private IP (literal) | BLOCKED | `test_private_and_local_urls_rejected` |
| SSRF DNS rebinding (resolved private) | BLOCKED | `test_hostname_resolving_to_private_ip_is_blocked`, `test_connection_guard_rejects_private_resolved_ip` |
| SSRF via redirect | BLOCKED | `test_opener_rejects_redirects` |
| Malicious file (executable magic) | BLOCKED (400) | `test_executable_content_is_rejected` |
| Unauthorised document download | BLOCKED (401/404) | vehicle/claim/inspection document-access tests |
| Customer search without active partnership | BLOCKED (empty) | `test_search_requires_active_partnership` |
| Phone exposure without consent | BLOCKED (empty string) | `test_phone_returned_only_with_consent` |

All adversarial attempts returned the expected denial; none resulted in data
exposure. All testing used isolated test databases / `e2e.sqlite3` only.

---

## 4. Unresolved vulnerabilities

- **Medium (residual SSRF note)**: outbound hosts are resolved and validated, and
  redirects are now rejected. The connection still uses `socket.create_connection`
  to a validated IP; a dedicated egress-allowlist proxy remains an optional
  defence-in-depth layer (not required for staging).
- **Low**: `CREDENTIAL_ENCRYPTION_KEY` falls back to `SECRET_KEY` if unset (staging
  env sets it explicitly). File extension↔magic consistency is not fully enforced
  (executables are rejected). KYC flag and webhook verification are enabled via the
  staging env (fail-closed otherwise).

No Critical or High findings remain.

---

## 5. Business & financial verification

- Quotation → application → underwriting → payment → verified issuance → claims
  continue to pass (174 backend tests + 6 E2E journeys).
- Premium/commission/payment/refund ledger postings are balanced, immutable and
  currency-consistent.
- **Proposed (NOT implemented — pending accounting approval)**:
  - Claim settlement: add `8000` "Claims Payable" (liability); on settle Debit
    `8000` / Credit `1000` Bank/Cash. (Alternative: memo-only.)
  - Insurer settlement: add `8100` "Insurer Settlements Payable"; on instruct
    Debit `3000` Premium Revenue / Credit `8100`; on settle Debit `8100` /
    Credit `1000`. Reconcile = status only.
  These mappings require chart-of-accounts sign-off before any code is written.

---

## 6. Staging configuration checklist

Artifacts created: `backend/.env.staging.example`, `docker-compose.staging.yml`.

- [x] Separate database (`autoinssure_staging`) and separate volumes (project
      `autoinsure-staging`).
- [x] Separate credentials (`STAGING_SECRET_KEY`, `STAGING_DB_PASSWORD`).
- [x] Production-like settings (`DJANGO_DEBUG=False`, explicit `ALLOWED_HOSTS`).
- [x] HTTPS (edge TLS; `SECURE_SSL_REDIRECT/SESSION_COOKIE_SECURE/HSTS` set).
- [x] Explicit CORS/CSRF origins.
- [x] Explicit `CREDENTIAL_ENCRYPTION_KEY`.
- [x] `KYC_REQUIRED_FOR_POLICY_ISSUANCE=True`.
- [x] Webhook verification configured (`M_PESA_ALLOWED_IPS`, `FLW_WEBHOOK_HASH`) —
      fail-closed otherwise.
- [x] Sandbox-only gateway credentials; no live payment keys.
- [x] No production customer data (seed synthetic data only).

Staging bring-up (do NOT run without approval):

```bash
cp backend/.env.staging.example backend/.env   # fill placeholders
STAGING_SECRET_KEY=<secret> STAGING_DB_PASSWORD=<secret> \
  docker compose -p autoinsure-staging -f docker-compose.staging.yml up --build
docker compose -p autoinsure-staging exec web python manage.py migrate
docker compose -p autoinsure-staging exec web python manage.py seed_e2e  # or synthetic seed
```

---

## 7. Financial approval requirements

The claim-settlement and insurer-settlement debit/credit mappings (section 5) are
the only pending approvals. They are NOT required to start staging and do not
affect the correctness of existing postings, but must be approved before
production.

---

## 8. Final staging acceptance decision

**ACCEPTED FOR CONTROLLED STAGING**

Basis:
- All ten hardening fixes were independently re-verified in code; the single
  inaccuracy found (redirect handling) was corrected and regression-tested.
- Full suite is green: 174 backend tests, 26 frontend tests, 6 E2E journeys, clean
  lint/build/check/migrations.
- Every adversarial attempt was denied with no data exposure.
- A staging-only configuration (separate DB, credentials, HTTPS, fail-closed
  webhooks, KYC, sandbox-only) is prepared and not deployed.

Conditions:
- Staging must remain non-production: synthetic data only, sandbox gateway
  credentials only.
- The two financial accounting mappings require approval before production.
- Live gateway sandbox verification is still outstanding.

Not production-ready. No deployment, commit, or push was performed.
