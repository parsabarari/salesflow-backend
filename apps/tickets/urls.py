from django.urls import path

from apps.tickets.views import TicketDetailView, TicketListCreateView

urlpatterns = [
    path("<int:organization_id>/tickets/", TicketListCreateView.as_view(), name="ticket-list-create"),
    path("<int:organization_id>/tickets/<int:ticket_id>/", TicketDetailView.as_view(), name="ticket-detail"),
]
