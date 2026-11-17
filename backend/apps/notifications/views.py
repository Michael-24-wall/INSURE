from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.models import is_platform_admin, user_org_ids

from .models import Message, Notification
from .serializers import MessageSerializer, NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["is_read", "category"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"count": self.get_queryset().filter(is_read=False).count()})

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        n = self.get_object()
        n.is_read = True
        n.save(update_fields=["is_read"])
        return Response(NotificationSerializer(n).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"updated": updated})


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["claim"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Message.objects.filter(Q(sender=self.request.user) | Q(recipient=self.request.user)).select_related(
            "sender", "recipient"
        )

    def _is_claim_participant(self, user, claim):
        if is_platform_admin(user):
            return True
        if claim.customer_id == user.id:
            return True
        return claim.policy.insurer.organization_id in user_org_ids(user)

    def perform_create(self, serializer):
        claim = serializer.validated_data.get("claim")
        recipient = serializer.validated_data.get("recipient")
        user = self.request.user
        if claim is not None:
            if not self._is_claim_participant(user, claim):
                raise PermissionDenied("You can only message about claims you are part of.")
            if not self._is_claim_participant(recipient, claim):
                raise ValidationError({"recipient": "Recipient is not a participant in this claim."})
            if user.id == recipient.id:
                raise ValidationError({"recipient": "You cannot message yourself."})
        serializer.save(sender=user)
