"""Finance API: double-entry ledger, settlements, exchange rates and currency config."""
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.services import log_action
from apps.common.models import is_platform_admin, user_org_ids
from apps.common.permissions import IsPlatformAdmin
from apps.common.scoping import user_insurer_ids
from apps.insurance.models import Insurer, Policy

from .models import (
    CurrencyConfig,
    ExchangeRate,
    JournalEntry,
    LedgerAccount,
    LedgerEntry,
    PlatformFee,
    Settlement,
)
from .serializers import (
    CurrencyConfigSerializer,
    ExchangeRateSerializer,
    JournalEntryCreateSerializer,
    JournalEntrySerializer,
    LedgerAccountSerializer,
    LedgerEntrySerializer,
    PlatformFeeSerializer,
    SettlementCreateSerializer,
    SettlementSerializer,
    SettlementSettleSerializer,
)
from .services import (
    LedgerError,
    create_settlement_from_verified_payments,
    financial_dashboard,
    post_journal_entry,
    ledger_balances,
    premium_tracking_summary,
    reverse_journal_entry,
)


def _scope_journal_entries(user, qs):
    if is_platform_admin(user):
        return qs
    org_ids = user_org_ids(user)
    insurer_ids = user_insurer_ids(user)
    conditions = Q()
    if user.role == User.Role.CUSTOMER:
        conditions |= Q(payment__user=user) | Q(policy__customer=user)
    if insurer_ids:
        conditions |= Q(policy__insurer_id__in=insurer_ids)
        conditions |= Q(payment__application__quotation__insurer_id__in=insurer_ids)
        conditions |= Q(settlement__insurer__organization_id__in=org_ids)
    if org_ids:
        conditions |= Q(commission__dealership_id__in=org_ids)
        conditions |= Q(commission__organization_id__in=org_ids)
    if user.role == User.Role.AGENT:
        conditions |= Q(commission__agent=user)
    if not conditions:
        return qs.none()
    return qs.filter(conditions).distinct()


def _scope_settlements(user, qs):
    if is_platform_admin(user):
        return qs
    org_ids = user_org_ids(user)
    insurer_ids = user_insurer_ids(user)
    if insurer_ids:
        return qs.filter(insurer__organization_id__in=org_ids)
    return qs.none()


class FinancialDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        insurer_ids = None
        if not is_platform_admin(request.user):
            if request.user.role == User.Role.CUSTOMER:
                insurer_ids = None
            else:
                insurer_ids = user_insurer_ids(request.user)
        return Response(
            financial_dashboard(
                request.user,
                start=start,
                end=end,
                insurer_ids=insurer_ids,
            )
        )


class PremiumTrackingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        policy = get_object_or_404(Policy, pk=pk)
        user = request.user
        allowed = is_platform_admin(user) or policy.customer_id == user.id
        if not allowed and user_insurer_ids(user):
            allowed = policy.insurer_id in user_insurer_ids(user)
        if not allowed:
            raise PermissionDenied("You do not have access to this policy's financial records.")
        return Response(premium_tracking_summary(policy, policy.customer.full_name))


class LedgerBalancesView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        return Response(ledger_balances())


class LedgerAccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LedgerAccountSerializer
    permission_classes = [IsPlatformAdmin]
    filterset_fields = ["type", "currency", "is_active"]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name"]

    def get_queryset(self):
        return LedgerAccount.objects.all()


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = JournalEntrySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "currency", "payment", "policy", "claim", "commission", "settlement"]
    search_fields = ["reference", "description"]
    ordering_fields = ["created_at", "posted_at", "reference"]

    def get_queryset(self):
        return _scope_journal_entries(
            self.request.user,
            JournalEntry.objects.select_related("posted_by", "reversal_of").prefetch_related("entries__account"),
        )


    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        entry = self.get_object()
        if not is_platform_admin(request.user):
            raise PermissionDenied("Only platform finance administrators can reverse journal entries.")
        reason = request.data.get("reason") or "Manual reversal"
        try:
            reversed_entry = reverse_journal_entry(
                reference=f"REV-{entry.reference}",
                original_entry=entry,
                reason=reason,
                posted_by=request.user,
            )
        except LedgerError as exc:
            raise ValidationError({"detail": str(exc)})
        log_action(request.user, "finance.journal_entry_reversed", reversed_entry, changes={"original": entry.reference})
        return Response(JournalEntrySerializer(reversed_entry).data, status=status.HTTP_201_CREATED)


