from django.contrib import admin

from .models import Commission, Payment, Refund, Transaction


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ("reference", "raw_response", "created_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "purpose", "amount", "method", "status", "verified_at", "created_at")
    list_filter = ("status", "method", "purpose")
    search_fields = ("reference", "provider_reference", "user__email", "receipt_number")
    inlines = [TransactionInline]


admin.site.register(Refund)
admin.site.register(Commission)
admin.site.register(Transaction)
