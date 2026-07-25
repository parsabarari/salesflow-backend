from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.collaboration.models import CommentMention
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Customer, CustomerType
from apps.leads.models import Lead
from apps.organizations.models import Membership, MembershipRole, Organization


class CommentCRUDTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.agent_a = Membership.objects.create(
            user=User.objects.create_user(email="agenta@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        self.agent_b = Membership.objects.create(
            user=User.objects.create_user(email="agentb@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        self.lead = Lead.objects.create(
            organization=self.organization, owner=self.agent_a, source="web", email="lead@example.com"
        )
        self.customer = Customer.objects.create(
            organization=self.organization, type=CustomerType.INDIVIDUAL, name="Jane", email="jane@example.com"
        )
        clear_current_organization()

    def _comments_url(self):
        return f"/api/v1/organizations/{self.organization.id}/comments/"

    def _detail_url(self, comment_id):
        return f"/api/v1/organizations/{self.organization.id}/comments/{comment_id}/"

    def test_owner_can_comment_on_lead(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._comments_url(), {"parent_type": "lead", "parent_id": self.lead.id, "body": "Hello"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["parent_type"], "lead")

    def test_agent_can_comment_on_own_lead(self):
        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.post(
            self._comments_url(), {"parent_type": "lead", "parent_id": self.lead.id, "body": "Hi"}, format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_agent_cannot_comment_on_others_lead(self):
        self.client.force_authenticate(user=self.agent_b.user)
        response = self.client.post(
            self._comments_url(), {"parent_type": "lead", "parent_id": self.lead.id, "body": "Hi"}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_parent_type_and_id_required_together(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._comments_url() + "?parent_type=lead")
        self.assertEqual(response.status_code, 400)

    def test_list_comments_for_parent(self):
        self.client.force_authenticate(user=self.owner.user)
        self.client.post(self._comments_url(), {"parent_type": "lead", "parent_id": self.lead.id, "body": "A"}, format="json")
        self.client.post(self._comments_url(), {"parent_type": "lead", "parent_id": self.lead.id, "body": "B"}, format="json")

        response = self.client.get(self._comments_url() + f"?parent_type=lead&parent_id={self.lead.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_mention_creates_commentmention_for_valid_member(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._comments_url(),
            {"parent_type": "lead", "parent_id": self.lead.id, "body": f"Hey @{self.agent_a.user.email} check this"},
            format="json",
        )
        self.assertEqual(response.data["mentioned_membership_ids"], [self.agent_a.id])

        set_current_organization(self.organization.id)
        try:
            self.assertEqual(CommentMention.objects.filter(comment_id=response.data["id"]).count(), 1)
        finally:
            clear_current_organization()

    def test_mention_ignored_for_non_member_email(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._comments_url(),
            {"parent_type": "lead", "parent_id": self.lead.id, "body": "Hey @nobody@nowhere.com check this"},
            format="json",
        )
        self.assertEqual(response.data["mentioned_membership_ids"], [])

    def test_editing_body_resyncs_mentions(self):
        self.client.force_authenticate(user=self.owner.user)
        create_response = self.client.post(
            self._comments_url(),
            {"parent_type": "lead", "parent_id": self.lead.id, "body": f"Hey @{self.agent_a.user.email}"},
            format="json",
        )
        comment_id = create_response.data["id"]

        patch_response = self.client.patch(
            self._detail_url(comment_id), {"body": f"Actually @{self.agent_b.user.email}"}, format="json"
        )
        self.assertEqual(patch_response.data["mentioned_membership_ids"], [self.agent_b.id])

    def test_author_can_edit_own_comment(self):
        self.client.force_authenticate(user=self.agent_a.user)
        create_response = self.client.post(
            self._comments_url(), {"parent_type": "lead", "parent_id": self.lead.id, "body": "Original"}, format="json"
        )
        response = self.client.patch(self._detail_url(create_response.data["id"]), {"body": "Edited"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["body"], "Edited")

    def test_non_author_non_admin_cannot_edit(self):
        self.client.force_authenticate(user=self.agent_a.user)
        create_response = self.client.post(
            self._comments_url(), {"parent_type": "lead", "parent_id": self.lead.id, "body": "Original"}, format="json"
        )
        comment_id = create_response.data["id"]

        manager = Membership.objects.create(
            user=User.objects.create_user(email="manager@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_MANAGER,
        )
        set_current_organization(self.organization.id)
        try:
            self.lead.owner = manager  # so manager's team-scope covers this lead
            self.lead.save(update_fields=["owner"])
            manager.reports_to = None
            self.agent_a.reports_to = manager
            self.agent_a.save(update_fields=["reports_to"])
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=manager.user)
        response = self.client.patch(self._detail_url(comment_id), {"body": "Hijacked"}, format="json")
        self.assertEqual(response.status_code, 403)  # visible (team scope) but not author, not Owner/Admin

    def test_delete_soft_deletes(self):
        self.client.force_authenticate(user=self.owner.user)
        create_response = self.client.post(
            self._comments_url(), {"parent_type": "lead", "parent_id": self.lead.id, "body": "Bye"}, format="json"
        )
        response = self.client.delete(self._detail_url(create_response.data["id"]))
        self.assertEqual(response.status_code, 204)
