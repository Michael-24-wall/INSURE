# AUTOINSURE CONNECT
## System Report and Functional Description

**Document Type:** System Report (architecture + functional specification)
**Project:** AutoInsure Connect
**Platform:** Web-based vehicle insurance marketplace and policy-administration platform
**Project Directory:** `INSURE`
**Status:** Implemented and verified end-to-end

---

## 1. Executive Summary

AutoInsure Connect is a full-stack, multi-tenant vehicle insurance platform that connects
vehicle owners (customers), insurance providers, insurance agents, vehicle inspectors,
claims officers and platform administrators in one digital marketplace.

It automates the entire insurance lifecycle — from a customer's first quotation request
through quotation comparison, formal application, underwriting approval, premium payment,
policy issuance, vehicle inspection, claims handling and renewal — with role-based
access control, a hardened authentication layer, background automation, and an
administrative back office.

The system is built as a Django REST API backend and a React single-page application
frontend, backed by PostgreSQL (production) or SQLite (development), Redis (caching and
task queuing), and Celery (asynchronous task execution and scheduled jobs). It ships with
Docker/nginx deployment assets and a CI pipeline.

> This document describes the **implemented** system. A product-vision description of
> "intended" features is unnecessary — the functionality below exists, is wired end-to-end,
> and is covered by an automated test suite (91 passing tests) plus a live API walkthrough.

---

## 2. System Purpose

AutoInsure centralizes vehicle insurance operations so that:

- Customers can register vehicles, request and compare quotations, apply for cover, pay
  premiums, view policies and file claims from one place.
- Insurance providers can publish products, receive and underwrite applications, issue
  policies and settle claims.
- Agents can convert marketplace enquiries into formal applications and earn tracked
  commissions.
- Inspectors can carry out pre-insurance and claims inspections with photographic damage
  records and AI-assisted analysis.
- Claims officers can manage claims through a defined state machine.
- Administrators can verify organizations and users, perform KYC review, and monitor the
  platform through dashboards, audit logs and exports.

---

## 3. System Users and Responsibilities

### 3.1 Customers (`customer`)
- Register and manage a profile (with optional KYC).
- Register vehicles and upload documents.
- Request insurance quotations through the marketplace.
- Compare and select quotations, then create and submit applications.
- Pay premiums (M-Pesa, card, or bank transfer).
- View and renew policies.
- File and respond to claims.

### 3.2 Insurance Providers (`provider_admin`, `provider_staff`)
- Manage the insurer profile and product catalogue (products, rates, coverage options).
- Review, approve or reject applications.
- Verify payments and issue policies.
- Manage commissions and integrations.

### 3.2b Dealerships (`dealer_admin`, `dealer_staff`)
- Register as a motor-vehicle dealership and manage a public business profile.
- Manage branches, staff and vehicle inventory (with photographs).
- Discover insurers, request and manage partnerships.
- Request quotations and initiate applications on behalf of customers (with consent).

### 3.3 Insurance Agents (`agent`)
- View the open marketplace.
- Create applications on behalf of customers (agent-assisted sales).
- Track commissions generated from policies they originate.

### 3.4 Vehicle Inspectors (`inspector`)
- Carry out scheduled inspections.
- Record damage by vehicle zone (severity, description, photo, estimated repair cost).
- Use AI-assisted damage analysis.
- Complete inspections and submit reports.

### 3.5 Claims Officers (`claims_officer`)
- Review and assign claims.
- Request additional information, schedule inspections, assess, approve, settle and close
  claims.

### 3.6 Platform Administrators (`admin`, `super_admin`)
- Manage users, roles and account status.
- Review organizations (verify/reject/suspend).
- Perform customer KYC review.
- View platform-wide dashboards, financial reports, audit logs and CSV exports.
- Configure platform settings.

---

## 4. System Architecture

### 4.1 High-level components

