from django.urls import path

from apps.customers.views import (
    ContactDetailView, ContactListCreateView, ContactRestoreView,
    CustomerDetailView, CustomerListView, CustomerRestoreView,
)

urlpatterns = [
    path("<int:organization_id>/customers/", CustomerListView.as_view(), name="customer-list"),
    path("<int:organization_id>/customers/<int:customer_id>/", CustomerDetailView.as_view(), name="customer-detail"),
    path("<int:organization_id>/customers/<int:customer_id>/restore/", CustomerRestoreView.as_view(), name="customer-restore"),
    path("<int:organization_id>/customers/<int:customer_id>/contacts/", ContactListCreateView.as_view(), name="contact-list-create"),
    path("<int:organization_id>/contacts/<int:contact_id>/", ContactDetailView.as_view(), name="contact-detail"),
    path("<int:organization_id>/contacts/<int:contact_id>/restore/", ContactRestoreView.as_view(), name="contact-restore"),
]
