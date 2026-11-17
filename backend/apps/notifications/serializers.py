from rest_framework import serializers

from .models import Message, Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "title", "message", "category", "link", "is_read", "created_at")
        read_only_fields = ("id", "title", "message", "category", "link", "created_at")


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.full_name", read_only=True)
    recipient_name = serializers.CharField(source="recipient.full_name", read_only=True)

    class Meta:
        model = Message
        fields = (
            "id", "sender", "sender_name", "recipient", "recipient_name", "subject",
            "body", "claim", "read_at", "created_at",
        )
        read_only_fields = ("id", "sender", "sender_name", "recipient_name", "read_at", "created_at")