class JournalEntryManualCreateView(APIView):
    """Manually post a balanced journal entry (platform finance / platform admin only)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_platform_admin(request.user):
            raise PermissionDenied("Only platform finance administrators can post manual journal entries.")
        serializer = JournalEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            entry = post_journal_entry(
                reference=data["reference"],
                description=data["description"],
                lines=data["lines"],
                currency=data["currency"],
                posted_by=request.user,
            )
        except LedgerError as exc:
            raise ValidationError({"detail": str(exc)})
        log_action(request.user, "finance.journal_entry_posted", entry, changes={"reference": entry.reference})
        return Response(JournalEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class LedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LedgerEntrySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["direction", "currency", "account", "journal_entry"]
    ordering_fields = ["created_at", "amount"]

    def get_queryset(self):
        return _scope_journal_entries(
            self.request.user, LedgerEntry.objects.select_related("account", "journal_entry")
        )


class ExchangeRateViewSet(viewsets.ModelViewSet):
    serializer_class = ExchangeRateSerializer
    permission_classes = [IsPlatformAdmin]
    filterset_fields = ["from_currency", "to_currency"]
    ordering_fields = ["effective_at", "created_at"]

    def get_queryset(self):
        return ExchangeRate.objects.all()

    def perform_create(self, serializer):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage exchange rates.")
        serializer.save()

    def perform_update(self, serializer):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage exchange rates.")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage exchange rates.")
        instance.delete()


class SettlementViewSet(viewsets.ModelViewSet):
    serializer_class = SettlementSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "currency", "insurer"]
    ordering_fields = ["created_at", "amount_due", "amount_settled"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return _scope_settlements(
            self.request.user, Settlement.objects.select_related("insurer", "settled_by")
        )

    def perform_create(self, serializer):
        user = self.request.user
        if not is_platform_admin(user) and user.role not in {
            User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF, User.Role.ADMIN, User.Role.SUPER_ADMIN
        }:
            raise PermissionDenied("Only authorised staff can create insurer settlements.")
        insurer = serializer.validated_data.get("insurer")
        if not is_platform_admin(user) and insurer.organization_id not in user_org_ids(user):
            raise PermissionDenied("Not allowed to settle this insurer.")
        settlement = serializer.save()
        from apps.common.utils import generate_reference

        if not settlement.reference:
            settlement.reference = generate_reference("SET", 10)
            settlement.save(update_fields=["reference"])
        log_action(user, "finance.settlement.created", settlement, changes={"reference": settlement.reference})

    @action(detail=True, methods=["post"], url_path="instruct")
    def instruct(self, request, pk=None):
        settlement = self.get_object()
        if not is_platform_admin(request.user) and settlement.insurer.organization_id not in user_org_ids(request.user):
            raise PermissionDenied("Not allowed for this insurer.")
        if settlement.status != Settlement.Status.PENDING:
            raise ValidationError("Only pending settlements can be instructed.")
        settlement.status = Settlement.Status.INSTRUCTED
        settlement.save(update_fields=["status"])
        log_action(request.user, "finance.settlement.instructed", settlement)
        return Response(SettlementSerializer(settlement).data)

    @action(detail=True, methods=["post"], url_path="settle")
    def settle(self, request, pk=None):
        settlement = self.get_object()
        if not is_platform_admin(request.user) and settlement.insurer.organization_id not in user_org_ids(request.user):
            raise PermissionDenied("Not allowed for this insurer.")
        serializer = SettlementSettleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if settlement.status != Settlement.Status.INSTRUCTED:
            raise ValidationError("Only instructed settlements can be settled.")
        amount = settlement.amount_due  # full settlement of the amount due
        settlement.amount_settled = amount
        settlement.status = Settlement.Status.SETTLED
        settlement.settled_at = timezone.now()
        settlement.settled_by = request.user
        settlement.settlement_reference = serializer.validated_data.get("settlement_reference", "")
        settlement.reconciliation_notes = serializer.validated_data.get("reconciliation_notes", "")
        settlement.save()
        log_action(request.user, "finance.settlement.settled", settlement)
        return Response(SettlementSerializer(settlement).data)

    @action(detail=True, methods=["post"], url_path="reconcile")
    def reconcile(self, request, pk=None):
        settlement = self.get_object()
        if not is_platform_admin(request.user):
            raise PermissionDenied("Only platform finance administrators can reconcile settlements.")
        if settlement.status != Settlement.Status.SETTLED:
            raise ValidationError("Only settled settlements can be reconciled.")
        settlement.status = Settlement.Status.RECONCILED
        settlement.reconciliation_notes = request.data.get("reconciliation_notes", settlement.reconciliation_notes)
        settlement.save(update_fields=["status", "reconciliation_notes"])
        log_action(request.user, "finance.settlement.reconciled", settlement)
        return Response(SettlementSerializer(settlement).data)


class CurrencyConfigViewSet(viewsets.ModelViewSet):
    serializer_class = CurrencyConfigSerializer
    permission_classes = [IsPlatformAdmin]
    ordering_fields = ["country"]

    def get_queryset(self):
        return CurrencyConfig.objects.all()

    def perform_create(self, serializer):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage currency config.")
        serializer.save()

    def perform_update(self, serializer):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage currency config.")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage currency config.")
        instance.delete()


class PlatformFeeViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformFeeSerializer
    permission_classes = [IsPlatformAdmin]
    ordering_fields = ["code", "amount"]

    def get_queryset(self):
        return PlatformFee.objects.all()

    def perform_create(self, serializer):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage platform fees.")
        serializer.save()

    def perform_update(self, serializer):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage platform fees.")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform finance administrators can manage platform fees.")
        instance.delete()
