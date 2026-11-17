"""Request correlation and logging helpers."""
import logging
import threading
import uuid

_local = threading.local()


def get_request_id():
    return getattr(_local, "request_id", None)


class RequestIdMiddleware:
    """Assign a correlation id to each request and echo it back.

    Uses the client-supplied ``X-Request-ID`` header when present (trusted only
    as an identifier, never for authorisation), otherwise generates one.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        _local.request_id = request_id
        try:
            response = self.get_response(request)
        finally:
            _local.request_id = None
        response["X-Request-ID"] = request_id
        return response


class RequestIdLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id() or "-"
        return True
