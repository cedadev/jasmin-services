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


@drf_spectacular.utils.extend_schema_view(
    list=drf_spectacular.utils.extend_schema(
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
)
class RolesNestedUnderServicesViewSet(rf_viewsets.ReadOnlyModelViewSet):
    """View roles for a service."""

    serializer_class = serializers.RoleSerializer
    required_scopes = ["jasmin.services.serviceroles.all"]
    lookup_field = "name"

    def get_queryset(self):

        # Add query to lookup roleholders by date.
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

        # Get the correct service to get roles form.
        # This view can either be nexted under /services/pk/roles or
        # /categories/<name>/services/<name>roles/
        # And we will get slightly different kwargs in each case.
        try:
            # If nested, we will get the category and service name.
            service = models.Service.objects.get(
                category__name=self.kwargs["category_name"],
                name=self.kwargs["service_name"],
            )
        except KeyError:
            # Otherwise, we get the service pk.
            service = models.Service.objects.get(pk=self.kwargs["service_pk"])

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
        return queryset


class ServicesNestedUnderCategoriesViewSet(ServicesViewSet):
    """Viewset to allow services to be nested under categories.

    Same as ServicesViewset, but lookup the service by name instead of pk,
    and filter by category.
    """

    lookup_field = "name"
    required_scopes = ["jasmin.services.services.all"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(category__name=self.kwargs["category_name"])


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
