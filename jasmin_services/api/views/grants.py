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


@django.utils.decorators.method_decorator(
    django.contrib.auth.decorators.login_not_required, name="dispatch"
)
class GrantsViewSet(rf_mixins.ListModelMixin, rf_viewsets.GenericViewSet):
    """Get the grants associated with a user."""

    required_scopes = ["jasmin.services.userservices.all"]
    serializer_class = serializers.GrantSerializer
    # filterset_class = filters.UserGrantsFilter

    def get_queryset(self):
        # If we are generating swagger definitions, return the correct
        # queryset to allow types to be infered without error.
        if getattr(self, "swagger_fake_view", False):
            return models.Grant.objects.none()

        queryset = models.Grant.objects.filter(
            revoked=False,
            expires__gte=dt.datetime.now(),
        ).prefetch_related(
            "access__role__service__category",
            "access__user",
        )
        return queryset


@drf_spectacular.utils.extend_schema_view(
    list=drf_spectacular.utils.extend_schema(
        parameters=[
            drf_spectacular.utils.OpenApiParameter(
                name="user_username",
                required=True,
                type=str,
                location=drf_spectacular.utils.OpenApiParameter.PATH,
            ),
            drf_spectacular.utils.OpenApiParameter(
                name="service",
                required=False,
                type=str,
                description="Name of the service you would like to filter the grants for.",
            ),
            drf_spectacular.utils.OpenApiParameter(
                name="category",
                required=False,
                type=str,
                description="Name of the category you would like to filter the grants for.",
            ),
            drf_spectacular.utils.OpenApiParameter(
                name="role",
                required=False,
                type=str,
                description="Name of the role you would like to filter the grants for.",
            ),
        ]
    ),
)
@django.utils.decorators.method_decorator(
    django.contrib.auth.decorators.login_not_required, name="dispatch"
)
class UserGrantsViewSet(GrantsViewSet):
    """Get the grants associated with a user."""

    required_scopes = ["jasmin.services.userservices.all"]
    serializer_class = serializers.UserGrantSerializer
    filterset_class = filters.UserGrantsFilter

    def get_queryset(self):
        # If we are generating swagger definitions, return the correct
        # queryset to allow types to be infered without error.
        if getattr(self, "swagger_fake_view", False):
            return models.Grant.objects.none()

        queryset = super().get_queryset()
        queryset = queryset.filter(
            access__user__username=self.kwargs["user_username"],
        )

        return queryset
