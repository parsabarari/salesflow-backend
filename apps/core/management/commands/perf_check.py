"""Roadmap Phase 4 — index/query performance pass.

Seeds a throwaway organization with realistic data volume, then runs
EXPLAIN ANALYZE against the exact queryset shapes used by the heaviest
list endpoints, to confirm the indexes already defined in docs/04-erd.md
are actually being chosen by the Postgres query planner (rather than
just existing on paper).

Also supports seeding a second, larger "noise" organization under a
different name — needed because with only one organization in the
table, `organization_id` has zero selectivity (every row matches), so
Postgres has no reason to prefer a composite (organization_id, X) index
over a plain single-column one. A second, bigger org makes
organization_id genuinely selective, which is the realistic multi-
tenant situation this schema is actually designed for (06-architecture.md §1).

Usage:
    python manage.py perf_check --seed 5000
    python manage.py perf_check --noise 20000
    python manage.py perf_check --explain
    python manage.py perf_check --cleanup

Deliberately separate steps rather than one seed-explain-cleanup run:
lets you re-run --explain repeatedly against the same seeded data while
iterating, without re-seeding every time.
"""
import random
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.activities.models import Activity, ActivityStatus, ActivityType
from apps.core.context import (
    clear_current_organization,
    disable_unscoped_mode,
    enable_unscoped_mode,
    set_current_organization,
)
from apps.customers.models import Contact, Customer, CustomerLeadLink, CustomerType
from apps.leads.models import Lead, LeadStage
from apps.notifications.models import Notification, NotificationType
from apps.organizations.models import Membership, MembershipRole, Organization
from apps.tickets.models import Ticket, TicketStatus

PERF_ORG_NAME = "__perf_check_org__"
NOISE_ORG_NAME = "__perf_check_noise_org__"


