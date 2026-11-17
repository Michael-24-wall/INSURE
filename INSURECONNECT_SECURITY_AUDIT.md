# INSURECONNECT — Security Audit (Release 1.0)

Date: 2026-11-17
Companion to `SECURITY.md` (findings history). This is the current state.

## Conclusion

**No open Critical or High findings.** All critical/high issues found during the
programme were fixed and regression-tested (see `SECURITY.md`).

## Resolved (IMPLEMENTED AND VERIFIED)

| Area | Fix | Evidence |
| --- | --- | --- |
| Inspections cross-tenant leak | Removed unassigned fallback; `_require_download` on report/photo; inspector-only AI | `apps/inspections/tests.py` |
| Claim document download | Explicit claimant/insurer-org/admin check | `apps/claims/tests.py` |
| Finance read exposure | Chart/rates/currency/fees → `IsPlatformAdmin` | `apps/finance/tests.py` |
| Platform settings read | `IsPlatformAdmin` GET/PUT | `apps/analytics/tests.py` |
| Payment refund claim branch | Insurer resolution for claim-linked payments | `apps/payments/views.py` |
| AI risk scoping | `insurer_ids` scoping | `apps/ai_services/tests.py` |
| SSRF | Literal IP + DNS-resolution + validating pinned connection + no-redirect | `apps/integrations/tests.py` |
| Webhook fail-closed | M-Pesa allowlist / Flutterwave hash required when `DEBUG=false` | `apps/payments/tests.py` |
| Dealer PII | Partnership required; phone only with consent | `apps/business_network/tests.py` |
| Claim messaging | Participant/recipient authorization | `apps/notifications/tests.py` |
| File content | Executable magic-byte rejection | `apps/vehicles/tests.py` |

## Remaining (Low / Informational — do NOT block staging)

- `CREDENTIAL_ENCRYPTION_KEY` falls back to `SECRET_KEY` if unset → set explicitly.
- `KYC_REQUIRED_FOR_POLICY_ISSUANCE` defaults off → enable in production.
- CORS/CSRF origins default to dev → set production origins.
- Full extension↔magic file consistency (follow-up).
- SSRF egress-allowlist proxy (optional defence-in-depth).

## Verified security boundaries (TESTED AND PASSED)

- JWT rotation/blacklist/versioning, TOTP 2FA, account lockout, login rate limit.
- Tenant isolation across claims/vehicles/inspections/finance/documents/organisations.
- Object-level authorization (IDOR) on all sensitive endpoints.
- Payment: callbacks never issue policies; amount/currency validated; idempotent.
- Document downloads: authenticated, `private, no-store`, no public URLs.
- Audit logging on all sensitive state changes.

## Actions required from you

None blocking for staging. Production requires the Low items above to be configured
(set `CREDENTIAL_ENCRYPTION_KEY`, KYC flag, production CORS/CSRF origins).
