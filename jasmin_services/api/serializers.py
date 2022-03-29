import collections

import django.contrib.auth
import rest_framework.serializers as rf_serial

from .. import models


class ServiceRolesListSerializer(rf_serial.ListSerializer):
    def to_representation(self, data):
        data = super().to_representation(data)

        result = collections.defaultdict(set)
        for item in data:
            result[item["username"]].add(item["role"])

        return result

    @property
    def data(self):
        ret = rf_serial.BaseSerializer.data.fget(self)
        return rf_serial.ReturnDict(ret, serializer=self)


class ServiceRolesSerializer(rf_serial.ModelSerializer):
    role = rf_serial.CharField(source="access.role.name")
    username = rf_serial.CharField(source="access.user.username")

    class Meta:
        model = models.Grant
        fields = ["username", "role"]
        list_serializer_class = ServiceRolesListSerializer
