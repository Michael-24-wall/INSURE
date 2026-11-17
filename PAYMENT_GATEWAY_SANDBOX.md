# Payment gateway sandbox verification

This document describes repeatable verification for the M-Pesa Daraja and Flutterwave card adapters. It does not contain credentials and must never be used to fabricate a successful payment.

## Safety rules

- Never commit consumer keys, passkeys, shortcodes or webhook hashes.
- Never mark a payment successful from a callback alone; the server must call Daraja STK query or Flutterwave `verify_by_reference`.
- Do not run paid or production requests while testing.
- Keep `M_PESA_ENV=sandbox` and `FLW_ENV=sandbox` for sandbox testing.
- Use the bank-transfer/manual verification path to test settlement workflows without a gateway.

## Configuration (sandbox only)

Set these in the local environment or an untracked `.env` file:

| Variable | Purpose |
| --- | --- |
| `M_PESA_CONSUMER_KEY` | Daraja sandbox consumer key |
| `M_PESA_CONSUMER_SECRET` | Daraja sandbox consumer secret |
| `M_PESA_SHORTCODE` | Daraja sandbox business shortcode |
| `M_PESA_PASSKEY` | Daraja sandbox Lipa na M-Pesa passkey |
| `M_PESA_CALLBACK_URL` | Public HTTPS callback URL, for example a tunnel to `/api/v1/payments/mpesa/callback/` |
| `M_PESA_ENV=sandbox` | Selects `https://sandbox.safaricom.co.ke` |
| `M_PESA_ALLOWED_IPS` | Optional comma-separated Safaricom egress IPs |
| `M_PESA_TRUST_FORWARDED_FOR=false` | Leave false unless a trusted reverse proxy sets the header |
| `FLW_SECRET_KEY` | Flutterwave sandbox secret key |
| `FLW_PUBLIC_KEY` | Flutterwave sandbox public key |
| `FLW_ENV=sandbox` | Environment label |
| `FLW_WEBHOOK_HASH` | Value configured as the webhook secret hash in Flutterwave |
| `CARD_REDIRECT_URL` | Frontend return URL after hosted checkout |

## Automated checks (no external credentials)

Run these from `backend/` with the project virtual environment:

```bash
python manage.py test apps.payments
python manage.py test apps.finance
```

Covered without credentials:

- Bank payment creation, manual verification, receipts and duplicate-payment blocking.
- Idempotency-Key reuse.
- Callback handling when gateways are unconfigured never marks a payment successful.
- M-Pesa callback IP allowlist and `X-Forwarded-For` spoof rejection.
- Flutterwave webhook signature rejection/acceptance and event idempotency.
- Card initiation fails safely when the gateway is not configured.
- Refund limits and stale-payment timeouts.
- Finance scoping, ledger posting and settlement reconciliation.

## Manual sandbox procedure — M-Pesa

1. Configure the sandbox variables and expose the callback URL over HTTPS.
2. Start the backend and confirm `GET /api/v1/payments/gateways/` reports `mpesa_configured: true`.
3. Create a customer application and initiate a payment with `method: mpesa` and a sandbox phone number.
4. Confirm the payment becomes `processing` and that `checkout_request_id` is stored.
5. Complete or cancel the STK prompt in the sandbox simulator.
6. Confirm the callback is stored as a `WebhookEvent` and that the server performs an STK query before changing status.
7. Confirm the successful callback creates one receipt, one `Transaction`, and a balanced finance journal entry. Repeat the callback and confirm no duplicate transaction or journal entry is created.
8. Confirm a failed callback marks the payment `failed` and does not issue a policy.

## Manual sandbox procedure — card

1. Configure the Flutterwave sandbox key and `FLW_WEBHOOK_HASH`.
2. Confirm `GET /api/v1/payments/gateways/` reports `card_configured: true`.
3. Initiate a card payment and open the returned hosted checkout link.
4. Complete the sandbox checkout and return to `CARD_REDIRECT_URL`.
5. Confirm the webhook is accepted only when `verif-hash` matches, then re-verified through Flutterwave before completion.
6. Repeat the webhook and confirm the payment and webhook event are not duplicated.
7. Confirm a cancelled/failed checkout leaves the payment unpaid.

## Credential-dependent tests not covered by the automated suite

- Live Daraja OAuth token acquisition and STK push.
- Daraja STK query against Safaricom sandbox.
- Live Flutterwave hosted-checkout creation and signature verification.
- Receipt of real sandbox callbacks through a public HTTPS URL.
- Provider settlement timing and bank reconciliation against actual bank statements.

These must be executed manually in sandbox and recorded as external verification, never mocked as successful.
