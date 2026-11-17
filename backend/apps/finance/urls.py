from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CurrencyConfigViewSet,
    ExchangeRateViewSet,
    FinancialDashboardView,
    JournalEntryManualCreateView,
    JournalEntryViewSet,
    LedgerAccountViewSet,
    LedgerBalancesView,
    LedgerEntryViewSet,
    PlatformFeeViewSet,
    PremiumTrackingView,
    SettlementViewSet,
)

router = DefaultRouter()
router.register("ledger/accounts", LedgerAccountViewSet, basename="ledger-accounts")
router.register("ledger/journal-entries", JournalEntryViewSet, basename="ledger-journal-entries")
router.register("ledger/entries", LedgerEntryViewSet, basename="ledger-entries")
router.register("settlements", SettlementViewSet, basename="settlements")
router.register("currency-configs", CurrencyConfigViewSet, basename="currency-configs")
router.register("exchange-rates", ExchangeRateViewSet, basename="exchange-rates")
router.register("platform-fees", PlatformFeeViewSet, basename="platform-fees")

urlpatterns = [
    path("dashboard/", FinancialDashboardView.as_view(), name="finance-dashboard"),
    path("ledger/balances/", LedgerBalancesView.as_view(), name="ledger-balances"),
    path("premium-tracking/<uuid:pk>/", PremiumTrackingView.as_view(), name="finance-premium-tracking"),
    path("journal-entries/manual/", JournalEntryManualCreateView.as_view(), name="finance-journal-entry-manual"),
    path("", include(router.urls)),
]
