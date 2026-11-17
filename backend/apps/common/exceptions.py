from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        detail = response.data
        if isinstance(detail, dict) and "detail" in detail:
            message = detail["detail"]
        elif isinstance(detail, dict):
            parts = []
            for field, errors in detail.items():
                if isinstance(errors, (list, tuple)):
                    parts.append(f"{field}: {', '.join(str(e) for e in errors)}")
                else:
                    parts.append(f"{field}: {errors}")
            message = "; ".join(parts)
        elif isinstance(detail, list):
            message = "; ".join(str(e) for e in detail)
        else:
            message = str(detail)
        response.data = {
            "success": False,
            "error": {
                "code": getattr(exc, "default_code", "error"),
                "message": message,
                "details": detail,
            },
        }
    return response
