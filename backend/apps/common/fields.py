"""Reusable DRF field helpers."""
from django.conf import settings
from rest_framework import serializers

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}
DOCUMENT_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf", ".doc", ".docx"}

# Declared MIME types we accept. This is client-supplied and therefore only a
# first line of defence; the magic-byte check below rejects known executables.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heic",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Leading bytes that unambiguously identify executable/script content. Files
# whose payload begins with one of these are rejected regardless of extension
# or declared MIME type.
DANGEROUS_MAGIC = (
    (b"\x7fELF", "ELF executable"),
    (b"MZ", "DOS/Windows executable"),
    (b"\xca\xfe\xba\xbe", "Mach-O executable"),
    (b"\xfe\xed\xfa\xce", "Mach-O executable"),
    (b"\xce\xfa\xed\xfe", "Mach-O executable"),
    (b"\xcf\xfa\xed\xfe", "Mach-O executable"),
    (b"#!", "script"),
)


def _has_dangerous_magic(file):
    try:
        file.seek(0)
        head = file.read(8)
        file.seek(0)
    except (OSError, ValueError):
        return None
    for magic, label in DANGEROUS_MAGIC:
        if head.startswith(magic):
            return label
    return None


def _ext(name):
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


class ValidatedFileField(serializers.FileField):
    """FileField that enforces an extension allowlist and a size cap.

    Pass ``allowed_extensions`` to restrict the allowlist (defaults to the
    document set). ``max_size`` defaults to ``FILE_UPLOAD_MAX_MEMORY_SIZE``.
    """

    default_error_messages = {
        "invalid_extension": "File type is not allowed. Allowed: {allowed}.",
        "invalid_content_type": "This file type cannot be uploaded.",
        "too_large": "File exceeds the maximum allowed size of {max_size} bytes.",
        "unsafe_content": "File content is not an allowed document type.",
    }

    def __init__(self, *, allowed_extensions=None, max_size=None, **kwargs):
        self.allowed_extensions = set(allowed_extensions or DOCUMENT_EXTENSIONS)
        self.max_size = max_size or settings.FILE_UPLOAD_MAX_MEMORY_SIZE
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        file = super().to_internal_value(data)
        if file is None:
            return file
        name = getattr(file, "name", "") or ""
        if self.allowed_extensions and _ext(name) not in self.allowed_extensions:
            self.fail("invalid_extension", allowed=", ".join(sorted(self.allowed_extensions)))
        size = getattr(file, "size", 0) or 0
        if self.max_size and size > self.max_size:
            self.fail("too_large", max_size=self.max_size)
        content_type = getattr(file, "content_type", None)
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            self.fail("invalid_content_type")
        if _has_dangerous_magic(file):
            self.fail("unsafe_content")
        return file
