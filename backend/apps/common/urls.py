from django.urls import path

from .views import HealthView, MetaView

urlpatterns = [
    path("health/", HealthView.as_view(), name="api-health"),
    path("meta/", MetaView.as_view(), name="api-meta"),
]
