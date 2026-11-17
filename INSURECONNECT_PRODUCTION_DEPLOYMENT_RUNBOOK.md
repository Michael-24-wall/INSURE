# INSURECONNECT — Production Deployment Runbook

Date: 2026-11-17
Status: PREPARED — DO NOT DEPLOY WITHOUT APPROVAL.

## Architecture

- **App server:** gunicorn `config.wsgi:application` (3 workers, timeout 120) — `backend/Dockerfile`.
- **Reverse proxy / static:** nginx serves the SPA and proxies `/api`, `/media`, `/static`, `/admin` — `frontend/nginx.conf`.
- **Background tasks:** Celery worker + beat (reconciliation, quote expiry, renewal reminders, policy lapse).
- **Database:** PostgreSQL (production). **Cache/queue:** Redis.
- **Object storage:** private S3 bucket (see `INSURECONNECT_PRIVATE_STORAGE_REPORT.md`).

## Pre-deploy (one-time)

1. Provision PostgreSQL with a dedicated production database/user + TLS.
2. Provision Redis with auth.
3. Provision a private S3-compatible bucket + credentials.
4. Provision an SMTP relay (email) and, if approved, an SMS provider.
5. Obtain and install (in secret store, not source) Daraja + Flutterwave production
   credentials and webhook IP/hash values.
6. Provision an HTTPS certificate for the production domain.

## Configuration (backend `.env`, backend-only)

```
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<strong random>
DJANGO_ALLOWED_HOSTS=app.example.com
FRONTEND_URL=https://app.example.com
CORS_ALLOWED_ORIGINS=https://app.example.com
CSRF_TRUSTED_ORIGINS=https://app.example.com
CREDENTIAL_ENCRYPTION_KEY=<strong random>
DATABASE_URL=postgresql://user:pass@db:5432/autoinssure
REDIS_URL/CACHE_URL/CELERY_BROKER_URL=redis://...
KYC_REQUIRED_FOR_POLICY_ISSUANCE=True
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True / CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000 (+ INCLUDE_SUBDOMAINS/PRELOAD)
M_PESA_* / M_PESA_ALLOWED_IPS / FLW_* / FLW_WEBHOOK_HASH=<production values>
EMAIL_BACKEND=... (SMTP)
```

## Deploy sequence

1. Build images: `docker compose build`.
2. Run migrations: `docker compose exec web python manage.py migrate`.
3. `collectstatic`.
4. Start worker + beat + web + frontend.
5. Verify `GET /health/` returns 200 and `/api/docs/` is reachable.
6. Smoke-test login, a quote request, and (if approved) a sandbox payment.

## Rollback

- Keep the previous image tags; `docker compose up -d` with the previous tag.
- Migrations are additive; reverse via the documented migration rollback only if a
  specific migration requires it (do not reset the DB).

## Operations

- Structured logs with request IDs (`config/settings.py` LOGGING).
- Optional Sentry (`SENTRY_DSN`).
- Health checks: `/health/`; Celery beat monitors the scheduled jobs.
- Rate limiting: auth / AI / dealer-search / webhook throttles (defaults in settings).
