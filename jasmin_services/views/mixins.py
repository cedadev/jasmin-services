import django.http

from .. import models


class WithServiceMixin:
    """Mixin to add service to class-based view attributes."""

    @staticmethod
    def get_service(category_name, service_name):
        """Get a service from it's category and name."""
        try:
            return models.Service.objects.get(name=service_name, category__name=category_name)
        except models.Service.DoesNotExist as err:
            raise django.http.Http404("Service does not exist.") from err

    def setup(self, request, *args, **kwargs):
        """Add service to class atrributes."""
        # pylint: disable=attribute-defined-outside-init

        # Get the service from the request.
        self.service = self.get_service(kwargs["category"], kwargs["service"])
        if self.service.disabled:
            raise django.http.Http404("Service has been retired.")

        super().setup(request, *args, **kwargs)
