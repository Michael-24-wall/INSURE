import uuid

import pyotp
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken

from .tokens import VersionedTokenObtainPairSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.common.models import is_platform_admin
from apps.common.permissions import IsPlatformAdmin
from apps.common.utils import safe_enqueue
from apps.notifications.services import notify
from apps.notifications.tasks import send_password_reset_email, send_verification_email

from .models import (
    AgentProfile,
    CustomerProfile,
    EmailVerificationToken,
    InspectorProfile,
    PasswordResetToken,
    User,
)
from .serializers import (
    AdminUserUpdateSerializer,
    CustomerKycReviewSerializer,
    CustomerKycSubmitSerializer,
    CustomerRegisterSerializer,
    DealerRegisterSerializer,
    EmailVerifySerializer,
    LoginSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProviderRegisterSerializer,
    TotpCodeSerializer,
    TotpDisableSerializer,
    TotpVerifySerializer,
    UserPublicSerializer,
)


class AuthThrottle(AnonRateThrottle):
    scope = "auth"


def _auth_response(user):
    refresh = VersionedTokenObtainPairSerializer.get_token(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": MeSerializer(user).data,
    }


def _register_response(user, verification_token):
    body = {
        "user": UserPublicSerializer(user).data,
        "message": "Account created. Verify your email to activate all features.",
    }
    # In debug/sandbox the verification token is surfaced to allow local testing
    # without a configured mail transport. It is never exposed in production.
    if settings.DEBUG:
        body["verification_token"] = str(verification_token.token)
    return body


class CustomerRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    @transaction.atomic
    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, vt = serializer.save()
        notify(user, "Welcome to AutoInsure Connect", "Your customer account has been created.", "account")
        transaction.on_commit(lambda: safe_enqueue(send_verification_email, user.id, str(vt.token)))
        return Response(_register_response(user, vt), status=status.HTTP_201_CREATED)


class ProviderRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    @transaction.atomic
    def post(self, request):
        serializer = ProviderRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, org, vt = serializer.save()
        notify(
            user,
            "Provider organization submitted",
            f"{org.name} is pending verification by the platform administration.",
            "organization",
        )
        transaction.on_commit(lambda: safe_enqueue(send_verification_email, user.id, str(vt.token)))
        body = _register_response(user, vt)
        body["organization"] = {"id": str(org.id), "name": org.name, "status": org.status}
        return Response(body, status=status.HTTP_201_CREATED)


class DealerRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    @transaction.atomic
    def post(self, request):
        serializer = DealerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, org, vt = serializer.save()
        notify(
            user,
            "Dealership submitted for verification",
            f"{org.name} is pending verification by the platform administration.",
            "organization",
        )
        transaction.on_commit(lambda: safe_enqueue(send_verification_email, user.id, str(vt.token)))
        body = _register_response(user, vt)
        body["organization"] = {"id": str(org.id), "name": org.name, "type": org.organization_type, "status": org.status}
        return Response(body, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        password = serializer.validated_data["password"]
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if user_obj.is_locked:
            return Response(
                {"detail": "Account temporarily locked due to failed login attempts. Try again later."},
                status=status.HTTP_423_LOCKED,
            )
        user = authenticate(request=request, username=email, password=password)
        if user is None:
            user_obj.failed_login_attempts += 1
            if user_obj.failed_login_attempts >= 5:
                user_obj.locked_until = timezone.now() + timezone.timedelta(minutes=15)
                user_obj.failed_login_attempts = 0
            user_obj.save(update_fields=["failed_login_attempts", "locked_until"])
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"detail": "Account disabled."}, status=status.HTTP_403_FORBIDDEN)

        user.failed_login_attempts = 0
        user.locked_until = None
        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR"))
        user.last_login_ip = (ip or "").split(",")[0].strip() or None
        user.save(update_fields=["failed_login_attempts", "locked_until", "last_login_ip"])
        if user.totp_enabled:
            challenge = uuid.uuid4().hex
            cache.set(f"2fa:{challenge}", str(user.id), timeout=settings.TOTP_CHALLENGE_SECONDS)
            return Response({"otp_required": True, "challenge": challenge})
        return Response(_auth_response(user))


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except Exception:
                # The refresh token is already invalid/expired; the client
                # session is still cleared locally either way.
                pass
        return Response({"detail": "Logged out."})


class MeView(APIView):
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        user = request.user
        allowed = {"first_name", "last_name", "phone"}
        for field in allowed:
            if field in request.data:
                setattr(user, field, request.data[field])
        profile_map = {
            "customer": (CustomerProfile, ["national_id", "date_of_birth", "address", "city", "county"]),
            "agent": (AgentProfile, ["license_number", "region"]),
            "inspector": (InspectorProfile, ["certification_number", "region", "capacity_per_day"]),
        }
        entry = profile_map.get(user.role)
        if entry:
            model, fields = entry
            profile, _ = model.objects.get_or_create(user=user)
            for field in fields:
                if field in request.data:
                    setattr(profile, field, request.data[field])
            profile.save()
        user.save()
        return Response(MeSerializer(user).data)


class EmailVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = EmailVerificationToken.objects.select_related("user").get(token=serializer.validated_data["token"])
        except EmailVerificationToken.DoesNotExist:
            return Response({"detail": "Invalid verification token."}, status=status.HTTP_400_BAD_REQUEST)
        if not token.is_valid():
            return Response({"detail": "Token expired or already used."}, status=status.HTTP_400_BAD_REQUEST)
        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
        token.user.email_verified = True
        token.user.save(update_fields=["email_verified"])
        return Response({"detail": "Email verified successfully."})


