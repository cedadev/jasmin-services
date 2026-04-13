import datetime as dt
from unittest import mock

import django.contrib.auth
import django.core.mail
import django.test

import jasmin_metadata.models
import jasmin_services.models
from jasmin_services.models.behaviours import (
    JoinJISCMailListBehaviour,
    KeycloakAttributeBehaviour,
    LdapGroupBehaviour,
    LdapTagBehaviour,
)


class BehaviourTestBase(django.test.TestCase):
    def setUp(self):
        self.user = django.contrib.auth.get_user_model().objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )
        self.user.notify_if_not_exists = mock.Mock()
        self.user.notify = mock.Mock()
        self.metadata_form = jasmin_metadata.models.Form.objects.create(name="test_form")
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
            metadata_form=self.metadata_form,
        )
        self.access = jasmin_services.models.Access.objects.create(
            user=self.user,
            role=self.role,
        )


class JoinJISCMailListBehaviourTest(BehaviourTestBase):
    def setUp(self):
        super().setUp()
        self.behaviour = JoinJISCMailListBehaviour.objects.create(list_name="TEST-LIST")
        self.role.behaviours.add(self.behaviour)

    def test_apply_raises_attribute_error_without_user_type(self):
        """apply() accesses user.user_type, which doesn't exist on Django's default User model."""
        with self.assertRaises(AttributeError):
            self.behaviour.apply(self.user, self.role)

    def test_apply_skips_service_user(self):
        """apply() sends no email and does not add a SERVICE user to joined_users."""
        self.user.user_type = "SERVICE"
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(len(django.core.mail.outbox), 0)
        self.assertFalse(self.behaviour.joined_users.filter(pk=self.user.pk).exists())

    def test_apply_skips_shared_user(self):
        """apply() sends no email and does not add a SHARED user to joined_users."""
        self.user.user_type = "SHARED"
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(len(django.core.mail.outbox), 0)
        self.assertFalse(self.behaviour.joined_users.filter(pk=self.user.pk).exists())

    def test_apply_skips_training_user(self):
        """apply() sends no email and does not add a TRAINING user to joined_users."""
        self.user.user_type = "TRAINING"
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(len(django.core.mail.outbox), 0)
        self.assertFalse(self.behaviour.joined_users.filter(pk=self.user.pk).exists())

    def test_apply_sends_email_and_adds_user(self):
        """apply() sends a subscription email and adds a STANDARD user to joined_users."""
        self.user.user_type = "STANDARD"
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(len(django.core.mail.outbox), 1)
        self.assertEqual(
            django.core.mail.outbox[0].subject,
            "Adding test@example.com (Test User) to test-list mailing list",
        )
        self.assertTrue(self.behaviour.joined_users.filter(pk=self.user.pk).exists())

    def test_apply_skips_already_joined_user(self):
        """apply() sends no email when the user is already in joined_users."""
        self.user.user_type = "STANDARD"
        self.behaviour.joined_users.add(self.user)
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(len(django.core.mail.outbox), 0)
        self.assertEqual(self.behaviour.joined_users.filter(pk=self.user.pk).count(), 1)

    def test_unapply_is_noop(self):
        """unapply() does nothing — users must unsubscribe themselves."""
        self.behaviour.joined_users.add(self.user)
        self.behaviour.unapply(self.user, self.role)
        self.assertTrue(self.behaviour.joined_users.filter(pk=self.user.pk).exists())
        self.assertEqual(len(django.core.mail.outbox), 0)

    def test_email_update_unapply_removes_user(self):
        """email_update_unapply() sends a removal email and removes the user from joined_users."""
        self.behaviour.joined_users.add(self.user)
        self.behaviour.email_update_unapply(self.user, self.role)
        self.assertEqual(len(django.core.mail.outbox), 1)
        self.assertFalse(self.behaviour.joined_users.filter(pk=self.user.pk).exists())

    def test_email_update_unapply_skips_user_not_joined(self):
        """email_update_unapply() does nothing when the user is not in joined_users."""
        self.behaviour.email_update_unapply(self.user, self.role)
        self.assertEqual(len(django.core.mail.outbox), 0)

    def test_email_update_unapply_skips_user_with_no_email(self):
        """email_update_unapply() does nothing and leaves joined_users unchanged when the user has no email address."""
        self.user.email = ""
        self.user.save()
        self.behaviour.joined_users.add(self.user)
        self.behaviour.email_update_unapply(self.user, self.role)
        self.assertEqual(len(django.core.mail.outbox), 0)
        self.assertTrue(self.behaviour.joined_users.filter(pk=self.user.pk).exists())


