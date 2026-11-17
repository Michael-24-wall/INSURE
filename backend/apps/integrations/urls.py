from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IntegrationViewSet, WebhookEventViewSet

router = DefaultRouter()
router.register("webhook-events", WebhookEventViewSet, basename="webhook-events")
router.register("", IntegrationViewSet, basename="integrations")

urlpatterns = [path("", include(router.urls))]
