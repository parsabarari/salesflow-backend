from django.contrib.contenttypes.models import ContentType

from apps.audit.models import AuditActionType, AuditLog


class AuditLogService:
    @staticmethod
    def record(*, organization, actor_membership, action_type: str, target, metadata: dict | None = None) -> AuditLog:
        return AuditLog.objects.create(
            organization=organization,
            actor_membership=actor_membership,
            action_type=action_type,
            target_content_type=ContentType.objects.get_for_model(target),
            target_object_id=target.pk,
            metadata=metadata or {},
        )
    