class LdapTagBehaviourTest(BehaviourTestBase):
    def setUp(self):
        super().setUp()
        self.behaviour = LdapTagBehaviour.objects.create(tag="test-tag")
        self.role.behaviours.add(self.behaviour)
        self.mock_account = mock.MagicMock()
        self.mock_account.tags = []
        self.user.account = self.mock_account

    def test_apply_adds_tag(self):
        """apply() appends the tag to account.tags and saves."""
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(self.mock_account.tags, ["test-tag"])
        self.mock_account.save.assert_called_once()

    def test_apply_skips_if_tag_already_present(self):
        """apply() does not duplicate the tag or save when it is already present."""
        self.mock_account.tags = ["test-tag"]
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(self.mock_account.tags, ["test-tag"])
        self.mock_account.save.assert_not_called()

    def test_unapply_removes_tag(self):
        """unapply() removes the tag from account.tags and saves."""
        self.mock_account.tags = ["test-tag", "other-tag"]
        self.behaviour.unapply(self.user, self.role)
        self.assertEqual(self.mock_account.tags, ["other-tag"])
        self.mock_account.save.assert_called_once()

    def test_unapply_skips_if_tag_not_present(self):
        """unapply() does not modify account.tags or save when the tag is absent."""
        self.mock_account.tags = ["other-tag"]
        self.behaviour.unapply(self.user, self.role)
        self.assertEqual(self.mock_account.tags, ["other-tag"])
        self.mock_account.save.assert_not_called()


class LdapGroupBehaviourTest(BehaviourTestBase):
    def setUp(self):
        super().setUp()
        self.behaviour = LdapGroupBehaviour.objects.create(
            ldap_model="SomeGroup", group_name="test-group"
        )
        self.role.behaviours.add(self.behaviour)
        self.mock_group = mock.MagicMock()
        self.mock_group.member_uids = []
        self.behaviour.get_ldap_group = mock.Mock(return_value=self.mock_group)

    def test_apply_adds_username_to_group(self):
        """apply() appends the username to member_uids and saves."""
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(self.mock_group.member_uids, ["testuser"])
        self.mock_group.save.assert_called_once()

    def test_apply_skips_if_already_member(self):
        """apply() does not duplicate the username or save when already a member."""
        self.mock_group.member_uids = ["testuser"]
        self.behaviour.apply(self.user, self.role)
        self.assertEqual(self.mock_group.member_uids, ["testuser"])
        self.mock_group.save.assert_not_called()

    def test_unapply_removes_username_from_group(self):
        """unapply() removes the username from member_uids and saves."""
        self.mock_group.member_uids = ["testuser", "other"]
        self.behaviour.unapply(self.user, self.role)
        self.assertEqual(self.mock_group.member_uids, ["other"])
        self.mock_group.save.assert_called_once()

    def test_unapply_skips_if_not_member(self):
        """unapply() does not modify member_uids or save when the user is not a member."""
        self.mock_group.member_uids = ["other"]
        self.behaviour.unapply(self.user, self.role)
        self.assertEqual(self.mock_group.member_uids, ["other"])
        self.mock_group.save.assert_not_called()


