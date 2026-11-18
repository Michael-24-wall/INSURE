# INSURECONNECT Account Setup Status

## Status

Test accounts are available for isolated local development and the disposable E2E database. The setup command is idempotent and never deletes users, organizations, policies, payments, or accounting records.

- Local development database: **13 QA users created** in the existing `backend/db.sqlite3` without reset.
- Local QA organizations: **3** (`QA Test Insurer`, `QA Test Agency`, `QA Test Dealership`).
- Local QA memberships: **10**.
- Generated credentials: `INSURECONNECT_TEST_CREDENTIALS.md` (gitignored).
- Machine-readable account data: `backend/.test-accounts.json` (gitignored).
- E2E database: refreshed by `npm run prepare:e2e`; `seed_e2e` clears prior QA fixtures and `seed_test_accounts` recreates them.

Passwords are generated with `secrets.token_urlsafe` and are unique per account. Do not reuse them outside local/E2E testing.

## Command

```bash
cd backend
python manage.py seed_test_accounts --allow-local
```

For the disposable E2E database, the same command is run automatically by `npm run prepare:e2e` after `seed_e2e`. Use `--rotate-passwords` only when an explicit rotation is needed. The command refuses `DJANGO_DEBUG=False` and refuses a non-E2E database unless `--allow-local` is supplied.

## Accounts and role mapping

| Test role | Application role | Home | Organization |
| --- | --- | --- | --- |
| Platform super admin | `super_admin` | `/admin` | Platform |
| Platform admin | `admin` | `/admin` | Platform |
| Insurer admin | `provider_admin` | `/provider` | QA Test Insurer |
| Insurer staff | `provider_staff` | `/provider` | QA Test Insurer |
| Underwriter | `provider_staff` | `/provider` | QA Test Insurer |
| Claims officer | `claims_officer` | `/claims` | QA Test Insurer |
| Finance officer | `provider_staff` | `/provider` | QA Test Insurer |
| Vehicle inspector | `inspector` | `/inspector` | QA Test Insurer |
| Insurance agent | `agent` | `/agent` | QA Test Insurer |
| Insurance broker | `agent` | `/agent` | QA Test Agency |
| Dealer admin | `dealer_admin` | `/dealer` | QA Test Dealership |
| Dealer staff | `dealer_staff` | `/dealer` | QA Test Dealership |
| Customer | `customer` | `/app` | Platform |

## Role limitations

- **Underwriter:** no dedicated model role exists; mapped to provider staff.
- **Finance officer:** no dedicated model role exists; mapped to provider staff. Platform ledger balances, manual journal posting, and settlement reconciliation remain platform-admin-only.
- **Broker:** no dedicated model role exists; mapped to agent with an agency membership.
- **Additional supported roles:** dealer staff, claims officer, inspector, agent, platform admin, and super admin are covered.

## Data safety

- The local command uses `get_or_create`/`update_or_create` and does not clear the development database.
- Existing accounts with a conflicting role are rejected rather than overwritten.
- E2E still uses its separate `backend/e2e.sqlite3` and `backend/e2e-media/` resources.
- No production database, production media, external account, payment, SMS, or email was created or changed.
- No accounting accounts, postings, chart of accounts, or migrations were added or modified.
