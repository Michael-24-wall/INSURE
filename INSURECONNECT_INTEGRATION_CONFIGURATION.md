# INSURECONNECT Integration Configuration

## Safe defaults

Local development and E2E deliberately run with external delivery disabled:

- M-Pesa and Flutterwave keys are blank, so payment initiation fails safely instead of simulating success.
- Email uses the console backend.
- Notifications use in-app delivery by default.
- Files use local `MEDIA_ROOT` storage with protected download responses.
- `CELERY_TASK_ALWAYS_EAGER=True` by default for local workflows.
- Payment and settlement tests use the bank/manual verification path.

No production credentials, paid services, external messages, or production file migrations are required for the local and E2E suite.

## Configuration checker

Run from `backend/`:

```bash
python manage.py check_integrations
python manage.py check_integrations --json
python manage.py check_integrations --strict
```

The checker never prints secret values. `--strict` exits non-zero when an integration marked as required is incomplete. Email is required only when `email` is present in `NOTIFICATION_CHANNELS`; SMS and S3-compatible storage are reported as not configured until implemented/approved.

## M-Pesa Daraja

Required variables:

| Variable | Purpose |
| --- | --- |
| `M_PESA_CONSUMER_KEY` | Daraja app consumer key |
| `M_PESA_CONSUMER_SECRET` | Daraja app consumer secret |
| `M_PESA_SHORTCODE` | Business shortcode |
| `M_PESA_PASSKEY` | Lipa na M-Pesa passkey |
| `M_PESA_CALLBACK_URL` | Public HTTPS callback ending `/api/v1/payments/mpesa/callback/` |
| `M_PESA_ENV` | `sandbox` or `production` |
| `M_PESA_ALLOWED_IPS` | Comma-separated callback egress ranges |
| `M_PESA_TRUST_FORWARDED_FOR` | Keep `False` unless behind a trusted proxy |

The adapter selects the Safaricom sandbox or production base URL from `M_PESA_ENV`. A callback alone never completes a payment; the server performs an STK query. Secrets are read from environment configuration only.

## Flutterwave cards

Required variables:

| Variable | Purpose |
| --- | --- |
| `FLW_SECRET_KEY` | Server-side Flutterwave secret key |
| `FLW_PUBLIC_KEY` | Flutterwave public key |
| `FLW_ENV` | `sandbox` or `production` |
| `FLW_WEBHOOK_HASH` | Webhook `verif-hash` secret |
| `CARD_REDIRECT_URL` | Frontend return URL after hosted checkout |

Configure the provider webhook for the public HTTPS endpoint ending `/api/v1/payments/card/callback/`. Unsigned or mismatched webhooks are rejected. The server re-verifies the transaction before marking it successful.

## Email

Required when email delivery is enabled:

| Variable | Purpose |
| --- | --- |
| `EMAIL_BACKEND` | Keep console locally; use `django.core.mail.backends.smtp.EmailBackend` for SMTP |
| `EMAIL_HOST` | SMTP host |
| `EMAIL_PORT` | SMTP port, usually `587` or `465` |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password or app password |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | Enable exactly one, never both |
| `EMAIL_TIMEOUT` | SMTP timeout in seconds |
| `DEFAULT_FROM_EMAIL` | Sender address |
| `NOTIFICATION_CHANNELS` | Add `email` only when delivery is ready |

Transactional authentication emails use Django email delivery directly; the notification channel controls other notifications.

## SMS

No SMS adapter is implemented. When `sms` is requested, the channel logs and skips delivery. Do not configure `sms` in `NOTIFICATION_CHANNELS` for acceptance testing until a provider adapter and delivery receipts are implemented and approved.

## Private S3-compatible storage

`STORAGES["default"]` still uses `FileSystemStorage`. The application is not yet prepared to switch storage safely because it needs dependency review, private-bucket policy, encryption, signed access/streaming design, migration approval, and verification of protected upload/download behavior. Do not activate S3 or migrate files without explicit approval.

## Tenant integration records

Insurer-specific integrations are managed through `/api/v1/integrations/` by platform admins or provider administrators. Integration credentials and webhook secrets are encrypted at rest using `CREDENTIAL_ENCRYPTION_KEY`. A missing or placeholder key must be replaced before storing real integration secrets.

Outbound integration URLs are restricted to public HTTP/HTTPS hosts; local, private, reserved, redirect, and DNS-rebinding targets are rejected. Integration test failures are recorded instead of being reported as success.

## Recommended verification

```bash
cd backend
python manage.py check
python manage.py check_integrations
python manage.py test apps.payments
python manage.py test apps.finance
python manage.py test
```

See `PAYMENT_GATEWAY_SANDBOX.md` for the manual M-Pesa and Flutterwave sandbox procedures, and `INSURECONNECT_EXTERNAL_ACCOUNTS_SETUP.md` for account-registration guidance.
