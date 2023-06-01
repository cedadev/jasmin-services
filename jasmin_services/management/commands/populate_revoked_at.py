import django.core.management.base
import jasmin_notifications.models

import jasmin_services.models


class Command(django.core.management.base.BaseCommand):
    help = "Populate revoked_at field."

    def handle(self, *args, **options):
        grants = jasmin_services.models.Grant.objects.filter(revoked=True, revoked_at=None)

        notification_type = jasmin_notifications.models.NotificationType.objects.get(
            name="grant_revoked"
        )

        for grant in grants:
            try:
                notification = jasmin_notifications.models.UserNotification.objects.get(
                    notification_type=notification_type, user=grant.user, target_id=grant.id
                )
            except jasmin_notifications.models.UserNotification.DoesNotExist:
                self.stdout.write(f"No notification was found for grant {grant.id}")
            else:
                grant.revoked_at = notification.created_at
                grant.save()
