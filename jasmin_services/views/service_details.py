import random
import string
from datetime import date

import django.urls
from django.db.models import Q

from .. import models
from . import common, mixins


class ServiceDetailsView(
    mixins.AsyncLoginRequiredMixin,
    mixins.WithServiceMixin,
    mixins.AccessListMixin,
    mixins.AsyncTemplateView,
):
    """Handle ``/<category>/<service>/``.

    Responds to GET requests only. The user must be authenticated.

    Displays details for a service, including details of current access and requests.
    """

    @staticmethod
    async def get_service_roleholders(service, role_name):
        """Get the holders of a given role for a service."""
        holders = (
            models.Grant.objects.filter(
                access__role__service=service,
                expires__gt=date.today(),
                revoked=False,
            )
            .filter_active()
            .filter(access__role__name=role_name)
            .select_related("access__user")
        )
        result = []
        async for item in holders:
            result.append(item.access.user)
        return result

    async def get_context_data(self, **kwargs):
        """Add information about service to the context."""
        self.service = await self.aget_service(kwargs["category"], kwargs["service"])
        context = await super().get_context_data(**kwargs)

        user = await self.request.auser()

        # Get the active grants and requests for the service as a whole
        grants = (
            models.Grant.objects.filter(access__role__service=self.service, access__user=user)
            .filter_active()
            .prefetch_related("metadata", "access__role__service__category")
        )
        requests = (
            models.Request.objects.filter(access__role__service=self.service, access__user=user)
            .filter_active()
            .prefetch_related("metadata", "access__role__service__category")
        )

        # Get the roles the user is able to apply for.
        # This is any roles which aren't hidden, or any role the user
        # Has an access (request or grant) for.
        may_apply_roles = []
        async for role in self.service.roles.filter(
            Q(hidden=False) | Q(access__user=user)
        ).distinct():
            if await role.auser_may_apply(user):
                may_apply_roles.append(role)

        # Check if the user has any active grants in the service
        user_has_grant = await grants.aexists()

        # If the user holds an active grant in the service
        # get all the current managers and deputies of a services so that
        # we can display this information to users of the service.
        if user_has_grant:
            managers = await self.get_service_roleholders(self.service, "MANAGER")
            deputies = await self.get_service_roleholders(self.service, "DEPUTY")
        else:
            managers = []
            deputies = []

        context |= {
            "service": self.service,
            "roles": may_apply_roles,
            "managers": managers,
            "deputies": deputies,
            "user_may_apply": common.user_may_apply(user, self.service),
            "user_has_grant": user_has_grant,
            "accesses": await self.display_accesses(user, grants, requests),
        }
        return context

    def get_template_names(self):
        """Allow overriding the template at multiple levels."""
        return [
            f"jasmin_services/{self.service.category.name}/{self.service.name}/service_details.html",
            f"jasmin_services/{self.service.category.name}/service_details.html",
            "jasmin_services/service_details.html",
        ]
