# INSURECONNECT — Payment Integration Report

Date: 2026-11-17

## Status summary

| Gateway | Adapter | Idempotency | Fail-closed | Re-verification | Reconciliation | External verification |
| --- | --- | --- | --- | --- | --- | --- |
| M-Pesa Daraja | IMPLEMENTED (`apps/payments/gateways.py`) | ✅ `WebhookEvent` | ✅ `M_PESA_ALLOWED_IPS` required when `DEBUG=false` | ✅ STK query (`handle_stk_callback`) | ✅ `reconcile_pending_mpesa` | ⚠️ BLOCKED BY CREDENTIALS |
| Flutterwave card | IMPLEMENTED | ✅ `WebhookEvent` | ✅ `FLW_WEBHOOK_HASH` required when `DEBUG=false` | ✅ `verify_by_reference` (`verify_card_payment`) | ✅ `reconcile_pending_card` | ⚠️ BLOCKED BY CREDENTIALS |
| Bank/manual | IMPLEMENTED | ✅ (manual verify) | — | — | — | ✅ IMPLEMENTED AND VERIFIED |

## M-Pesa Daraja — IMPLEMENTED BUT NOT EXTERNALLY VERIFIED

Files: `apps/payments/gateways.py` (`MpesaDarajaClient`), `apps/payments/services.py`
(`initiate_premium_payment`, `handle_stk_callback`), `apps/payments/tasks.py`
(`reconcile_pending_mpesa`, `timeout_stale_payments`).

- OAuth token acquisition (`/oauth/v1/generate`, Basic auth) — implemented.
- STK Push (`/mpesa/stkpush/v1/processrequest`) with `Password` = base64(shortcode+passkey+timestamp) — implemented.
- STK query (`/mpesa/stkpushquery/v1/query`) is the **authoritative** confirmation.
- Callback: idempotent via `WebhookEvent`, amount-checked, and always re-verified via STK query; never marks success from the callback alone.
- IP allowlist (`M_PESA_ALLOWED_IPS`) + optional trusted `X-Forwarded-For`; **fails closed** when unset in production.
- Late/out-of-order callbacks handled by correlation on `checkout_request_id`.

Required sandbox credentials (backend env only, never committed):
`M_PESA_CONSUMER_KEY`, `M_PESA_CONSUMER_SECRET`, `M_PESA_SHORTCODE`,
`M_PESA_PASSKEY`, `M_PESA_ENV=sandbox`, `M_PESA_CALLBACK_URL` (public HTTPS),
`M_PESA_ALLOWED_IPS`.

## Flutterwave — IMPLEMENTED BUT NOT EXTERNALLY VERIFIED

Files: `apps/payments/gateways.py` (`FlutterwaveCardGateway`),
`apps/payments/services.py` (`verify_card_payment`), `apps/payments/views.py`
(`CardCallbackView`).

- Hosted-checkout initiation (`/payments`) — implemented; card data never stored.
- `verify_by_reference` is the **authoritative** confirmation; amount + currency checked.
- Webhook: `verif-hash` compared with `hmac.compare_digest`; **fails closed** when
  `FLW_WEBHOOK_HASH` is unset in production; event idempotent via `WebhookEvent`.
- Refunds handled through the platform `create_refund` (reversal ledger) — provider-side
  refund API not called (documented gap, see below).

Required sandbox credentials: `FLW_SECRET_KEY`, `FLW_PUBLIC_KEY`,
`FLW_ENV=sandbox`, `FLW_WEBHOOK_HASH`, `CARD_REDIRECT_URL`.

## Shared payment architecture — IMPLEMENTED AND VERIFIED

- Single `Payment` model + `complete_payment`/`fail_payment`/`create_refund` shared by all methods; no duplicated engines.
- `complete_payment` is idempotent (returns early if already succeeded) and posts the premium ledger entry exactly once (`PAY-{reference}`).
- Amount/currency validated against the original payment; reference traced via `provider_reference`/`merchant_reference`/`checkout_request_id`.
- Policy issuance requires a verified premium payment (`issue-policy` guard) — callbacks cannot issue policies.
- `timeout_stale_payments` + reconciliation tasks recover abandoned records.

## Sandbox test matrix

| # | Scenario | Status |
| --- | --- | --- |
| 1–3 | M-Pesa success / failed / cancelled STK | ⚠️ BLOCKED BY CREDENTIALS |
| 4 | Delayed callback | ✅ IMPLEMENTED (idempotent, re-verified) — live timing untested |
| 5 | Duplicate callback | ✅ IMPLEMENTED AND VERIFIED (tests) |
| 6 | Invalid callback | ✅ IMPLEMENTED AND VERIFIED (tests) |
| 7–8 | Incorrect amount / currency | ✅ IMPLEMENTED AND VERIFIED (tests) |
| 9 | Unknown transaction reference | ✅ IMPLEMENTED (logged, not applied) |
| 10–11 | Flutterwave success / failed | ⚠️ BLOCKED BY CREDENTIALS |
| 12 | Invalid Flutterwave signature | ✅ IMPLEMENTED AND VERIFIED (tests) |
| 13 | Duplicate Flutterwave webhook | ✅ IMPLEMENTED AND VERIFIED (tests) |
| 14 | Provider timeout | ✅ IMPLEMENTED (timeouts + `safe_enqueue`; reconciliation) |
| 15 | Provider↔internal reconciliation | ✅ IMPLEMENTED (tasks) — live data untested |

## Known gaps (not blockers for staging)

- Flutterwave provider-side refund API is not called; platform refund posts a reversal
  ledger entry and marks the payment refunded, but the provider must be refunded
  manually/out-of-band until that adapter is added.
- No provider-level transaction reference export for bank reconciliation; the
  `Transaction`/`Payment` tables are the source of truth.

## Actions required from you

1. Provide Daraja **sandbox** consumer key/secret, shortcode, passkey, and a public
   HTTPS callback endpoint.
2. Provide Flutterwave **sandbox** secret/public keys and a webhook hash.
3. Approve live activation separately from sandbox testing.
