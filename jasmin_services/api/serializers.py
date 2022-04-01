"""Serializers for the jasmin_services api."""
import collections

import django.contrib.auth
import rest_framework.serializers as rf_serial

from .. import models


class UserSerializer(rf_serial.HyperlinkedModelSerializer):
    """Basic UserSerializer to provide a link to the full one."""

    class Meta:
        model = django.contrib.auth.get_user_model()
        fields = ["id", "url", "username"]
        extra_kwargs = {"url": {"view_name": "user-detail", "lookup_field": "username"}}


class AccessSerializer(rf_serial.ModelSerializer):
    """Serializer for list of Accesses."""

    user = UserSerializer()

    class Meta:
        model = models.Access
        fields = ["id", "user"]


class RoleListSerializer(rf_serial.ModelSerializer):
    """Serializer basic list of roles."""

    class Meta:
        model = models.Role
        fields = ["id", "name"]


class RoleSerializer(rf_serial.ModelSerializer):
    """Serializer for roles with holders."""

    accesses = AccessSerializer(many=True)

    class Meta:
        model = models.Role
        fields = ["id", "name", "accesses"]


class CategoryListSerializer(rf_serial.ModelSerializer):
    class Meta:
        model = models.Category
        fields = ["id", "name"]


class ServiceListSerializer(rf_serial.HyperlinkedModelSerializer):
    """Serializer for simple details about a service."""

    category = CategoryListSerializer()

    class Meta:
        model = models.Service
        fields = ["id", "url", "category", "name", "summary", "hidden"]


class ServiceSerializer(ServiceListSerializer):
    """Serializer for full details of a service."""

    roles = RoleListSerializer(many=True)

    class Meta:
        model = models.Service
        fields = "__all__"
