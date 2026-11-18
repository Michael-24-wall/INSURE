"""Django settings for AutoInsure Connect."""
import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


if "test" in sys.argv:
    os.environ.setdefault("THROTTLE_ANON", "100000/minute")
    os.environ.setdefault("THROTTLE_USER", "100000/minute")
    os.environ.setdefault("THROTTLE_AUTH", "100000/minute")
    os.environ.setdefault("THROTTLE_WEBHOOK", "100000/minute")
    os.environ.setdefault("THROTTLE_AI", "100000/minute")
    os.environ.setdefault("THROTTLE_SEARCH", "100000/minute")

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me-in-production")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

# Fail fast rather than run insecurely in production. These guards only fire
# when DEBUG is disabled, so local development is unaffected.
_INSECURE_SECRETS = {"", "dev-insecure-change-me-in-production", "change-me", "change-me-too"}
if not DEBUG and SECRET_KEY in _INSECURE_SECRETS:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a strong, random value when DJANGO_DEBUG is off."
    )
if not DEBUG and ("*" in ALLOWED_HOSTS or not ALLOWED_HOSTS):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list explicit hostnames when DJANGO_DEBUG is off."
    )

# Prometheus metrics. Off by default; enable to instrument requests, cache and
# the database, and expose the /metrics endpoint (restrict access at the edge).
PROMETHEUS_METRICS_ENABLED = env_bool("PROMETHEUS_METRICS_ENABLED", False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.business_network",
    "apps.vehicles",
    "apps.insurance",
    "apps.inspections",
    "apps.claims",
    "apps.payments",
    "apps.finance",
    "apps.notifications",
    "apps.integrations",
    "apps.audit",
    "apps.analytics",
    "apps.ai_services",
    "django_prometheus",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.RequestIdMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
]

if PROMETHEUS_METRICS_ENABLED:
    MIDDLEWARE.insert(0, "django_prometheus.middleware.PrometheusBeforeMiddleware")
    MIDDLEWARE.append("django_prometheus.middleware.PrometheusAfterMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    import dj_database_url  # type: ignore

    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

if PROMETHEUS_METRICS_ENABLED:
    _PROMETHEUS_ENGINES = {
        "django.db.backends.postgresql": "django_prometheus.db.backends.postgresql",
        "django.db.backends.sqlite3": "django_prometheus.db.backends.sqlite3",
        "django.db.backends.mysql": "django_prometheus.db.backends.mysql",
    }
    for _db in DATABASES.values():
        _engine = _db.get("ENGINE", "")
        if _engine in _PROMETHEUS_ENGINES:
            _db["ENGINE"] = _PROMETHEUS_ENGINES[_engine]

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.tokens.VersionedJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", "120/minute"),
        "user": env("THROTTLE_USER", "1200/minute"),
        "auth": env("THROTTLE_AUTH", "10/minute"),
        "webhook": env("THROTTLE_WEBHOOK", "300/minute"),
        "ai": env("THROTTLE_AI", "30/minute"),
        "search": env("THROTTLE_SEARCH", "300/hour"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AutoInsure Connect API",
    "DESCRIPTION": "Multi-tenant motor insurance platform API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", 30))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", 7))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CORS_ALLOWED_ORIGINS = [
    o.strip() for o in env("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

# TLS / transport hardening. Defaults are safe for production (behind a TLS
# terminator) and relaxed for local development via environment variables.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", 31536000 if not DEBUG else 0))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", "same-origin")

# Celery / Redis
REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    "reconcile-pending-mpesa": {
        "task": "apps.payments.tasks.reconcile_pending_mpesa",
        "schedule": 120.0,
    },
    "reconcile-pending-card": {
        "task": "apps.payments.tasks.reconcile_pending_card",
        "schedule": 120.0,
    },
    "timeout-stale-payments": {
        "task": "apps.payments.tasks.timeout_stale_payments",
        "schedule": 900.0,
    },
    "expire-quotation-requests": {
        "task": "apps.insurance.tasks.expire_quotation_requests",
        "schedule": 3600.0,
    },
    "lapse-expired-policies": {
        "task": "apps.insurance.tasks.lapse_expired_policies",
        "schedule": 86400.0,
    },
    "send-renewal-reminders": {
        "task": "apps.insurance.tasks.send_renewal_reminders",
        "schedule": 86400.0,
    },
}

