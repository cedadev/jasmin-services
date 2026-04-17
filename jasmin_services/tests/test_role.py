import datetime as dt
from unittest import mock

import django.contrib.auth
import django.test

import jasmin_metadata.models
import jasmin_services.models


class RoleUserHasRoleTest(django.test.TestCase):
    """Tests for Role.user_has_role()."""

    def setUp(self):
        self.user = django.contrib.auth.get_user_model().objects.create_user(
            username="testuser",
        )
        self.user.notify_if_not_exists = mock.Mock()
        self.user.notify = mock.Mock()
        metadata_form = jasmin_metadata.models.Form.objects.create(name="test_form")
        category = jasmin_services.models.Category.objects.create(
            name="test_category",
            long_name="Test Category",
            position=1,
        )
        service = jasmin_services.models.Service.objects.create(
            category=category,
            name="test_service",
            summary="Test service",
            description="",
        )
        self.role = jasmin_services.models.Role.objects.create(
            service=service,
            name="test_role",
            description="",
            metadata_form=metadata_form,
        )
        self.access = jasmin_services.models.Access.objects.create(
            user=self.user,
            role=self.role,
        )

    def test_user_with_active_grant_has_role(self):
        """A non-revoked, non-expired grant means the user has the role."""
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=False,
        )
        self.assertTrue(self.role.user_has_role(self.user))

    def test_user_with_grant_expiring_today_has_role(self):
        """Grant expiring today is still active (gte comparison)."""
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today(),
            revoked=False,
        )
        self.assertTrue(self.role.user_has_role(self.user))

    def test_user_with_revoked_grant_does_not_have_role(self):
        """A revoked grant, even with a future expiry, does not count."""
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=True,
        )
        self.assertFalse(self.role.user_has_role(self.user))

    def test_user_with_expired_grant_does_not_have_role(self):
        """A grant that expired yesterday does not count."""
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() - dt.timedelta(days=1),
            revoked=False,
        )
        self.assertFalse(self.role.user_has_role(self.user))

    def test_user_without_grant_does_not_have_role(self):
        """An Access record with no associated Grant means the user does not have the role."""
        self.assertFalse(self.role.user_has_role(self.user))

    def test_other_users_grant_does_not_count(self):
        """An active grant belonging to a different user does not satisfy the check."""
        other_user = django.contrib.auth.get_user_model().objects.create_user(
            username="otheruser",
        )
        other_access = jasmin_services.models.Access.objects.create(
            user=other_user,
            role=self.role,
        )
        jasmin_services.models.Grant.objects.create(
            access=other_access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=False,
        )
        self.assertFalse(self.role.user_has_role(self.user))

    def test_user_with_revoked_and_active_grants_has_role(self):
        """An active grant counts even when a revoked grant also exists."""
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=True,
        )
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=False,
        )
        self.assertTrue(self.role.user_has_role(self.user))

    def test_user_with_no_access_record_does_not_have_role(self):
        """A user with no Access record for the role does not have it."""
        user_without_access = django.contrib.auth.get_user_model().objects.create_user(
            username="noaccessuser",
        )
        self.assertFalse(self.role.user_has_role(user_without_access))
