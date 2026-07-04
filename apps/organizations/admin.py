from django.contrib import admin

from .models import Invitation, Membership, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at", "deleted_at")
    search_fields = ("name",)
    readonly_fields = ("created_at",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "organization", "role", "reports_to", "created_at", "deleted_at")
    list_filter = ("role",)
    search_fields = ("user__email", "organization__name")
    readonly_fields = ("created_at",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "organization", "role", "status", "expires_at", "created_at")
    list_filter = ("role", "status")
    search_fields = ("email", "organization__name")
    readonly_fields = ("created_at",)
