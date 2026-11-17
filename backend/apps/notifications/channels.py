"""Notification delivery channels.

`notify()` fans out to every enabled channel. In-app is always on; email and
SMS are opt-in via ``NOTIFICATION_CHANNELS`` so that transactional workflows
don't spam users unless the operator enables them.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class InAppChannel:
    name = "in_app"

    def send(self, user, title, message, category="system", link=""):
        from .models import Notification

        return Notification.objects.create(
            user=user, title=title, message=message, category=category, link=link
        )


class EmailChannel:
    name = "email"

    def send(self, user, title, message, category="system", link=""):
        if not getattr(user, "email", None):
            return None
        from apps.common.utils import safe_enqueue

        from .tasks import send_notification_email

        return safe_enqueue(send_notification_email, user.id, title, message, link)


class SmsChannel:
    name = "sms"

    def send(self, user, title, message, category="system", link=""):
        # SMS requires a provider (e.g. Africa's Talking). Without one, this is
        # a deliberate no-op so we never pretend an SMS was delivered.
        if not getattr(user, "phone", None):
            return None
        logger.info("SMS channel not configured; skipping SMS to %s", user.phone)
        return None


_CHANNELS = {
    "in_app": InAppChannel,
    "email": EmailChannel,
    "sms": SmsChannel,
}


def get_channels():
    names = settings.NOTIFICATION_CHANNELS
    return [_CHANNELS[name]() for name in names if name in _CHANNELS]
