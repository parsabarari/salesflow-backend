from django.contrib import admin

from apps.tickets.models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "customer", "status", "priority", "assignee", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("subject",)
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return Ticket.unscoped.all()