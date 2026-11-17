import uuid

from django.conf import settings
from django.db import models


class AIServiceLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="ai_logs")
    task = models.CharField(max_length=60, db_index=True)
    provider = models.CharField(max_length=60, default="heuristic")
    input_summary = models.CharField(max_length=255, blank=True)
    output = models.JSONField(default=dict, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
