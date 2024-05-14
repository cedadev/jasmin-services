"""APIViews for the jasmin_services API."""

import datetime as dt

import django.contrib.auth
import django.db.models as dj_models
import django.utils.timezone
import drf_spectacular.utils
import jasmin_django_utils.api.viewsets
import rest_framework.decorators as rf_decorators
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

    @drf_spectacular.utils.extend_schema(
        parameters=[
            drf_spectacular.utils.OpenApiParameter(
                name="on_date",
                required=False,
                type=dt.date,
                description="ISO Date on which you would like to know the active roles for a service.",
            )
        ],
        responses=serializers.RoleSerializer(many=True),
    )
    @rf_decorators.action(detail=True, required_scopes=["jasmin.services.serviceroles.all"])
    def roles(self, request, pk=None):
        """List roles in a services and their holders."""
        self.filterset_fields = []
        self.search_fields = []

        date_string = self.request.query_params.get("on_date", False)
        if date_string:
            on_date = dt.date.fromisoformat(date_string)
        else:
            on_date = dt.date.today()
        on_date_end = dt.datetime.combine(
            on_date,
            dt.time(hour=23, minute=59, second=59),
            tzinfo=django.utils.timezone.get_current_timezone(),
        )

        service = self.get_object()
        queryset = models.Role.objects.filter(service=service).prefetch_related(
            dj_models.Prefetch(
                "accesses",
                queryset=models.Access.objects.filter(
                    # There is no "revoked_at" field, so we must exclude all revoked accesses.
                    grant__revoked=False,
                    # The given grant must have been granted before the end of the day we are interested in.
                    grant__granted_at__lte=on_date_end,
                    # And expire after the end of the date we are interested in.
                    grant__expires__gt=on_date_end,
                ),
            )
        )
        serializer = serializers.RoleSerializer(queryset, many=True, context={"request": request})
        return rf_response.Response(serializer.data)


class UsersViewSet(
    jasmin_django_utils.api.viewsets.ActionSerializerMixin,
    rf_viewsets.GenericViewSet,
):
    queryset = django.contrib.auth.get_user_model().objects
    lookup_field = "username"
    action_serializers = {
        "services": serializers.ServiceListSerializer,
        "grants": serializers.UserGrantSerializer,
    }
    required_scopes = ["jasmin.services.userservices.all"]

    @drf_spectacular.utils.extend_schema(
        responses=serializers.ServiceListSerializer(many=True),
    )
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

    @drf_spectacular.utils.extend_schema(
        responses=serializers.UserGrantSerializer(many=True),
    )
    @rf_decorators.action(detail=True)
    def grants(self, request, username=None):
        """List the grants of a given user."""
        user = self.get_object()
        queryset = models.Grant.objects.filter(
            access__user=user,
            revoked=False,
            expires__gte=dt.datetime.now(),
        ).prefetch_related("access__role__service")

        filter_params = {}

        # Option to filter by service query param
        service = self.request.query_params.get("service")
        if service is not None:
            filter_params["access__role__service__name"] = service

        # Option to filter by category query param
        category = self.request.query_params.get("category")
        if category is not None:
            filter_params["access__role__service__category__name"] = category

        queryset = queryset.filter(**filter_params)

        serializer = serializers.UserGrantSerializer(
            queryset, many=True, context={"request": request}
        )
        return rf_response.Response(serializer.data)


class CategoriesViewSet(
    jasmin_django_utils.api.viewsets.ActionSerializerMixin,
    rf_viewsets.ReadOnlyModelViewSet,
):
    """Details of services categories."""

    queryset = models.Category.objects.prefetch_related("services")
    lookup_field = "name"
    serializer_class = serializers.CategoryListSerializer
    required_scopes = ["jasmin.services.categories.all"]
    action_serializers = {
        "list": serializers.CategoryListSerializer,
        "retrieve": serializers.CategorySerializer,
    }
    filterset_fields = ["name"]
    search_fields = ["name", "summary"]
