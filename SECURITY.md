# INSURECONNECT — Security Review

Security posture and known findings for the INSURECONNECT platform. Findings are
ranked by severity. Verified fixes in this pass are marked **Resolved**; remaining
items are marked with an exact remediation note. No security control was disabled
to make tests pass.

## Resolved (this pass)

| Severity | Area | Issue | Fix |
| --- | --- | --- | --- |
| High | Inspections | Unassigned inspections (`organization_id IS NULL`) were listable by any provider/dealer/agent, and report/photo downloads had no object-level check. | Removed the unassigned fallback in `get_queryset`; added `_require_download` authorization to `download_report`/`download_damage_photo` and inspector-only `ai_assist`. |
| High | Claims | Claim document download relied only on queryset scoping; the upload path checked more strictly. | `download_document` now mirrors the upload check (claimant / insurer org / platform admin). |
| Medium | Finance | Chart of accounts, exchange rates, currency config and platform fees were readable by any authenticated user. | Those four viewsets are now `IsPlatformAdmin`. |
| Medium | Analytics | `PlatformSettingView` returned all platform settings to any authenticated user. | `GET`/`PUT` now require `IsPlatformAdmin`. |
| Medium | Payments | `refund` omitted the claim branch, denying providers refund of claim/inspection payments they own. | `refund` now resolves the insurer from `claim`-linked payments. |
| Medium | AI | `suspicious_payment_indicators` scoped to the calling user rather than their insurers. | Scoping now uses `insurer_ids`. |
| Medium | Integrations (SSRF) | A hostname resolving to a private/reserved IP passed validation (literal-IP only). | `outbound_url_error` now resolves hostnames and rejects non-global addresses. |
| Medium | Integrations (SSRF TOCTOU) | Hostname re-resolved at connect time after validation (DNS rebinding). | `_resolve_public_address` + validating HTTP/HTTPS connection pin the validated IP (SNI preserved) and redirects are not followed. |
| High | Webhooks | M-Pesa/Flutterwave callbacks accepted unsigned/unallowlisted requests when credentials were unset. | `_ip_allowed`/`_signature_valid` now fail closed in production; signatures/allowlists enforced when configured. |
| Medium | PII | Dealer customer search returned full email + phone to any dealership. | Requires an active partnership; phone returned only with customer consent. |
| Medium | Messaging | Any user could message an arbitrary recipient/claim. | `perform_create` requires both parties to be participants of the referenced claim. |
| Medium | File content | Executable/script payloads could be uploaded with an allowed extension. | `ValidatedFileField` rejects known executable magic bytes. |

## Remaining findings

### Medium

- None open.

### Low / Informational

- **`CREDENTIAL_ENCRYPTION_KEY` falls back to `SECRET_KEY`** (`apps/integrations/crypto.py`).
  Set `CREDENTIAL_ENCRYPTION_KEY` explicitly in production.
- **File content inspection (extension↔magic consistency)** is a follow-up
  (`apps/common/fields.py`): executables are rejected, but a full
  extension-vs-content match is not enforced to avoid false rejections.
- **`KYC_REQUIRED_FOR_POLICY_ISSUANCE`** defaults to `False`; enable in production.
- **`CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS`** default to dev origins; set
  production origins via `.env`.

## General posture

- JWT access/refresh with rotation + blacklisting and token-version invalidation
  (`apps/accounts/tokens.py`).
- TOTP two-factor authentication, account lockout after repeated failed logins.
- Tenant isolation via `apps/common/scoping.py` and per-app object-level checks;
  document downloads use `protected_file_response` (`Cache-Control: private,
  no-store`) and are audit-logged.
- Failed-production guards in `config/settings.py`: insecure `DJANGO_SECRET_KEY` or
  wildcard `DJANGO_ALLOWED_HOSTS` raise `ImproperlyConfigured` when `DEBUG` is off.
- Webhooks: M-Pesa STK callbacks are idempotent and always re-verified against the
  Daraja STK query; Flutterwave card callbacks are re-verified via `verify()`.
- Rate limiting on auth, AI, dealer search and webhook endpoints.

## Verifying

```bash
# Backend (from backend/)
python manage.py test --parallel 4          # 172 tests

# Frontend (from frontend/)
npm run lint
npm test -- --run
npm run build
npm run test:e2e                             # isolated E2E database, 6 tests
```
