import datetime as dt

import django.db.models as djmodels
import rest_framework as rf
import rest_framework.generics as rf_generics
import rest_framework.views as rf_views

from .. import models
from . import serializers


class ServiceRolesView(rf_generics.ListAPIView):
    """List the roles users hold for a given service."""

    serializer_class = serializers.ServiceRolesSerializer

    def get_queryset(self):
        category = self.request.parser_context["kwargs"].get("category")
        service = self.request.parser_context["kwargs"].get("service")
        try:
            service = models.Service.objects.get(category__name=category, name=service)
        except models.Service.DoesNotExist:
            return rf.response.Response(
                {"error": "JS_UNKNOWN_SERVICE"}, rf.status.HTTP_404_NOT_FOUND
            )

        return (
            models.Grant.objects.filter_active()
            .filter(
                access__role__service=service,
                revoked=False,
                expires__gte=dt.datetime.now(),
            )
            .select_related("access__role", "access__user")
        )
