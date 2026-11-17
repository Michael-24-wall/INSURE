from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomerProfile, EmailVerificationToken, InspectorProfile, PasswordResetToken, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("email", "role", "is_active", "email_verified", "is_staff", "created_at")
    list_filter = ("role", "is_active", "email_verified", "is_staff")
    search_fields = ("email", "first_name", "last_name", "phone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone")}),
        ("Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "email_verified", "groups", "user_permissions")}),
        ("Security", {"fields": ("failed_login_attempts", "locked_until", "last_login_ip")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "role", "password1", "password2")}),
    )
    readonly_fields = ("created_at", "updated_at")


admin.site.register(CustomerProfile)
admin.site.register(InspectorProfile)
admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)
