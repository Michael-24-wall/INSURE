from django.contrib import admin

from .models import Message, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "category", "is_read", "created_at")
    list_filter = ("category", "is_read")
    search_fields = ("user__email", "title")


admin.site.register(Message)
