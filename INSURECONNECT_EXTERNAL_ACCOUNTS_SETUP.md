# INSURECONNECT External Test Account Setup

## Scope and safety

This guide covers sandbox/test accounts for M-Pesa Daraja, Flutterwave, email delivery, SMS, and private object storage. It does **not** create accounts, accept terms, purchase services, deploy infrastructure, or contain real credentials.

- Use sandbox/test mode only. No live payments, bulk email, SMS, or paid storage.
- Use synthetic data. Never use production customer data.
- Store credentials only in an untracked `.env` file or a secret manager. Never commit them.
- Keep `DJANGO_DEBUG=False` and live keys out of local/E2E environments.
- Do not mark a payment, message, or upload successful unless the provider confirms it.

## Accounts and credentials to obtain

| Integration | Account to create | Credentials/config required | Callback or webhook | Activation status |
| --- | --- | --- | --- | --- |
| M-Pesa Daraja | Safaricom Daraja developer account and sandbox app | Consumer key, consumer secret, business shortcode, Lipa na M-Pesa passkey | Public HTTPS URL ending `/api/v1/payments/mpesa/callback/` | Sandbox account not created here |
| Flutterwave | Flutterwave sandbox/test account | Secret key, public key, webhook secret hash | Public HTTPS URL ending `/api/v1/payments/card/callback/` | Sandbox account not created here |
| Email | SMTP sandbox or test inbox provider | SMTP host, port, username, password, TLS/SSL settings, sender address | Not applicable | Not configured here |
| SMS | SMS provider account | Provider name, API base URL, API key, sender ID | Delivery callback if supported | Blocked: no provider adapter exists |
| Private storage | S3-compatible object-storage account or bucket | Endpoint, region, bucket, access key, secret key, private ACL policy | Not applicable | Blocked pending approval and dependency setup |

## M-Pesa Daraja sandbox

1. Create a Daraja developer account and a sandbox app.
2. Request sandbox access for Lipa na M-Pesa STK Push and STK Query.
3. Record the consumer key, consumer secret, shortcode, and passkey in a secret manager or untracked `.env`.
4. Expose a public HTTPS callback to `/api/v1/payments/mpesa/callback/`. A temporary HTTPS tunnel is acceptable for sandbox testing only.
5. Set `M_PESA_ENV=sandbox`. Do not use production credentials.
6. Add Safaricom callback egress ranges to `M_PESA_ALLOWED_IPS` for staging/production-like checks. Leave `M_PESA_TRUST_FORWARDED_FOR=False` unless a trusted reverse proxy sets the header.
7. Confirm the backend reports M-Pesa as configured through `python manage.py check_integrations`.
8. Run the manual sandbox procedure in `PAYMENT_GATEWAY_SANDBOX.md`. The authoritative confirmation is the Daraja STK query, not the callback alone.

## Flutterwave sandbox

1. Create a sandbox/test Flutterwave account.
2. Copy the test secret key and test public key into an untracked `.env`.
3. Configure a webhook secret hash and set the same value as `FLW_WEBHOOK_HASH`.
4. Point the webhook at the public HTTPS endpoint ending `/api/v1/payments/card/callback/`.
5. Set `FLW_ENV=sandbox` and a local or staging `CARD_REDIRECT_URL`.
6. Confirm `check_integrations` reports Flutterwave as configured.
7. Complete the manual sandbox procedure in `PAYMENT_GATEWAY_SANDBOX.md`. Always re-verify the transaction with Flutterwave before marking a payment successful.

## Email delivery

1. Create a sandbox SMTP account or use a local mail-capture service.
2. Set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`.
3. Set `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, and `DEFAULT_FROM_EMAIL`.
4. Add `email` to `NOTIFICATION_CHANNELS` only when the test mailbox is ready.
5. Verify a test email is received. Never send to real customers.

Local development keeps the console email backend. E2E keeps the safe local defaults and does not require an external mailbox.

## SMS delivery

SMS is **not operational**. The notification channel currently logs a clear skip message when SMS is requested. Do not add `sms` to `NOTIFICATION_CHANNELS` and claim delivery until a provider adapter, credentials, sender ID, retry handling, and delivery receipts are implemented and approved.

## Private object storage

The application currently uses local filesystem storage and protected download responses. S3-compatible storage is **not activated** because it requires:

- review and approval to use the chosen provider and paid service;
- adding and vetting storage dependencies;
- private-bucket policy, encryption, signed URL/streaming behavior, and file migration approval;
- verification that existing upload validation and authorization checks remain intact.

Do not migrate production files or change the storage backend without explicit approval. Document the proposed endpoint, bucket, region, retention policy, encryption, and access model before activation.

## Required verification

From `backend/`:

```bash
python manage.py check_integrations
python manage.py test apps.payments
python manage.py test apps.finance
```

Record only pass/fail evidence. Never paste secrets, access tokens, full callback payloads containing customer data, or provider dashboards into reports.
