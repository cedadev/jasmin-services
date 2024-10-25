"""APIViews for the jasmin_services API."""

import datetime as dt

import django.contrib.auth.decorators
import django.db.models as dj_models
import django.utils.decorators
import django.utils.timezone
import drf_spectacular.utils
import jasmin_django_utils.api.viewsets
import rest_framework.decorators as rf_decorators
import rest_framework.mixins as rf_mixins
import rest_framework.response as rf_response
import rest_framework.viewsets as rf_viewsets

from .. import models
from . import filters, serializers


@django.utils.decorators.method_decorator(
    django.contrib.auth.decorators.login_not_required, name="dispatch"
)
class ServicesViewSet(
    jasmin_django_utils.api.viewsets.ActionSerializerMixin,
    rf_viewsets.ReadOnlyModelViewSet,
):
    """View and get details of a service."""

    queryset = models.Service.objects.all().prefetch_related("category")
    serializer_class = serializers.ServiceSerializer
    action_serializers = {
        "list": serializers.ServiceListSerializer,
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
            ),
        ]
    ),
)
@django.utils.decorators.method_decorator(
    django.contrib.auth.decorators.login_not_required, name="dispatch"
)
class RolesNestedUnderServicesViewSet(rf_viewsets.ReadOnlyModelViewSet):
    """View roles for a service."""

    serializer_class = serializers.RoleSerializer
    required_scopes = ["jasmin.services.serviceroles.all"]
    lookup_field = "name"
    filterset_class = filters.RoleFilter

    def get_queryset(self):
        # If we are generating swagger definitions, return the correct
        # queryset to allow types to be infered without error.
        if getattr(self, "swagger_fake_view", False):
            return models.Role.objects.none()

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


@drf_spectacular.utils.extend_schema_view(
    list=drf_spectacular.utils.extend_schema(
        parameters=[
            drf_spectacular.utils.OpenApiParameter(
                name="category_name",
                type=str,
                location=drf_spectacular.utils.OpenApiParameter.PATH,
            ),
        ],
    ),
    retrieve=drf_spectacular.utils.extend_schema(
        parameters=[
            drf_spectacular.utils.OpenApiParameter(
                name="category_name",
                type=str,
                location=drf_spectacular.utils.OpenApiParameter.PATH,
            ),
        ]
    ),
)
@django.utils.decorators.method_decorator(
    django.contrib.auth.decorators.login_not_required, name="dispatch"
)
class ServicesNestedUnderCategoriesViewSet(ServicesViewSet):
    """Viewset to allow services to be nested under categories.

    Same as ServicesViewset, but lookup the service by name instead of pk,
    and filter by category.
    """

    lookup_field = "name"
    required_scopes = ["jasmin.services.services.all"]
    filterset_fields = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()

        # If we are generating swagger definitions, return the correct
        # queryset to allow types to be infered without error.
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()

        return queryset.filter(category__name=self.kwargs["category_name"])


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
class UserGrantsViewSet(rf_mixins.ListModelMixin, rf_viewsets.GenericViewSet):
    """Get the grants associated with a user."""

    required_scopes = ["jasmin.services.userservices.all"]
    serializer_class = serializers.UserGrantSerializer
    filterset_class = filters.UserGrantsFilter

    def get_queryset(self):
        # If we are generating swagger definitions, return the correct
        # queryset to allow types to be infered without error.
        if getattr(self, "swagger_fake_view", False):
            return models.Grant.objects.none()

        queryset = models.Grant.objects.filter(
            access__user__username=self.kwargs["user_username"],
            revoked=False,
            expires__gte=dt.datetime.now(),
        ).prefetch_related("access__role__service")
        return queryset


@django.utils.decorators.method_decorator(
    django.contrib.auth.decorators.login_not_required, name="dispatch"
)
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
