import uuid

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel

ZONES = [
    {"key": "front_bumper", "label": "Front Bumper", "side": "front"},
    {"key": "bonnet", "label": "Bonnet", "side": "front"},
    {"key": "windshield", "label": "Windshield", "side": "front"},
    {"key": "front_left_door", "label": "Front Left Door", "side": "left"},
    {"key": "rear_left_door", "label": "Rear Left Door", "side": "left"},
    {"key": "front_right_door", "label": "Front Right Door", "side": "right"},
    {"key": "rear_right_door", "label": "Rear Right Door", "side": "right"},
    {"key": "roof", "label": "Roof", "side": "top"},
    {"key": "rear_bumper", "label": "Rear Bumper", "side": "rear"},
    {"key": "boot", "label": "Boot / Trunk", "side": "rear"},
    {"key": "rear_windshield", "label": "Rear Windshield", "side": "rear"},
    {"key": "left_front_wheel", "label": "Left Front Wheel", "side": "left"},
    {"key": "right_front_wheel", "label": "Right Front Wheel", "side": "right"},
    {"key": "left_rear_wheel", "label": "Left Rear Wheel", "side": "left"},
    {"key": "right_rear_wheel", "label": "Right Rear Wheel", "side": "right"},
    {"key": "headlights", "label": "Headlights", "side": "front"},
    {"key": "taillights", "label": "Taillights", "side": "rear"},
    {"key": "side_mirrors", "label": "Side Mirrors", "side": "left"},
    {"key": "interior", "label": "Interior", "side": "top"},
    {"key": "engine", "label": "Engine / Mechanical", "side": "front"},
]
ZONE_KEYS = {z["key"] for z in ZONES}


class Inspection(TimeStampedModel):
    class Type(models.TextChoices):
        PRE_INSURANCE = "pre_insurance", "Pre-Insurance Inspection"
        CLAIM_ASSESSMENT = "claim_assessment", "Claim Assessment"
        RENEWAL = "renewal", "Renewal Inspection"
        PERIODIC = "periodic", "Periodic Inspection"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection_number = models.CharField(max_length=30, unique=True, db_index=True)
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="inspections"
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="inspections"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="requested_inspections"
    )
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, related_name="inspections")
    application = models.ForeignKey(
        "insurance.Application", null=True, blank=True, on_delete=models.SET_NULL, related_name="inspections"
    )
    policy = models.ForeignKey(
        "insurance.Policy", null=True, blank=True, on_delete=models.SET_NULL, related_name="inspections"
    )
    claim = models.ForeignKey(
        "claims.Claim", null=True, blank=True, on_delete=models.SET_NULL, related_name="inspections"
    )
    inspection_type = models.CharField(max_length=30, choices=Type.choices, default=Type.PRE_INSURANCE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    report_summary = models.TextField(blank=True)
    report_file = models.FileField(upload_to="inspections/reports/", null=True, blank=True)
    overall_condition = models.CharField(
        max_length=20,
        choices=[("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"), ("poor", "Poor")],
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.inspection_number


class DamageRecord(TimeStampedModel):
    class Severity(models.TextChoices):
        MINOR = "minor", "Minor"
        MODERATE = "moderate", "Moderate"
        SEVERE = "severe", "Severe"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="damages")
    zone = models.CharField(max_length=50)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MINOR)
    description = models.TextField(blank=True)
    photo = models.FileField(upload_to="inspections/damages/", null=True, blank=True)
    estimated_repair_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ai_assisted = models.BooleanField(default=False)
    ai_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inspection.inspection_number} - {self.zone}"
