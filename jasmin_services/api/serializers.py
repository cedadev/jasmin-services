"""Serializers for the jasmin_services api."""
import collections

import django.contrib.auth
import rest_framework.serializers as rf_serial

from .. import models


class ServiceUserSerializer(rf_serial.HyperlinkedModelSerializer):
    """Basic UserSerializer to provide a link to the full one."""

    class Meta:
        model = django.contrib.auth.get_user_model()
        fields = ["id", "url", "username"]
        extra_kwargs = {"url": {"view_name": "user-detail", "lookup_field": "username"}}


class AccessSerializer(rf_serial.ModelSerializer):
    """List of service accesses."""

    user = ServiceUserSerializer()

    class Meta:
        model = models.Access
        fields = ["id", "user"]


class RoleListSerializer(rf_serial.ModelSerializer):
    """Basic list of roles."""

    class Meta:
        model = models.Role
        fields = ["id", "name"]


class RoleSerializer(rf_serial.ModelSerializer):
    """Detail of role with holders."""

    accesses = AccessSerializer(many=True)

    class Meta:
        model = models.Role
        fields = ["id", "name", "accesses"]


class CategoryListSerializer(rf_serial.HyperlinkedModelSerializer):
    """Basic information about a service category."""

    class Meta:
        model = models.Category
        fields = ["id", "url", "name"]
        extra_kwargs = {"url": {"view_name": "category-detail", "lookup_field": "name"}}


class ServiceListSerializer(rf_serial.HyperlinkedModelSerializer):
    """Simple details about a service."""

    category = CategoryListSerializer()

    class Meta:
        model = models.Service
        fields = ["id", "url", "category", "name", "summary", "hidden"]


class CategoryServiceSerializer(ServiceListSerializer):
    """Simple details about a service, excluding it's category."""

    class Meta:
        model = models.Service
        fields = ["id", "url", "name", "summary", "hidden"]


class CategorySerializer(CategoryListSerializer):
    """Details of a service category."""

    services = CategoryServiceSerializer(many=True)

    class Meta:
        model = models.Category
        extra_kwargs = {"url": {"view_name": "category-detail", "lookup_field": "name"}}
        fields = ["id", "url", "name", "long_name", "position", "services"]


class ServiceSerializer(ServiceListSerializer):
    """Full details of a service."""

    roles = RoleListSerializer(many=True)

    class Meta:
        model = models.Service
        fields = [
            "id",
            "url",
            "name",
            "category",
            "roles",
            "summary",
            "description",
            "approver_message",
            "instution_countries",
            "hidden",
            "position",
            "ceda_managed",
        ]