# Caching: local memory by default, Redis in production.
if env("CACHE_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("CACHE_URL")}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Integration / secrets
CREDENTIAL_ENCRYPTION_KEY = env("CREDENTIAL_ENCRYPTION_KEY", "")
M_PESA_CONSUMER_KEY = env("M_PESA_CONSUMER_KEY", "")
M_PESA_CONSUMER_SECRET = env("M_PESA_CONSUMER_SECRET", "")
M_PESA_SHORTCODE = env("M_PESA_SHORTCODE", "")
M_PESA_PASSKEY = env("M_PESA_PASSKEY", "")
M_PESA_CALLBACK_URL = env("M_PESA_CALLBACK_URL", "https://example.com/api/v1/payments/mpesa/callback/")
M_PESA_ENV = env("M_PESA_ENV", "sandbox")
M_PESA_SANDBOX_MODE = env_bool("M_PESA_SANDBOX_MODE", True)
# Optional IP allowlist for the M-Pesa callback (Safaricom's egress ranges).
# Empty means no IP filtering. The authoritative verification remains the
# Daraja STK query, which is performed regardless of the source IP.
M_PESA_ALLOWED_IPS = [ip.strip() for ip in env("M_PESA_ALLOWED_IPS", "").split(",") if ip.strip()]
# Only trust X-Forwarded-For when the app is behind a trusted reverse proxy.
# Trusting it by default allows callers to spoof the allowlist.
M_PESA_TRUST_FORWARDED_FOR = env_bool("M_PESA_TRUST_FORWARDED_FOR", False)

# Card gateway (Flutterwave hosted checkout). Blank means the card method is
# disabled and users must use M-Pesa or bank transfer.
FLW_SECRET_KEY = env("FLW_SECRET_KEY", "")
FLW_PUBLIC_KEY = env("FLW_PUBLIC_KEY", "")
FLW_ENV = env("FLW_ENV", "sandbox")
# Flutterwave dashboard webhook hash. When set, callbacks without a matching
# `verif-hash` header are rejected before any payment lookup or verification.
FLW_WEBHOOK_HASH = env("FLW_WEBHOOK_HASH", "")
CARD_REDIRECT_URL = env("CARD_REDIRECT_URL", "http://localhost:5173/app/payments")

# Payment automation.
PAYMENT_MPESA_TIMEOUT_MINUTES = int(env("PAYMENT_MPESA_TIMEOUT_MINUTES", 15))
PAYMENT_BANK_TIMEOUT_DAYS = int(env("PAYMENT_BANK_TIMEOUT_DAYS", 7))
PAYMENT_CARD_TIMEOUT_MINUTES = int(env("PAYMENT_CARD_TIMEOUT_MINUTES", 30))

# Compliance. Enable in production to block policy issuance until the
# policyholder's KYC is verified.
KYC_REQUIRED_FOR_POLICY_ISSUANCE = env_bool("KYC_REQUIRED_FOR_POLICY_ISSUANCE", False)

# Default reporting currency. Used only when a record does not carry an
# explicit currency (e.g. premium tracking for a policy with no payment yet).
DEFAULT_CURRENCY = env("DEFAULT_CURRENCY", "KES")

# Caching TTL for dashboard aggregates.
DASHBOARD_CACHE_SECONDS = int(env("DASHBOARD_CACHE_SECONDS", 60))

# TOTP two-factor authentication.
TOTP_ISSUER = env("TOTP_ISSUER", "AutoInsure Connect")
TOTP_CHALLENGE_SECONDS = int(env("TOTP_CHALLENGE_SECONDS", 300))

# Error tracking (optional; disabled unless a DSN is provided and DEBUG is off).
SENTRY_DSN = env("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", "development")
if SENTRY_DSN and not DEBUG:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", 0.1)),
        send_default_pii=False,
    )

# AI providers
AI_PROVIDER = env("AI_PROVIDER", "heuristic")
AI_API_KEY = env("AI_API_KEY", "")
AI_API_URL = env("AI_API_URL", "")
AI_MODEL = env("AI_MODEL", "gpt-4o")

FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@autoinssure.local")
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "20"))

# Notification delivery channels enabled for `notify()`. In-app is always on;
# email and SMS are opt-in. Transactional auth emails (verification, password
# reset) are always sent regardless of this setting.
NOTIFICATION_CHANNELS = [c.strip() for c in env("NOTIFICATION_CHANNELS", "in_app").split(",") if c.strip()]

FILE_UPLOAD_MAX_MEMORY_SIZE = int(env("FILE_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(env("DATA_UPLOAD_MAX_MEMORY_SIZE", 25 * 1024 * 1024))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.common.middleware.RequestIdLogFilter"},
    },
    "formatters": {
        "structured": {
            "format": "%(asctime)s %(levelname)s %(name)s [req=%(request_id)s] %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "filters": ["request_id"],
        }
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
