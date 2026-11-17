from django.contrib import admin

from .models import Claim, ClaimDocument, ClaimStatusHistory


class ClaimDocumentInline(admin.TabularInline):
    model = ClaimDocument
    extra = 0


class ClaimStatusInline(admin.TabularInline):
    model = ClaimStatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "changed_by", "notes")


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("claim_number", "customer", "policy", "claim_type", "status", "amount_claimed", "officer")
    list_filter = ("status", "claim_type")
    search_fields = ("claim_number", "customer__email", "policy__policy_number")
    inlines = [ClaimDocumentInline, ClaimStatusInline]


admin.site.register(ClaimDocument)
admin.site.register(ClaimStatusHistory)