```
                    +-------------------+
   Browser  <-----> |  React SPA (Vite) |      (frontend)
                    +---------+---------+
                              |  /api/v1 (proxy)
                              v
                    +-------------------+
                    |  nginx (edge)     |  (static + reverse proxy)
                    +---------+---------+
                              |
                    +---------v---------+
                    |  Django + DRF API |  (backend, gunicorn)
                    +----+----+----+----+
                         |    |    |
              +----------+    |    +----------+
              |               |               |
       +------v------+  +-----v-----+  +------v------+
       |  PostgreSQL |  |   Redis   |  |   Celery    |
       |  (SQLite    |  | (cache +  |  | (worker +   |
       |   in dev)   |  |  broker)  |  |  beat)      |
       +-------------+  +-----------+  +-------------+
```

### 4.2 Technology stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Django 5.2, Django REST Framework 3.16 |
| Authentication | SimpleJWT (access/refresh), PyOTP (TOTP 2FA) |
| API docs | drf-spectacular (OpenAPI / Swagger) |
| Database | PostgreSQL (production) / SQLite (development) |
| Cache & queue | Redis |
| Async tasks | Celery (worker + beat scheduler) |
| Payments | M-Pesa Daraja (STK push), Flutterwave (card), manual bank |
| AI | Provider abstraction (heuristic default; remote vision/OCR pluggable) |
| Frontend | React 18, Vite 5, React Query, React Router 6, Tailwind CSS, Recharts, Three.js / react-three-fiber |
| Observability | Structured logging + request IDs, Sentry (optional), Prometheus (optional) |
| Serving | Gunicorn, WhiteNoise, nginx |
| Deployment | Docker, Docker Compose, GitHub Actions CI |

### 4.3 Backend application layout (13 Django apps)

| App | Responsibility |
|---|---|
| `common` | Base models (timestamps, soft-delete, UUID), permissions, pagination, exceptions, scoping helpers, request middleware |
| `accounts` | Custom user model, roles, auth (JWT/2FA/KYC), verification & reset tokens |
| `organizations` | Organizations (insurer/dealer/agency/platform), memberships, documents, verification history |
| `business_network` | Dealership inventory, branches, partnerships, partnership requests/activity, customer consent, commission terms |
| `vehicles` | Vehicles (soft-deletable), documents |
| `insurance` | Insurers, products, quotations, applications, policies, pricing engine |
| `claims` | Claims, documents, status history, state machine |
| `inspections` | Inspections, damage records, zones |
| `payments` | Payments, transactions, refunds, commissions, gateways, webhooks |
| `notifications` | In-app notifications, messages, delivery channels |
| `integrations` | Insurer REST/webhook integrations, credential encryption, logs |
| `audit` | Immutable audit log + middleware |
| `analytics` | Dashboards, financial reports, CSV exports, platform settings |
| `ai_services` | Assistant, damage analysis, document classification/extraction, fraud indicators |

---

## 5. Data Model (core entities)

- **User** — email-based auth, role, verification flags, lockout counters, TOTP secret,
  token version. Linked one-to-one profiles: `CustomerProfile` (KYC), `AgentProfile`
  (commission rate), `InspectorProfile` (certification, capacity).
- **Organization** — insurer/agency/inspection/platform type, verification status,
  slug. Linked `Membership` (role per user), `OrganizationDocument`.
- **Vehicle** — registration, make/model/year, category, fuel, usage, value; soft-delete
  with a per-owner unique registration constraint. Linked `VehicleDocument`.
- **Insurer** — one-to-one with an Organization, rating, payout ratio. Linked `Product`
  (category, base premium rate, min premium, excess, benefits/exclusions, version) and
  `CoverageOption`.
- **QuotationRequest** — customer, vehicle, coverage type, sum insured, status
  (pending → quoted → selected → converted / expired / cancelled), expiry.
- **Quotation** — insurer + product, premium, excess, benefits, validity, source
  (`internal` engine or `provider_api`).
