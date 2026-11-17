from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health(_request):
    return JsonResponse({"status": "ok", "service": "autoinssure-connect"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/v1/", include("apps.common.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/organizations/", include("apps.organizations.urls")),
    path("api/v1/business-network/", include("apps.business_network.urls")),
    path("api/v1/vehicles/", include("apps.vehicles.urls")),
    path("api/v1/", include("apps.insurance.urls")),
    path("api/v1/inspections/", include("apps.inspections.urls")),
    path("api/v1/claims/", include("apps.claims.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/finance/", include("apps.finance.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/integrations/", include("apps.integrations.urls")),
    path("api/v1/ai/", include("apps.ai_services.urls")),
    path("api/v1/admin/", include("apps.analytics.urls")),
    path("api/v1/analytics/", include("apps.analytics.analytics_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.PROMETHEUS_METRICS_ENABLED:
    urlpatterns += [path("", include("django_prometheus.urls"))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
