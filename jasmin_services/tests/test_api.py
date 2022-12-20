"""Tests for the api endpoints."""
import datetime as dt
from zoneinfo import ZoneInfo

import oauth2_provider.models
import rest_framework.test as rf_test

from .. import models
from ..api import scopes


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
                    "url": f"http://testserver/api/v1/services/{self.service1.id}/",
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
                    "url": f"http://testserver/api/v1/services/{self.service2.id}/",
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
                "url": f"http://testserver/api/v1/services/{self.service1.id}/",
                "name": "testservice1",
                "category": {
                    "id": self.category.id,
                    "url": "http://testserver/api/v1/categories/test_cat/",
                    "name": "test_cat",
                },
                "roles": [],
                "summary": "First test category",
                "description": "This should be a long description.",
                "approver_message": "",
                "institution_countries": [],
                "hidden": True,
                "position": 9999,
                "ceda_managed": False,
            },
        )
