# AutoInsure Connect

A full-stack insurance platform covering customer acquisition, insurer underwriting,
quotation → application → payment → policy issuance, claims, inspections, commissions,
notifications, analytics and an audit trail.

## Stack

- **Backend**: Django 5.2 + Django REST Framework 3.16, SQLite (dev) / PostgreSQL (prod),
  Celery + Redis, JWT auth, M-Pesa Daraja / Flutterwave card gateways, heuristic AI services.
- **Frontend**: React 18 + Vite 5 + Tailwind 3 + React Router 6 + TanStack Query 5 + Axios.

## Layout

```
backend/    Django project (config/ + apps/)
frontend/   React SPA
docker-compose.yml   PostgreSQL + Redis + web + celery worker/beat + nginx SPA
```

## Quickstart (development)

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows (Git Bash: source .venv/Scripts/activate)
pip install -r requirements.txt
cp .env.example .env              # then set DJANGO_SECRET_KEY, etc.
python manage.py migrate
python manage.py seed_demo        # creates demo accounts and sample data
python manage.py runserver
```

The API is served at `http://127.0.0.1:8000/api/v1/`.

### Frontend

```bash
cd frontend
npm install
npm run dev                       # http://127.0.0.1:5173
```

Vite proxies `/api` and `/media` to the backend (see `frontend/vite.config.js`).

## Demo accounts

| Role          | Email                        | Password        |
| ------------- | ---------------------------- | --------------- |
| Super admin   | `admin@autoinssure.local`    | `Admin@12345`   |
| Customer      | `customer@example.com`       | `Customer@12345`|
| Insurer       | `insurer@example.com`        | `Insurer@12345` |
| Claims officer| `claims@example.com`         | `Claims@12345`  |
| Inspector     | `inspector@example.com`      | `Inspector@12345`|
| Agent         | `agent@example.com`          | `Agent@12345`   |

## Roles

`customer`, `provider_admin`, `provider_staff`, `agent`, `inspector`,
`claims_officer`, `dealer_admin`, `dealer_staff`, `admin`, `super_admin`.

Role home routes: `/app` (customer), `/provider`, `/agent`, `/inspector`,
`/dealer`, `/claims`, `/admin`.

## Insurance lines

Motor insurance (`comprehensive`, `third party`, `third party/fire/theft`,
`commercial`, `motorcycle`) is operational end-to-end. The other nine lines
(health, life, business, property, travel, marine, agriculture, accident and
liability) are surfaced in the UI as "expanding" and have no backend pricing or
product workflow yet — the platform never generates fictitious quotes or premiums
for them.

## Testing

```bash
# Backend (run from backend/)
python manage.py test --parallel 4          # 159 tests

# Frontend unit tests (frontend/)
npm test -- --run                           # 26 tests

# Frontend lint (frontend/)
npm run lint

# Production build (frontend/)
npm run build

# Browser end-to-end (frontend/) — isolated e2e.sqlite3, backend :8001, Vite :5174
npm run test:e2e                            # 6 journeys
```

The E2E suite uses a disposable `backend/e2e.sqlite3` and `backend/e2e-media/` and
never touches the development database.

## Production (Docker)

```bash
cp backend/.env.example backend/.env   # fill in DJANGO_SECRET_KEY and gateway creds
DJANGO_SECRET_KEY=<strong-secret> docker compose up --build
```

The SPA is served on port `80` (nginx) and proxies `/api`, `/media`, `/static`
and `/admin` to the Django `web` service.

## Key configuration (`backend/.env`)

- `DATABASE_URL` — empty for SQLite, otherwise `postgresql://…`.
- `CELERY_TASK_ALWAYS_EAGER=True` for local dev (no Redis needed).
- M-Pesa: `M_PESA_*` (leave blank to disable; payments then require authorised
  manual reconciliation — success is never auto-marked without verification).
- Card: `FLW_*` (Flutterwave).
- AI: `AI_PROVIDER=heuristic` by default.

## Notes

- Payment success is **evidence-based**: M-Pesa/card payments are never marked
  successful without a gateway verification or authorised manual reconciliation.
- Organization verification is required before insurer products are tradeable.
- Every sensitive state change is captured in the audit log.

See also: `PROJECT_STATUS.md`, `SECURITY.md`, `AUTOINSURE_SYSTEM_REPORT.md`,
`PAYMENT_GATEWAY_SANDBOX.md`.
