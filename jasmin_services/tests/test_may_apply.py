import datetime as dt
from unittest import mock

import django.contrib.auth
import django.contrib.messages
import django.contrib.messages.storage.cookie
import django.http
import django.test
import django.views.generic.base

import jasmin_metadata.models
import jasmin_services.models
import jasmin_services.views.mixins


class MayApplyMixinTest(django.test.TestCase):
    """Tests for MayApplyMixin.dispatch()."""

    class _TestView(jasmin_services.views.mixins.MayApplyMixin, django.views.generic.base.View):
        def get(self, request, *args, **kwargs):
            return django.http.HttpResponse("OK")

    def setUp(self):
        self.user = django.contrib.auth.get_user_model().objects.create_user(
            username="testuser",
        )
        self.user.notify_if_not_exists = mock.Mock()
        self.user.notify = mock.Mock()
        metadata_form = jasmin_metadata.models.Form.objects.create(name="test_form")

        prerequisite_category = jasmin_services.models.Category.objects.create(
            name="prerequisite_category",
            long_name="Prerequisite Category",
            position=1,
        )
        self.prerequisite_service = jasmin_services.models.Service.objects.create(
            category=prerequisite_category,
            name="prerequisite_service",
            summary="Prerequisite service",
            description="",
        )
        self.prerequisite_role = jasmin_services.models.Role.objects.create(
            service=self.prerequisite_service,
            name="prerequisite_role",
            description="",
            metadata_form=metadata_form,
        )

        restricted_category = jasmin_services.models.Category.objects.create(
            name="restricted_category",
            long_name="Restricted Category",
            position=2,
            require_role_to_apply=self.prerequisite_role,
        )
        self.restricted_service = jasmin_services.models.Service.objects.create(
            category=restricted_category,
            name="restricted_service",
            summary="Restricted service",
            description="",
        )

        unrestricted_category = jasmin_services.models.Category.objects.create(
            name="unrestricted_category",
            long_name="Unrestricted Category",
            position=3,
        )
        self.unrestricted_service = jasmin_services.models.Service.objects.create(
            category=unrestricted_category,
            name="unrestricted_service",
            summary="Unrestricted service",
            description="",
        )

    def _dispatch(self, service):
        """Dispatch a GET request to the test view for the given service."""
        request = django.test.RequestFactory().get("/")
        request.user = self.user
        request._messages = django.contrib.messages.storage.cookie.CookieStorage(request)

        view = self._TestView()
        view.service = service
        view.request = request
        view.args = []
        view.kwargs = {}
        return view.dispatch(request), request

    def test_no_require_role_to_apply_allows_access(self):
        """When no role is required by the category, the mixin passes the request through."""
        response, _ = self._dispatch(self.unrestricted_service)
        self.assertEqual(response.status_code, 200)

    def test_user_with_required_role_allows_access(self):
        """A user who holds the required role is passed through by the mixin."""
        access = jasmin_services.models.Access.objects.create(
            user=self.user,
            role=self.prerequisite_role,
        )
        jasmin_services.models.Grant.objects.create(
            access=access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=False,
        )
        response, _ = self._dispatch(self.restricted_service)
        self.assertEqual(response.status_code, 200)

    def test_user_without_required_role_is_redirected(self):
        """A user who lacks the required role is redirected to that role's service detail page."""
        response, _ = self._dispatch(self.restricted_service)
        self.assertEqual(response.status_code, 302)
        self.assertIn("prerequisite_category", response["Location"])
        self.assertIn("prerequisite_service", response["Location"])

    def test_user_without_required_role_receives_warning_message(self):
        """The redirect is accompanied by a warning message naming both services."""
        response, request = self._dispatch(self.restricted_service)
        messages = list(django.contrib.messages.get_messages(request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, django.contrib.messages.WARNING)
        self.assertIn("prerequisite_service", str(messages[0]))
        self.assertIn("restricted_service", str(messages[0]))

    def test_user_with_revoked_grant_is_redirected(self):
        """A revoked grant does not satisfy the role requirement."""
        access = jasmin_services.models.Access.objects.create(
            user=self.user,
            role=self.prerequisite_role,
        )
        jasmin_services.models.Grant.objects.create(
            access=access,
            granted_by="admin",
            expires=dt.date.today() + dt.timedelta(days=365),
            revoked=True,
        )
        response, _ = self._dispatch(self.restricted_service)
        self.assertEqual(response.status_code, 302)

    def test_user_with_expired_grant_is_redirected(self):
        """An expired grant does not satisfy the role requirement."""
        access = jasmin_services.models.Access.objects.create(
            user=self.user,
            role=self.prerequisite_role,
        )
        jasmin_services.models.Grant.objects.create(
            access=access,
            granted_by="admin",
            expires=dt.date.today() - dt.timedelta(days=1),
            revoked=False,
        )
        response, _ = self._dispatch(self.restricted_service)
        self.assertEqual(response.status_code, 302)
