from django.contrib import admin

from .models import Membership, Organization, OrganizationDocument


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "organization_type", "status", "verified_at", "created_at")
    list_filter = ("organization_type", "status")
    search_fields = ("name", "registration_number", "email")
    inlines = [MembershipInline]


admin.site.register(Membership)
admin.site.register(OrganizationDocument)
