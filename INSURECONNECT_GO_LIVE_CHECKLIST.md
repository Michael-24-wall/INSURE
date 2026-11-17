# INSURECONNECT — Go-Live Checklist (Release 1.0)

Date: 2026-11-17

Legend: ✅ done · ⚠️ partial/blocked · ❌ not done

## Gate 1 — Engineering ✅

- [x] Backend tests pass (174).
- [x] Frontend tests + lint + build pass (26 / clean / code-split).
- [x] Browser E2E passes (6).
- [x] `manage.py check` + `makemigrations --check` clean.
- [x] No Critical/High security findings.
- [x] No unresolved data-integrity issues.

## Gate 2 — Payment ⚠️ BLOCKED BY CREDENTIALS

- [x] Adapters implemented + fail-closed + idempotent (internal tests pass).
- [ ] Daraja sandbox verified (needs credentials).
- [ ] Flutterwave sandbox verified (needs credentials).
- [ ] Webhook validation verified live.
- [ ] Reconciliation verified against real sandbox records.
- [ ] Live production activation separately approved.

## Gate 3 — Accounting ⚠️ BLOCKED BY APPROVAL

- [x] Premium/commission/refund ledger implemented + verified.
- [x] Claim-settlement + insurer-settlement mappings prepared.
- [ ] Accounting model approved (Option A recommended).
- [ ] Settlement journal postings implemented + tested.
- [ ] Reconciliation verified.

## Gate 4 — Data security ⚠️ PARTIAL

- [x] Authenticated downloads + object-level authorization (verified).
- [x] Tenant isolation (verified).
- [ ] Private object storage implemented (needs credentials + dependency approval).
- [ ] Backup/restore rehearsal passed.

## Gate 5 — Operations ⚠️ PARTIAL

- [x] Production configuration prepared (`docker-compose`, `.env.staging.example`, runbook).
- [x] Structured logs + request IDs + optional Sentry configured.
- [x] Health checks + Celery beat scheduled jobs.
- [ ] Monitoring/alerting configured (external).
- [ ] Deployment + rollback plan rehearsed.
- [ ] Incident/recovery procedures finalised.

## Gate 6 — Business & compliance ❌ REQUIRES EXTERNAL CONFIRMATION

- [ ] Launch insurance categories confirmed (motor only at launch).
- [ ] Insurer/partner arrangements signed.
- [ ] Regulatory/licensing/legal review completed.
- [ ] Customer terms, privacy policy, operational policies reviewed.

## Overall

**NOT production-ready** while Gates 2–6 are incomplete. Staging is permitted once the
staging checklist in `INSURECONNECT_RELEASE_1_FINAL_READINESS_REPORT.md` is satisfied.
