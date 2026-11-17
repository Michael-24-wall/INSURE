from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.services import log_action
from apps.common.models import is_platform_admin, user_org_ids
from apps.common.scoping import user_insurer_ids
from apps.common.utils import generate_reference
from apps.insurance.models import Application, Insurer, Quotation, QuotationRequest
from apps.insurance.serializers import QuotationRequestSerializer
from apps.insurance.services import generate_quotes
from apps.organizations.models import Organization
from apps.vehicles.models import Vehicle

from .models import (
    CustomerConsent,
    DealerBranch,
    DealerVehicle,
    DealerVehiclePhoto,
    Partnership,
    PartnershipActivity,
    PartnershipCommissionTerms,
    PartnershipRequest,
)
from .serializers import (
    ConsentCreateSerializer,
    CustomerConsentSerializer,
    DealerBranchSerializer,
    DealerVehiclePhotoUploadSerializer,
    DealerVehicleSerializer,
    DealershipDiscoverSerializer,
    InsurerDiscoverSerializer,
    PartnershipActionSerializer,
    PartnershipCommissionTermsSerializer,
    PartnershipRequestCreateSerializer,
    PartnershipRequestRespondSerializer,
    PartnershipRequestSerializer,
    PartnershipSerializer,
)
from .services import (
    create_partnership_request,
    grant_consent,
    notify_org,
    reactivate_partnership,
    respond_to_partnership_request,
    suspend_partnership,
    terminate_partnership,
    user_dealer_org,
    withdraw_consent,
)


class InsurerDiscoverViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InsurerDiscoverSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["display_name", "organization__name", "organization__county"]
    filterset_fields = ["organization__county", "organization__status"]
    ordering_fields = ["display_name", "rating"]

    def get_queryset(self):
        qs = Insurer.objects.filter(
            organization__status=Organization.Status.VERIFIED, is_active=True
        ).select_related("organization").prefetch_related("products")
        return qs


class DealershipDiscoverViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DealershipDiscoverSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "trading_name", "county"]
    filterset_fields = ["county", "status"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        return (
            Organization.objects.filter(
                organization_type=Organization.Type.DEALER, status=Organization.Status.VERIFIED
            )
            .prefetch_related("branches", "inventory")
        )


class PartnershipRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PartnershipRequestSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["status"]
    search_fields = ["from_organization__name", "to_organization__name"]

    def get_queryset(self):
        qs = PartnershipRequest.objects.select_related("from_organization", "to_organization")
        if is_platform_admin(self.request.user):
            return qs
        org_ids = user_org_ids(self.request.user)
        return qs.filter(Q(from_organization_id__in=org_ids) | Q(to_organization_id__in=org_ids))

    def create(self, request, *args, **kwargs):
        serializer = PartnershipRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org_ids = set(user_org_ids(request.user))
        from_org_id = request.data.get("from_organization")
        from_org = Organization.objects.filter(pk=from_org_id, id__in=org_ids).first()
        if not from_org:
            raise PermissionDenied("You can only send requests from your own organization.")
        to_org = get_object_or_404(Organization, pk=serializer.validated_data["to_organization"])
        if to_org.status != Organization.Status.VERIFIED:
            raise ValidationError("You can only request a partnership with a verified organization.")
        try:
            req = create_partnership_request(
                from_org, to_org, serializer.validated_data.get("message", ""), request.user
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
        log_action(request.user, "partnership_request.created", req)
        return Response(PartnershipRequestSerializer(req).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        req = self.get_object()
        org_ids = set(user_org_ids(request.user))
        if req.to_organization_id not in org_ids and not is_platform_admin(request.user):
            raise PermissionDenied("Only the receiving organization can respond.")
        serializer = PartnershipRequestRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_name = serializer.validated_data["action"]
        note = serializer.validated_data.get("note", "")
        try:
            result = respond_to_partnership_request(req, action_name, request.user, note)
        except ValueError as exc:
            raise ValidationError(str(exc))
        log_action(request.user, f"partnership_request.{action_name}", req)
        if isinstance(result, Partnership):
            return Response(PartnershipSerializer(result).data)
        return Response(PartnershipRequestSerializer(result).data)


class PartnershipViewSet(viewsets.ModelViewSet):
    serializer_class = PartnershipSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["status"]
    search_fields = ["insurer__display_name", "dealership__name"]

    def get_queryset(self):
        qs = Partnership.objects.select_related("insurer", "dealership").prefetch_related(
            "activity", "commission_terms"
        )
        if is_platform_admin(self.request.user):
            return qs
        org_ids = user_org_ids(self.request.user)
        insurer_ids = user_insurer_ids(self.request.user)
        return qs.filter(Q(dealership_id__in=org_ids) | Q(insurer_id__in=insurer_ids)).distinct()

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        partnership = self.get_object()
        self._assert_partner(partnership)
        serializer = PartnershipActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        suspend_partnership(partnership, request.user, serializer.validated_data.get("reason", ""))
        log_action(request.user, "partnership.suspended", partnership)
        return Response(PartnershipSerializer(partnership).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        partnership = self.get_object()
        self._assert_partner(partnership)
        reactivate_partnership(partnership, request.user)
        log_action(request.user, "partnership.reactivated", partnership)
        return Response(PartnershipSerializer(partnership).data)

    @action(detail=True, methods=["post"])
    def terminate(self, request, pk=None):
        partnership = self.get_object()
        self._assert_partner(partnership)
        serializer = PartnershipActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        terminate_partnership(partnership, request.user, serializer.validated_data.get("reason", ""))
        log_action(request.user, "partnership.terminated", partnership)
        return Response(PartnershipSerializer(partnership).data)

    @action(detail=True, methods=["get", "post"], url_path="commission-terms")
    def commission_terms(self, request, pk=None):
        partnership = self.get_object()
        if request.method == "GET":
            return Response(PartnershipCommissionTermsSerializer(partnership.commission_terms.all(), many=True).data)
        if not is_platform_admin(request.user):
            self._assert_insurer_partner(partnership)
        serializer = PartnershipCommissionTermsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(partnership=partnership)
        log_action(request.user, "partnership.commission_terms_added", partnership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _assert_partner(self, partnership):
        if is_platform_admin(self.request.user):
            return
        org_ids = set(user_org_ids(self.request.user))
        insurer_ids = set(user_insurer_ids(self.request.user))
        if partnership.dealership_id not in org_ids and partnership.insurer_id not in insurer_ids:
            raise PermissionDenied("You are not a party to this partnership.")

    def _assert_insurer_partner(self, partnership):
        if is_platform_admin(self.request.user):
            return
        insurer_ids = set(user_insurer_ids(self.request.user))
        if partnership.insurer_id not in insurer_ids:
            raise PermissionDenied("Only the insurer can manage commission terms.")


class DealerBranchViewSet(viewsets.ModelViewSet):
    serializer_class = DealerBranchSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["is_active"]
    search_fields = ["name", "county"]

    def get_queryset(self):
        qs = DealerBranch.objects.select_related("dealership")
        if is_platform_admin(self.request.user):
            return qs
        dealer_org = user_dealer_org(self.request.user)
        if not dealer_org:
            return qs.none()
        return qs.filter(dealership=dealer_org)

    def perform_create(self, serializer):
        dealer_org = self._require_dealer()
        serializer.save(dealership=dealer_org)

    def perform_update(self, serializer):
        self._assert_owns(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_owns(instance)
        instance.delete()

    def _require_dealer(self):
        dealer_org = user_dealer_org(self.request.user)
        if not dealer_org and not is_platform_admin(self.request.user):
            raise PermissionDenied("Only dealership users can manage branches.")
        return dealer_org

    def _assert_owns(self, branch):
        if is_platform_admin(self.request.user):
            return
        dealer_org = user_dealer_org(self.request.user)
        if not dealer_org or branch.dealership_id != dealer_org.id:
            raise PermissionDenied("Not allowed.")


class DealerVehicleViewSet(viewsets.ModelViewSet):
    serializer_class = DealerVehicleSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "category", "fuel_type", "condition", "branch"]
    search_fields = ["make", "model", "vin", "registration_number"]
    ordering_fields = ["created_at", "asking_price", "year"]

    def get_queryset(self):
        qs = DealerVehicle.objects.select_related("dealership", "branch").prefetch_related("photos")
        if is_platform_admin(self.request.user):
            return qs
        dealer_org = user_dealer_org(self.request.user)
        if dealer_org:
            return qs.filter(dealership=dealer_org)
        # Insurers with an active partnership can view the dealer's available inventory.
        insurer_ids = user_insurer_ids(self.request.user)
        if insurer_ids:
            return qs.filter(
                dealership__insurer_partnerships__insurer_id__in=insurer_ids,
                dealership__insurer_partnerships__status=Partnership.Status.ACTIVE,
                status=DealerVehicle.Status.AVAILABLE,
            ).distinct()
        return qs.none()

    def perform_create(self, serializer):
        dealer_org = self._require_dealer()
        serializer.save(dealership=dealer_org)

    def perform_update(self, serializer):
        self._assert_owns(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_owns(instance)
        instance.delete()

    @action(detail=True, methods=["post"], url_path="photos", parser_classes=[MultiPartParser, FormParser])
    def upload_photo(self, request, pk=None):
        vehicle = self.get_object()
        self._assert_owns(vehicle)
        serializer = DealerVehiclePhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = DealerVehiclePhoto.objects.create(
            vehicle=vehicle,
            image=serializer.validated_data["image"],
            is_primary=serializer.validated_data.get("is_primary", False),
            order=vehicle.photos.count(),
        )
        if photo.is_primary:
            vehicle.photos.exclude(pk=photo.pk).update(is_primary=False)
        # Drop the prefetched relation so the response reflects the new photo.
        vehicle.refresh_from_db()
        return Response(DealerVehicleSerializer(vehicle).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"photos/(?P<photo_id>[^/.]+)")
    def delete_photo(self, request, pk=None, photo_id=None):
        vehicle = self.get_object()
        self._assert_owns(vehicle)
        photo = get_object_or_404(DealerVehiclePhoto, pk=photo_id, vehicle=vehicle)
        photo.image.delete(save=False)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="mark-sold")
    def mark_sold(self, request, pk=None):
        vehicle = self.get_object()
        self._assert_owns(vehicle)
        vehicle.status = DealerVehicle.Status.SOLD
        vehicle.sold_at = timezone.now()
        vehicle.save(update_fields=["status", "sold_at"])
        log_action(request.user, "dealer_vehicle.sold", vehicle)
        return Response(DealerVehicleSerializer(vehicle).data)

    def _require_dealer(self):
        dealer_org = user_dealer_org(self.request.user)
        if not dealer_org and not is_platform_admin(self.request.user):
            raise PermissionDenied("Only dealership users can manage inventory.")
        return dealer_org

    def _assert_owns(self, vehicle):
        if is_platform_admin(self.request.user):
            return
        dealer_org = user_dealer_org(self.request.user)
        if not dealer_org or vehicle.dealership_id != dealer_org.id:
            raise PermissionDenied("Not allowed.")


class CustomerConsentViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerConsentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["status"]

    def get_queryset(self):
        qs = CustomerConsent.objects.select_related("customer", "dealership", "insurer")
        if is_platform_admin(self.request.user):
            return qs
        dealer_org = user_dealer_org(self.request.user)
        insurer_ids = user_insurer_ids(self.request.user)
        if self.request.user.role == User.Role.CUSTOMER:
            return qs.filter(customer=self.request.user)
        return qs.filter(
            Q(dealership=dealer_org) | Q(insurer_id__in=insurer_ids)
        ).distinct() if (dealer_org or insurer_ids) else qs.none()

    def create(self, request, *args, **kwargs):
        dealer_org = user_dealer_org(request.user)
        if not dealer_org and not is_platform_admin(request.user):
            raise PermissionDenied("Only dealership users can record customer consent.")
        serializer = ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = get_object_or_404(User, pk=serializer.validated_data["customer"], role=User.Role.CUSTOMER)
        insurer = get_object_or_404(Insurer, pk=serializer.validated_data["insurer"])
        consent = grant_consent(
            customer,
            dealer_org,
            insurer,
            serializer.validated_data.get("data_categories"),
            serializer.validated_data.get("consent_method", CustomerConsent.Method.DIGITAL),
        )
        log_action(request.user, "customer_consent.granted", consent)
        return Response(CustomerConsentSerializer(consent).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        consent = self.get_object()
        if consent.customer_id != request.user.id and not is_platform_admin(request.user):
            dealer_org = user_dealer_org(request.user)
            if not dealer_org or consent.dealership_id != dealer_org.id:
                raise PermissionDenied("Not allowed.")
        withdraw_consent(consent)
        log_action(request.user, "customer_consent.withdrawn", consent)
        return Response(CustomerConsentSerializer(consent).data)


class DealerQuotationRequestView(APIView):
    """Create a dealer-originated quotation request for a connected insurer."""

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        dealer_org = user_dealer_org(request.user)
        if not dealer_org and not is_platform_admin(request.user):
            raise PermissionDenied("Only dealership users can submit dealer quotations.")

        data = request.data
        inventory_id = data.get("inventory_vehicle")
        insurer_id = data.get("insurer")
        customer_id = data.get("customer")

        inventory = get_object_or_404(DealerVehicle, pk=inventory_id, dealership=dealer_org)
        insurer = get_object_or_404(Insurer, pk=insurer_id)
        customer = get_object_or_404(User, pk=customer_id, role=User.Role.CUSTOMER)

        partnership = Partnership.objects.filter(
            insurer=insurer, dealership=dealer_org, status=Partnership.Status.ACTIVE
        ).first()
        if not partnership:
            raise ValidationError("No active partnership exists with the selected insurer.")

        consent = grant_consent(
            customer, dealer_org, insurer,
            data.get("data_categories"),
            data.get("consent_method", CustomerConsent.Method.DIGITAL),
        )

        vehicle = self._customer_vehicle(customer, inventory)

        req = QuotationRequest.objects.create(
            request_number=generate_reference("QR", 10),
            customer=customer,
            vehicle=vehicle,
            insurer=insurer,
            coverage_type=data.get("coverage_type", "comprehensive"),
            sum_insured=data.get("sum_insured") or inventory.asking_price,
            desired_start_date=data.get("desired_start_date"),
            notes=data.get("notes", ""),
            dealership=dealer_org,
            dealership_branch_id=inventory.branch_id,
            partnership=partnership,
            consent=consent,
            expires_at=timezone.now() + timedelta(days=14),
        )
        generate_quotes(req, insurer_ids=[insurer.id])
        notify_org(
            insurer.organization,
            "New dealer quotation request",
            f"{dealer_org.name} requested cover for {vehicle.registration_number} ({req.request_number}).",
            "quotation",
            f"/provider/quotes/{req.id}",
        )
        log_action(request.user, "dealer_quotation.requested", req, changes={"insurer": str(insurer.id)})
        return Response(
            {"request": QuotationRequestSerializer(req).data, "consent": CustomerConsentSerializer(consent).data},
            status=status.HTTP_201_CREATED,
        )

    def _customer_vehicle(self, customer, inventory):
        reg = inventory.registration_number or (f"VIN-{inventory.vin[:14]}" if inventory.vin else f"UNREG-{inventory.id.hex[:8].upper()}")
        vehicle = Vehicle.objects.filter(owner=customer, registration_number=reg).first()
        if not vehicle:
            vehicle = Vehicle.objects.create(
                owner=customer,
                registration_number=reg,
                make=inventory.make,
                model=inventory.model,
                manufacturing_year=inventory.year,
                category=inventory.category,
                fuel_type=inventory.fuel_type,
                estimated_value=inventory.asking_price,
            )
        return vehicle


class DealerCustomerSearchView(APIView):
    """Look up a customer so dealership staff can raise a quotation for them."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "search"

    def get(self, request):
        dealer_org = user_dealer_org(request.user)
        is_admin = is_platform_admin(request.user)
        if not dealer_org and not is_admin:
            raise PermissionDenied("Only dealership users can look up customers.")

        # PII minimisation: only dealerships with an active insurer partnership
        # may look up customers, and the phone number is only returned when the
        # customer has granted that dealership explicit consent.
        if dealer_org and not is_admin:
            has_active_partnership = Partnership.objects.filter(
                dealership=dealer_org, status=Partnership.Status.ACTIVE
            ).exists()
            if not has_active_partnership:
                return Response([])

        term = (request.query_params.get("search") or "").strip()
        if len(term) < 2:
            return Response([])

        customers = list(
            User.objects.filter(role=User.Role.CUSTOMER, is_active=True)
            .filter(
                Q(email__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(phone__icontains=term)
            )
            .order_by("first_name", "last_name", "email")[:20]
        )
        consented_ids = set()
        if dealer_org and customers:
            consented_ids = set(
                CustomerConsent.objects.filter(
                    dealership=dealer_org,
                    status=CustomerConsent.Status.GRANTED,
                    customer_id__in=[customer.id for customer in customers],
                ).values_list("customer_id", flat=True)
            )
        return Response(
            [
                {
                    "id": str(customer.id),
                    "name": customer.full_name,
                    "email": customer.email,
                    "phone": customer.phone if (is_admin or customer.id in consented_ids) else "",
                }
                for customer in customers
            ]
        )
