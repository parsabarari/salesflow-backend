from django.contrib.contenttypes.models import ContentType

from apps.notifications.models import Notification


class NotificationService:
    @staticmethod
    def create(*, recipient_membership, notification_type: str, related_object) -> Notification:
        content_type = ContentType.objects.get_for_model(related_object.__class__)
        return Notification.objects.create(
            recipient_membership=recipient_membership,
            type=notification_type,
            related_content_type=content_type,
            related_object_id=related_object.id,
        )

    @staticmethod
    def mark_read(notification: Notification) -> Notification:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return notification

    @staticmethod
    def mark_all_read(recipient_membership) -> int:
        return Notification.objects.filter(recipient_membership=recipient_membership, is_read=False).update(is_read=True)