- **Application** — one-to-one quotation, customer, agent (optional), status
  (draft → submitted → under_review → more_info → approved/rejected → policy_issued).
- **Policy** — policy number, cover period, premium, sum insured, status
  (active → expired/lapsed/cancelled), certificate, renewal-reminder tracking.
- **Claim** — policy, type, incident, amount, status state machine, officer, decision,
  settlement. Linked `ClaimDocument` (with SHA-256 checksum) and `ClaimStatusHistory`.
- **Inspection** — vehicle/application/policy/claim links, type, status
  (requested → scheduled → in_progress → completed/cancelled), report. Linked `DamageRecord`.
- **Payment** — purpose, method (mpesa/card/bank), status, amount, idempotency key,
  provider references, receipt. Linked `Transaction` (charge/refund), `Refund`, `Commission`
  (agent- or dealership-attributed).
- **Business network** — `DealerBranch`, `DealerVehicle` (+ photos), `Partnership`
  (insurer–dealer, many-to-many), `PartnershipRequest`, `PartnershipActivity`,
  `CustomerConsent`, `PartnershipCommissionTerms`, and dealership/partnership/consent
  attribution on `QuotationRequest` and `Application`.

All primary keys are UUIDs. Most mutable records are time-stamped; vehicles/products use
soft deletion.

---

## 6. Authentication and Security

### 6.1 Authentication
- JWT (SimpleJWT): short-lived **access token** (30 min) and **refresh token** (7 days),
  rotated on refresh with blacklisting of the old token.
- **Token versioning**: a `token_version` claim on the token; changing or resetting a
  password increments the user's version, invalidating all outstanding tokens immediately.
- **2FA (TOTP)**: users can enable an authenticator-app second factor; login then requires
  an OTP step via a short-lived, cache-backed challenge.
- Email verification and password-reset flows (token delivered via Celery email task).
- Account lockout after 5 failed logins (15 minutes) plus per-scope rate throttling
  (anonymous, authenticated, auth, webhook).

### 6.2 Authorization
- Role-based permission classes (`IsPlatformAdmin`, `IsSuperAdmin`, `IsCustomer`,
  `IsProviderUser`, `IsInspector`, `IsClaimsOfficer`, `IsOrgMember`, etc.).
