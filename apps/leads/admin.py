from django.contrib import admin

from apps.core.admin import UnscopedFKAdminMixin
from apps.leads.models import Lead, LeadStageHistory, LeadTag, Tag


class LeadStageHistoryInline(UnscopedFKAdminMixin, admin.TabularInline):
    model = LeadStageHistory
    extra = 0
    can_delete = False
    readonly_fields = ("from_stage", "to_stage", "changed_by", "changed_at", "reason")

    def get_queryset(self, request):
        return LeadStageHistory.unscoped.all()

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Lead)
class LeadAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "owner", "stage", "email", "phone", "is_archived", "created_at")
    list_filter = ("stage", "is_archived")
    search_fields = ("email", "phone", "source")
    readonly_fields = ("created_at",)
    inlines = [LeadStageHistoryInline]

    def get_queryset(self, request):
        return Lead.unscoped.all()


@admin.register(Tag)
class TagAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "organization", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return Tag.unscoped.all()


@admin.register(LeadTag)
class LeadTagAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "lead", "tag", "created_at")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return LeadTag.unscoped.all()


@admin.register(LeadStageHistory)
class LeadStageHistoryAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "lead", "from_stage", "to_stage", "changed_by", "changed_at")
    list_filter = ("to_stage",)
    readonly_fields = ("lead", "from_stage", "to_stage", "changed_by", "changed_at", "reason")

    def get_queryset(self, request):
        return LeadStageHistory.unscoped.all()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