@django.test.override_settings(
    JASMIN_SERVICES={
        "DEFAULT_EXPIRY_DELTA": dt.timedelta(days=365 * 3),
        "NOTIFY_EXPIRE_DELTAS": [],
        "JISCMAIL_TO_ADDRS": ["test@example.com"],
        "DEFAULT_METADATA_FORM": 1,
        "LDAP_GROUPS": [],
        "KEYCLOAK": {
            "SERVER_URL": "http://test-keycloak",
            "REALM_NAME": "test-realm",
            "USERNAME": "admin",
            "PASSWORD": "password",
        },
    }
)
class KeycloakAttributeBehaviourTest(BehaviourTestBase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("keycloak.KeycloakAdmin")
        self.mock_keycloak_admin_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.behaviour = KeycloakAttributeBehaviour.objects.create()
        self.role.behaviours.add(self.behaviour)

    def test_apply_calls_group_user_add(self):
        """apply() looks up the Keycloak group by service name and adds the user to it."""
        mock_admin = self.mock_keycloak_admin_class.return_value
        mock_admin.get_group_by_path.return_value = {"id": "group-uuid"}
        mock_admin.get_user_id.return_value = "user-uuid"

        self.behaviour.apply(self.user, self.role)

        mock_admin.group_user_add.assert_called_once_with("user-uuid", "group-uuid")
        mock_admin.group_user_remove.assert_not_called()

    def test_unapply_calls_group_user_remove(self):
        """unapply() looks up the Keycloak group by service name and removes the user from it."""
        mock_admin = self.mock_keycloak_admin_class.return_value
        mock_admin.get_group_by_path.return_value = {"id": "group-uuid"}
        mock_admin.get_user_id.return_value = "user-uuid"

        self.behaviour.unapply(self.user, self.role)

        mock_admin.group_user_remove.assert_called_once_with("user-uuid", "group-uuid")
        mock_admin.group_user_add.assert_not_called()

    def test_disable_calls_unapply_when_only_other_service_grant_active(self):
        """disable() calls unapply() for service_a even when an active grant for service_b shares the behaviour.

        Because unapply() is service-specific (it removes the user from /{service.name}),
        a grant on a different service must not prevent unapply for this one.
        """
        service_b = jasmin_services.models.Service.objects.create(
            category=self.category,
            name="service_b",
            summary="Service B",
            description="Service B description",
        )
        role_b = jasmin_services.models.Role.objects.create(
            service=service_b,
            name="role_b",
            metadata_form=self.metadata_form,
        )
        role_b.behaviours.add(self.behaviour)
        access_b = jasmin_services.models.Access.objects.create(user=self.user, role=role_b)
        jasmin_services.models.Grant.objects.create(
            access=access_b,
            granted_by="admin",
            revoked=False,
            expires=dt.date.today() + dt.timedelta(days=365),
        )

        mock_admin = self.mock_keycloak_admin_class.return_value
        mock_admin.get_group_by_path.return_value = {"id": "group-uuid"}
        mock_admin.get_user_id.return_value = "user-uuid"
        mock_admin.reset_mock()

        self.role.disable(self.user)

        mock_admin.group_user_remove.assert_called_once_with("user-uuid", "group-uuid")

    def test_disable_skips_unapply_when_same_service_grant_active(self):
        """disable() does not call unapply() when the user has an active grant on another role within the same service."""
        role_b = jasmin_services.models.Role.objects.create(
            service=self.service,
            name="role_b",
            metadata_form=self.metadata_form,
        )
        role_b.behaviours.add(self.behaviour)
        access_b = jasmin_services.models.Access.objects.create(user=self.user, role=role_b)
        jasmin_services.models.Grant.objects.create(
            access=access_b,
            granted_by="admin",
            revoked=False,
            expires=dt.date.today() + dt.timedelta(days=365),
        )

        mock_admin = self.mock_keycloak_admin_class.return_value
        mock_admin.get_group_by_path.return_value = {"id": "group-uuid"}
        mock_admin.get_user_id.return_value = "user-uuid"
        mock_admin.reset_mock()

        self.role.disable(self.user)

        mock_admin.group_user_remove.assert_not_called()


class RoleEnableTest(BehaviourTestBase):
    def setUp(self):
        super().setUp()
        self.behaviour = LdapTagBehaviour.objects.create(tag="role-enable-tag")
        self.role.behaviours.add(self.behaviour)
        self.mock_account = mock.MagicMock()
        self.mock_account.tags = []
        self.user.account = self.mock_account

    def test_enable_calls_apply_on_behaviour(self):
        """enable() calls apply() on all behaviours attached to the role."""
        self.role.enable(self.user)
        self.assertEqual(self.mock_account.tags, ["role-enable-tag"])
        self.mock_account.save.assert_called_once()

    @django.test.override_settings(IS_CEDA_IMPORT=True)
    def test_enable_skips_during_ceda_import(self):
        """enable() does not call apply() when IS_CEDA_IMPORT is True."""
        self.role.enable(self.user)
        self.assertEqual(self.mock_account.tags, [])
        self.mock_account.save.assert_not_called()

    @django.test.override_settings(MIGRATED_USERS=["other_user"])
    def test_enable_skips_unmigrated_user(self):
        """enable() does not call apply() when the user is not in MIGRATED_USERS."""
        self.role.enable(self.user)
        self.assertEqual(self.mock_account.tags, [])
        self.mock_account.save.assert_not_called()

    @django.test.override_settings(MIGRATED_USERS=["testuser"])
    def test_enable_applies_for_migrated_user(self):
        """enable() calls apply() when the user is explicitly listed in MIGRATED_USERS."""
        self.role.enable(self.user)
        self.assertEqual(self.mock_account.tags, ["role-enable-tag"])
        self.mock_account.save.assert_called_once()


class RoleDisableTest(BehaviourTestBase):
    def setUp(self):
        super().setUp()
        self.behaviour = LdapTagBehaviour.objects.create(tag="role-disable-tag")
        self.role.behaviours.add(self.behaviour)
        self.mock_account = mock.MagicMock()
        self.mock_account.tags = ["role-disable-tag"]
        self.user.account = self.mock_account

    def _create_second_role(self):
        second_service = jasmin_services.models.Service.objects.create(
            category=self.category,
            name="second_service",
            summary="Second service",
            description="Second service description",
        )
        second_role = jasmin_services.models.Role.objects.create(
            service=second_service,
            name="second_role",
            metadata_form=self.metadata_form,
        )
        second_role.behaviours.add(self.behaviour)
        return second_role

    def test_disable_calls_unapply_when_no_grants(self):
        """disable() calls unapply() when the user has no active grants for any role sharing the behaviour."""
        self.role.disable(self.user)
        self.assertEqual(self.mock_account.tags, [])
        self.mock_account.save.assert_called_once()

    def test_disable_skips_unapply_with_active_grant(self):
        """disable() does not call unapply() when the user has an active grant on another role sharing the behaviour."""
        second_role = self._create_second_role()
        access_b = jasmin_services.models.Access.objects.create(user=self.user, role=second_role)
        today = dt.date.today()
        jasmin_services.models.Grant.objects.create(
            access=access_b,
            granted_by="admin",
            revoked=False,
            expires=today + dt.timedelta(days=365),
        )
        self.mock_account.reset_mock()
        self.mock_account.tags = ["role-disable-tag"]

        self.role.disable(self.user)

        self.assertEqual(self.mock_account.tags, ["role-disable-tag"])
        self.mock_account.save.assert_not_called()

    def test_disable_calls_unapply_when_only_revoked_grant_remains(self):
        """disable() calls unapply() when the only remaining grant on a shared role is revoked."""
        second_role = self._create_second_role()
        access_b = jasmin_services.models.Access.objects.create(user=self.user, role=second_role)
        today = dt.date.today()
        jasmin_services.models.Grant.objects.create(
            access=access_b,
            granted_by="admin",
            revoked=True,
            expires=today + dt.timedelta(days=365),
        )
        self.mock_account.reset_mock()
        self.mock_account.tags = ["role-disable-tag"]

        self.role.disable(self.user)

        self.assertEqual(self.mock_account.tags, [])
        self.mock_account.save.assert_called_once()

    def test_disable_calls_unapply_when_only_expired_grant_remains(self):
        """disable() calls unapply() when the only remaining grant on a shared role is expired."""
        second_role = self._create_second_role()
        access_b = jasmin_services.models.Access.objects.create(user=self.user, role=second_role)
        yesterday = dt.date.today() - dt.timedelta(days=1)
        jasmin_services.models.Grant.objects.create(
            access=access_b,
            granted_by="admin",
            revoked=False,
            expires=yesterday,
        )
        self.mock_account.reset_mock()
        self.mock_account.tags = ["role-disable-tag"]

        self.role.disable(self.user)

        self.assertEqual(self.mock_account.tags, [])
        self.mock_account.save.assert_called_once()

    @django.test.override_settings(IS_CEDA_IMPORT=True)
    def test_disable_skips_during_ceda_import(self):
        """disable() does not call unapply() when IS_CEDA_IMPORT is True."""
        self.role.disable(self.user)
        self.assertEqual(self.mock_account.tags, ["role-disable-tag"])
        self.mock_account.save.assert_not_called()

    @django.test.override_settings(MIGRATED_USERS=["other_user"])
    def test_disable_skips_unmigrated_user(self):
        """disable() does not call unapply() when the user is not in MIGRATED_USERS."""
        self.role.disable(self.user)
        self.assertEqual(self.mock_account.tags, ["role-disable-tag"])
        self.mock_account.save.assert_not_called()
