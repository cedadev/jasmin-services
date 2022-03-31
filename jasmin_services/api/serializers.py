"""Serializers for the jasmin_services api."""
import collections

import rest_framework.serializers as rf_serial

from .. import models


class ServiceRoleSerializer(rf_serial.ModelSerializer):
    """Serializer for roles in a service."""

    class Meta:
        model = models.Role
        fields = ["id", "name"]


class ServiceListSerializer(rf_serial.ModelSerializer):
    """Serializer for simple details about a service."""

    category = rf_serial.SlugRelatedField(slug_field="name", read_only=True)

    class Meta:
        model = models.Service
        fields = ["id", "category", "name", "summary"]


class ServiceSerializer(ServiceListSerializer):
    """Serializer for full details of a service."""

    roles = ServiceRoleSerializer(many=True)

    class Meta:
        model = models.Service
        fields = "__all__"


class ServiceRolesListSerializer(rf_serial.ListSerializer):
    """
    Serialize role output into dict of lists of user roles.

    We serialize as a list so we can do aggregation.
    """

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

    def update(self, _instance, _validated_data):
        """Do not provide a way to update roles from here."""
        raise NotImplementedError()


class ServiceRolesSerializer(rf_serial.ModelSerializer):
    """Base serializer returns list of usernames with roles."""

    role = rf_serial.CharField(source="access.role.name")
    username = rf_serial.CharField(source="access.user.username")

    class Meta:
        model = models.Grant
        fields = ["username", "role"]
        list_serializer_class = ServiceRolesListSerializer

    @classmethod
    def get_schema_components(cls, _path, _method):
        """Return schema components."""
        return {
            "ServiceRoles": {
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
                "example": {
                    "fry": ["USER"],
                    "professor": ["USER", "MANAGER"],
                    "leela": ["USER"],
                },
            }
        }
