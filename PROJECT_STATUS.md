# AutoInsure Connect — Project Status

Last updated: 2026-11-16

## Production-readiness validation (current increment)
- **E2E server lifecycle and port isolation**: development Vite now proxies to the canonical backend at `127.0.0.1:8000`; the E2E harness is isolated to backend `127.0.0.1:8001` and Vite `127.0.0.1:5174`. Playwright starts Django directly (no wrapper process), uses `reuseExistingServer: !process.env.CI` for both servers, and checks the real Django `GET /health/` endpoint. `npm run prepare:e2e` resets and reseeds the disposable E2E database/media, and the E2E backend environment includes CORS/CSRF/frontend origins for port `5174`.
- **E2E conflict root cause and fix**: the previous failure came from `frontend/.env` pointing dev Vite at `8001` while an orphaned E2E Django process held `8001`, combined with Playwright's backend `reuseExistingServer: false`; the wrapper script could also leave its spawned server behind after a failed run. Restoring the dev proxy to `8000`, launching Django directly, reseeding before each run, and removing stale project-owned E2E Vite processes fixed the conflict.
- **Isolated browser E2E harness**: Playwright runs against a dedicated `backend/e2e.sqlite3` and `backend/e2e-media/`, a seeded database (`seed_e2e`), backend on `127.0.0.1:8001` and Vite on `127.0.0.1:5174`; system Chrome (`channel: "chrome"`) is used because the managed Chromium download is blocked in this environment.
- **E2E coverage (`6 passed`)**: customer registration + email verification + login; insurer and dealership registration with platform-admin organization verification; customer quotation → application → approval → payment → verification → policy issuance → certificate download; RBAC/tenant-isolation assertions for admin/customer/dealer APIs; dealer partnership → commission terms → customer quotation → dealer application → commission flow.
- **E2E verification after port fix**: `npm run test:e2e` -> `6 passed (1.3m)`, including certificate download through the `5174` origin. After teardown there were no listeners on `8001` or `5174`, only transient `TIME_WAIT` sockets. Pre-existing dev servers on `8000`/`5173` were left running and must be restarted to reload the corrected `.env` proxy target.
- **Payment boundary regression tests**: successful M-Pesa STK and Flutterwave card callbacks mark only the payment as succeeded and never issue a policy; card callbacks require a configured gateway and matching amount/currency; STK remains amount-validated and idempotent.
- **Protected document delivery**: vehicle, claim, organization, inspection report/damage-photo, policy certificate and receipt downloads use authenticated endpoints with object-level scoping, `Cache-Control: private, no-store`, and audit logging (`*.document_downloaded`, `inspection.*_downloaded`); raw storage URLs are hidden from serializers.
- **Business-network fixes**: dealer quotations now normalize `sum_insured` before pricing/matching, partnership actions are no longer blocked by `http_method_names`, commission-term writes ignore client-supplied partnership IDs, and serializer `source` conflicts were removed.
- **Vite proxy correctness**: `vite.config.js` uses `loadEnv` so `.env` `VITE_API_PROXY_TARGET` is honored; this fixed the registration 500 when proxied through Vite.
- **Frontend test isolation**: Vitest is restricted to `src/**/*.{test,spec}.{js,jsx}` so Playwright specs are not collected by the unit runner.
- **Verification**: backend `172 tests OK` (parallel run); frontend `26 tests OK`; production build passed (bundle code-split); browser E2E `6 passed`; Django `check` clean; `makemigrations --check` reports no changes; full frontend lint clean.
- **Multi-layer validation pass**: produced `INSURECONNECT_MULTI_LAYER_VALIDATION_REPORT.md`. Two additional low-severity integrity fixes — (1) `apps/notifications/views.py` now validates that both sender and recipient are participants of a claim before a claim message is created; (2) `apps/analytics/services.py:provider_dashboard` scopes `open_quotation_requests` to the provider's insurers/open marketplace instead of returning a global count.
- **Release 1.0 staging hardening**: produced `INSURECONNECT_RELEASE_1_STAGING_READINESS.md`. Implemented webhook fail-closed behaviour (`MpesaCallbackView._ip_allowed`, `CardCallbackView._signature_valid`), SSRF DNS-rebinding connection guard (`apps/integrations/adapters.py` validating opener), dealer customer-search PII minimisation (active partnership required; phone only with consent), currency derivation in `premium_tracking_summary` (`DEFAULT_CURRENCY`), executable magic-byte upload rejection (`apps/common/fields.py`), and frontend bundle code-splitting (`manualChunks` + lazy `VehicleScene`/`AdminDashboard`). Claim-settlement and insurer-settlement journal postings are documented as proposals requiring chart-of-accounts approval.

