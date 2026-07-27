from django.contrib import admin

from apps.core.admin import UnscopedFKAdminMixin
from apps.collaboration.models import Attachment, Comment, CommentMention


class CommentMentionInline(UnscopedFKAdminMixin, admin.TabularInline):
    model = CommentMention
    extra = 0
    readonly_fields = ("mentioned_membership", "created_at")

    def get_queryset(self, request):
        return CommentMention.unscoped.all()

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Comment)
class CommentAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "author", "parent_display", "created_at")
    search_fields = ("body",)
    readonly_fields = ("created_at",)
    inlines = [CommentMentionInline]

    def get_queryset(self, request):
        return Comment.unscoped.all()

    def parent_display(self, obj):
        return f"{obj.parent_content_type.model} #{obj.parent_object_id}"
    parent_display.short_description = "Parent"


@admin.register(CommentMention)
class CommentMentionAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "comment", "mentioned_membership", "created_at")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return CommentMention.unscoped.all()


@admin.register(Attachment)
class AttachmentAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "original_filename", "parent_display", "uploaded_by", "file_size_bytes", "created_at")
    search_fields = ("original_filename",)
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return Attachment.unscoped.all()

    def parent_display(self, obj):
        return f"{obj.parent_content_type.model} #{obj.parent_object_id}"
    parent_display.short_description = "Parent"
