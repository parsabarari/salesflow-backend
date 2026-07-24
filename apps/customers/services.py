from django.db import transaction

from apps.core.normalization import normalize_email, normalize_phone
from apps.customers.models import Contact, Customer, CustomerLeadLink, CustomerType


class CustomerMatchService:
    """Business Rules 5.3 / 6.3 — checks both a Customer's own
    email/phone AND any active Contact's email/phone linked to that
    Customer. Soft-deleted Customers/Contacts already excluded by their
    managers (PRD §7)."""

    @staticmethod
    def find_matching_customer_ids(*, email, phone) -> list[int]:
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        if not normalized_email and not normalized_phone:
            return []

        matched_ids = set()

        for customer in Customer.objects.only("id", "email", "phone"):
            if normalized_email and normalize_email(customer.email) == normalized_email:
                matched_ids.add(customer.id)
                continue
            if normalized_phone and normalize_phone(customer.phone) == normalized_phone:
                matched_ids.add(customer.id)

        for contact in Contact.objects.only("id", "email", "phone", "customer_id"):
            if normalized_email and normalize_email(contact.email) == normalized_email:
                matched_ids.add(contact.customer_id)
                continue
            if normalized_phone and normalize_phone(contact.phone) == normalized_phone:
                matched_ids.add(contact.customer_id)

        return sorted(matched_ids)


class CustomerService:
    @staticmethod
    @transaction.atomic
    def resolve_won_lead(*, lead) -> dict:
        """Business Rules 5.3 — executed when a Lead transitions to Won."""

        matching_ids = CustomerMatchService.find_matching_customer_ids(email=lead.email, phone=lead.phone)

        if len(matching_ids) == 0:
            # ASSUMPTION, not specified in the docs (flagging rather than
            # silently deciding): a Lead carries no company/individual
            # indicator, so an auto-created Customer defaults to
            # `individual`. Editable afterward via PATCH /customers/{id}.
            # Recommend recording this default in Business Rules once confirmed.
            customer = Customer.objects.create(
                organization=lead.organization,
                type=CustomerType.INDIVIDUAL,
                name=lead.email or lead.phone or f"Lead #{lead.id}",
                email=lead.email,
                phone=lead.phone,
            )
            CustomerLeadLink.objects.create(customer=customer, lead=lead)
            lead.customer = customer
            lead.requires_manual_customer_selection = False
            lead.save(update_fields=["customer", "requires_manual_customer_selection"])
            return {"outcome": "created", "customer_id": customer.id}

        if len(matching_ids) == 1:
            customer = Customer.objects.get(id=matching_ids[0])
            CustomerLeadLink.objects.create(customer=customer, lead=lead)
            lead.customer = customer
            lead.requires_manual_customer_selection = False
            lead.save(update_fields=["customer", "requires_manual_customer_selection"])
            return {"outcome": "linked", "customer_id": customer.id}

        # More than one match: don't auto-link (Business Rules 5.3.4)
        lead.requires_manual_customer_selection = True
        lead.save(update_fields=["requires_manual_customer_selection"])
        return {"outcome": "manual_selection_required", "candidate_customer_ids": matching_ids}

    @staticmethod
    @transaction.atomic
    def resolve_manual_selection(*, lead, customer_id) -> Customer:
        if not lead.requires_manual_customer_selection:
            raise ValueError("This Lead does not require manual customer selection.")

        # Re-run the match rather than trusting a stored candidate list
        # (none is persisted — the docs only require the IDs appear in
        # the original API response, not that they're stored server-side).
        # This also guards against resolve-customer being called with an
        # arbitrary customer_id that was never actually a match.
        matching_ids = CustomerMatchService.find_matching_customer_ids(email=lead.email, phone=lead.phone)
        if customer_id not in matching_ids:
            raise ValueError("customer_id is not one of the matching candidates for this Lead.")

        customer = Customer.objects.get(id=customer_id)
        CustomerLeadLink.objects.create(customer=customer, lead=lead)
        lead.customer = customer
        lead.requires_manual_customer_selection = False
        lead.save(update_fields=["customer", "requires_manual_customer_selection"])
        return customer


class ContactService:
    @staticmethod
    def create(*, customer, name, email=None, phone=None) -> Contact:
        return Contact.objects.create(customer=customer, name=name, email=email, phone=phone)

    @staticmethod
    def remove(*, contact) -> None:
        # Business Rules 6.1 / ERD §9 note: company-type Customer must
        # keep at least one Contact. Enforced here, at the only place
        # a Contact can be removed (service layer, not a DB constraint,
        # matching the ERD's own reasoning for why this isn't a CHECK).
        customer = contact.customer
        if customer.type == CustomerType.COMPANY:
            remaining = Contact.objects.filter(customer=customer).exclude(id=contact.id).count()
            if remaining == 0:
                raise ValueError("Cannot remove the last Contact of a company-type Customer.")
        contact.delete()
