import re

from django.db import transaction

from apps.leads.models import Lead, LeadStage, LeadStageHistory
from apps.core.permissions import SCOPE_FULL, SCOPE_OWN, SCOPE_TEAM
from apps.organizations.services import TeamService


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower()


def normalize_phone(phone: str | None) -> str | None:
    """Business Rules 4.3: strip formatting before comparison. The rule's
    own example ('+1 (555) 123-4567' vs '5551234567') requires more than
    stripping spaces/dashes/parens — it also needs the leading NANP
    country code normalized away, or those two never match."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


class LeadDuplicateService:
    """Business Rules 4.3 — non-blocking duplicate warning.

    Implementation note: matching is done in Python rather than at the
    DB layer, since phone numbers aren't stored pre-normalized (ERD §6
    has no normalized_phone column) and Postgres citext already handles
    case-insensitive email equality but not punctuation-stripped phone
    comparison. A full Python scan over active Leads in the org is
    acceptable at the PRD's stated target scale (5-50 users per org,
    01-product-requirements.md §3) — if lead volume per org grows well
    beyond that, this would be worth revisiting (e.g. a normalized
    generated column + DB-level index), but that's not justified yet.
    """

    @staticmethod
    def find_possible_duplicates(*, email: str | None, phone: str | None, exclude_lead_id=None) -> list[int]:
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        if not normalized_email and not normalized_phone:
            return []

        candidates = Lead.objects.filter(is_archived=False)
        if exclude_lead_id is not None:
            candidates = candidates.exclude(id=exclude_lead_id)

        duplicate_ids = []
        for candidate in candidates.only("id", "email", "phone"):
            if normalized_email and normalize_email(candidate.email) == normalized_email:
                duplicate_ids.append(candidate.id)
                continue
            if normalized_phone and normalize_phone(candidate.phone) == normalized_phone:
                duplicate_ids.append(candidate.id)
        return duplicate_ids


# Free movement between all non-terminal stages (Business Rules 5.2) —
# encoded as "any non-terminal stage can move to any other non-terminal
# stage, or to Lost" rather than an explicit adjacency list, since the
# rule is explicitly "free in either direction, including skipping stages."
NON_TERMINAL_STAGES = {
    LeadStage.NEW,
    LeadStage.CONTACTED,
    LeadStage.QUALIFIED,
    LeadStage.PROPOSAL,
    LeadStage.NEGOTIATION,
}


class LeadStageTransitionService:
    @staticmethod
    @transaction.atomic
    def transition(*, lead: Lead, to_stage: str, changed_by, reason: str | None = None) -> Lead:
        if to_stage not in LeadStage.values:
            raise ValueError(f"'{to_stage}' is not a valid stage.")

        # Won is terminal (Business Rules 5.2) — no transition is permitted
        # once a Lead is Won, since Won triggers Customer creation/linking
        # (Business Rules 5.3), a side effect that must not be silently
        # re-triggered or undone by a later stage change.
        if lead.stage == LeadStage.WON:
            raise ValueError("Won is terminal — this Lead can no longer change stage.")

        if to_stage == LeadStage.LOST and not reason:
            raise ValueError("lost_reason is required when transitioning to Lost.")

        from_stage = lead.stage
        lead.stage = to_stage

        if to_stage == LeadStage.LOST:
            lead.lost_reason = reason
        elif from_stage == LeadStage.LOST:
            # Business Rules 5.2: Lost is reversible ("reactivating" a
            # lost deal). Assumption (not explicitly stated in the docs,
            # flagging as a judgment call): lost_reason is cleared on
            # reactivation, since it described *why it was lost that
            # time* and would be stale/misleading if left behind on a
            # Lead that's active again. The DB CHECK constraint only
            # requires lost_reason IS NOT NULL while stage='lost', so
            # clearing it here isn't required by the schema — it's a
            # data-hygiene choice, easy to revert if you'd rather keep it.
            lead.lost_reason = None

        # NOTE: Business Rules 5.3 (Won -> Customer matching/linking) is
        # deliberately NOT implemented here. docs/07-implementation-
        # roadmap.md scopes that logic to Phase 2.1 ("Won→Customer
        # linking logic"), since it depends on apps.customers.Customer,
        # which doesn't exist yet (Phase 1.3 is Leads only). Reaching
        # Won in this phase just marks the stage as terminal; no
        # Customer row is created and requires_manual_customer_selection
        # stays False. This will be wired in once Customer exists.

        lead.save(update_fields=["stage", "lost_reason"])

        LeadStageHistory.objects.create(
            lead=lead,
            from_stage=from_stage,
            to_stage=to_stage,
            changed_by=changed_by,
            reason=reason,
        )
        return lead
    

def assert_can_assign_owner(*, actor_membership, target_owner, scope: str) -> None:
    """Enforces who a Lead's owner can be set to, per the same PRD 5.3
    scope resolved for the request. Not a Business-Rules-numbered rule
    on its own — it's the natural implication of "Own only" / "Full
    (team)" applying to Lead *creation/assignment*, not just visibility."""

    if scope == SCOPE_FULL:
        return
    if scope == SCOPE_OWN:
        if target_owner.id != actor_membership.id:
            raise ValueError("You can only create or assign Leads to yourself.")
        return
    if scope == SCOPE_TEAM:
        if target_owner.id == actor_membership.id:
            return
        if TeamService.is_in_team(actor_membership, target_owner.id):
            return
        raise ValueError("You can only assign Leads to yourself or your team.")
    raise ValueError("You do not have permission to assign Lead ownership.")
    

class LeadService:
    @staticmethod
    @transaction.atomic
    def create_lead(*, organization, owner, source, email=None, phone=None) -> Lead:
        """Centralizes Lead creation so every creation path gets the
        initial stage-history row (Domain Model §8 — 'first row on
        creation has no from_stage'). Previously this was written inline
        only in the view, so any other creation path silently skipped it."""
        lead = Lead.objects.create(organization=organization, owner=owner, source=source, email=email, phone=phone)
        LeadStageHistory.objects.create(lead=lead, from_stage=None, to_stage=lead.stage, changed_by=owner)
        return lead