## Security hardening and frontend completion (this increment)
- **Inspection cross-tenant isolation**: removed the `organization_id__isnull=True` fallback in `apps/inspections/views.py:get_queryset` that let any provider/dealer/agent list unassigned customer inspections; added explicit object-level authorization to `download_report`, `download_damage_photo` and `ai_assist` (report/photo downloads and AI assist now require the claimant, assigned inspector, linked organisation staff, or platform admin).
- **Claim document download authorization**: `apps/claims/views.py:download_document` now mirrors the upload path's check (claimant, insurer organisation member, or platform admin), so a stray tenant user cannot download claim evidence.
- **Finance read exposure**: `LedgerAccountViewSet`, `ExchangeRateViewSet`, `CurrencyConfigViewSet` and `PlatformFeeViewSet` are now `IsPlatformAdmin`-only (previously any authenticated user could read the chart of accounts and configuration).
- **Platform settings read exposure**: `PlatformSettingView` (`/api/v1/admin/settings/`) is now `IsPlatformAdmin` for both GET and PUT.
- **Payment refund claim branch**: `PaymentViewSet.refund` now resolves the insurer from `claim`-linked payments, matching `verify`, so providers can refund claim-excess/inspection payments they own.
- **Risk-indicator tenant scoping**: `suspicious_payment_indicators` now scopes to the provider's insurers (via `insurer_ids`) instead of the calling user's own payments.
- **SSRF hardening**: `apps/integrations/adapters.py:outbound_url_error` now resolves hostnames and rejects any address that resolves to a local/private/reserved range, closing the DNS-rebinding-to-private-IP gap (a residual TOCTOU between check and connection remains, noted in `SECURITY.md`).
- **Frontend fixes**: restored logo link to the role home path; added detail-route page titles; implemented the `wide` `Modal` prop; removed a redundant ternary in `ApplicationDetail`; removed dead landing footer links; scoped the customer "Complete your payment" list to `approved` applications and linked each to its detail page; added missing loading/error states to Vehicles, Products, Inspector dashboard, Commissions and Notifications.
- **Missing package marker**: added the missing `apps/finance/__init__.py`. The finance app was previously a namespace package, which silently excluded its 12 tests from the full `manage.py test` discovery run; the full suite now runs `159` tests.

## Multi-line positioning correction (previous increment)
- Repositioned the public experience around **INSURECONNECT — All Insurance. One Connected Ecosystem.**
- Replaced motor-only landing copy with a global insurance ecosystem narrative covering customers, insurers, brokers, agents, dealerships, corporate organisations, partners, inspectors and administrators.
- Added all ten insurance lines to the public information architecture: Motor, Health and Medical, Life, Business and Commercial, Property and Home, Travel, Marine and Cargo, Agriculture, Personal Accident and Liability.
- Kept capability claims truthful: the backend currently exposes operational product and quotation workflows only for motor categories (`comprehensive`, third party, third party/fire/theft, commercial motor and motorcycle). The other lines are marked as expanding in the UI and never show fake products, quotes, policies or payments.
- Updated authenticated product discovery so customers choose an insurance line first; live motor quotation flow is preserved and non-motor lines provide an explicit provider-led onboarding message.
- Updated authentication, provider product management, quotation empty states, policy labels, metadata and footer language to remove motor-only positioning while preserving motor-specific workflows where they are genuinely required.

### Current verification
- Frontend tests: `26 tests OK`
- Frontend production build: passed
- Browser end-to-end suite: `6 passed` after this copy/layout increment; landing, registration and login routes render with the new global positioning.
- Frontend lint: existing Three.js `react/no-unknown-property` errors remain in untouched 3D components; no new errors were introduced by this increment.

## Completed functionality

### Core platform (pre-existing, preserved)
- JWT authentication (access/refresh, token versioning), 2FA (TOTP), email verification, password reset, KYC.
- Vehicles, quotations (internal pricing engine), applications, policies, claims (state machine), inspections, payments (M-Pesa / card / bank), commissions, notifications, analytics, AI services, audit logging.
- Roles: customer, provider_admin, provider_staff, agent, inspector, claims_officer, admin, super_admin.
- Docker/nginx/CI deployment, 142 backend automated tests plus 26 frontend unit tests and browser end-to-end coverage.

