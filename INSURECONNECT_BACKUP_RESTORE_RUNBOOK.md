# INSURECONNECT — Backup & Restore Runbook

Date: 2026-11-17
Status: PROCEDURE PREPARED — REHEARSAL NOT YET PERFORMED (Gate 4).

## What to back up

1. **PostgreSQL** (`autoinssure`) — the source of truth.
2. **Private object storage** (documents/certificates).
3. **Secrets** (environment / secret store) — backup separately, never in the DB dump.

## Backup (PostgreSQL)

```bash
docker compose exec db pg_dump -U <user> -Fc autoinssure > backup_$(date +%Y%m%d_%H%M%S).dump
```

Schedule: at least daily; retain 30 days + weekly for 12 weeks (retention to be approved).

## Restore (isolated rehearsal)

1. Spin up an isolated PostgreSQL instance (NOT the production DB).
2. `docker compose exec -T db pg_restore -U <user> -d <scratch_db> < backup.dump`
3. Verify row counts for `accounts_user`, `insurance_policy`, `payments_payment`,
   `finance_journalentry`, `claims_claim`.
4. Verify a balanced ledger sample (`debits == credits` per journal entry).
5. Verify object-storage keys referenced by `FileField.name` exist in the bucket
   (spot-check documents).

## Object storage

- Enable bucket versioning and cross-region/cross-account replication per policy.
- Document download is application-streamed, so no public URLs need restoring.

## Restore-from-disaster sequence

1. Restore PostgreSQL from the latest dump.
2. Point the app at the restored DB + bucket.
3. Run `manage.py migrate` (idempotent) and `collectstatic`.
4. Run the full test suite + a smoke transaction in an isolated environment.
5. Record the rehearsal result and date in this file.

## Verification gate

Backup/restore must pass an actual rehearsal (Gate 4) before production readiness.
