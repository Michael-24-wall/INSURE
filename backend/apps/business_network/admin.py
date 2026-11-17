from django.contrib import admin

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


@admin.register(DealerBranch)
class DealerBranchAdmin(admin.ModelAdmin):
    list_display = ("name", "dealership", "county", "is_active")
    search_fields = ("name", "dealership__name")


@admin.register(DealerVehicle)
class DealerVehicleAdmin(admin.ModelAdmin):
    list_display = ("make", "model", "year", "dealership", "status", "asking_price")
    list_filter = ("status", "condition", "category")
    search_fields = ("make", "model", "vin", "registration_number", "dealership__name")


@admin.register(DealerVehiclePhoto)
class DealerVehiclePhotoAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "is_primary", "order")


@admin.register(Partnership)
class PartnershipAdmin(admin.ModelAdmin):
    list_display = ("insurer", "dealership", "status", "effective_date", "expiry_date")
    list_filter = ("status",)
    search_fields = ("insurer__display_name", "dealership__name")


@admin.register(PartnershipRequest)
class PartnershipRequestAdmin(admin.ModelAdmin):
    list_display = ("from_organization", "to_organization", "status", "created_at")
    list_filter = ("status",)


@admin.register(PartnershipActivity)
class PartnershipActivityAdmin(admin.ModelAdmin):
    list_display = ("partnership", "action", "actor", "created_at")


@admin.register(CustomerConsent)
class CustomerConsentAdmin(admin.ModelAdmin):
    list_display = ("customer", "dealership", "insurer", "status", "consent_method", "granted_at")
    list_filter = ("status", "consent_method")


@admin.register(PartnershipCommissionTerms)
class PartnershipCommissionTermsAdmin(admin.ModelAdmin):
    list_display = ("partnership", "commission_type", "rate", "fixed_amount", "status")
    list_filter = ("commission_type", "status")
