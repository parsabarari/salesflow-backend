from django.test import TestCase

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead
from apps.leads.services import LeadDuplicateService
from apps.organizations.models import Membership, MembershipRole, Organization


class LeadDuplicateServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner_membership = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )

    def tearDown(self):
        clear_current_organization()

    def test_normalized_email_match_found(self):
        Lead.objects.create(organization=self.organization, owner=self.owner_membership, source="web", email="Jane@Example.com  ".strip())
        duplicates = LeadDuplicateService.find_possible_duplicates(email="  jane@example.com", phone=None)
        self.assertEqual(len(duplicates), 1)

    def test_normalized_phone_match_found(self):
        Lead.objects.create(organization=self.organization, owner=self.owner_membership, source="web", phone="+1 (555) 123-4567")
        duplicates = LeadDuplicateService.find_possible_duplicates(email=None, phone="5551234567")
        self.assertEqual(len(duplicates), 1)

    def test_archived_leads_excluded_from_matching(self):
        lead = Lead.objects.create(organization=self.organization, owner=self.owner_membership, source="web", email="jane@example.com")
        lead.is_archived = True
        lead.save(update_fields=["is_archived"])
        duplicates = LeadDuplicateService.find_possible_duplicates(email="jane@example.com", phone=None)
        self.assertEqual(duplicates, [])

    def test_no_match_returns_empty(self):
        duplicates = LeadDuplicateService.find_possible_duplicates(email="nobody@example.com", phone=None)
        self.assertEqual(duplicates, [])
