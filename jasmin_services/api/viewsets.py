import rest_framework.viewsets as rf_viewsets


class ActionSerializerMixin:
    """Mixin to allow per-action serializer."""

    def get_serializer_class(self):

        if hasattr(self, "action_serializers"):
            return self.action_serializers.get(self.action, self.serializer_class)

        return super().get_serializer_class()
