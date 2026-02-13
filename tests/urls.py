"""URLs for tests of jasmin_services."""

import django.contrib.auth
import drf_spectacular.views
import rest_framework.response as rf_response
import rest_framework.routers as rf_routers
import rest_framework.viewsets as rf_viewsets
from django.urls import include, path

from jasmin_services.api.urls import router as js_api_router


class MockUserViewSet(rf_viewsets.ReadOnlyModelViewSet):
    """Mock user viewset for testing hyperlinked relations."""

    queryset = django.contrib.auth.get_user_model().objects.all()
    lookup_field = "username"


api_router = rf_routers.DefaultRouter()
api_router.registry.extend(js_api_router.registry)
api_router.register("v1/users", MockUserViewSet, basename="user")

urlpatterns = [
    # fmt: off
    path("services/", include("jasmin_services.urls", namespace="services")),

    path("api/", include([
            path("schema/", drf_spectacular.views.SpectacularAPIView.as_view(), name="schema"),
            path('schema/swagger-ui/', drf_spectacular.views.SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
            path("", include(api_router.urls)),
    ])),
    # fmt: on
]
