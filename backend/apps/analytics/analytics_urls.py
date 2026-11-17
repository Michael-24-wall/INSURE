from django.urls import path

from .views import DashboardView, FinancialReportView, ProviderPerformanceView

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("reports/financial/", FinancialReportView.as_view(), name="financial-report"),
    path("providers/performance/", ProviderPerformanceView.as_view(), name="provider-performance"),
]
