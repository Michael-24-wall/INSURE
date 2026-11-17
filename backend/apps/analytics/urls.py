from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminDashboardView,
    AuditLogViewSet,
    ExportView,
    PlatformSettingView,
)

router = DefaultRouter()
router.register("audit-logs", AuditLogViewSet, basename="audit-logs")

urlpatterns = [
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("settings/", PlatformSettingView.as_view(), name="platform-settings"),
    path("exports/<str:resource>/", ExportView.as_view(), name="admin-export"),
    path("", include(router.urls)),
]
