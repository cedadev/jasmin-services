"""Tests for the api endpoints."""

import datetime as dt
from zoneinfo import ZoneInfo

import django.conf
import django.contrib.auth
import oauth2_provider.models
import rest_framework.test as rf_test

import jasmin_metadata.models

from .. import models
from ..api import scopes

DJANGO_TZ = ZoneInfo(django.conf.settings.TIME_ZONE)

# Python <3.12 does not support the %:z strftime format.
# So we must construct the correct offset string ourselves.
utc_offset_amount = int(dt.datetime.now(tz=DJANGO_TZ).utcoffset().total_seconds() / 3600)
utc_offset = f"+{utc_offset_amount:02}:00"
if utc_offset == "+00:00":
    utc_offset = "Z"


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
        self.category1 = models.Category.objects.create(
            name="test_cat1", long_name="Meow", position=1
        )
        self.category2 = models.Category.objects.create(
            name="test_cat2", long_name="Woof", position=1
        )
        self.service1 = models.Service.objects.create(
            category=self.category1,
            name="testservice1",
            summary="First test category",
            description="This should be a long description.",
        )
        self.service2 = models.Service.objects.create(
            category=self.category2,
            name="testservice2",
            summary="Another test category",
            description="This should be a long description.",
        )
        # Grant the user roles within the services.
        manager_role = models.Role.objects.create(
            service=self.service1, name="MANAGER", description="Manager.", metadata_form=metaform
        )
        manager_access = models.Access.objects.create(user=self.user, role=manager_role)
        self.manager_grant = models.Grant.objects.create(
            access=manager_access,
            granted_by=self.user.username,
            expires=dt.date.today() + dt.timedelta(days=365),
        )
        deputy_role = models.Role.objects.create(
            service=self.service2, name="DEPUTY", description="Deputy.", metadata_form=metaform
        )
        deputy_access = models.Access.objects.create(user=self.user, role=deputy_role)
        self.deputy_grant = models.Grant.objects.create(
            access=deputy_access,
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
        services_list_data = response.json()
        expected_services = [
            {
                "id": self.service1.id,
                "url": f"http://testserver/api/v1/categories/{self.service1.category.name}/services/{self.service1.name}/",
                "category": {
                    "id": self.category1.id,
                    "url": "http://testserver/api/v1/categories/test_cat1/",
                    "name": "test_cat1",
                },
                "name": "testservice1",
                "summary": "First test category",
                "hidden": True,
            },
            {
                "id": self.service2.id,
                "url": f"http://testserver/api/v1/categories/{self.service2.category.name}/services/{self.service2.name}/",
                "category": {
                    "id": self.category2.id,
                    "url": "http://testserver/api/v1/categories/test_cat2/",
                    "name": "test_cat2",
                },
                "name": "testservice2",
                "summary": "Another test category",
                "hidden": True,
            },
        ]
        self.assertListEqual(services_list_data, expected_services)

    def test_services_detail(self):
        """Test that the service detail view works."""
        response = self.client.get(
            "/api/v1/services/1/", HTTP_AUTHORIZATION=f"Bearer {self.token.token}"
        )
        self.assertEqual(response.status_code, 200)
        service_detail_data = response.json()
        expected_service = {
            "id": self.service1.id,
            "url": f"http://testserver/api/v1/categories/{self.service1.category.name}/services/{self.service1.name}/",
            "name": "testservice1",
            "category": {
                "id": self.category1.id,
                "url": "http://testserver/api/v1/categories/test_cat1/",
                "name": "test_cat1",
            },
            "roles": [{"id": 1, "name": "MANAGER"}],
            "summary": "First test category",
            "description": "This should be a long description.",
            "approver_message": "",
            "institution_countries": [],
            "hidden": True,
            "position": 9999,
            "ceda_managed": False,
        }
        self.assertDictEqual(service_detail_data, expected_service)


class UserGrantsTest(BaseTest):
    def test_user(self):
        """Test the user grants API endpoint."""
        response = self.client.get(
            f"/api/v1/users/{self.user.username}/grants/",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        user_grants_data = response.json()
        expected_grants = [
            {
                "id": self.manager_grant.id,
                "service": {
                    "id": self.service1.id,
                    "url": "http://testserver/api/v1/categories/test_cat1/services/testservice1/",
                    "category": {
                        "id": self.category1.id,
                        "url": "http://testserver/api/v1/categories/test_cat1/",
                        "name": "test_cat1",
                    },
                    "name": "testservice1",
                    "summary": "First test category",
                    "hidden": True,
                },
                "role": {"id": 1, "name": "MANAGER"},
                "granted_at": self.manager_grant.granted_at.astimezone(DJANGO_TZ).strftime(
                    f"%Y-%m-%dT%H:%M:%S.%f{utc_offset}"
                ),
                "expires": self.manager_grant.expires.strftime("%Y-%m-%d"),
                "revoked": False,
                "revoked_at": None,
                "user_reason": "",
            },
            {
                "id": self.deputy_grant.id,
                "service": {
                    "id": self.service2.id,
                    "url": "http://testserver/api/v1/categories/test_cat2/services/testservice2/",
                    "category": {
                        "id": self.category2.id,
                        "url": "http://testserver/api/v1/categories/test_cat2/",
                        "name": "test_cat2",
                    },
                    "name": "testservice2",
                    "summary": "Another test category",
                    "hidden": True,
                },
                "role": {"id": 2, "name": "DEPUTY"},
                "granted_at": self.deputy_grant.granted_at.astimezone(DJANGO_TZ).strftime(
                    f"%Y-%m-%dT%H:%M:%S.%f{utc_offset}"
                ),
                "expires": self.deputy_grant.expires.strftime("%Y-%m-%d"),
                "revoked": False,
                "revoked_at": None,
                "user_reason": "",
            },
        ]
        self.assertListEqual(user_grants_data, expected_grants)

    def test_grants_filter_category(self):
        """Test that filtering with category query param works."""
        response = self.client.get(
            f"/api/v1/users/{self.user.username}/grants/?category={self.category1.name}",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        filtered_category_data = response.json()
        expected_category_grants = [
            {
                "id": self.manager_grant.id,
                "service": {
                    "id": self.service1.id,
                    "url": "http://testserver/api/v1/categories/test_cat1/services/testservice1/",
                    "category": {
                        "id": self.category1.id,
                        "url": "http://testserver/api/v1/categories/test_cat1/",
                        "name": "test_cat1",
                    },
                    "name": "testservice1",
                    "summary": "First test category",
                    "hidden": True,
                },
                "role": {"id": 1, "name": "MANAGER"},
                "granted_at": self.manager_grant.granted_at.astimezone(DJANGO_TZ).strftime(
                    f"%Y-%m-%dT%H:%M:%S.%f{utc_offset}"
                ),
                "expires": self.manager_grant.expires.strftime("%Y-%m-%d"),
                "revoked": False,
                "revoked_at": None,
                "user_reason": "",
            }
        ]
        self.assertListEqual(filtered_category_data, expected_category_grants)

    def test_grants_filter_service(self):
        """Test that filtering with service query param works."""
        response = self.client.get(
            f"/api/v1/users/{self.user.username}/grants/?service={self.service2.name}",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        filtered_service_data = response.json()
        expected_service_grants = [
            {
                "id": self.deputy_grant.id,
                "service": {
                    "id": self.service2.id,
                    "url": "http://testserver/api/v1/categories/test_cat2/services/testservice2/",
                    "category": {
                        "id": self.category2.id,
                        "url": "http://testserver/api/v1/categories/test_cat2/",
                        "name": "test_cat2",
                    },
                    "name": "testservice2",
                    "summary": "Another test category",
                    "hidden": True,
                },
                "role": {"id": 2, "name": "DEPUTY"},
                "granted_at": self.deputy_grant.granted_at.astimezone(DJANGO_TZ).strftime(
                    f"%Y-%m-%dT%H:%M:%S.%f{utc_offset}"
                ),
                "expires": self.deputy_grant.expires.strftime("%Y-%m-%d"),
                "revoked": False,
                "revoked_at": None,
                "user_reason": "",
            }
        ]
        self.assertListEqual(filtered_service_data, expected_service_grants)

    def test_grants_filter_role(self):
        """Test that filtering with role query param works."""
        response = self.client.get(
            f"/api/v1/users/{self.user.username}/grants/?role=MANAGER",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        filtered_role_data = response.json()
        expected_role_grants = [
            {
                "id": self.manager_grant.id,
                "service": {
                    "id": self.service1.id,
                    "url": "http://testserver/api/v1/categories/test_cat1/services/testservice1/",
                    "category": {
                        "id": self.category1.id,
                        "url": "http://testserver/api/v1/categories/test_cat1/",
                        "name": "test_cat1",
                    },
                    "name": "testservice1",
                    "summary": "First test category",
                    "hidden": True,
                },
                "role": {"id": 1, "name": "MANAGER"},
                "granted_at": self.manager_grant.granted_at.astimezone(DJANGO_TZ).strftime(
                    f"%Y-%m-%dT%H:%M:%S.%f{utc_offset}"
                ),
                "expires": self.manager_grant.expires.strftime("%Y-%m-%d"),
                "revoked": False,
                "revoked_at": None,
                "user_reason": "",
            }
        ]
        self.assertListEqual(filtered_role_data, expected_role_grants)


class CategoriesTest(BaseTest):
    def test_categories_list(self):
        """Test that the categories list view works."""
        response = self.client.get(
            "/api/v1/categories/", HTTP_AUTHORIZATION=f"Bearer {self.token.token}"
        )
        self.assertEqual(response.status_code, 200)
        categories_data = response.json()
        expected_categories = [
            {
                "id": self.category1.id,
                "url": "http://testserver/api/v1/categories/test_cat1/",
                "name": "test_cat1",
            },
            {
                "id": self.category2.id,
                "url": "http://testserver/api/v1/categories/test_cat2/",
                "name": "test_cat2",
            },
        ]
        self.assertListEqual(categories_data, expected_categories)

    def test_categories_detail(self):
        """Test that the category detail view works."""
        response = self.client.get(
            "/api/v1/categories/test_cat1/", HTTP_AUTHORIZATION=f"Bearer {self.token.token}"
        )
        self.assertEqual(response.status_code, 200)
        category_detail_data = response.json()
        expected_category = {
            "id": self.category1.id,
            "url": "http://testserver/api/v1/categories/test_cat1/",
            "name": "test_cat1",
            "long_name": "Meow",
            "position": 1,
            "services": [
                {
                    "id": self.service1.id,
                    "url": "http://testserver/api/v1/categories/test_cat1/services/testservice1/",
                    "name": "testservice1",
                    "summary": "First test category",
                    "hidden": True,
                }
            ],
        }
        self.assertDictEqual(category_detail_data, expected_category)


class NestedServicesTest(BaseTest):
    def test_category_services_list(self):
        """Test that services nested under categories works."""
        response = self.client.get(
            "/api/v1/categories/test_cat1/services/",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        nested_services_data = response.json()
        expected_nested_services = [
            {
                "id": self.service1.id,
                "url": f"http://testserver/api/v1/categories/{self.service1.category.name}/services/{self.service1.name}/",
                "category": {
                    "id": self.category1.id,
                    "url": "http://testserver/api/v1/categories/test_cat1/",
                    "name": "test_cat1",
                },
                "name": "testservice1",
                "summary": "First test category",
                "hidden": True,
            }
        ]
        self.assertListEqual(nested_services_data, expected_nested_services)

    def test_category_services_detail(self):
        """Test that service detail nested under categories works."""
        response = self.client.get(
            "/api/v1/categories/test_cat1/services/testservice1/",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        nested_service_detail_data = response.json()
        expected_nested_service = {
            "id": self.service1.id,
            "url": f"http://testserver/api/v1/categories/{self.service1.category.name}/services/{self.service1.name}/",
            "name": "testservice1",
            "category": {
                "id": self.category1.id,
                "url": "http://testserver/api/v1/categories/test_cat1/",
                "name": "test_cat1",
            },
            "roles": [{"id": 1, "name": "MANAGER"}],
            "summary": "First test category",
            "description": "This should be a long description.",
            "approver_message": "",
            "institution_countries": [],
            "hidden": True,
            "position": 9999,
            "ceda_managed": False,
        }
        self.assertDictEqual(nested_service_detail_data, expected_nested_service)


class RolesTest(BaseTest):
    def test_service_roles_by_id(self):
        """Test roles endpoint nested under services by ID."""
        response = self.client.get(
            f"/api/v1/services/{self.service1.id}/roles/",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        roles_data = response.json()
        expected_roles = [
            {
                "id": 1,
                "name": "MANAGER",
                "accesses": [
                    {
                        "id": 1,
                        "user": {
                            "id": self.user.id,
                            "url": "http://testserver/api/v1/users/testuser/",
                            "username": "testuser",
                            "email": "testuser@example.com",
                        },
                    }
                ],
            }
        ]
        self.assertListEqual(roles_data, expected_roles)

    def test_service_roles_by_category_and_name(self):
        """Test roles endpoint nested under categories/services by name."""
        response = self.client.get(
            "/api/v1/categories/test_cat1/services/testservice1/roles/",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        nested_roles_data = response.json()
        expected_nested_roles = [
            {
                "id": 1,
                "name": "MANAGER",
                "accesses": [
                    {
                        "id": 1,
                        "user": {
                            "id": self.user.id,
                            "url": "http://testserver/api/v1/users/testuser/",
                            "username": "testuser",
                            "email": "testuser@example.com",
                        },
                    }
                ],
            }
        ]
        self.assertListEqual(nested_roles_data, expected_nested_roles)


class UserServicesTest(BaseTest):
    def test_user_services(self):
        """Test the user services API endpoint."""
        response = self.client.get(
            f"/api/v1/users/{self.user.username}/services/",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        user_services_data = response.json()
        expected_user_services = [
            {
                "id": self.service1.id,
                "url": f"http://testserver/api/v1/categories/{self.service1.category.name}/services/{self.service1.name}/",
                "category": {
                    "id": self.category1.id,
                    "url": "http://testserver/api/v1/categories/test_cat1/",
                    "name": "test_cat1",
                },
                "name": "testservice1",
                "summary": "First test category",
                "hidden": True,
            },
            {
                "id": self.service2.id,
                "url": f"http://testserver/api/v1/categories/{self.service2.category.name}/services/{self.service2.name}/",
                "category": {
                    "id": self.category2.id,
                    "url": "http://testserver/api/v1/categories/test_cat2/",
                    "name": "test_cat2",
                },
                "name": "testservice2",
                "summary": "Another test category",
                "hidden": True,
            },
        ]
        self.assertListEqual(user_services_data, expected_user_services)