### Business Network & insurer-dealer ecosystem (this increment)
- **Dealership organization type** (`dealer`) with richer company fields (trading name, country, county, tax ID, logo, representative).
- **Insurer onboarding enrichment** (trading name, country, county, tax ID, representative, licence expiry).
- **Dealership registration** (`POST /api/v1/auth/register/dealer/`) with verification status and admin review.
- **Organization verification status history** (`OrganizationStatusHistory`).
- **Business Network app** (`apps/business_network`):
  - `DealerBranch`, `DealerVehicle`, `DealerVehiclePhoto` (inventory with statuses AVAILABLE/RESERVED/SOLD/UNAVAILABLE, photos, branch assignment).
  - `Partnership` (insurer–dealer, many-to-many, statuses pending/under_review/more_info/approved/active/rejected/suspended/terminated), unique active constraint.
  - `PartnershipRequest` (send / approve / reject / more-info), `PartnershipActivity`.
  - `CustomerConsent` (explicit consent before data sharing, grant/withdraw).
  - `PartnershipCommissionTerms` (fixed / percentage, per product).
- **Dealer-to-insurer transactions**: dealer-originated quotation requests with attribution (dealership, branch, partnership, consent), restricted insurer quote generation, integrated with the existing quotation/application/payment/policy engine (no parallel engine).
- **Dealership referral commissions**: `PartnershipCommissionTerms` + automatic dealer commission creation on policy issuance (tracked with originating dealership, exposed in the commission API and scoped to dealer users).
- **Frontend**: orange/white/blue design-token theme; dealership + insurer Business Network pages (discover, partnerships, requests, inventory, commission terms); dealership registration flow.
- **Tests**: 13 new tests covering partnerships, tenant isolation, inventory, dealer transactions, consent, commissions, and dealership registration (total 117).

### Dealer–insurer quotation workflow (this increment)
- **Directed quotation requests**: optional `insurer` on `QuotationRequest`, review statuses (`under_review`, `more_info`, `rejected`), insurer notes, clarification notes/timestamps, reviewer/timestamp tracking.
- **Insurer inbox**: tenant-scoped list (directed requests + own quotations + open marketplace only), filters by status, cover type, dealership, created date range and search; dealer scoping by dealership; customer scoping by owner.
- **Request processing**: start review, request information, decline, and dealer/customer clarification, with status guards, participant/organization notifications and audit logs.
- **Quotation preparation**: premium, taxes, fees, other charges, excess, benefits/exclusions, coverage limits, deductibles, terms, notes and custom expiry; `total_payable`; quote-level request-info/decline and edits while `received`/`more_info`.
- **Compare, select and apply**: dealer/customer selection with quote/request expiry and terminal-status guards; dealer `dealer-create` application endpoint (ownership verified, application submitted, request converted, customer/insurer notified); customer application creation still uses the existing flow.
- **Frontend**: role-aware quotation list (customer/insurer/dealer) with status tabs, search and filters; quotation detail with review actions, clarification modal, charges/total/limits/deductibles, compare/select/apply; dealer routes and navigation; applications list/detail safe and read-only for dealership users.
- **Tests**: 6 new dealer–insurer workflow tests (targeted visibility, review/info/decline, quote preparation, clarify/select/apply, expiry blocking, multiple insurers on open requests). `apps.insurance` + `apps.business_network` suite: 40 tests passing; production frontend build and changed-file lint pass.

