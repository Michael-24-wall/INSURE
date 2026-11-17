from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApplicationViewSet,
    InsurerViewSet,
    PolicyViewSet,
    ProductViewSet,
    QuotationRequestViewSet,
    QuotationViewSet,
)

router = DefaultRouter()
router.register("insurers", InsurerViewSet, basename="insurers")
router.register("products", ProductViewSet, basename="products")
router.register("quotations", QuotationViewSet, basename="quotations")
router.register("quotation-requests", QuotationRequestViewSet, basename="quotation-requests")
router.register("applications", ApplicationViewSet, basename="applications")
router.register("policies", PolicyViewSet, basename="policies")

urlpatterns = [path("", include(router.urls))]
