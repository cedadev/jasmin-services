import django.http

from .. import models


class WithServiceMixin:
    """Mixin to add service to class-based view attributes."""

    @staticmethod
    def get_service(category_name: str, service_name: str) -> models.Service:
        """Get a service from it's category and name."""
        try:
            service = models.Service.objects.get(name=service_name, category__name=category_name)
        except models.Service.DoesNotExist as err:
            raise django.http.Http404("Service does not exist.") from err
        if service.disabled:
            raise django.http.Http404("Service has been retired.")
        return service

    @staticmethod
    async def aget_service(category_name: str, service_name: str) -> models.Service:
        """Async version of get_service."""
        try:
            service = await models.Service.objects.select_related("category").aget(
                name=service_name, category__name=category_name
            )
        except models.Service.DoesNotExist as err:
            raise django.http.Http404("Service does not exist.") from err
        if service.disabled:
            raise django.http.Http404("Service has been retired.")
        return service


class AsyncContextMixin:
    """Reimpliment ContextMixin async.

    https://github.com/django/django/blob/main/django/views/generic/base.py#L21
    """

    extra_context = None

    async def get_context_data(self, **kwargs):
        kwargs.setdefault("view", self)
        if self.extra_context is not None:
            kwargs.update(self.extra_context)
        return kwargs


class AsyncTemplateView(
    django.views.generic.base.TemplateResponseMixin,
    AsyncContextMixin,
    django.views.View,
):
    """Reimpliment TemplateView as async.

    https://github.com/django/django/blob/main/django/views/generic/base.py#L220
    """

    async def get(self, request, *args, **kwargs):
        context = await self.get_context_data(**kwargs)
        return self.render_to_response(context)
