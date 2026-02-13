import random
import string
from datetime import date

import asgiref.sync
import django.contrib.auth.mixins
import django.http
import django.urls
from django.db.models import Q

from .. import models
from . import common, mixins


class WithServiceMixin:
    """Mixin to add service to class-based view attributes."""

    @staticmethod
    def get_service(category_name: str, service_name: str) -> models.Service:
        """Get a service from its category and name."""
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


class AsyncLoginRequiredMixin(
    django.contrib.auth.mixins.LoginRequiredMixin,
):
    def handle_no_permission(self):
        """Wrap the handle_no_permission function to return an async response if required.

        Similar to : https://github.com/django/django/blob/main/django/views/generic/base.py#L145
        """
        response = super().handle_no_permission()
        if self.view_is_async and (not asgiref.sync.iscoroutinefunction(response)):

            async def func():
                return response

            return func()
        return response


class AccessListMixin:
    """Mixin to process a list of grants and requests for display on the frontend."""

    @staticmethod
    async def process_access(access, user, id_part, id_, may_apply_override=None):
        # Allow overriding the user_may_apply calculation.
        if may_apply_override is None:
            may_apply = await access.access.role.auser_may_apply(user)
        else:
            may_apply = may_apply_override

        access.frontend = {
            "start": (
                access.requested_at if isinstance(access, models.Request) else access.granted_at
            ),
            "id": f"{id_part}_{id_}",
            "type": ("REQUEST" if isinstance(access, models.Request) else "GRANT"),
            "apply_url": django.urls.reverse(
                "jasmin_services:role_apply",
                kwargs={
                    "category": access.access.role.service.category.name,
                    "service": access.access.role.service.name,
                    "role": access.access.role.name,
                    "bool_grant": 0 if isinstance(access, models.Request) else 1,
                    "previous": access.id,
                },
            ),
            "may_apply": may_apply,
        }
        return access

    async def display_accesses(self, user, grants, requests, may_apply_override=None):
        """Process a list of either requests or grants for display."""
        processed = []

        # This ID is used to create CSS ids. Must be unique per access.
        id_part = "".join(random.choice(string.ascii_lowercase) for i in range(5))
        id_ = 0
        # We loop through the list, and add some information which is not otherwise available.
        async for grant in grants:
            processed.append(
                await self.process_access(
                    grant, user, id_part, id_, may_apply_override=may_apply_override
                )
            )
            id_ += 1
        async for request in requests:
            processed.append(
                await self.process_access(
                    request, user, id_part, id_, may_apply_override=may_apply_override
                )
            )
            id_ += 1

        accesses = sorted(processed, key=lambda x: x.frontend["start"], reverse=True)

        return accesses
