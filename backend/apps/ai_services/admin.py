from django.contrib import admin

from .models import AIServiceLog


@admin.register(AIServiceLog)
class AIServiceLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "task", "provider", "user", "confidence")
    list_filter = ("task", "provider")
    readonly_fields = [f.name for f in AIServiceLog._meta.fields]

    def has_add_permission(self, request):
        return False
