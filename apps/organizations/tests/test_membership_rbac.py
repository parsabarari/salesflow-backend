from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditActionType, AuditLog
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization
from apps.organizations.services import TeamService


class MembershipRBACTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        self.other_organization = Organization.objects.create(name="Other")

        self.owner_user = User.objects.create_user(email="owner@example.com", password="secret")
        self.admin_user = User.objects.create_user(email="admin@example.com", password="secret")
        self.agent_user = User.objects.create_user(email="agent@example.com", password="secret")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(user=self.owner_user, organization=self.organization, role=MembershipRole.OWNER)
        self.admin = Membership.objects.create(user=self.admin_user, organization=self.organization, role=MembershipRole.ADMIN)
        self.agent = Membership.objects.create(user=self.agent_user, organization=self.organization, role=MembershipRole.SALES_AGENT)
        clear_current_organization()

    def _url(self, membership_id):
        return f"/api/v1/organizations/{self.organization.id}/memberships/{membership_id}/"

    def test_owner_can_change_role(self):
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.patch(self._url(self.agent.id), {"role": MembershipRole.SALES_MANAGER}, format="json")
        self.assertEqual(response.status_code, 200)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.role, MembershipRole.SALES_MANAGER)
        self.assertTrue(
            AuditLog.unscoped.filter(action_type=AuditActionType.ROLE_CHANGED, target_object_id=self.agent.id).exists()
        )

    def test_sales_agent_cannot_change_roles(self):
        self.client.force_authenticate(user=self.agent_user)
        response = self.client.patch(self._url(self.admin.id), {"role": MembershipRole.VIEWER}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_cannot_change_own_role(self):
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.patch(self._url(self.owner.id), {"role": MembershipRole.ADMIN}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_admin_cannot_promote_to_owner(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(self._url(self.agent.id), {"role": MembershipRole.OWNER}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_owner_can_transfer_ownership(self):
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.patch(self._url(self.agent.id), {"role": MembershipRole.OWNER}, format="json")
        self.assertEqual(response.status_code, 200)

        self.agent.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(self.agent.role, MembershipRole.OWNER)
        self.assertEqual(self.owner.role, MembershipRole.ADMIN)  # auto-demoted

        self.assertTrue(
            AuditLog.unscoped.filter(action_type=AuditActionType.OWNERSHIP_TRANSFERRED, target_object_id=self.agent.id).exists()
        )
        self.assertTrue(
            AuditLog.unscoped.filter(
                action_type=AuditActionType.ROLE_CHANGED,
                target_object_id=self.owner.id,
                metadata__reason="auto_demoted_after_ownership_transfer",
            ).exists()
        )

    def test_membership_in_other_org_returns_404(self):
        set_current_organization(self.other_organization.id)
        other_org_membership = Membership.objects.create(
            user=User.objects.create_user(email="stranger@example.com", password="secret"),
            organization=self.other_organization,
            role=MembershipRole.VIEWER,
        )
        clear_current_organization()

        self.client.force_authenticate(user=self.owner_user)
        response = self.client.patch(self._url(other_org_membership.id), {"role": MembershipRole.ADMIN}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_owner_can_remove_member(self):
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.delete(self._url(self.agent.id))
        self.assertEqual(response.status_code, 204)
        self.agent.refresh_from_db()
        self.assertIsNotNone(self.agent.deleted_at)
        self.assertTrue(
            AuditLog.unscoped.filter(action_type=AuditActionType.MEMBER_REMOVED, target_object_id=self.agent.id).exists()
        )

    def test_cannot_remove_self(self):
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.delete(self._url(self.owner.id))
        self.assertEqual(response.status_code, 400)

    def test_removed_member_cannot_still_use_admin_permissions(self):
        set_current_organization(self.organization.id)
        self.admin.deleted_at = timezone.now()
        self.admin.save(update_fields=["deleted_at"])
        clear_current_organization()

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(self._url(self.agent.id), {"role": MembershipRole.VIEWER}, format="json")
        self.assertEqual(response.status_code, 404)


class TeamServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.manager = Membership.objects.create(
            user=User.objects.create_user(email="manager@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_MANAGER,
        )
        self.direct_report = Membership.objects.create(
            user=User.objects.create_user(email="report@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
            reports_to=self.manager,
        )
        self.sub_report = Membership.objects.create(
            user=User.objects.create_user(email="subreport@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
            reports_to=self.direct_report,
        )
        clear_current_organization()

    def test_team_is_direct_reports_only_not_recursive(self):
        set_current_organization(self.organization.id)
        try:
            team_ids = TeamService.team_membership_ids(self.manager)
        finally:
            clear_current_organization()

        self.assertEqual(team_ids, [self.direct_report.id])
        self.assertNotIn(self.sub_report.id, team_ids)