class PasswordChangeView(APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.token_version += 1
        request.user.save()
        return Response({"detail": "Password changed. Please log in again."})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        body = {"detail": "If an account exists, a reset link has been generated."}
        if user:
            token = PasswordResetToken.objects.create(
                user=user, expires_at=timezone.now() + timezone.timedelta(hours=2)
            )
            transaction.on_commit(lambda: safe_enqueue(send_password_reset_email, user.id, str(token.token)))
            if settings.DEBUG:
                body["reset_token"] = str(token.token)
        return Response(body)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = PasswordResetToken.objects.select_related("user").get(token=serializer.validated_data["token"])
        except PasswordResetToken.DoesNotExist:
            return Response({"detail": "Invalid reset token."}, status=status.HTTP_400_BAD_REQUEST)
        if not token.is_valid():
            return Response({"detail": "Reset token expired or already used."}, status=status.HTTP_400_BAD_REQUEST)
        token.user.set_password(serializer.validated_data["new_password"])
        token.user.failed_login_attempts = 0
        token.user.locked_until = None
        token.user.token_version += 1
        token.user.save()
        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
        return Response({"detail": "Password reset successfully."})


class CustomerKycView(APIView):
    def get(self, request):
        if request.user.role != User.Role.CUSTOMER:
            return Response({"detail": "Only customers have a KYC profile."}, status=status.HTTP_403_FORBIDDEN)
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        from .serializers import CustomerProfileSerializer

        return Response(CustomerProfileSerializer(profile).data)

    def post(self, request):
        if request.user.role != User.Role.CUSTOMER:
            return Response({"detail": "Only customers can submit KYC."}, status=status.HTTP_403_FORBIDDEN)
        serializer = CustomerKycSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        for field in ("national_id", "date_of_birth", "address", "city", "county"):
            value = serializer.validated_data.get(field)
            if value is not None:
                setattr(profile, field, value)
        profile.kyc_status = "pending"
        profile.kyc_submitted_at = timezone.now()
        profile.kyc_notes = ""
        profile.save()
        from .serializers import CustomerProfileSerializer

        return Response(CustomerProfileSerializer(profile).data)


def _verify_totp(user, code):
    if not user.totp_secret:
        return False
    try:
        return bool(pyotp.TOTP(user.totp_secret).verify(code))
    except Exception:
        return False


class TwoFactorSetupView(APIView):
    def post(self, request):
        user = request.user
        if user.totp_enabled:
            return Response(
                {"detail": "Disable two-factor authentication before setting it up again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = False
        user.save(update_fields=["totp_secret", "totp_enabled"])
        uri = pyotp.TOTP(secret, issuer=settings.TOTP_ISSUER).provisioning_uri(
            name=user.email, issuer_name=settings.TOTP_ISSUER
        )
        return Response({"secret": secret, "uri": uri})


class TwoFactorConfirmView(APIView):
    def post(self, request):
        serializer = TotpCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.totp_secret:
            return Response({"detail": "Set up two-factor authentication first."}, status=status.HTTP_400_BAD_REQUEST)
        if not _verify_totp(user, serializer.validated_data["code"]):
            return Response({"detail": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)
        user.totp_enabled = True
        user.save(update_fields=["totp_enabled"])
        return Response({"detail": "Two-factor authentication enabled."})


class TwoFactorDisableView(APIView):
    def post(self, request):
        serializer = TotpDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["password"]):
            return Response({"detail": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST)
        user.totp_secret = ""
        user.totp_enabled = False
        user.save(update_fields=["totp_secret", "totp_enabled"])
        return Response({"detail": "Two-factor authentication disabled."})


class TwoFactorVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = TotpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = cache.get(f"2fa:{serializer.validated_data['challenge']}")
        if not user_id:
            return Response({"detail": "Invalid or expired challenge."}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(pk=user_id).first()
        if not user or not user.totp_enabled:
            return Response({"detail": "Invalid challenge."}, status=status.HTTP_400_BAD_REQUEST)
        if not _verify_totp(user, serializer.validated_data["code"]):
            return Response({"detail": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(f"2fa:{serializer.validated_data['challenge']}")
        return Response(_auth_response(user))


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserPublicSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = User.objects.all().order_by("-created_at").prefetch_related("customer_profile")
    filterset_fields = ["role", "is_active", "email_verified"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering_fields = ["created_at", "email", "role"]

    @action(detail=True, methods=["patch"], url_path="manage")
    def manage(self, request, pk=None):
        user = self.get_object()
        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserPublicSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="kyc-review")
    def kyc_review(self, request, pk=None):
        user = self.get_object()
        profile = CustomerProfile.objects.filter(user=user).first()
        if not profile:
            return Response({"detail": "This user has no customer profile."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CustomerKycReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        notes = serializer.validated_data.get("notes", "")
        if action == "approve":
            profile.kyc_status = "verified"
        else:
            profile.kyc_status = "rejected"
        profile.kyc_notes = notes
        profile.save()
        notify(
            user,
            "KYC review completed",
            f"Your identity verification was {profile.kyc_status}." + (f" {notes}" if notes else ""),
            "account",
        )
        from .serializers import CustomerProfileSerializer

        return Response(CustomerProfileSerializer(profile).data)
