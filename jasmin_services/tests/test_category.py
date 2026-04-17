import django.contrib.auth
import django.contrib.messages.storage.cookie
import django.http
import django.test
import django.views.generic.base

import jasmin_metadata.models
import jasmin_services.models
import jasmin_services.views.mixins


class CategoryRequireRoleOnDeleteTest(django.test.TestCase):
    """Tests for the on_delete behaviour of Category.require_role_to_apply."""

    class _TestView(jasmin_services.views.mixins.MayApplyMixin, django.views.generic.base.View):
        def get(self, request, *args, **kwargs):
            return django.http.HttpResponse("OK")

    def setUp(self):
        self.user = django.contrib.auth.get_user_model().objects.create_user(
            username="testuser",
        )
        metadata_form = jasmin_metadata.models.Form.objects.create(name="test_form")
        prerequisite_category = jasmin_services.models.Category.objects.create(
            name="prerequisite_category",
            long_name="Prerequisite Category",
            position=1,
        )
        prerequisite_service = jasmin_services.models.Service.objects.create(
            category=prerequisite_category,
            name="prerequisite_service",
            summary="Prerequisite service",
            description="",
        )
        self.prerequisite_role = jasmin_services.models.Role.objects.create(
            service=prerequisite_service,
            name="prerequisite_role",
            description="",
            metadata_form=metadata_form,
        )
        self.category = jasmin_services.models.Category.objects.create(
            name="restricted_category",
            long_name="Restricted Category",
            position=2,
            require_role_to_apply=self.prerequisite_role,
        )
        self.restricted_service = jasmin_services.models.Service.objects.create(
            category=self.category,
            name="restricted_service",
            summary="Restricted service",
            description="",
        )

    def _dispatch(self, service):
        request = django.test.RequestFactory().get("/")
        request.user = self.user
        request._messages = django.contrib.messages.storage.cookie.CookieStorage(request)

        view = self._TestView()
        view.service = service
        view.request = request
        view.args = []
        view.kwargs = {}
        return view.dispatch(request)

    def test_deleting_role_does_not_delete_category(self):
        """Deleting the required role must not cascade-delete the category."""
        self.prerequisite_role.delete()
        self.assertTrue(
            jasmin_services.models.Category.objects.filter(pk=self.category.pk).exists()
        )

    def test_deleting_role_clears_require_role_to_apply(self):
        """Deleting the required role sets require_role_to_apply to NULL on the category."""
        self.prerequisite_role.delete()
        self.category.refresh_from_db()
        self.assertIsNone(self.category.require_role_to_apply)

    def test_after_role_deletion_mixin_allows_access(self):
        """Once the required role is deleted, all users should be able to apply."""
        self.prerequisite_role.delete()
        # Fetch fresh from DB — the in-memory instance has category cached with the old FK value.
        fresh_service = jasmin_services.models.Service.objects.get(pk=self.restricted_service.pk)
        response = self._dispatch(fresh_service)
        self.assertEqual(response.status_code, 200)