### Policy issuance (quotation-to-policy lifecycle) — completed
- **Insurer approval enforcement**: `POST /api/v1/applications/{id}/issue-policy/` requires `Application.Status.APPROVED` (set via the insurer `approve` action) before a policy can be issued (`apps/insurance/views.py:902`).
- **Authorisation**: `_provider_action` restricts underwriting actions (review, info request, approve, reject, issue) to `PROVIDER_ADMIN`/`PROVIDER_STAFF`/`ADMIN`/`SUPER_ADMIN` staff belonging to the application's insurer organization; dealership users (`DEALER_ADMIN`/`DEALER_STAFF`) and customers cannot issue policies or access restricted insurer operations.
- **Verified payment requirement**: issuance requires a premium `Payment` with `status=SUCCEEDED` and `verified_at IS NOT NULL` (an actually verified payment record), so callbacks/manual verification that only mark a payment succeeded cannot by themselves trigger issuance. STK/card callbacks and the manual verify endpoint call `complete_payment` only — they never invoke `issue_policy`.
- **Duplicate issuance prevention**: `issue_policy` locks the application row (`select_for_update`) and rejects issuance when a `Policy` already exists for the application; concurrent duplicate requests serialize and the second is rejected.
- **KYC gate**: when `KYC_REQUIRED_FOR_POLICY_ISSUANCE` is set, the policyholder's KYC must be verified before issuance.
- **Secure policy document access**: added `PolicyViewSet.document` (`GET /api/v1/policies/{id}/document/`, `policies-document`) returning the generated PDF certificate, scoped to the policyholder, the policy's insurer staff, and platform admins; dealership users cannot access it.
- **Relationships preserved**: issued `Policy` links to its `Application` (OneToOne), `Quotation`, insurer, product, vehicle, and customer; agent/dealer commissions are auto-created on issuance as before.
- **Tests**: full backend suite `117 tests OK`; Django `manage.py check` clean; migration `insurance.0005_application_reviewed_at` created and applied; production frontend build passes (frontend lint's remaining `react/no-unknown-property` errors are pre-existing three.js JSX-prop flags in untouched files).

### Financial operations and transaction intelligence (this increment) — completed
- **Finance backend**: added `financial_dashboard`, `premium_tracking_summary`, `ledger_balances`, `mark_payment_settled`, `reconcile_settlement`, and `create_settlement_from_verified_payments` in `backend/apps/finance/services.py`.
- **Finance API**: added finance routes under `/api/v1/finance/` via `backend/apps/finance/urls.py` and `backend/config/urls.py`; dashboard, ledger balances, premium tracking, settlement, journal, ledger and currency endpoints are routed through the finance app.
- **Financial dashboard**: `GET /api/v1/finance/dashboard/` returns customer and insurer/provider-scoped financial data, optional `start`/`end`, gross/net premium collected, refunds, collected this month, premium earned recognized, commissions outstanding, outstanding settlements, payments by method/insurer, and settlements.
- **Premium tracking**: `GET /api/v1/finance/premium-tracking/{policy_id}/` is scoped to the policyholder, insurer staff, or platform admin.
- **Ledger balances**: `GET /api/v1/finance/ledger/balances/` is restricted to platform admin.
- **Transactions**: settlement lifecycle (`pending -> instructed -> settled -> reconciled`) and auto creation from verified payments implemented; refunds reduce net premium collected.

### Financial operations and transaction intelligence — tests and frontend
- Added `backend/apps/finance/tests.py` with 9 financial operations tests covering dashboard access/scoping, admin financial reporting, customer scope, refunds, premium tracking, ledger balances, settlement lifecycle, and auto settlement.
- Final verification completed: full backend suite `117 tests OK`; targeted finance tests OK; Django check clean; migration check clean; production frontend build passes; changed-file frontend lint passes.
- Frontend provider dashboard now consumes `GET /api/v1/finance/dashboard/` and displays net premium collected, premium earned recognized, commissions outstanding, and outstanding settlements.

### Platform polish, integration and payment readiness (this increment) — completed
- **Frontend tests configured**: Vitest + jsdom + Testing Library, shared setup, deterministic KES/UTC formatting helpers; 9 test files / 26 tests passing.
- **Routing fixes**: added `/app/claims/:id` and `/inspector/inspections/:id`; claims detail now respects the claims role guard.
- **Accessibility**: associated form labels/IDs and validation ARIA, dialog semantics/focus trapping/focus restore/Escape handling for shared modals and the AI assistant, table captions/header scopes, accessible tabs and labelled search.
- **Dashboard resilience**: verified loading/error/empty states across customer, provider, admin, agent, dealer and business-network screens; added retries for document/inspection failures; prevented silent list truncation with explicit pagination sizes.
- **Provider finance date range**: provider dashboard can filter the finance dashboard by start/end date and clear the range.
- **Payments UI hardening**: gateway/counts warnings, required manual provider reference, refund amount/reason validation.
- **Auth polish**: demo account shortcuts are development-only; password reset notice is displayed; dealer registration copy corrected.
- **Payment gateway readiness**: added `PAYMENT_GATEWAY_SANDBOX.md` with repeatable Daraja/Flutterwave sandbox procedures, credential requirements and automated-vs-manual test coverage. No gateway success is simulated.
- **M-Pesa callback security**: IP allowlist retained; spoofable `X-Forwarded-For` is ignored unless `M_PESA_TRUST_FORWARDED_FOR=true`. Callback completion now also validates the authoritative STK-query amount and handles duplicate/late callbacks without a server error.
- **Card callback security**: optional `verif-hash` validation via `FLW_WEBHOOK_HASH` using constant-time comparison; invalid/missing signatures are rejected before event/payment processing. Gateway verification now requires matching amount and currency.
- **Abuse throttling**: scoped throttles for AI operations (`THROTTLE_AI`, default 30/minute) and dealer customer lookup (`THROTTLE_SEARCH`, default 300/hour).
- **Verification**: full backend suite `134 tests OK`; targeted payments/finance suite `28 tests OK`; frontend `26 tests OK`; browser end-to-end suite passes; production frontend build passes; Django `check` clean; migration check clean; changed-file lint clean.

## In-progress / partial

- Insurer-side "discover dealerships" page is implemented; dealer-side quotation request UI and dealer quotation tracking/compare/apply flow are now implemented for the current increment. Broader dealer onboarding polish remains.
- Dealer vehicle photo upload UI is implemented (upload, set primary, delete), with backend validation tests.
- Authenticated protected download endpoints now cover vehicle, claim and organization documents, inspection reports/damage photos, policy certificates and receipts. Remaining production hardening: private object storage and file-content inspection.

## Blocked / external dependencies

- Live third-party credentials for M-Pesa (Daraja), Flutterwave (card) and a remote AI provider — code paths are implemented but require sandbox credentials to smoke-test end-to-end.

## Outstanding tests

- External sandbox verification for live Daraja and Flutterwave flows, as documented in `PAYMENT_GATEWAY_SANDBOX.md`; credentials are not available in this environment.
- Browser E2E coverage passes for registration, customer journeys, dealer-network/commission flows and RBAC/tenant isolation; live third-party Daraja/Flutterwave sandbox verification remains outstanding.

## Known limitations

- PostgreSQL full-text search is not implemented (search uses `icontains`).
- Frontend remains JavaScript (TypeScript migration not started).
- Prometheus metrics are wired but disabled by default (`PROMETHEUS_METRICS_ENABLED`).
- Insurer licence expiry is captured on the model but not yet surfaced in a dedicated onboarding form field or a licence-expiry reminder task.
- File uploads enforce extension, client-declared MIME and size limits; content inspection is still a follow-up. Direct media URLs are not served in production with Django `DEBUG=false`; protected authenticated delivery is implemented, while private object storage remains a follow-up.
- Dealer customer lookup is role-gated and throttled but still searches platform-wide customer records; it should be constrained to consent or exact identifier when the product flow allows.
- **Multi-line insurance status**: only motor product categories (`comprehensive`, `third_party`, `third_party_fire_theft`, `commercial`, `motorcycle`) are operational end-to-end (pricing, quotations, applications, policies). Health, life, business, property, travel, marine, agriculture, accident and liability lines are surfaced in the UI as "expanding" and have no backend product/pricing workflow — no fictitious quotes or premiums are generated for them. Extending `Product.Category` and the pricing engine for non-motor lines requires per-line requirements (insurable object, benefits, exclusions) and real insurer product configuration.
- **Claim settlement does not post a ledger journal entry** (`apps/claims/views.py:settle`): settlement records `settled_amount`/`settlement_reference` but does not create a double-entry posting. A claims-payout account must be added to the chart of accounts and the posting wired into `settle` before claim payouts are reflected in ledger balances.
- **Insurer settlement `settle`/`reconcile` do not post journal entries** (`apps/finance/views.py`): the settlement lifecycle updates status/amounts but does not move cash/settlement-payable accounts; `create_settlement_from_verified_payments`, `mark_payment_settled` and `reconcile_settlement` exist but are not wired to views.
- **SMS notifications are a documented stub** (`apps/notifications/channels.py`): only in-app and (opt-in) email are delivered; SMS requires a provider configuration.
- **SSRF residual TOCTOU** (`apps/integrations/adapters.py`): hostname resolution is validated at check time, but the downstream `urllib.request` re-resolves; a full fix requires a custom opener that resolves and connects to the validated address.
