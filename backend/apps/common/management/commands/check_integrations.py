"""Report external integration readiness without printing secrets."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Report M-Pesa, Flutterwave, email, SMS, and storage configuration status."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit non-zero when a required production integration is incomplete.",
        )

    def handle(self, *args, **options):
        checks = self._checks()
        if options["json"]:
            self.stdout.write(json.dumps(checks, indent=2))
        else:
            self._print_table(checks)

        missing = [name for name, check in checks.items() if check["required"] and not check["ready"]]
        if options["strict"] and missing:
            raise CommandError("Integration configuration incomplete: " + ", ".join(missing))

    def _checks(self):
        mpesa_fields = [
            "M_PESA_CONSUMER_KEY",
            "M_PESA_CONSUMER_SECRET",
            "M_PESA_SHORTCODE",
            "M_PESA_PASSKEY",
        ]
        mpesa_missing = [name for name in mpesa_fields if not getattr(settings, name, "")]
        callback = getattr(settings, "M_PESA_CALLBACK_URL", "")
        if not callback.startswith("https://") or "example.com" in callback:
            mpesa_missing.append("M_PESA_CALLBACK_URL")
        if getattr(settings, "M_PESA_ENV", "sandbox") not in {"sandbox", "production"}:
            mpesa_missing.append("M_PESA_ENV")
        if not getattr(settings, "M_PESA_ALLOWED_IPS", []):
            mpesa_missing.append("M_PESA_ALLOWED_IPS")

        flw_fields = ["FLW_SECRET_KEY", "FLW_PUBLIC_KEY", "FLW_WEBHOOK_HASH"]
        flw_missing = [name for name in flw_fields if not getattr(settings, name, "")]
        if getattr(settings, "FLW_ENV", "sandbox") not in {"sandbox", "production"}:
            flw_missing.append("FLW_ENV")

        email_backend = settings.EMAIL_BACKEND
        email_missing = []
        if email_backend == "django.core.mail.backends.console.EmailBackend":
            email_missing.append("EMAIL_BACKEND")
        elif email_backend == "django.core.mail.backends.smtp.EmailBackend":
            for name in ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD"):
                if not getattr(settings, name, ""):
                    email_missing.append(name)
            if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
                email_missing.append("EMAIL_USE_TLS/EMAIL_USE_SSL conflict")
        email_ready = not email_missing
        channels = list(settings.NOTIFICATION_CHANNELS)
        sms_requested = "sms" in channels
        sms_ready = False
        sms_missing = ["SMS provider adapter is not implemented; use in-app or email"]

        storage_backend = settings.STORAGES["default"]["BACKEND"]
        s3_ready = "s3" in storage_backend.lower()
        storage_missing = [] if s3_ready else ["S3-compatible private storage is not activated"]
        insecure_encryption_keys = {"", "change-me", "change-me-too"}
        encryption_ready = settings.CREDENTIAL_ENCRYPTION_KEY not in insecure_encryption_keys
        encryption_missing = [] if encryption_ready else ["CREDENTIAL_ENCRYPTION_KEY"]

        return {
            "mpesa": {
                "ready": not mpesa_missing,
                "required": True,
                "environment": settings.M_PESA_ENV,
                "missing": mpesa_missing,
            },
            "flutterwave": {
                "ready": not flw_missing,
                "required": True,
                "environment": settings.FLW_ENV,
                "missing": flw_missing,
            },
            "email": {
                "ready": email_ready,
                "required": "email" in channels,
                "backend": email_backend,
                "configured_channels": channels,
                "missing": email_missing,
            },
            "sms": {
                "ready": sms_ready,
                "required": sms_requested,
                "implemented": False,
                "missing": sms_missing,
            },
            "storage": {
                "ready": s3_ready,
                "required": False,
                "backend": storage_backend,
                "media_root": str(settings.MEDIA_ROOT),
                "missing": storage_missing,
            },
            "credential_encryption": {
                "ready": encryption_ready,
                "required": True,
                "missing": encryption_missing,
            },
        }

    def _print_table(self, checks):
        names = {
            "mpesa": "M-Pesa Daraja",
            "flutterwave": "Flutterwave cards",
            "email": "Email delivery",
            "sms": "SMS delivery",
            "storage": "Private storage",
            "credential_encryption": "Integration secret encryption",
        }
        self.stdout.write("Integration configuration status (secrets are never printed):")
        for key, check in checks.items():
            if check["ready"]:
                status = "READY"
            elif check["required"]:
                status = "MISSING"
            else:
                status = "NOT CONFIGURED"
            detail = ", ".join(check["missing"]) if check["missing"] else "configured"
            self.stdout.write(f"- {names[key]}: {status} ({detail})")
        self.stdout.write("")
        self.stdout.write("No external credentials were created or modified.")
