import django.contrib.auth.decorators
import django.db.models as dj_models
import django.utils.decorators
import rest_framework.decorators as rf_decorators
import rest_framework.mixins as rf_mixins
import rest_framework.response as rf_response
import rest_framework.viewsets as rf_viewsets

from ... import models
from .. import serializers


@django.utils.decorators.method_decorator(
    django.contrib.auth.decorators.login_not_required, name="dispatch"
)
class CategoriesViewSet(rf_viewsets.ReadOnlyModelViewSet):
    """Details of services categories."""

    def get_serializer_class(self):
        """Allow different actions for different serializers."""
        if hasattr(self, "action_serializers"):
            return self.action_serializers.get(self.action, self.serializer_class)
        return super().get_serializer_class()

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
