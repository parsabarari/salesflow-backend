from django.utils import timezone

from apps.activities.models import Activity, ActivityStatus
from apps.core.redis_client import get_redis_client
from apps.leads.models import Lead, LeadStage
from apps.tickets.models import Ticket, TicketStatus

CACHE_KEY_PREFIX = "dashboard_summary:"
CACHE_TTL_SECONDS = 60  # Architecture doc §4


class DashboardService:
    @staticmethod
    def get_summary(organization_id: int) -> dict:
        redis = get_redis_client()
        cache_key = f"{CACHE_KEY_PREFIX}{organization_id}"

        cached = redis.get(cache_key)
        if cached is not None:
            import json
            return json.loads(cached)

        summary = DashboardService._compute_summary()

        import json
        redis.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(summary))
        return summary

    @staticmethod
    def _compute_summary() -> dict:
        """Runs inside the ambient organization context already set by
        OrgScopedViewSetMixin — every queryset below is automatically
        org-scoped via the manager, same as every other service in this
        codebase."""
        lead_counts_by_stage = {
            stage: Lead.objects.filter(stage=stage).count() for stage in LeadStage.values
        }
        total_leads = sum(lead_counts_by_stage.values())
        won_count = lead_counts_by_stage.get(LeadStage.WON, 0)
        lost_count = lead_counts_by_stage.get(LeadStage.LOST, 0)
        closed_count = won_count + lost_count
        # Conversion rate: Won / (Won + Lost) — leads still active in
        # the pipeline aren't a meaningful denominator for "conversion"
        # yet, since they haven't reached a terminal outcome. ASSUMPTION
        # (not specified anywhere in the docs — flagging): if no leads
        # have reached a terminal stage yet, conversion_rate is 0.0
        # rather than undefined/null, to keep the response shape simple
        # for the frontend.
        conversion_rate = round(won_count / closed_count, 4) if closed_count > 0 else 0.0

        open_ticket_statuses = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.REOPENED]
        open_tickets_count = Ticket.objects.filter(status__in=open_ticket_statuses).count()

        upcoming_activities = list(
            Activity.objects.filter(status=ActivityStatus.PENDING, due_date__gte=timezone.now())
            .order_by("due_date")
            .values("id", "type", "due_date", "assignee_id")[:10]
        )
        for activity in upcoming_activities:
            activity["due_date"] = activity["due_date"].isoformat()

        return {
            "lead_counts_by_stage": lead_counts_by_stage,
            "total_leads": total_leads,
            "conversion_rate": conversion_rate,
            "open_tickets_count": open_tickets_count,
            "upcoming_activities": upcoming_activities,
        }