class Command(BaseCommand):
    help = "Seed data + EXPLAIN ANALYZE the heaviest list-endpoint queries (roadmap Phase 4)."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=0, help="Seed N leads (+ related rows) into the perf-test org.")
        parser.add_argument("--noise", type=int, default=0, help="Seed N leads into a SEPARATE, second org, to make organization_id selective for multi-tenant index checks.")
        parser.add_argument("--explain", action="store_true", help="Run EXPLAIN ANALYZE against the key list-endpoint querysets, scoped to the perf-test org.")
        parser.add_argument("--cleanup", action="store_true", help="Delete both perf-test organizations and all their data.")

    def handle(self, *args, **options):
        if not any([options["seed"], options["noise"], options["explain"], options["cleanup"]]):
            self.stdout.write(self.style.WARNING("Nothing to do — pass --seed N, --noise N, --explain, or --cleanup."))
            return
        if options["seed"]:
            self._seed(options["seed"], PERF_ORG_NAME)
        if options["noise"]:
            self._seed(options["noise"], NOISE_ORG_NAME)
        if options["explain"]:
            self._explain()
        if options["cleanup"]:
            self._cleanup()

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------
    def _seed(self, n, org_name):
        org, _ = Organization.objects.get_or_create(name=org_name)
        set_current_organization(org.id)
        try:
            owner_user, _ = User.objects.get_or_create(email=f"perf-owner-{org.id}@example.com", defaults={"password": "x"})
            agent_a_user, _ = User.objects.get_or_create(email=f"perf-agent-a-{org.id}@example.com", defaults={"password": "x"})
            agent_b_user, _ = User.objects.get_or_create(email=f"perf-agent-b-{org.id}@example.com", defaults={"password": "x"})
            support_user, _ = User.objects.get_or_create(email=f"perf-support-{org.id}@example.com", defaults={"password": "x"})

            owner, _ = Membership.objects.get_or_create(user=owner_user, organization=org, defaults={"role": MembershipRole.OWNER})
            agent_a, _ = Membership.objects.get_or_create(user=agent_a_user, organization=org, defaults={"role": MembershipRole.SALES_AGENT})
            agent_b, _ = Membership.objects.get_or_create(user=agent_b_user, organization=org, defaults={"role": MembershipRole.SALES_AGENT})
            support, _ = Membership.objects.get_or_create(user=support_user, organization=org, defaults={"role": MembershipRole.SUPPORT_AGENT})
            if agent_a.reports_to_id is None:
                agent_a.reports_to = owner
                agent_a.save(update_fields=["reports_to"])

            self.stdout.write(f"Seeding {n} leads into org #{org.id} ({org_name})...")

            stages = [LeadStage.NEW, LeadStage.CONTACTED, LeadStage.QUALIFIED, LeadStage.PROPOSAL, LeadStage.NEGOTIATION, LeadStage.WON, LeadStage.LOST]
            owners = [agent_a, agent_b, owner]
            batch, leads = [], []
            for i in range(n):
                lead = Lead(
                    organization=org,
                    owner=random.choice(owners),
                    source=random.choice(["web", "referral", "cold_call", "event"]),
                    email=f"perf-lead-{org.id}-{i}@example.com",
                    stage=random.choice(stages),
                    is_archived=random.random() < 0.05,
                )
                if lead.stage == LeadStage.LOST:
                    lead.lost_reason = "Budget"
                batch.append(lead)
                if len(batch) >= 1000:
                    leads.extend(Lead.all_objects.bulk_create(batch))
                    batch = []
            if batch:
                leads.extend(Lead.all_objects.bulk_create(batch))

            # Customers + CustomerLeadLink, derived from a subset of Won leads
            won_leads = [l for l in leads if l.stage == LeadStage.WON][:max(1, n // 20)]
            customers = Customer.all_objects.bulk_create([
                Customer(organization=org, type=CustomerType.INDIVIDUAL, name=f"Perf Customer {i}", email=lead.email)
                for i, lead in enumerate(won_leads)
            ])
            CustomerLeadLink.objects.bulk_create([
                CustomerLeadLink(customer=customer, lead=lead)
                for customer, lead in zip(customers, won_leads)
            ])

            # Tickets against those customers
            Ticket.all_objects.bulk_create([
                Ticket(
                    organization=org, customer=customer, subject="Perf ticket",
                    status=random.choice(TicketStatus.values), assignee=support, created_by=owner,
                )
                for customer in customers
            ])

            # Activities against a subset of leads, spread across past/future due dates
            lead_ct = ContentType.objects.get_for_model(Lead)
            now = timezone.now()
            activities = Activity.all_objects.bulk_create([
                Activity(
                    organization=org, type=random.choice(ActivityType.values),
                    parent_content_type=lead_ct, parent_object_id=lead.id,
                    assignee=random.choice(owners),
                    due_date=now + timedelta(hours=random.randint(-48, 48)),
                    status=ActivityStatus.PENDING,
                )
                for lead in leads[: max(1, n // 5)]
            ])

            # Notifications for the owner, for the notification-list query
            notifications = Notification.objects.bulk_create([
                Notification(recipient_membership=owner, type=NotificationType.LEAD_ASSIGNED,
                              related_content_type=lead_ct, related_object_id=lead.id,
                              is_read=random.random() < 0.5)
                for lead in leads[: max(1, n // 5)]
            ])

            self.stdout.write(self.style.SUCCESS(
                f"Seeded {len(leads)} leads, {len(customers)} customers, {len(customers)} tickets, "
                f"{len(activities)} activities, {len(notifications)} notifications in org #{org.id} ({org_name})."
            ))
        finally:
            clear_current_organization()

    # ------------------------------------------------------------------
    # EXPLAIN ANALYZE
    # ------------------------------------------------------------------
    def _explain(self):
        try:
            org = Organization.all_objects.get(name=PERF_ORG_NAME)
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR("No perf-test org found — run --seed N first."))
            return

        set_current_organization(org.id)
        try:
            agent_a = Membership.unscoped.get(organization=org, user__email=f"perf-agent-a-{org.id}@example.com")
            owner = Membership.unscoped.get(organization=org, user__email=f"perf-owner-{org.id}@example.com")
            support = Membership.unscoped.get(organization=org, user__email=f"perf-support-{org.id}@example.com")
            team_ids = [agent_a.id, owner.id]
            lead_ct = ContentType.objects.get_for_model(Lead)
            sample_lead_id = Lead.objects.filter(organization=org).values_list("id", flat=True).first()
            now = timezone.now()

            checks = [
                ("Leads — SCOPE_OWN (idx_leads_org_owner)",
                 Lead.objects.filter(is_archived=False, owner_id=agent_a.id)),
                ("Leads — SCOPE_TEAM (idx_leads_org_owner)",
                 Lead.objects.filter(is_archived=False, owner_id__in=team_ids)),
                ("Leads — filter by stage (idx_leads_org_stage)",
                 Lead.objects.filter(stage=LeadStage.WON)),
                ("Customers — SCOPE_OWN via lead_links",
                 Customer.objects.filter(lead_links__lead__owner_id=agent_a.id).distinct()),
                ("Tickets — status + assignee (idx_tickets_org_assignee / idx_tickets_org_status)",
                 Ticket.objects.filter(status=TicketStatus.OPEN, assignee_id=support.id)),
                ("Activities — due/overdue sweep (idx_activities_assignee_due)",
                 Activity.objects.filter(status=ActivityStatus.PENDING, due_date__lte=now + timedelta(hours=24))),
                ("Activities — by parent (idx_activities_parent)",
                 Activity.objects.filter(parent_content_type=lead_ct, parent_object_id=sample_lead_id)),
                ("Notifications — unread for recipient (idx_ntf_recipient_read_created)",
                 Notification.objects.filter(recipient_membership_id=owner.id, is_read=False).order_by("-created_at")),
            ]

            for label, queryset in checks:
                self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {label} ==="))
                self.stdout.write(queryset.explain(analyze=True, buffers=True))
        finally:
            clear_current_organization()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def _cleanup(self):
        for org_name in (PERF_ORG_NAME, NOISE_ORG_NAME):
            try:
                org = Organization.all_objects.get(name=org_name)
            except Organization.DoesNotExist:
                self.stdout.write(f"No org named {org_name!r} found — nothing to clean up.")
                continue

            org_id = org.id
            set_current_organization(org_id)
            try:
                Notification.unscoped.filter(recipient_membership__organization_id=org_id).delete()
                Activity.all_objects.filter(organization_id=org_id).delete()
                CustomerLeadLink.unscoped.filter(customer__organization_id=org_id).delete()
                Ticket.all_objects.filter(organization_id=org_id).delete()
                Customer.all_objects.filter(organization_id=org_id).delete()
                Lead.all_objects.filter(organization_id=org_id).delete()
                Membership.all_objects.filter(organization_id=org_id).delete()
            finally:
                clear_current_organization()
            org.hard_delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted org #{org_id} ({org_name}) and all its data."))
