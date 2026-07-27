from django.contrib import admin

from apps.core.admin import UnscopedFKAdminMixin
from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "action_type", "actor_membership", "target_display", "organization", "created_at")
    list_filter = ("action_type",)
    readonly_fields = (
        "actor_membership", "action_type", "target_content_type",
        "target_object_id", "metadata", "organization", "created_at",
    )

    def get_queryset(self, request):
        return AuditLog.unscoped.all()

    def target_display(self, obj):
        return f"{obj.target_content_type.model} #{obj.target_object_id}"
    target_display.short_description = "Target"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
