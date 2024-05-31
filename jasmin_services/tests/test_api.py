"""Tests for the api endpoints."""

import datetime as dt
from zoneinfo import ZoneInfo

import oauth2_provider.models
import rest_framework.test as rf_test
import django.contrib.auth
import django.conf

from .. import models
from ..api import scopes

import jasmin_metadata.models


class BaseTest(rf_test.APITestCase):
    """Base test with two services category, access token, etc."""

    def setUp(self):
        # Setup auth.
        application_model = oauth2_provider.models.get_application_model()
        self.application = application_model.objects.create(
            client_type="confidential",
            client_id="client_id",
            client_secret="client_secret",
            authorization_grant_type="client-credentials",
            # allowed_scope=" ".join(scopes.SCOPES.keys()),
        )
        token_model = oauth2_provider.models.get_access_token_model()
        self.token = token_model.objects.create(
            application=self.application,
            scope=" ".join(scopes.SCOPES.keys()),
            token="access_token",
            expires=dt.datetime.now(tz=ZoneInfo("Etc/GMT")) + dt.timedelta(days=1),
        )
        # Make a user.
        UserModel = django.contrib.auth.get_user_model()
        self.user = UserModel.objects.create(
            username="testuser",
            email="testuser@example.com",
        )
        metaform = jasmin_metadata.models.Form.objects.create(name="test")
        # Populate some data.
        self.category = models.Category.objects.create(
            name="test_cat", long_name="Meow", position=1
        )
        self.service1 = models.Service.objects.create(
            category=self.category,
            name="testservice1",
            summary="First test category",
            description="This should be a long description.",
        )
        self.service2 = models.Service.objects.create(
            category=self.category,
            name="testservice2",
            summary="Another test category",
            description="This should be a long description.",
        )
        # Grant the user a role within the service.
        role = models.Role.objects.create(
            service=self.service1, name="MANAGER", description="Manager.", metadata_form=metaform
        )
        access = models.Access.objects.create(user=self.user, role=role)
        self.grant = models.Grant.objects.create(
            access=access,
            granted_by=self.user.username,
            expires=dt.date.today() + dt.timedelta(days=365),
        )
        super().setUp()

    def tearDown(self):
        self.token.delete()
        self.application.delete()
        super().tearDown()


class ServiceGoodScopeTest(BaseTest):
    def test_services_list(self):
        """Check that the API's list services view works."""
        response = self.client.get(
            "/api/v1/services/", HTTP_AUTHORIZATION=f"Bearer {self.token.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(
            response.json(),
            [
                {
                    "id": self.service1.id,
                    "url": f"http://testserver/api/v1/categories/{self.service1.category.name}/services/{self.service1.name}/",
                    "category": {
                        "id": self.category.id,
                        "url": "http://testserver/api/v1/categories/test_cat/",
                        "name": "test_cat",
                    },
                    "name": "testservice1",
                    "summary": "First test category",
                    "hidden": True,
                },
                {
                    "id": self.service2.id,
                    "url": f"http://testserver/api/v1/categories/{self.service2.category.name}/services/{self.service2.name}/",
                    "category": {
                        "id": self.category.id,
                        "url": "http://testserver/api/v1/categories/test_cat/",
                        "name": "test_cat",
                    },
                    "name": "testservice2",
                    "summary": "Another test category",
                    "hidden": True,
                },
            ],
        )

    def test_services_detail(self):
        """Test that the service detail view works."""
        response = self.client.get(
            "/api/v1/services/1/", HTTP_AUTHORIZATION=f"Bearer {self.token.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.json(),
            {
                "id": self.service1.id,
                "url": f"http://testserver/api/v1/categories/{self.service1.category.name}/services/{self.service1.name}/",
                "name": "testservice1",
                "category": {
                    "id": self.category.id,
                    "url": "http://testserver/api/v1/categories/test_cat/",
                    "name": "test_cat",
                },
                "roles": [{"id": 1, "name": "MANAGER"}],
                "summary": "First test category",
                "description": "This should be a long description.",
                "approver_message": "",
                "institution_countries": [],
                "hidden": True,
                "position": 9999,
                "ceda_managed": False,
            },
        )


class UserGrantsTest(BaseTest):
    def test_user(self):
        """Test that a page has been made for the user."""
        response = self.client.get(
            f"/api/v1/users/{self.user.username}/grants/",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(
            response.json(),
            [
                {
                    "id": self.grant.id,
                    "service": {
                        "id": self.service1.id,
                        "url": "http://testserver/api/v1/categories/test_cat/services/testservice1/",
                        "category": {
                            "id": self.category.id,
                            "url": "http://testserver/api/v1/categories/test_cat/",
                            "name": "test_cat",
                        },
                        "name": "testservice1",
                        "summary": "First test category",
                        "hidden": True,
                    },
                    "role": {"id": 1, "name": "MANAGER"},
                    "granted_at": self.grant.granted_at.astimezone(
                        ZoneInfo(django.conf.settings.TIME_ZONE)
                    ).strftime("%Y-%m-%dT%H:%M:%S.%f%:z"),
                    "expires": self.grant.expires.strftime("%Y-%m-%d"),
                    "revoked": False,
                    "revoked_at": None,
                    "user_reason": "",
                }
            ],
        )
        # self.assertIn("content?", response.content.decode(utf-8))


#     def test_grants_list(self):
#         """Check that the API's list grants view works."""
#         response = self.client.get(
#             f"/api/v1/users/{self.user}/grants/", HTTP_AUTHORIZATION=f"Bearer {self.token.token}"
#         )
#         self.assertEqual(response.status_code, 200)
#         self.assertListEqual(
#             response.json(),
#             [
#                 {
#                     info here...
#                 }
#             ],
#         )

#     def test_grants_filter_category(self):
#         """Test that filtering with category query param works."""
#         response = self.client.get(

#         )

#     def test_grants_filter_service(self):

#     def test_grants_filter_role(self):

#     def test_grants_filter_multiple_params(self):
