from django.contrib.contenttypes.models import ContentType

from apps.activities.models import Activity, ActivityStatus
from apps.customers.models import Customer
from apps.leads.models import Lead

# Business Rules 8.2 — an Activity's parent is exactly one of Lead or
# Customer. Keyed by the API's parent_type string (API Spec §7).
PARENT_MODEL_MAP = {
    "lead": Lead,
    "customer": Customer,
}


def resolve_parent(parent_type: str, parent_id: int, organization_id: int):
    """Looks up the parent Lead/Customer, scoped to organization_id
    explicitly (not via the ambient context-based manager) so this
    works the same whether or not organization context happens to be
    set, and so a cross-org parent_id can never be attached (AGENTS.md:
    every reference between tenant-scoped rows must be validated against
    the same organization_id)."""
    model = PARENT_MODEL_MAP.get(parent_type)
    if model is None:
        raise ValueError("parent_type must be 'lead' or 'customer'.")
    try:
        return model.all_objects.get(id=parent_id, organization_id=organization_id, deleted_at__isnull=True)
    except model.DoesNotExist:
        raise ValueError(f"No {parent_type} with id={parent_id} in this organization.")


class ActivityService:
    @staticmethod
    def create(*, organization, parent_type: str, parent_id: int, assignee, activity_type: str, due_date):
        parent = resolve_parent(parent_type, parent_id, organization.id)
        content_type = ContentType.objects.get_for_model(parent.__class__)
        return Activity.objects.create(
            organization=organization,
            type=activity_type,
            parent_content_type=content_type,
            parent_object_id=parent.id,
            assignee=assignee,
            due_date=due_date,
        )

    @staticmethod
    def update_fields(activity: Activity, **fields) -> Activity:
        """Plain field edits (type, due_date, assignee) — status changes
        go through update_status() below, since that path carries the
        Business Rules 8.1 transition validation a generic field-set
        shouldn't silently bypass."""
        for field, value in fields.items():
            setattr(activity, field, value)
        activity.save(update_fields=list(fields.keys()))
        return activity

    @staticmethod
    def update_status(activity: Activity, to_status: str) -> Activity:
        """Business Rules 8.1: Activity status is Pending -> Completed,
        or Pending -> Cancelled. Both Completed and Cancelled are
        terminal — the rule only names Cancelled as reachable
        exclusively from Pending, and there's no stated path out of
        Completed either, so both are treated as end states here."""
        if to_status not in (ActivityStatus.COMPLETED, ActivityStatus.CANCELLED):
            raise ValueError("status must be 'completed' or 'cancelled'.")
        if activity.status != ActivityStatus.PENDING:
            raise ValueError(
                f"Cannot transition from '{activity.status}' — only a Pending "
                "activity can be marked Completed or Cancelled."
            )
        activity.status = to_status
        activity.save(update_fields=["status"])
        return activity
