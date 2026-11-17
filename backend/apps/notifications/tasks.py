"""Celery tasks for out-of-band notification delivery."""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task
def send_notification_email(user_id, title, message, link=""):
    from apps.accounts.models import User

    user = User.objects.filter(pk=user_id).first()
    if not user or not user.email:
        return
    body = message
    if link:
        url = link if link.startswith("http") else f"{settings.FRONTEND_URL}{link}"
        body = f"{message}\n\n{url}"
    send_mail(title, body, settings.DEFAULT_FROM_EMAIL, [user.email])


@shared_task
def send_verification_email(user_id, token):
    from apps.accounts.models import User

    user = User.objects.filter(pk=user_id).first()
    if not user or not user.email:
        return
    url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_mail(
        "Verify your AutoInsure Connect account",
        f"Welcome to AutoInsure Connect. Verify your email address to activate your account:\n\n{url}",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )


@shared_task
def send_password_reset_email(user_id, token):
    from apps.accounts.models import User

    user = User.objects.filter(pk=user_id).first()
    if not user or not user.email:
        return
    url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    send_mail(
        "Reset your AutoInsure Connect password",
        f"A password reset was requested for your account. Use the link below to choose a new password:\n\n{url}",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
