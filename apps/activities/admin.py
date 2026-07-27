from django.contrib import admin

from apps.core.admin import UnscopedFKAdminMixin
from apps.activities.models import Activity


@admin.register(Activity)
class ActivityAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "type", "parent_display", "assignee", "due_date", "status", "created_at")
    list_filter = ("type", "status")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return Activity.unscoped.all()

    def parent_display(self, obj):
        return f"{obj.parent_content_type.model} #{obj.parent_object_id}"
    parent_display.short_description = "Parent"
