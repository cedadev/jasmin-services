"""APIViews for the jasmin_services API."""
import datetime as dt

import django.shortcuts as djshortcuts
import rest_framework.generics as rf_generics

from .. import models
from . import serializers


class ServiceRolesView(rf_generics.ListAPIView):
    """List the roles users hold for a given service."""

    serializer_class = serializers.ServiceRolesSerializer
    required_scopes = ["jasmin.services.serviceroles.all"]

    def get_queryset(self):
        """Return valid users and roles for a given service."""
        # Service and service category are part of the URL.
        category = self.request.parser_context["kwargs"].get("category")
        service = self.request.parser_context["kwargs"].get("service")

        # If the service does not exist, return an error.
        service = djshortcuts.get_object_or_404(
            models.Service, category__name=category, name=service
        )

        # Return a queryset containg only valid grants.
        return (
            models.Grant.objects.filter_active()
            .filter(
                access__role__service=service,
                revoked=False,
                expires__gte=dt.datetime.now(),
            )
            .select_related("access__role", "access__user")
        )
