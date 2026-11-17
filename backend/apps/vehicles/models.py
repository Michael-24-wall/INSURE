import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedModel


class Vehicle(TimeStampedModel, SoftDeleteModel):
    class Category(models.TextChoices):
        SALOON = "saloon", "Saloon"
        SUV = "suv", "SUV / 4x4"
        PICKUP = "pickup", "Pickup"
        VAN = "van", "Van / Minibus"
        TRUCK = "truck", "Truck"
        BUS = "bus", "Bus"
        MOTORCYCLE = "motorcycle", "Motorcycle"
        THREE_WHEELER = "three_wheeler", "Three Wheeler"
        OTHER = "other", "Other"

    class Fuel(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"
        HYBRID = "hybrid", "Hybrid"
        ELECTRIC = "electric", "Electric"
        LPG = "lpg", "LPG"

    class Usage(models.TextChoices):
        PRIVATE = "private", "Private"
        COMMERCIAL = "commercial", "Commercial"
        PSV = "psv", "Public Service Vehicle"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vehicles")
    registration_number = models.CharField(max_length=20, db_index=True)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    manufacturing_year = models.PositiveIntegerField(
        validators=[MinValueValidator(1950), MaxValueValidator(2100)]
    )
    chassis_number = models.CharField(max_length=100, blank=True)
    engine_cc = models.PositiveIntegerField(null=True, blank=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.SALOON)
    fuel_type = models.CharField(max_length=20, choices=Fuel.choices, default=Fuel.PETROL)
    usage = models.CharField(max_length=20, choices=Usage.choices, default=Usage.PRIVATE)
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    color = models.CharField(max_length=50, blank=True)
    seat_capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "registration_number"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_owner_active_vehicle_reg",
            )
        ]

    def __str__(self):
        return f"{self.registration_number} ({self.make} {self.model})"


class VehicleDocument(TimeStampedModel):
    class DocType(models.TextChoices):
        LOGBOOK = "logbook", "Logbook"
        INSURANCE_CERTIFICATE = "insurance_certificate", "Insurance Certificate"
        INSPECTION_CERTIFICATE = "inspection_certificate", "Inspection Certificate"
        PHOTO = "photo", "Vehicle Photo"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=40, choices=DocType.choices)
    file = models.FileField(upload_to="vehicles/documents/%Y/%m/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    is_verified = models.BooleanField(default=False)
    extracted_data = models.JSONField(default=dict, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.vehicle.registration_number} - {self.document_type}"
