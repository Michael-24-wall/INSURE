import os

from django.http import FileResponse


def protected_file_response(file_field, filename=None):
    """Return a private, non-cacheable attachment for an authorised caller."""
    if not file_field:
        return None
    name = filename or os.path.basename(file_field.name or "document")
    response = FileResponse(
        file_field.open("rb"),
        as_attachment=True,
        filename=name,
        content_type="application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response
