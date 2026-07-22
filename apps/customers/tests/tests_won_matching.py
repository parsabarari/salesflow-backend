from django.test import TestCase

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Contact, Customer, CustomerType
from apps.customers.services import CustomerService
from apps.leads.models import LeadStage
from apps.leads.services import LeadService, LeadStageTransitionService
from apps.organizations.models import Membership, MembershipRole, Organization


class WonCustomerMatchingTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )

    def tearDown(self):
        clear_current_organization()

    def _won(self, lead):
        return LeadStageTransitionService.transition(lead=lead, to_stage=LeadStage.WON, changed_by=self.owner)

    def test_zero_matches_creates_new_customer(self):
        lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="new@example.com")
        lead = self._won(lead)
        self.assertIsNotNone(lead.customer_id)
        self.assertFalse(lead.requires_manual_customer_selection)
        self.assertEqual(Customer.objects.get(id=lead.customer_id).type, CustomerType.INDIVIDUAL)

    def test_exactly_one_match_links_existing_customer(self):
        existing = Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="Jane", email="jane@example.com")
        lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="jane@example.com")
        lead = self._won(lead)
        self.assertEqual(lead.customer_id, existing.id)
        self.assertFalse(lead.requires_manual_customer_selection)

    def test_match_via_contact_email_not_just_customer_email(self):
        company = Customer.objects.create(organization=self.organization, type=CustomerType.COMPANY, name="Acme Corp")
        Contact.objects.create(customer=company, name="Bob", email="bob@acmecorp.com")
        lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="bob@acmecorp.com")
        lead = self._won(lead)
        self.assertEqual(lead.customer_id, company.id)

    def test_multiple_matches_flags_manual_selection_and_does_not_link(self):
        Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="A", email="shared@example.com")
        Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="B", email="shared@example.com")
        lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="shared@example.com")
        lead = self._won(lead)
        self.assertIsNone(lead.customer_id)
        self.assertTrue(lead.requires_manual_customer_selection)

    def test_soft_deleted_customer_excluded_from_matching(self):
        stale = Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="Old", email="old@example.com")
        stale.delete()
        lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="old@example.com")
        lead = self._won(lead)
        self.assertNotEqual(lead.customer_id, stale.id)  # a NEW customer should be created instead

    def test_resolve_manual_selection_links_chosen_candidate(self):
        candidate_a = Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="A", email="shared@example.com")
        Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="B", email="shared@example.com")
        lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="shared@example.com")
        lead = self._won(lead)
        self.assertTrue(lead.requires_manual_customer_selection)

        CustomerService.resolve_manual_selection(lead=lead, customer_id=candidate_a.id)
        lead.refresh_from_db()
        self.assertEqual(lead.customer_id, candidate_a.id)
        self.assertFalse(lead.requires_manual_customer_selection)

    def test_resolve_manual_selection_rejects_non_candidate_id(self):
        Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="A", email="shared@example.com")
        Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="B", email="shared@example.com")
        unrelated = Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="Unrelated", email="other@example.com")
        lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="shared@example.com")
        lead = self._won(lead)

        with self.assertRaises(ValueError):
            CustomerService.resolve_manual_selection(lead=lead, customer_id=unrelated.id)
