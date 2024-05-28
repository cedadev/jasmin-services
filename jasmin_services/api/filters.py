import django_filters.rest_framework

from .. import models


class RoleFilter(django_filters.rest_framework.FilterSet):

    name = django_filters.rest_framework.AllValuesMultipleFilter()

    class Meta:
        model = models.Role
        fields = ["name"]
