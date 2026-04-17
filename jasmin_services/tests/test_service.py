import datetime as dt
from unittest import mock

import django.contrib.auth
import django.test

import jasmin_metadata.models
import jasmin_services.models


class ServiceGetUserActiveRolesTest(django.test.TestCase):
    """Tests for Service.get_user_active_roles()."""

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
        self.service = jasmin_services.models.Service.objects.create(
            category=category,
            name="test_service",
            summary="Test service",
            description="",
        )
        self.role = jasmin_services.models.Role.objects.create(
            service=self.service,
            name="test_role",
            description="",
            metadata_form=metadata_form,
        )
        self.access = jasmin_services.models.Access.objects.create(
            user=self.user,
            role=self.role,
        )

    def test_returns_role_for_active_grant(self):
        """A non-revoked, non-expired grant means the role is included."""
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=False,
        )
        self.assertIn(self.role, self.service.get_user_active_roles(self.user))

    def test_excludes_role_for_revoked_grant(self):
        """A revoked grant, even with a future expiry, is not included."""
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=True,
        )
        self.assertNotIn(self.role, self.service.get_user_active_roles(self.user))

    def test_excludes_role_for_expired_grant(self):
        """A grant that expired yesterday is not included."""
        jasmin_services.models.Grant.objects.create(
            access=self.access,
            granted_by="admin",
            expires=dt.date.today() - dt.timedelta(days=1),
            revoked=False,
        )
        self.assertNotIn(self.role, self.service.get_user_active_roles(self.user))

    def test_returns_empty_for_user_with_no_grants(self):
        """A user with an Access record but no grants gets an empty queryset."""
        self.assertFalse(self.service.get_user_active_roles(self.user).exists())

    def test_excludes_other_users_role(self):
        """An active grant belonging to a different user does not appear."""
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
        self.assertFalse(self.service.get_user_active_roles(self.user).exists())
