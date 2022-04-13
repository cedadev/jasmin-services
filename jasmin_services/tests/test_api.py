import datetime as dt

import oauth2_provider.models
import rest_framework.test as rf_test

from ..api import scopes

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


class BaseTest(rf_test.APITestCase):
    def setUp(self):
        application_model = oauth2_provider.models.get_application_model()
        app = application_model.objects.create(
            client_type="confidential",
            client_id="client_id",
            client_secret="client_secret",
            authorization_grant_type="client-credentials",
            # allowed_scope=" ".join(scopes.SCOPES.keys()),
        )
        token_model = oauth2_provider.models.get_access_token_model()
        token_model.objects.create(
            application=app,
            scope=" ".join(scopes.SCOPES.keys()),
            token="access_token",
            expires=dt.datetime.now(tz=ZoneInfo("Etc/GMT")) + dt.timedelta(days=1),
        )
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_services_list(self):
        print("ping")
