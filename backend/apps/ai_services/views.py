from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import viewsets

from apps.common.models import is_platform_admin, user_org_ids

from .models import AIServiceLog
from .services import (
    analyze_damage_image,
    classify_document,
    detect_duplicate_documents,
    extract_document_data,
    insurance_assistant,
    suspicious_claim_indicators,
    suspicious_payment_indicators,
)


class AssistantSerializer(serializers.Serializer):
    question = serializers.CharField()


class AIThrottledView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"


class AssistantView(AIThrottledView):
    def post(self, request):
        serializer = AssistantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = insurance_assistant(serializer.validated_data["question"], request.user)
        from django.utils import timezone

        AIServiceLog.objects.create(
            user=request.user,
            task="assistant",
            provider=result["provider"],
            input_summary=serializer.validated_data["question"][:255],
            output={"answer": result["answer"]},
        )
        return Response(result)


class DamageAnalysisView(AIThrottledView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image = request.FILES.get("image")
        if not image:
            return Response({"detail": "image is required"}, status=400)
        return Response(analyze_damage_image(image, request.user))


class DocumentClassifyView(AIThrottledView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file is required"}, status=400)
        return Response(classify_document(file, request.user))


class DocumentExtractView(AIThrottledView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file is required"}, status=400)
        return Response(extract_document_data(file, request.user))


class DuplicateCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, claim_id):
        from apps.claims.models import Claim

        claim = Claim.objects.filter(pk=claim_id).first()
        if not claim:
            return Response({"detail": "Claim not found."}, status=404)
        if not is_platform_admin(request.user):
            if claim.customer_id != request.user.id and claim.policy.insurer.organization_id not in user_org_ids(request.user):
                return Response({"detail": "Not allowed."}, status=403)
        return Response(detect_duplicate_documents(claim))


class RiskIndicatorsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {"admin", "super_admin", "provider_admin", "provider_staff", "claims_officer"} and not is_platform_admin(request.user):
            return Response({"detail": "Not allowed."}, status=403)
        insurer_ids = None
        if not is_platform_admin(request.user):
            from apps.common.scoping import user_insurer_ids

            insurer_ids = user_insurer_ids(request.user)
        return Response(suspicious_payment_indicators(request.user, insurer_ids=insurer_ids))


class ClaimRiskIndicatorsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {"admin", "super_admin", "provider_admin", "provider_staff", "claims_officer"} and not is_platform_admin(request.user):
            return Response({"detail": "Not allowed."}, status=403)
        insurer_ids = None
        if not is_platform_admin(request.user):
            from apps.common.scoping import user_insurer_ids

            insurer_ids = user_insurer_ids(request.user)
        return Response(suspicious_claim_indicators(insurer_ids))


class AIServiceLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from apps.common.models import is_platform_admin

        qs = AIServiceLog.objects.select_related("user")
        if is_platform_admin(self.request.user):
            return qs
        return qs.filter(user=self.request.user)
