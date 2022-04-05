"""APIViews for the jasmin_services API."""
import datetime as dt

import django.contrib.auth
import django.db.models as dj_models
import jasmin_django_utils.api.viewsets
import rest_framework.decorators as rf_decorators
import rest_framework.mixins as rf_mixins
import rest_framework.response as rf_response
import rest_framework.viewsets as rf_viewsets

from .. import models
from . import serializers


class ServicesViewSet(
    jasmin_django_utils.api.viewsets.ActionSerializerMixin,
    rf_viewsets.ReadOnlyModelViewSet,
):
    """View and get details of a service."""

    queryset = models.Service.objects.all().prefetch_related("category")
    serializer_class = serializers.ServiceSerializer
    action_serializers = {
        "list": serializers.ServiceListSerializer,
        "roles": serializers.RoleSerializer,
    }
    required_scopes = ["jasmin.services.services.all"]
    filterset_fields = ["category", "hidden", "ceda_managed"]
    search_fields = ["name"]

    @rf_decorators.action(
        detail=True, required_scopes=["jasmin.services.serviceroles.all"]
    )
    def roles(self, request, pk=None):
        """List roles in a services and their holders."""
        service = self.get_object()
        queryset = models.Role.objects.filter(service=service).prefetch_related(
            dj_models.Prefetch(
                "accesses",
                queryset=models.Access.objects.filter(
                    grant__revoked=False, grant__expires__gte=dt.datetime.now()
                ),
            )
        )
        serializer = serializers.RoleSerializer(
            queryset, many=True, context={"request": request}
        )
        return rf_response.Response(serializer.data)


class UsersViewSet(
    jasmin_django_utils.api.viewsets.ActionSerializerMixin,
    rf_viewsets.GenericViewSet,
):
    queryset = django.contrib.auth.get_user_model().objects
    lookup_field = "username"
    action_serializers = {"services": serializers.ServiceListSerializer}
    required_scopes = ["jasmin.services.userservices.all"]

    @rf_decorators.action(detail=True)
    def services(self, request, username=None):
        """List the services of a given user."""
        user = self.get_object()
        queryset = models.Service.objects.filter(
            role__access__user=user,
            role__access__grant__revoked=False,
            role__access__grant__expires__gte=dt.datetime.now(),
        )

        serializer = serializers.ServiceListSerializer(
            queryset, many=True, context={"request": request}
        )
        return rf_response.Response(serializer.data)
