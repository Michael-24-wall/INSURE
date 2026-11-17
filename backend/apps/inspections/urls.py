from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InspectionViewSet

router = DefaultRouter()
router.register("", InspectionViewSet, basename="inspections")

urlpatterns = [path("", include(router.urls))]
