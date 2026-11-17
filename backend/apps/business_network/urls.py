from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CustomerConsentViewSet,
    DealerBranchViewSet,
    DealerCustomerSearchView,
    DealerQuotationRequestView,
    DealerVehicleViewSet,
    DealershipDiscoverViewSet,
    InsurerDiscoverViewSet,
    PartnershipRequestViewSet,
    PartnershipViewSet,
)

router = DefaultRouter()
router.register("insurers", InsurerDiscoverViewSet, basename="network-insurers")
router.register("dealerships", DealershipDiscoverViewSet, basename="network-dealerships")
router.register("partnerships", PartnershipViewSet, basename="partnerships")
router.register("partnership-requests", PartnershipRequestViewSet, basename="partnership-requests")
router.register("branches", DealerBranchViewSet, basename="dealer-branches")
router.register("inventory", DealerVehicleViewSet, basename="dealer-inventory")
router.register("consents", CustomerConsentViewSet, basename="customer-consents")

urlpatterns = [
    path("dealer/quotations/", DealerQuotationRequestView.as_view(), name="dealer-quotations"),
    path("dealer/customers/", DealerCustomerSearchView.as_view(), name="dealer-customers"),
    path("", include(router.urls)),
]
