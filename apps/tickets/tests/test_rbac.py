from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Customer, CustomerType
from apps.organizations.models import Membership, MembershipRole, Organization


class TicketRBACTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.manager = Membership.objects.create(
            user=User.objects.create_user(email="manager@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_MANAGER,
        )
        self.sales_agent = Membership.objects.create(
            user=User.objects.create_user(email="agent@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        self.support_lead = Membership.objects.create(
            user=User.objects.create_user(email="supportlead@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SUPPORT_AGENT,
        )
        self.support_a = Membership.objects.create(
            user=User.objects.create_user(email="supporta@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SUPPORT_AGENT,
            reports_to=self.support_lead,
        )
        self.support_b = Membership.objects.create(
            user=User.objects.create_user(email="supportb@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SUPPORT_AGENT,
        )
        self.viewer = Membership.objects.create(
            user=User.objects.create_user(email="viewer@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.VIEWER,
        )
        self.customer = Customer.objects.create(
            organization=self.organization, type=CustomerType.INDIVIDUAL, name="Jane", email="jane@example.com"
        )
        clear_current_organization()

    def _list_url(self):
        return f"/api/v1/organizations/{self.organization.id}/tickets/"

    def _create_as(self, membership, assignee):
        self.client.force_authenticate(user=membership.user)
        return self.client.post(
            self._list_url(),
            {"customer_id": self.customer.id, "subject": "Issue", "assignee_id": assignee.id if assignee else None},
            format="json",
        )

    def test_sales_agent_has_no_ticket_access(self):
        self.client.force_authenticate(user=self.sales_agent.user)
        response = self.client.get(self._list_url())
        self.assertEqual(response.status_code, 403)

    def test_sales_manager_can_read_but_not_write(self):
        self._create_as(self.owner, self.support_a)
        self.client.force_authenticate(user=self.manager.user)

        get_response = self.client.get(self._list_url())
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(len(get_response.data), 1)

        post_response = self._create_as(self.manager, self.support_a)
        self.assertEqual(post_response.status_code, 403)

    def test_viewer_can_read_but_not_write(self):
        self._create_as(self.owner, self.support_a)
        self.client.force_authenticate(user=self.viewer.user)

        get_response = self.client.get(self._list_url())
        self.assertEqual(get_response.status_code, 200)

        post_response = self._create_as(self.viewer, self.support_a)
        self.assertEqual(post_response.status_code, 403)

    def test_support_agent_can_create_assigned_to_self(self):
        response = self._create_as(self.support_a, self.support_a)
        self.assertEqual(response.status_code, 201)

    def test_support_agent_can_assign_to_team_member(self):
        response = self._create_as(self.support_lead, self.support_a)
        self.assertEqual(response.status_code, 201)

    def test_support_agent_cannot_assign_outside_team(self):
        response = self._create_as(self.support_a, self.support_b)
        self.assertEqual(response.status_code, 400)

    def test_support_agent_sees_only_own_plus_team_tickets(self):
        self._create_as(self.support_lead, self.support_a)  # support_a reports to support_lead
        self._create_as(self.owner, self.support_b)  # support_b not on that team

        self.client.force_authenticate(user=self.support_lead.user)
        response = self.client.get(self._list_url())
        assignee_ids = {t["assignee_id"] for t in response.data}
        self.assertIn(self.support_a.id, assignee_ids)
        self.assertNotIn(self.support_b.id, assignee_ids)

    def test_owner_sees_all_tickets(self):
        self._create_as(self.owner, self.support_a)
        self._create_as(self.owner, self.support_b)

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._list_url())
        self.assertEqual(len(response.data), 2)