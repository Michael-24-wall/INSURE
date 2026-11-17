from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit.services import log_action
from apps.common.files import protected_file_response
from apps.common.models import is_platform_admin, user_org_ids
from apps.common.utils import generate_reference
from apps.inspections.models import Inspection
from apps.notifications.services import notify

from .models import Claim, ClaimDocument, ClaimStatusHistory
from .serializers import (
    AssignOfficerSerializer,
    ClaimCreateSerializer,
    ClaimDecisionSerializer,
    ClaimDocumentSerializer,
    ClaimInfoSerializer,
    ClaimInspectionSerializer,
    ClaimRejectSerializer,
    ClaimSerializer,
    ClaimSettleSerializer,
)
from .services import transition


class ClaimViewSet(viewsets.ModelViewSet):
    serializer_class = ClaimSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "claim_type", "policy", "officer"]
    search_fields = ["claim_number", "customer__email", "policy__policy_number", "location"]
    ordering_fields = ["created_at", "incident_date", "amount_claimed", "status"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = Claim.objects.select_related(
            "customer", "policy", "policy__insurer", "policy__vehicle", "officer"
        ).prefetch_related("documents", "status_history", "inspections")
        user = self.request.user
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.CUSTOMER:
            return qs.filter(customer=user)
        return qs.filter(policy__insurer__organization_id__in=user_org_ids(user))

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.CUSTOMER and not is_platform_admin(request.user):
            raise PermissionDenied("Only customers can submit claims.")
        serializer = ClaimCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        claim = serializer.save(
            claim_number=generate_reference("CLM", 10),
            customer=request.user,
            status=Claim.Status.SUBMITTED,
        )
        ClaimStatusHistory.objects.create(
            claim=claim, from_status="", to_status=Claim.Status.SUBMITTED, changed_by=request.user, notes="Claim submitted"
        )
        if claim.policy.insurer.organization_id:
            from apps.organizations.models import Membership

            officers = [
                m.user
                for m in Membership.objects.filter(
                    organization_id=claim.policy.insurer.organization_id,
                    is_active=True,
                    user__role__in=[User.Role.CLAIMS_OFFICER, User.Role.PROVIDER_ADMIN],
                ).select_related("user")
            ]
            for u in officers:
                notify(u, "New claim submitted", f"{claim.claim_number} requires attention.", "claim")
        notify(request.user, "Claim submitted", f"Claim {claim.claim_number} was submitted.", "claim")
        log_action(request.user, "claim.submitted", claim)
        return Response(ClaimSerializer(claim).data, status=status.HTTP_201_CREATED)

    def _assert_provider(self, claim, user):
        if is_platform_admin(user):
            return
        if user.role not in {
            User.Role.PROVIDER_ADMIN,
            User.Role.PROVIDER_STAFF,
            User.Role.CLAIMS_OFFICER,
        }:
            raise PermissionDenied("Only claims staff can manage this claim.")
        if claim.policy.insurer.organization_id not in user_org_ids(user):
            raise PermissionDenied("Not allowed for this claim.")

    def _advance(self, claim, target, actor, notes=""):
        try:
            return transition(claim, target, actor, notes)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    @action(detail=True, methods=["post"], url_path="assign-officer")
    def assign_officer(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        if request.user.role not in {User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF} and not is_platform_admin(request.user):
            raise PermissionDenied("Only provider administrators can assign claims.")
        serializer = AssignOfficerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        officer = User.objects.filter(
            pk=serializer.validated_data["officer"],
            role__in=[User.Role.CLAIMS_OFFICER, User.Role.PROVIDER_ADMIN],
        ).first()
        if not officer:
            raise ValidationError({"officer": "Claims officer not found."})
        claim.officer = officer
        claim.save(update_fields=["officer"])
        notify(officer, "Claim assigned", f"{claim.claim_number} was assigned to you.", "claim")
        notify(claim.customer, "Claims officer assigned", "A claims officer is now handling your claim.", "claim")
        log_action(request.user, "claim.officer_assigned", claim, changes={"officer": str(officer.id)})
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        self._advance(claim, Claim.Status.UNDER_REVIEW, request.user, request.data.get("notes", ""))
        notify(claim.customer, "Claim under review", f"{claim.claim_number} is under review.", "claim")
        log_action(request.user, "claim.review_started", claim)
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"], url_path="request-info")
    def request_info(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        serializer = ClaimInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._advance(claim, Claim.Status.INFO_REQUIRED, request.user, serializer.validated_data["notes"])
        notify(claim.customer, "Additional information required", serializer.validated_data["notes"], "claim")
        log_action(request.user, "claim.info_requested", claim)
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        claim = self.get_object()
        if claim.customer_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the claimant can respond.")
        if claim.status != Claim.Status.INFO_REQUIRED:
            raise ValidationError("This claim is not awaiting your response.")
        notes = request.data.get("notes", "").strip() or "Customer provided additional information."
        self._advance(claim, Claim.Status.UNDER_REVIEW, request.user, notes)
        from apps.organizations.models import Membership

        officers = Membership.objects.filter(
            organization_id=claim.policy.insurer.organization_id,
            is_active=True,
            user__role__in=[User.Role.CLAIMS_OFFICER, User.Role.PROVIDER_ADMIN],
        ).select_related("user")
        for m in officers:
            notify(m.user, "Claim response received", f"{claim.claim_number} was updated by the customer.", "claim")
        log_action(request.user, "claim.customer_responded", claim, changes={"notes": notes})
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"], url_path="schedule-inspection")
    def schedule_inspection(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        if claim.status not in {Claim.Status.UNDER_REVIEW, Claim.Status.INSPECTION_SCHEDULED}:
            raise ValidationError("Start the claim review before scheduling an inspection.")
        serializer = ClaimInspectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inspector = User.objects.filter(pk=serializer.validated_data["inspector"], role=User.Role.INSPECTOR).first()
        if not inspector:
            raise ValidationError({"inspector": "Inspector not found."})
        inspection = Inspection.objects.create(
            inspection_number=generate_reference("INS", 10),
            organization=claim.policy.insurer.organization,
            inspector=inspector,
            requested_by=request.user,
            vehicle=claim.policy.vehicle,
            claim=claim,
            policy=claim.policy,
            inspection_type=Inspection.Type.CLAIM_ASSESSMENT,
            status=Inspection.Status.SCHEDULED,
            scheduled_at=serializer.validated_data["scheduled_at"],
            location=serializer.validated_data["location"],
        )
        if claim.status in {Claim.Status.UNDER_REVIEW, Claim.Status.INSPECTION_SCHEDULED}:
            if claim.status == Claim.Status.UNDER_REVIEW:
                self._advance(claim, Claim.Status.INSPECTION_SCHEDULED, request.user, "Inspection scheduled")
        notify(inspector, "Claim inspection assigned", f"{inspection.inspection_number} for {claim.claim_number}.", "inspection")
        notify(claim.customer, "Inspection scheduled", "An inspector has been assigned to your claim.", "claim")
        log_action(request.user, "claim.inspection_scheduled", claim, changes={"inspection": inspection.inspection_number})
        return Response(ClaimSerializer(claim).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def assess(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        if claim.status != Claim.Status.INSPECTION_SCHEDULED:
            raise ValidationError("Only claims with a scheduled inspection can move to assessment.")
        self._advance(claim, Claim.Status.ASSESSMENT, request.user, request.data.get("notes", ""))
        notify(claim.customer, "Claim under assessment", f"{claim.claim_number} is being assessed.", "claim")
        log_action(request.user, "claim.assessment_started", claim)
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        serializer = ClaimDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data.get("approved_amount") or claim.amount_claimed
        if approved > claim.amount_claimed:
            raise ValidationError({"approved_amount": "Approved amount cannot exceed the claimed amount."})
        claim.approved_amount = approved
        claim.decision_notes = serializer.validated_data.get("notes", "")
        claim.save(update_fields=["approved_amount", "decision_notes"])
        self._advance(claim, Claim.Status.APPROVED, request.user, claim.decision_notes)
        notify(claim.customer, "Claim approved", f"{claim.claim_number} approved for {approved}.", "claim")
        log_action(request.user, "claim.approved", claim, changes={"approved_amount": str(approved)})
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        serializer = ClaimRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        claim.decision_notes = serializer.validated_data["notes"]
        claim.save(update_fields=["decision_notes"])
        self._advance(claim, Claim.Status.REJECTED, request.user, claim.decision_notes)
        notify(claim.customer, "Claim rejected", claim.decision_notes, "claim")
        log_action(request.user, "claim.rejected", claim)
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        serializer = ClaimSettleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if claim.status != Claim.Status.APPROVED:
            raise ValidationError("Only approved claims can be settled.")
        amount = serializer.validated_data["settled_amount"]
        if amount > (claim.approved_amount or claim.amount_claimed):
            raise ValidationError({"settled_amount": "Settlement cannot exceed the approved amount."})
        claim.settled_amount = amount
        claim.settlement_reference = serializer.validated_data["settlement_reference"]
        claim.save(update_fields=["settled_amount", "settlement_reference"])
        self._advance(claim, Claim.Status.SETTLED, request.user, f"Settled: {amount}")
        notify(claim.customer, "Claim settled", f"{claim.claim_number} settled for {amount}.", "claim")
        log_action(request.user, "claim.settled", claim, changes={"settled_amount": str(amount)})
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        claim = self.get_object()
        self._assert_provider(claim, request.user)
        self._advance(claim, Claim.Status.CLOSED, request.user, request.data.get("notes", ""))
        log_action(request.user, "claim.closed", claim)
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        claim = self.get_object()
        if claim.customer_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the claimant can withdraw.")
        self._advance(claim, Claim.Status.WITHDRAWN, request.user, request.data.get("notes", ""))
        log_action(request.user, "claim.withdrawn", claim)
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["get", "post"], url_path="documents", parser_classes=[MultiPartParser, FormParser, JSONParser])
    def documents(self, request, pk=None):
        claim = self.get_object()
        if request.method == "GET":
            return Response(
                ClaimDocumentSerializer(
                    claim.documents.all(), many=True, context=self.get_serializer_context()
                ).data
            )
        if claim.customer_id != request.user.id and claim.policy.insurer.organization_id not in user_org_ids(request.user):
            if not is_platform_admin(request.user):
                raise PermissionDenied("Not allowed.")
        serializer = ClaimDocumentSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        doc = serializer.save(claim=claim, uploaded_by=request.user)
        if doc.file:
            try:
                from apps.ai_services.services import classify_document

                result = classify_document(doc.file)
                doc.ai_classification = result.get("category", "")
                doc.ai_confidence = result.get("confidence")
                doc.save(update_fields=["ai_classification", "ai_confidence"])
            except Exception:
                pass
        log_action(request.user, "claim.document_uploaded", claim, changes={"document": str(doc.id)})
        return Response(
            ClaimDocumentSerializer(doc, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path=r"documents/(?P<doc_id>[^/.]+)/download",
        url_name="document-download",
    )
    def download_document(self, request, pk=None, doc_id=None):
        claim = self.get_object()
        if claim.customer_id != request.user.id and claim.policy.insurer.organization_id not in user_org_ids(request.user):
            if not is_platform_admin(request.user):
                raise PermissionDenied("Not allowed.")
        doc = get_object_or_404(ClaimDocument, pk=doc_id, claim=claim)
        response = protected_file_response(doc.file)
        if response is None:
            return Response({"detail": "Document file is unavailable."}, status=404)
        log_action(
            request.user,
            "claim.document_downloaded",
            claim,
            changes={"document": str(doc.id), "filename": doc.file.name},
        )
        return response

    @action(detail=True, methods=["delete"], url_path=r"documents/(?P<doc_id>[^/.]+)")
    def delete_document(self, request, pk=None, doc_id=None):
        claim = self.get_object()
        doc = get_object_or_404(ClaimDocument, pk=doc_id, claim=claim)
        if doc.uploaded_by_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the uploader can delete this document.")
        doc.file.delete(save=False)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
