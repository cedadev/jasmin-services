"""Serializers for the jasmin_services api."""
import collections

import django.contrib.auth
import rest_framework.serializers as rf_serial

from .. import models


class ServiceRolesListSerializer(rf_serial.ListSerializer):
    """Serialize role output into dict of lists of user roles."""

    def to_representation(self, data):
        """
        Mutate list of users and roles to dict of users.

        Each user has a list of roles.
        """
        data = super().to_representation(data)

        result = collections.defaultdict(set)
        for item in data:
            result[item["username"]].add(item["role"])

        return result

    @property
    def data(self):
        """Return a dict not a list."""
        ret = rf_serial.BaseSerializer.data.fget(self)
        return rf_serial.ReturnDict(ret, serializer=self)


class ServiceRolesSerializer(rf_serial.ModelSerializer):
    """Base serializer returns list of usernames with roles."""

    role = rf_serial.CharField(source="access.role.name")
    username = rf_serial.CharField(source="access.user.username")

    class Meta:
        model = models.Grant
        fields = ["username", "role"]
        list_serializer_class = ServiceRolesListSerializer
