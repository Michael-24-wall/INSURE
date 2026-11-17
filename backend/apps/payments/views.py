import hmac
import logging
from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import AgentProfile, User
from apps.audit.services import log_action
from apps.common.models import is_platform_admin, user_org_ids
from apps.insurance.models import Application, Policy
from apps.integrations.models import WebhookEvent
from apps.notifications.services import notify

from .models import Commission, Payment, Refund, Transaction
from .serializers import (
    CommissionCreateSerializer,
    CommissionSerializer,
    InitiatePaymentSerializer,
    PaymentSerializer,
    RefundCreateSerializer,
    RefundSerializer,
    TransactionSerializer,
    VerifyPaymentSerializer,
)
from .services import (
    PaymentError,
    complete_payment,
    create_refund,
    gateway_status,
    handle_stk_callback,
    initiate_premium_payment,
    verify_card_payment,
)

logger = logging.getLogger(__name__)


def _scope_payments(user):
    qs = Payment.objects.select_related(
        "user", "application", "policy", "claim", "application__quotation__insurer"
    ).prefetch_related("transactions", "refunds")
    if is_platform_admin(user):
        return qs
    if user.role == User.Role.CUSTOMER:
        return qs.filter(user=user)
    org_ids = user_org_ids(user)
    return qs.filter(
        Q(application__quotation__insurer__organization_id__in=org_ids)
        | Q(policy__insurer__organization_id__in=org_ids)
        | Q(claim__policy__insurer__organization_id__in=org_ids)
    ).distinct()


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "method", "purpose"]
    search_fields = ["reference", "provider_reference", "receipt_number", "user__email"]
    ordering_fields = ["created_at", "amount"]

    def get_queryset(self):
        return _scope_payments(self.request.user)

    @action(detail=False, methods=["post"], url_path="initiate")
    def initiate(self, request):
        if request.user.role != User.Role.CUSTOMER and not is_platform_admin(request.user):
            raise PermissionDenied("Only customers can initiate premium payments.")
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = get_object_or_404(
            Application, pk=serializer.validated_data["application"], customer=request.user
        )
        idem = request.headers.get("Idempotency-Key")
        try:
            payment, created = initiate_premium_payment(
                request.user,
                application,
                serializer.validated_data["method"],
                serializer.validated_data.get("phone", ""),
                idem,
            )
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)})
        log_action(request.user, "payment.initiated", payment)
        return Response(
            {"payment": PaymentSerializer(payment).data, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="gateways")
    def gateways(self, request):
        return Response(gateway_status())

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        payment = self.get_object()
        if not is_platform_admin(request.user):
            insurer_org_id = None
            if payment.application_id:
                insurer_org_id = payment.application.quotation.insurer.organization_id
            elif payment.policy_id:
                insurer_org_id = payment.policy.insurer.organization_id
            elif payment.claim_id:
                insurer_org_id = payment.claim.policy.insurer.organization_id
            if insurer_org_id not in user_org_ids(request.user):
                raise PermissionDenied("Only authorised provider staff or administrators can verify payments.")
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = complete_payment(
                payment.id,
                provider_reference=serializer.validated_data["provider_reference"],
                raw={"notes": serializer.validated_data.get("notes", ""), "manual": True},
                actor=request.user,
            )
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)})
        log_action(request.user, "payment.verified", payment, changes={"reference": payment.provider_reference})
        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        payment = self.get_object()
        if not is_platform_admin(request.user):
            insurer_org_id = None
            if payment.application_id:
                insurer_org_id = payment.application.quotation.insurer.organization_id
            elif payment.policy_id:
                insurer_org_id = payment.policy.insurer.organization_id
            elif payment.claim_id:
                insurer_org_id = payment.claim.policy.insurer.organization_id
            if insurer_org_id not in user_org_ids(request.user):
                raise PermissionDenied("Only authorised provider staff or administrators can refund payments.")
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refund = create_refund(
                payment, serializer.validated_data["amount"], serializer.validated_data["reason"], request.user
            )
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)})
        log_action(request.user, "payment.refunded", payment, changes={"refund": refund.reference, "amount": str(refund.amount)})
        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="receipt")
    def receipt(self, request, pk=None):
        payment = self.get_object()
        if payment.status != Payment.Status.SUCCEEDED:
            raise ValidationError("A receipt is only available for successful payments.")
        return Response(
            {
                "receipt_number": payment.receipt_number,
                "reference": payment.reference,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "method": payment.method,
                "paid_by": payment.user.full_name,
                "paid_at": payment.verified_at,
                "provider_reference": payment.provider_reference,
                "purpose": payment.purpose,
            }
        )


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["type", "status", "payment"]
    ordering_fields = ["created_at", "amount"]

    def get_queryset(self):
        payments = _scope_payments(self.request.user).values_list("id", flat=True)
        return Transaction.objects.filter(payment_id__in=payments)


class RefundViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status"]

    def get_queryset(self):
        payments = _scope_payments(self.request.user).values_list("id", flat=True)
        return Refund.objects.filter(payment_id__in=payments)


