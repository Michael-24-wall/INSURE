from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CardCallbackView,
    CommissionViewSet,
    MpesaCallbackView,
    PaymentViewSet,
    RefundViewSet,
    TransactionViewSet,
)

router = DefaultRouter()
router.register("transactions", TransactionViewSet, basename="transactions")
router.register("refunds", RefundViewSet, basename="refunds")
router.register("commissions", CommissionViewSet, basename="commissions")
router.register("", PaymentViewSet, basename="payments")

urlpatterns = [
    path("mpesa/callback/", MpesaCallbackView.as_view(), name="mpesa-callback"),
    path("card/callback/", CardCallbackView.as_view(), name="card-callback"),
    path("", include(router.urls)),
]
