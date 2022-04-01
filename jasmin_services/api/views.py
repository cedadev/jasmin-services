"""APIViews for the jasmin_services API."""
import datetime as dt

import rest_framework.decorators as rf_decorators
import rest_framework.response as rf_response
import rest_framework.viewsets as rf_viewsets

from .. import models
from . import serializers


class ServicesViewSet(
    jasmin_account_api.viewsets.ActionSerializerMixin, rf_viewsets.ReadOnlyModelViewSet
):
    """View and get details of a service."""

    queryset = models.Service.objects.all().prefetch_related("category")
    serializer_class = serializers.ServiceSerializer
    action_serializers = {"list": serializers.ServiceListSerializer}
    required_scopes = ["jasmin.services.services.all"]
    filterset_fields = ["category", "hidden", "ceda_managed"]
    search_fields = ["name"]

    @rf_decorators.action(detail=True)
    def roleholders(self, request, pk=None):
        """List users who hold roles in a service."""
        service = self.get_object()
        queryset = (
            models.Grant.objects.filter_active()
            .filter(
                access__role__service=service,
                revoked=False,
                expires__gte=dt.datetime.now(),
            )
            .select_related("access__role", "access__user")
        )
        serializer = serializers.ServiceRolesSerializer(queryset, many=True)
        return rf_response.Response(serializer.data)