- **Tenant scoping**: every list/detail queryset is filtered to the caller's organizations
  (e.g., a provider only sees their insurer's applications, quotes, claims, payments).
  Centralized helpers (`user_org_ids`, `user_insurer_ids`) reduce drift.

### 6.3 Data protection & hardening
- Production config guard — the app refuses to start with `DEBUG=False` and an insecure
  `SECRET_KEY` or wildcard `ALLOWED_HOSTS`.
- TLS/transport headers: HSTS, secure session/CSRF cookies, SSL redirect, `X-Frame-Options:
  DENY`, `Content-Type: nosniff`, referrer policy.
- Integration credentials encrypted at rest (Fernet) with an env-derived key.
- File-upload allowlist (extension + declared MIME + size) on all document/image fields.
- Payment callbacks: M-Pesa callback is idempotent and always re-queried against Daraja
  before marking a payment successful; optional IP allowlist; amount/checkout validation.
- Payment idempotency keys prevent duplicate charges.
- Request IDs for log correlation; optional Sentry error tracking and Prometheus metrics.
- Immutable audit log of business actions.

---

## 7. Functional Modules

### 7.1 Public site
Landing page with entry points to sign in and get covered.

### 7.2 Accounts & profile
Registration (customer or provider-with-organization), login (JWT + optional 2FA),
email verification, password change/reset, profile management, KYC submission and
admin KYC review.

### 7.3 Vehicles
Customer garage of vehicles with documents; ownership-scoped access; inspectors and
providers see vehicles linked to their organization's work.

### 7.4 Marketplace & quotations
Customers request quotations for a vehicle; the platform's internal pricing engine
(`compute_premium`) generates quotations from every verified insurer's matching active
product (base rate + usage surcharge, floored at minimum premium). Providers can also
submit manual (provider-API) quotations. Quotations can be selected, and requests expire
automatically (scheduled task).

### 7.5 Applications & policies
Selecting a quotation leads to an application (draft → submitted → review → more-info →
approved/rejected). On approval, the customer pays the premium; on verified payment the
provider issues a policy (with optional KYC enforcement). Policies support renewal and
automatic lapse/expiry.

### 7.6 Agent-assisted sales
Agents (or provider staff) can create an application on behalf of a customer from any open
marketplace quotation, attributing themselves. When the policy is issued, a commission is
automatically generated using the agent's rate; commissions are then approved and paid.

### 7.7 Claims
Customers file claims against active policies (validated against coverage period and sum
insured). Claims follow a strict state machine:

```
submitted → under_review → info_required → under_review
          → inspection_scheduled → assessment → approved → settled → closed
          → rejected → closed
```

Claims officers assign officers, request information, schedule inspections, assess,
approve (with amount), settle (with reference) and close. Customers can respond to
information requests. Documents are checksummed and AI-classified; every transition is
recorded in a status history.

### 7.8 Inspections
Inspections are requested (pre-insurance, claim-assessment, renewal, periodic), scheduled
to an inspector and organization, started, and completed with damage records by vehicle
zone (front/rear bumpers, doors, panels, wheels, lights, interior, engine) and an optional
AI-assisted damage image analysis. The frontend renders a 3D vehicle for zone selection.

### 7.9 Payments
- **M-Pesa**: Daraja STK push to the customer's phone; callback reconciles via a Daraja
  query (never trusts the callback alone).
- **Card**: Flutterwave hosted checkout; payment verified against Flutterwave.
- **Bank**: manual reconciliation by authorized provider staff.
- Refunds with balance enforcement; receipts; a full transaction ledger.

### 7.10 Notifications
In-app notifications (with unread count and mark-read) delivered through a channel
abstraction (in-app always; email/SMS opt-in). Claim messaging between customer and
provider.

### 7.11 Integrations
Insurer REST/webhook integration registry with encrypted credentials, a generic REST
adapter (retry, logging, connection test), and webhook event logging. New quotation
requests are pushed to enabled integrations as a best-effort background task.

### 7.12 Analytics & reporting
Role-specific dashboards (admin, provider, customer, inspector), financial reports by
method/purpose/period, provider performance, and CSV exports (payments, policies, claims,
users). Dashboard aggregates are cached.

### 7.13 AI services
A rules-based insurance assistant, heuristic image damage analysis (with a pluggable
remote vision provider), document classification/extraction, duplicate-document detection
(SHA-256), and fraud indicators (duplicate payment references, repeated failures, pending
backlogs, multiple claims per vehicle, high claim frequency, claims near the sum insured).
All AI output is advisory and marked `requires_human_review`.

### 7.14 Audit
Business actions (application approved, policy issued, claim settled, etc.) are written to
an immutable audit log with actor, entity, changes, IP and user-agent.

### 7.15 Business Network (insurer–dealer ecosystem)
A dedicated module that connects insurance companies and motor-vehicle dealerships:

- **Registration**: insurers and dealerships register independently with company details,
  regulatory/representative information and logos; both start `pending` and are reviewed by
  platform administrators (verify / request-more-info / reject / suspend / reactivate) with a
  recorded status history.
- **Discovery**: verified businesses discover one another (insurers discover dealerships and
  vice versa) with search, filters and per-viewer partnership status.
- **Partnerships**: a many-to-many insurer–dealer relationship with a full lifecycle
  (pending → under review → more-info → approved → active → suspended → terminated). Requests
  carry a message, response note, responder and timestamps; duplicate active partnerships are
  prevented at the database level; every action is audited and notified.
- **Dealership inventory**: branches and vehicles (with photos, transmission, mileage,
  condition, asking price, and AVAILABLE/RESERVED/SOLD/UNAVAILABLE status), strictly scoped to
  the owning dealership.
- **Dealer-to-insurer transactions**: a dealership selects an inventory vehicle and customer,
  records explicit customer consent, and requests quotations from connected insurers (quotes
  restricted to the selected insurer). The existing quotation/application/payment/policy engine
  is reused, with every dealer-originated record attributed to the dealership, branch,
  partnership and consent.
- **Commissions**: partnership-level commission terms (fixed or percentage, optionally per
  product) drive automatic dealer referral commissions on policy issuance, tracked with the
  originating dealership.

---

## 8. End-to-End Workflows (verified)

1. **Quote-to-policy**: register vehicle → request quotation → 2 quotes generated →
   select → create application → submit → provider approves → pay premium → provider
   verifies → issue policy (active).
2. **Agent sale**: agent opens marketplace → creates application for a customer →
   provider approves/pays/issues → commission auto-created → approved → paid.
3. **Claim**: file claim → officer reviews → requests info → customer responds →
   schedule inspection → assess → approve → settle → close.
4. **Inspection**: request → schedule to inspector → start → record damage → complete.
5. **Onboarding**: provider registers organization → admin verifies → insurer profile
   auto-created; customer submits KYC → admin approves.

---

## 9. Background Automation (Celery beat)

| Task | Schedule |
|---|---|
| Reconcile pending M-Pesa payments | every 2 min |
| Reconcile pending card payments | every 2 min |
| Timeout stale payments | every 15 min |
| Expire quotation requests | hourly |
| Lapse expired policies | daily |
| Send renewal reminders | daily |

Email/notification dispatch and integration pushes run as asynchronous Celery tasks.

---

## 10. Testing and Verification

- **91 automated tests** passing (accounts, insurance, claims, payments, inspections,
  organizations, vehicles, analytics, ai_services, integrations).
- `manage.py check` and `makemigrations --check` are clean.
- A live end-to-end walkthrough exercised every role and module against a running server,
  covering quotation, application, payment, policy, claim, inspection, commission,
  renewal, KYC, 2FA and administration.

---

## 11. Deployment

- **Docker**: multi-stage backend image (gunicorn + entrypoint that runs migrations and
  collectstatic); frontend image (build + nginx serving the SPA and proxying `/api`,
  `/media`, `/static`, `/admin`).
- **Docker Compose**: `db` (Postgres), `redis`, `web`, `worker` (Celery), `beat`
  (scheduler), `frontend` (nginx).
- **CI**: GitHub Actions runs backend `check`, `makemigrations --check`, and tests, plus
  the frontend build.
- **Health**: `/health/` and `/api/v1/health/` endpoints (database + cache checks).

---

## 12. Remaining / Deferred Work

The following are noted as future work rather than missing requirements:

- PostgreSQL full-text search (current search uses `icontains`).
- Frontend TypeScript migration and frontend unit tests.
- Live third-party credentials for M-Pesa, Flutterwave and the remote AI provider
  (code paths are implemented; sandbox smoke-testing is required before go-live).
- Prometheus metrics are wired but disabled by default (`PROMETHEUS_METRICS_ENABLED`).
- Load/penetration testing and a compliance/DR runbook.

---

## 13. Conclusion

AutoInsure Connect is a complete, production-oriented vehicle insurance platform. It
implements the full insurance value chain — marketplace quotations, applications,
underwriting, payments, policy issuance, inspections, claims, commissions and renewals —
with a hardened JWT/2FA authentication layer, tenant-scoped authorization, background
automation, observability, and a role-based admin back office. The system is containerized,
covered by an automated test suite, and has been verified end-to-end.

**AutoInsure Connect — Connecting vehicle owners, insurance providers and the future of digital insurance.**
