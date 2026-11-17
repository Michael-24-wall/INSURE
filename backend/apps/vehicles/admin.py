from django.contrib import admin

from .models import Vehicle, VehicleDocument


class VehicleDocumentInline(admin.TabularInline):
    model = VehicleDocument
    extra = 0


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "owner", "make", "model", "manufacturing_year", "category", "estimated_value")
    list_filter = ("category", "fuel_type", "usage", "is_active")
    search_fields = ("registration_number", "chassis_number", "make", "model", "owner__email")
    inlines = [VehicleDocumentInline]


admin.site.register(VehicleDocument)
