from django.contrib import admin

from .models import Application, CoverageOption, Insurer, Policy, Product, Quotation, QuotationRequest


class CoverageInline(admin.TabularInline):
    model = CoverageOption
    extra = 0


@admin.register(Insurer)
class InsurerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "organization", "license_number", "is_active", "rating")
    list_filter = ("is_active",)
    search_fields = ("display_name", "license_number", "organization__name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "insurer", "category", "base_premium_rate", "minimum_premium", "is_active", "version")
    list_filter = ("category", "is_active", "insurer")
    search_fields = ("name", "code", "insurer__display_name")
    inlines = [CoverageInline]


@admin.register(QuotationRequest)
class QuotationRequestAdmin(admin.ModelAdmin):
    list_display = ("request_number", "customer", "vehicle", "coverage_type", "status", "created_at")
    list_filter = ("status", "coverage_type")
    search_fields = ("request_number", "customer__email", "vehicle__registration_number")


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ("quotation_number", "request", "insurer", "premium", "status", "source")
    list_filter = ("status", "source", "insurer")
    search_fields = ("quotation_number", "request__request_number")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("application_number", "customer", "vehicle", "status", "submitted_at")
    list_filter = ("status",)
    search_fields = ("application_number", "customer__email", "vehicle__registration_number")


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("policy_number", "customer", "insurer", "product", "status", "start_date", "end_date", "premium")
    list_filter = ("status", "insurer", "product")
    search_fields = ("policy_number", "customer__email", "vehicle__registration_number")
