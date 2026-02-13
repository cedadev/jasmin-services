import datetime as dt
from unittest import mock

import django.contrib.auth
import django.test

import jasmin_metadata.models
import jasmin_services.models


class AccountReactivationTest(django.test.TestCase):
    def setUp(self):
        self.user = django.contrib.auth.get_user_model().objects.create_user(
            username="testuser",
            email="test@example.com",
        )
        self.user.notify_if_not_exists = mock.Mock()
        self.user.notify = mock.Mock()
        metadata_form = jasmin_metadata.models.Form.objects.create(name="test_form")
        self.category = jasmin_services.models.Category.objects.create(
            name="test_category",
            long_name="Test Category",
            position=1,
        )
        self.service = jasmin_services.models.Service.objects.create(
            category=self.category,
            name="test_service",
            summary="Test service",
            description="Test service description",
        )
        self.role = jasmin_services.models.Role.objects.create(
            service=self.service,
            name="test_role",
            description="Test role",
            metadata_form=metadata_form,
        )
        self.access = jasmin_services.models.Access.objects.create(
            user=self.user,
            role=self.role,
        )

    def test_reactivate_unexpired_grant(self):
        """
        Grant not yet expired should be fully reinstated with original expiry date.
        """
        future_expiry = dt.date.today() + dt.timedelta(days=180)
        grant = jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=future_expiry,
            revoked=True,
            user_reason="Account was suspended",
        )

        self.user.is_active = True
        self.user.save()

        grant.refresh_from_db()
        self.assertFalse(grant.revoked)
        self.assertEqual(grant.user_reason, "")
        self.assertEqual(grant.expires, future_expiry)

    def test_reactivate_recently_expired_grant(self):
        """
        Grant expired within last 2 years should create new 30-day grant.
        """
        expired_recently = dt.date.today() - dt.timedelta(days=365)
        grant = jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=expired_recently,
            revoked=True,
            user_reason="Account was suspended",
        )

        self.user.is_active = True
        self.user.save()

        grant.refresh_from_db()
        self.assertTrue(grant.revoked)

        new_grant = jasmin_services.models.Grant.objects.filter(
            access=self.access,
            previous_grant=grant,
        ).first()

        self.assertIsNotNone(new_grant)
        self.assertEqual(new_grant.granted_by, "admin")
        self.assertEqual(new_grant.expires, dt.date.today() + dt.timedelta(days=30))
        self.assertFalse(new_grant.revoked)

    def test_reactivate_old_expired_grant(self):
        """
        Grant expired more than 2 years ago should not be reinstated.
        """
        expired_long_ago = dt.date.today() - dt.timedelta(days=731)
        grant = jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=expired_long_ago,
            revoked=True,
            user_reason="Account was suspended",
        )

        self.user.is_active = True
        self.user.save()

        grant.refresh_from_db()
        self.assertTrue(grant.revoked)

        new_grant_count = jasmin_services.models.Grant.objects.filter(
            access=self.access,
            previous_grant=grant,
        ).count()

        self.assertEqual(new_grant_count, 0)

    def test_reactivate_at_two_year_boundary(self):
        """
        Grant expired exactly 730 days ago should still be reinstated.
        """
        expired_at_boundary = dt.date.today() - dt.timedelta(days=730)
        grant = jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=expired_at_boundary,
            revoked=True,
            user_reason="Account was suspended",
        )

        self.user.is_active = True
        self.user.save()

        new_grant = jasmin_services.models.Grant.objects.filter(
            access=self.access,
            previous_grant=grant,
        ).first()

        self.assertIsNotNone(new_grant)

    def test_reactivate_request(self):
        """
        Pending request rejected due to suspension should be reinstated.
        """
        request = jasmin_services.models.Request.objects.create(
            access=self.access,
            state=jasmin_services.models.RequestState.REJECTED,
            user_reason="Account was suspended",
        )

        self.user.is_active = True
        self.user.save()

        request.refresh_from_db()
        self.assertEqual(request.state, jasmin_services.models.RequestState.PENDING)
        self.assertEqual(request.user_reason, "")

    def test_different_revocation_reason_not_reinstated(self):
        """
        Grant revoked for a different reason should not be reinstated.
        """
        grant = jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=180),
            revoked=True,
            user_reason="Security violation",
        )

        self.user.is_active = True
        self.user.save()

        grant.refresh_from_db()
        self.assertTrue(grant.revoked)
        self.assertEqual(grant.user_reason, "Security violation")

    def test_disabled_service_not_reinstated(self):
        """
        Grant from disabled service should not be reinstated.
        """
        self.service.disabled = True
        self.service.save()

        grant = jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=180),
            revoked=True,
            user_reason="Account was suspended",
        )

        self.user.is_active = True
        self.user.save()

        grant.refresh_from_db()
        self.assertTrue(grant.revoked)
