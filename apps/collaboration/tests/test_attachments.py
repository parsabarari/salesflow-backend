import shutil
import tempfile

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.collaboration.models import Attachment
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead
from apps.organizations.models import Membership, MembershipRole, Organization

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}},
    MEDIA_ROOT=TEMP_MEDIA_ROOT,
)
class AttachmentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

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
        clear_current_organization()

    def _upload_url(self):
        return f"/api/v1/organizations/{self.organization.id}/attachments/"

    def _detail_url(self, attachment_id):
        return f"/api/v1/organizations/{self.organization.id}/attachments/{attachment_id}/"

    def _file(self, name="test.txt", content=b"hello world"):
        return SimpleUploadedFile(name, content, content_type="text/plain")

    def test_owner_can_upload_to_lead(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._upload_url(),
            {"parent_type": "lead", "parent_id": self.lead.id, "file": self._file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["original_filename"], "test.txt")
        self.assertEqual(response.data["file_size_bytes"], len(b"hello world"))

    def test_agent_can_upload_to_own_lead(self):
        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.post(
            self._upload_url(),
            {"parent_type": "lead", "parent_id": self.lead.id, "file": self._file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    def test_agent_cannot_upload_to_others_lead(self):
        self.client.force_authenticate(user=self.agent_b.user)
        response = self.client.post(
            self._upload_url(),
            {"parent_type": "lead", "parent_id": self.lead.id, "file": self._file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_ticket_parent_type_rejected(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._upload_url(),
            {"parent_type": "ticket", "parent_id": 1, "file": self._file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_returns_signed_url(self):
        self.client.force_authenticate(user=self.owner.user)
        create_response = self.client.post(
            self._upload_url(),
            {"parent_type": "lead", "parent_id": self.lead.id, "file": self._file()},
            format="multipart",
        )
        attachment_id = create_response.data["id"]

        response = self.client.get(self._detail_url(attachment_id))
        self.assertEqual(response.status_code, 200)
        self.assertIn("url", response.data)

    def test_delete_soft_deletes(self):
        self.client.force_authenticate(user=self.owner.user)
        create_response = self.client.post(
            self._upload_url(),
            {"parent_type": "lead", "parent_id": self.lead.id, "file": self._file()},
            format="multipart",
        )
        attachment_id = create_response.data["id"]

        response = self.client.delete(self._detail_url(attachment_id))
        self.assertEqual(response.status_code, 204)

        set_current_organization(self.organization.id)
        try:
            self.assertIsNotNone(Attachment.all_objects.get(id=attachment_id).deleted_at)
        finally:
            clear_current_organization()
