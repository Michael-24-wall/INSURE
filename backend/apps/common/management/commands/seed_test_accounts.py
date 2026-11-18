"""Create idempotent local/E2E test accounts for every supported role."""
import json
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import AgentProfile, CustomerProfile, InspectorProfile, User
from apps.common.test_accounts import TEST_ACCOUNTS, TEST_ACCOUNT_ORGS
from apps.insurance.models import Insurer
from apps.organizations.models import Membership, Organization


def _new_password():
    return f"Qa!{secrets.token_urlsafe(18)}"


class Command(BaseCommand):
    help = "Create or refresh idempotent local/E2E test accounts for all supported roles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-local",
            action="store_true",
            help="Allow a non-E2E local database. The command never deletes existing users or organizations.",
        )
        parser.add_argument(
            "--rotate-passwords",
            action="store_true",
            help="Generate and store new passwords for existing QA accounts.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        database_name = str(connection.settings_dict.get("NAME", "") or "")
        self._database_name = database_name
        if not settings.DEBUG:
            raise CommandError("seed_test_accounts only runs with DJANGO_DEBUG=True.")
        if "e2e" not in database_name.lower() and not options["allow_local"]:
            raise CommandError(
                "Refusing a non-E2E database without --allow-local "
                f"(current database: {database_name or 'unknown'})."
            )

        previous = self._read_previous()
        accounts = []
        users = {}

        for spec in TEST_ACCOUNTS:
            user = User.objects.filter(email__iexact=spec["email"]).first()
            created = user is None
            password = previous.get(spec["email"])
            if created or options["rotate_passwords"]:
                password = _new_password()

            if created:
                user = User.objects.create_user(
                    email=spec["email"],
                    password=password,
                    first_name=spec["first_name"],
                    last_name=spec["last_name"],
                    role=spec["role"],
                    phone="+254700000000",
                    email_verified=True,
                    is_staff=bool(spec.get("is_staff")),
                    is_superuser=bool(spec.get("is_superuser")),
                )
            else:
                if user.role != spec["role"]:
                    raise CommandError(
                        f"{spec['email']} exists with role '{user.role}', expected '{spec['role']}'."
                    )
                changed = []
                if not user.email_verified:
                    user.email_verified = True
                    changed.append("email_verified")
                if spec.get("is_staff") and not user.is_staff:
                    user.is_staff = True
                    changed.append("is_staff")
                if spec.get("is_superuser") and not user.is_superuser:
                    user.is_superuser = True
                    changed.append("is_superuser")
                if options["rotate_passwords"]:
                    user.set_password(password)
                    changed.append("password")
                if changed:
                    user.save(update_fields=changed)

            users[spec["key"]] = user
            accounts.append({"spec": spec, "user": user, "password": password})

        verified_by = users.get("admin") or users.get("superadmin")
        organizations = self._ensure_organizations(verified_by)
        self._ensure_profiles_and_memberships(accounts, organizations)
        self._write_credentials(accounts, organizations, database_name)

        self.stdout.write(self.style.SUCCESS(f"Test accounts ready in {database_name}."))
        self.stdout.write(f"Credentials: {self._credentials_path()}")
        self.stdout.write(f"Machine-readable: {self._json_path()}")

    def _ensure_organizations(self, verified_by):
        organizations = {}
        for spec in TEST_ACCOUNT_ORGS:
            org = Organization.objects.filter(name=spec["name"]).first()
            if org is None:
                org = Organization.objects.create(
                    name=spec["name"],
                    organization_type=spec["organization_type"],
                    registration_number=spec["registration_number"],
                    email=f"{spec['registration_number'].lower()}@example.com",
                    phone="+254700000000",
                    status=Organization.Status.VERIFIED,
                    verified_at=timezone.now(),
                    verified_by=verified_by,
                )
            else:
                if org.organization_type != spec["organization_type"]:
                    raise CommandError(
                        f"{spec['name']} exists as '{org.organization_type}', "
                        f"expected '{spec['organization_type']}'."
                    )
                changed = []
                if org.status != Organization.Status.VERIFIED:
                    org.status = Organization.Status.VERIFIED
                    changed.append("status")
                if org.verified_at is None:
                    org.verified_at = timezone.now()
                    changed.append("verified_at")
                if org.verified_by_id is None and verified_by is not None:
                    org.verified_by = verified_by
                    changed.append("verified_by")
                if changed:
                    org.save(update_fields=changed)

            if spec["organization_type"] == Organization.Type.INSURER:
                Insurer.objects.update_or_create(
                    organization=org,
                    defaults={
                        "display_name": spec["display_name"],
                        "license_number": spec["license_number"],
                        "description": "Isolated insurer for QA and E2E testing.",
                        "is_active": True,
                    },
                )
            organizations[spec["key"]] = org
        return organizations

    def _ensure_profiles_and_memberships(self, accounts, organizations):
        for account in accounts:
            spec = account["spec"]
            user = account["user"]

            if spec.get("profile") == "customer":
                CustomerProfile.objects.update_or_create(
                    user=user, defaults={"kyc_status": "verified"}
                )
            elif spec.get("profile") == "agent":
                AgentProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "license_number": f"QA-AGENT-{spec['key'].upper()}",
                        "commission_rate": 10,
                        "region": "Nairobi",
                        "is_verified": True,
                    },
                )
            elif spec.get("profile") == "inspector":
                InspectorProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "certification_number": "QA-INSPECTOR-001",
                        "region": "Nairobi",
                        "is_verified": True,
                        "capacity_per_day": 8,
                    },
                )

            for membership in spec.get("memberships", ()):
                Membership.objects.update_or_create(
                    user=user,
                    organization=organizations[membership["org"]],
                    defaults={"role": membership["role"], "is_active": True},
                )

    def _read_previous(self):
        path = self._json_path()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {
            account.get("email"): account.get("password")
            for account in payload.get("accounts", [])
            if account.get("email") and account.get("password")
        }

    def _write_credentials(self, accounts, organizations, database_name):
        payload_accounts = []
        for account in accounts:
            spec = account["spec"]
            org_names = [
                organizations[membership["org"]].name
                for membership in spec.get("memberships", ())
            ]
            payload_accounts.append(
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "role": spec["role"],
                    "role_label": spec["role_label"],
                    "email": spec["email"],
                    "password": account["password"],
                    "home": spec["home"],
                    "organizations": org_names,
                    "notes": spec["notes"],
                }
            )

        generated_at = timezone.now().isoformat()
        payload = {
            "generated_at": generated_at,
            "database": str(database_name),
            "accounts": payload_accounts,
        }
        self._json_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")

        rows = [
            "| Role | Email | Password | Home | Organization | Notes |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for account in payload_accounts:
            password = account["password"] or "(existing password unchanged)"
            organizations_text = ", ".join(account["organizations"]) or "Platform"
            rows.append(
                f"| {account['label']} | {account['email']} | `{password}` | "
                f"`{account['home']}` | {organizations_text} | {account['notes']} |"
            )

        content = "\n".join(
            [
                "# INSURECONNECT Test Credentials",
                "",
                "> LOCAL AND E2E TEST ACCOUNTS ONLY. Do not use these credentials in production.",
                "> This file is gitignored because it contains generated test passwords.",
                "",
                f"- Generated: `{generated_at}`",
                f"- Database: `{database_name}`",
                "- Create/refresh: `python manage.py seed_test_accounts --allow-local`",
                "- E2E accounts are refreshed by `npm run prepare:e2e`.",
                "",
                *rows,
                "",
                "## Role mapping notes",
                "",
                "- There is no dedicated Underwriter role; the underwriter test account uses Provider Staff.",
                "- There is no dedicated Finance Officer role; the finance test account uses Provider Staff.",
                "- There is no dedicated Broker role; the broker test account uses Agent in an agency organization.",
                "- Platform ledger balances, manual journal posting, and settlement reconciliation remain Platform Admin only.",
                "",
            ]
        )
        self._credentials_path().write_text(content, encoding="utf-8")

    def _credentials_path(self) -> Path:
        name = (
            "INSURECONNECT_TEST_CREDENTIALS_E2E.md"
            if "e2e" in self._database_name.lower()
            else "INSURECONNECT_TEST_CREDENTIALS.md"
        )
        return settings.BASE_DIR.parent / name

    def _json_path(self) -> Path:
        name = (
            ".test-accounts.e2e.json"
            if "e2e" in self._database_name.lower()
            else ".test-accounts.json"
        )
        return settings.BASE_DIR / name
