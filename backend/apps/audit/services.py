from .models import AuditLog
from .middleware import get_current_request


def log_action(actor, action, entity=None, entity_type=None, entity_id=None, changes=None, request=None):
    req = request or get_current_request()
    ip = None
    ua = ""
    if req is not None:
        forwarded = req.META.get("HTTP_X_FORWARDED_FOR")
        ip = (forwarded.split(",")[0].strip() if forwarded else req.META.get("REMOTE_ADDR")) or None
        ua = req.META.get("HTTP_USER_AGENT", "")[:255]
    if entity is not None:
        entity_type = entity_type or entity.__class__.__name__
        entity_id = entity_id or str(getattr(entity, "pk", ""))
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity_type=entity_type or "",
        entity_id=str(entity_id or ""),
        changes=changes or {},
        ip_address=ip,
        user_agent=ua,
    )
