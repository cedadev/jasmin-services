"""APIViews for the jasmin_services API."""
import datetime as dt

import django.shortcuts as djshortcuts
import rest_framework.generics as rf_generics
import rest_framework.schemas as rf_schemas

from .. import models
from . import serializers


class ServiceRolesView(rf_generics.ListAPIView):
    """List all the roles users held by all the users of a given service."""

    serializer_class = serializers.ServiceRolesSerializer
    pagination_class = None
    required_scopes = ["jasmin.services.serviceroles.all"]

    schema = rf_schemas.openapi.AutoSchema()
    # Override the schema.
    # rest_framework does not infer the response shape correctly
    # due to the custom ListSerializer.
    schema.get_components = serializers.ServiceRolesSerializer.get_schema_components

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


class ServiceRoleUsersView(rf_generics.ListAPIView):
    """List all the holders of a given role for a given service."""

    serializer_class = serializers.ServiceRoleUsersSerializer
    required_scopes = ["jasmin.services.serviceroles.all"]

    schema = rf_schemas.openapi.AutoSchema()
    # Override the schema.
    # rest_framework does not infer the response shape correctly
    # due to the custom Serializer.
    schema.get_components = serializers.ServiceRoleUsersSerializer.get_schema_components

    def get_queryset(self):
        """Return users with a given role for a given service."""
        # Service and service category are part of the URL.
        category = self.request.parser_context["kwargs"].get("category")
        service = self.request.parser_context["kwargs"].get("service")
        role = self.request.parser_context["kwargs"].get("role")

        # If the service does not exist, return an error.
        service = djshortcuts.get_object_or_404(
            models.Service, category__name=category, name=service
        )
        role = djshortcuts.get_object_or_404(models.Role, service=service, name=role)

        # Return a queryset containg only valid grants.
        return (
            models.Grant.objects.filter_active()
            .filter(
                access__role=role,
                revoked=False,
                expires__gte=dt.datetime.now(),
            )
            .select_related("access__user")
        )