class CommissionViewSet(viewsets.ModelViewSet):
    serializer_class = CommissionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "policy", "agent"]
    ordering_fields = ["created_at", "amount"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = Commission.objects.select_related("policy", "agent", "organization", "dealership")
        user = self.request.user
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.AGENT:
            return qs.filter(agent=user)
        if user.role in {User.Role.DEALER_ADMIN, User.Role.DEALER_STAFF}:
            return qs.filter(dealership_id__in=user_org_ids(user))
        return qs.filter(
            Q(organization_id__in=user_org_ids(user))
            | Q(policy__insurer__organization_id__in=user_org_ids(user))
        ).distinct()

    def create(self, request, *args, **kwargs):
        if request.user.role not in {User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF, User.Role.ADMIN, User.Role.SUPER_ADMIN}:
            raise PermissionDenied("Only provider staff or administrators can create commissions.")
        serializer = CommissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = get_object_or_404(Policy, pk=serializer.validated_data["policy"])
        if not is_platform_admin(request.user) and policy.insurer.organization_id not in user_org_ids(request.user):
            raise PermissionDenied("Not allowed for this policy.")
        agent = None
        if serializer.validated_data.get("agent"):
            agent = User.objects.filter(pk=serializer.validated_data["agent"], role=User.Role.AGENT).first()
            if not agent:
                raise ValidationError({"agent": "Agent not found."})
        rate = serializer.validated_data.get("rate")
        if rate is None:
            profile = AgentProfile.objects.filter(user=agent).first() if agent else None
            rate = profile.commission_rate if profile else Decimal("10.00")
        amount = (policy.premium * rate / Decimal("100")).quantize(Decimal("0.01"))
        commission = Commission.objects.create(
            policy=policy,
            agent=agent,
            organization=policy.insurer.organization,
            rate=rate,
            amount=amount,
            notes=serializer.validated_data.get("notes", ""),
        )
        log_action(request.user, "commission.created", commission, changes={"amount": str(amount)})
        return Response(CommissionSerializer(commission).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        commission = self.get_object()
        if not is_platform_admin(request.user) and request.user.role not in {User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF}:
            raise PermissionDenied("Not allowed.")
        if commission.status != Commission.Status.PENDING:
            raise ValidationError("Only pending commissions can be approved.")
        commission.status = Commission.Status.APPROVED
        commission.save(update_fields=["status"])
        log_action(request.user, "commission.approved", commission)
        return Response(CommissionSerializer(commission).data)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        commission = self.get_object()
        if not is_platform_admin(request.user) and request.user.role not in {User.Role.PROVIDER_ADMIN}:
            raise PermissionDenied("Not allowed.")
        if commission.status != Commission.Status.APPROVED:
            raise ValidationError("Only approved commissions can be paid.")
        from django.utils import timezone

        commission.status = Commission.Status.PAID
        commission.paid_at = timezone.now()
        commission.save(update_fields=["status", "paid_at"])
        # Double-entry ledger: paying a commission settles commission payable.
        from apps.finance.services import post_journal_entry

        post_journal_entry(
            reference=f"COMPAY-{commission.id}",
            description=f"Commission paid for policy {commission.policy.policy_number}",
            lines=[
                {"account": "5000", "direction": "debit", "amount": commission.amount, "reference": str(commission.id)},
                {"account": "1000", "direction": "credit", "amount": commission.amount, "reference": str(commission.id)},
            ],
            currency="KES",
            posted_by=request.user,
            commission=commission,
        )
        if commission.agent:
            notify(commission.agent, "Commission paid", f"Commission {commission.amount} was paid.", "payment")
        log_action(request.user, "commission.paid", commission)
        return Response(CommissionSerializer(commission).data)


class MpesaCallbackView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "webhook"

    def post(self, request):
        if not self._ip_allowed(request):
            return Response({"ResultCode": 0, "ResultDesc": "Rejected"}, status=status.HTTP_403_FORBIDDEN)
        result = handle_stk_callback(request.data)
        return Response({"ResultCode": result["result_code"], "ResultDesc": result["result_desc"]})

    def _ip_allowed(self, request):
        allowed = settings.M_PESA_ALLOWED_IPS
        if allowed:
            peers = {request.META.get("REMOTE_ADDR", "")}
            if settings.M_PESA_TRUST_FORWARDED_FOR:
                forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
                if forwarded:
                    peers.add(forwarded.split(",")[0].strip())
            return bool(peers & set(allowed))
        # Fail closed in production: an unallowlisted callback cannot be
        # trusted. DEBUG is allowed to accept callbacks without the allowlist.
        if settings.DEBUG:
            return True
        logger.error("M-Pesa callback rejected: M_PESA_ALLOWED_IPS is not configured.")
        return False


class CardCallbackView(APIView):
    """Flutterwave webhook. The authoritative confirmation is a verify() call."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "webhook"

    def post(self, request):
        if not self._signature_valid(request):
            return Response({"status": "rejected"}, status=status.HTTP_403_FORBIDDEN)
        tx_ref = (request.data or {}).get("data", {}).get("tx_ref") or (request.data or {}).get("tx_ref")
        if not tx_ref:
            return Response({"status": "ignored"})
        self._record_event(tx_ref, request.data)
        payment = Payment.objects.filter(reference=tx_ref, method=Payment.Method.CARD).first()
        if not payment:
            return Response({"status": "unknown"})
        try:
            verify_card_payment(payment.id)
        except Exception:
            logger.exception("Card webhook processing failed for %s", tx_ref)
        return Response({"status": "accepted"})

    def _signature_valid(self, request):
        expected = settings.FLW_WEBHOOK_HASH
        if expected:
            provided = request.headers.get("verif-hash", "")
            return bool(provided) and hmac.compare_digest(provided, expected)
        # Fail closed in production: an unsigned card webhook cannot be trusted.
        if settings.DEBUG:
            return True
        logger.error("Flutterwave webhook rejected: FLW_WEBHOOK_HASH is not configured.")
        return False

    def _record_event(self, tx_ref, payload):
        event_id = f"card:{tx_ref}"
        WebhookEvent.objects.get_or_create(
            provider="flutterwave",
            event_id=event_id,
            defaults={"event_type": "card_webhook", "payload": payload or {}},
        )
