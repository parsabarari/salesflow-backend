from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.collaboration.services import AttachmentService, CommentService
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead
from apps.organizations.models import Membership, MembershipRole, Organization


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}})
class CommentAttachmentRestoreTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.OWNER,
        )
        self.agent = Membership.objects.create(
            user=User.objects.create_user(email="agent@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.SALES_AGENT,
        )
        self.lead = Lead.objects.create(
            organization=self.organization, owner=self.agent, source="web", email="lead@example.com",
        )
        self.comment = CommentService.create(
            organization=self.organization, parent_type="lead", parent_id=self.lead.id,
            author=self.owner, body="hello",
        )
        self.comment.delete()

        self.attachment = AttachmentService.create(
            organization=self.organization, parent_type="lead", parent_id=self.lead.id,
            uploaded_by=self.owner, uploaded_file=SimpleUploadedFile("f.txt", b"hi"),
        )
        self.attachment.delete()
        clear_current_organization()

    def test_owner_can_restore_comment(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            f"/api/v1/organizations/{self.organization.id}/comments/{self.comment.id}/restore/"
        )
        self.assertEqual(response.status_code, 200)

    def test_agent_cannot_restore_comment(self):
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.post(
            f"/api/v1/organizations/{self.organization.id}/comments/{self.comment.id}/restore/"
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_can_restore_attachment(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            f"/api/v1/organizations/{self.organization.id}/attachments/{self.attachment.id}/restore/"
        )
        self.assertEqual(response.status_code, 200)
