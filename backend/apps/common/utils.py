import logging
import secrets
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_reference(prefix: str, length: int = 8) -> str:
    stamp = timezone.now().strftime("%y%m%d")
    rand = secrets.token_hex(length // 2).upper()
    return f"{prefix}-{stamp}-{rand}"


def add_days(days: int):
    return timezone.now() + timedelta(days=days)


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def safe_enqueue(task, *args, **kwargs):
    """Queue a Celery task without ever raising (best-effort dispatch).

    A broker outage must never break the synchronous request path.
    """
    try:
        return task.delay(*args, **kwargs)
    except Exception:
        logger.exception("Failed to enqueue task %s", getattr(task, "name", task))
        return None
