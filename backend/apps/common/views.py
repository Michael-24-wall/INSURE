from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            db_ok = False

        cache_ok = True
        try:
            from django.core.cache import cache

            cache.set("__healthcheck__", 1, 5)
            cache_ok = cache.get("__healthcheck__") == 1
        except Exception:
            cache_ok = False

        healthy = db_ok and cache_ok
        return Response(
            {
                "status": "ok" if healthy else "degraded",
                "database": db_ok,
                "cache": cache_ok,
            },
            status=200 if healthy else 503,
        )


class MetaView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.accounts.models import User
        from apps.insurance.models import Product

        return Response(
            {
                "service": "AutoInsure Connect",
                "version": "1.0.0",
                "roles": [r[0] for r in User.Role.choices],
                "product_categories": [c[0] for c in Product.Category.choices],
            }
        )
