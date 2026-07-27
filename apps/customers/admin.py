from django.contrib import admin

from apps.core.admin import UnscopedFKAdminMixin
from apps.customers.models import Contact, Customer, CustomerLeadLink


class ContactInline(UnscopedFKAdminMixin, admin.TabularInline):
    model = Contact
    extra = 0
    fields = ("name", "email", "phone", "deleted_at")
    readonly_fields = ("deleted_at",)

    def get_queryset(self, request):
        return Contact.unscoped.all()


@admin.register(Customer)
class CustomerAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "type", "email", "phone", "organization", "created_at")
    list_filter = ("type",)
    search_fields = ("name", "email", "phone")
    readonly_fields = ("created_at",)
    inlines = [ContactInline]

    def get_queryset(self, request):
        return Customer.unscoped.all()


@admin.register(Contact)
class ContactAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "customer", "email", "phone", "created_at")
    search_fields = ("name", "email", "phone")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return Contact.unscoped.all()


@admin.register(CustomerLeadLink)
class CustomerLeadLinkAdmin(UnscopedFKAdminMixin, admin.ModelAdmin):
    list_display = ("id", "customer", "lead", "linked_at")
    readonly_fields = ("linked_at",)

    def get_queryset(self, request):
        return CustomerLeadLink.unscoped.all()

    def has_change_permission(self, request, obj=None):
        return False
