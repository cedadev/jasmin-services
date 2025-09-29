import datetime as dt

import django.contrib.auth.decorators
import django.db.models as dj_models
import django.utils.decorators
import drf_spectacular.utils
import rest_framework.decorators as rf_decorators
import rest_framework.mixins as rf_mixins
import rest_framework.response as rf_response
import rest_framework.viewsets as rf_viewsets

from ... import models
from .. import filters, serializers


@drf_spectacular.utils.extend_schema_view(
    list=drf_spectacular.utils.extend_schema(
        parameters=[
            drf_spectacular.utils.OpenApiParameter(
                name="user_username",
                required=True,
                type=str,
                location=drf_spectacular.utils.OpenApiParameter.PATH,
            )
        ],
    )
)
@django.utils.decorators.method_decorator(
    django.contrib.auth.decorators.login_not_required, name="dispatch"
)
class UserServicesViewSet(rf_mixins.ListModelMixin, rf_viewsets.GenericViewSet):
    """Get the services assocated with a user."""

    required_scopes = ["jasmin.services.userservices.all"]
    serializer_class = serializers.ServiceListSerializer

    def get_queryset(self):
        # If we are generating swagger definitions, return the correct
        # queryset to allow types to be infered without error.
        if getattr(self, "swagger_fake_view", False):
            return models.Service.objects.none()

        return models.Service.objects.filter(
            role__access__user__username=self.kwargs["user_username"],
            role__access__grant__revoked=False,
            role__access__grant__expires__gte=dt.datetime.now(),
        ).distinct()
