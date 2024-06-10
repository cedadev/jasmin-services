import django_filters.rest_framework

from .. import models


class RoleFilter(django_filters.rest_framework.FilterSet):
    """Filter to allow filtering roles by name.

    Using an AllValuesMultipleFilter allows searching for more than one role at once.
    """

    name = django_filters.rest_framework.AllValuesMultipleFilter()

    class Meta:
        model = models.Role
        fields = ["name"]


class UserGrantsFilter(django_filters.rest_framework.FilterSet):
    """Filter to allow filtering user grants.

    Allow filtering by service name, category name, or role name.
    """

    service = django_filters.rest_framework.AllValuesFilter(
        field_name="access__role__service__name", label="Service name"
    )
    category = django_filters.rest_framework.AllValuesFilter(
        field_name="access__role__service__category__name", label="Category name"
    )
    role = django_filters.rest_framework.AllValuesMultipleFilter(
        field_name="access__role__name", label="Role name"
    )
