from django.contrib import admin

from .models import DamageRecord, Inspection


class DamageInline(admin.TabularInline):
    model = DamageRecord
    extra = 0


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("inspection_number", "vehicle", "inspection_type", "status", "inspector", "scheduled_at")
    list_filter = ("status", "inspection_type")
    search_fields = ("inspection_number", "vehicle__registration_number", "inspector__email")
    inlines = [DamageInline]


admin.site.register(DamageRecord)
