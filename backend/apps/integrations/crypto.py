import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _key():
    raw = settings.CREDENTIAL_ENCRYPTION_KEY
    if raw:
        digest = hashlib.sha256(raw.encode()).digest()
    else:
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return Fernet(_key()).encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return Fernet(_key()).decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError):
        return ""
