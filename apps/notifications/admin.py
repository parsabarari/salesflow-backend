from django.contrib import admin

from apps.core.admin import UnscopedFKAdminMixin
from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "type", "recipient_membership", "related_display", "is_read", "created_at")
    list_filter = ("type", "is_read")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return Notification.unscoped.all()

    def related_display(self, obj):
        return f"{obj.related_content_type.model} #{obj.related_object_id}"
    related_display.short_description = "Related object"
