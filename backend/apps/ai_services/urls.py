from django.urls import path

from .views import (
    AssistantView,
    ClaimRiskIndicatorsView,
    DamageAnalysisView,
    DocumentClassifyView,
    DocumentExtractView,
    DuplicateCheckView,
    RiskIndicatorsView,
)

urlpatterns = [
    path("assistant/", AssistantView.as_view(), name="ai-assistant"),
    path("damage-analysis/", DamageAnalysisView.as_view(), name="ai-damage"),
    path("document-classify/", DocumentClassifyView.as_view(), name="ai-doc-classify"),
    path("document-extract/", DocumentExtractView.as_view(), name="ai-doc-extract"),
    path("duplicates/<uuid:claim_id>/", DuplicateCheckView.as_view(), name="ai-duplicates"),
    path("risk-indicators/", RiskIndicatorsView.as_view(), name="ai-risk"),
    path("claim-risk/", ClaimRiskIndicatorsView.as_view(), name="ai-claim-risk"),
]
