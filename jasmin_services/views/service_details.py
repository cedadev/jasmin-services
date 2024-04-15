import random
import string
from datetime import date

import django.contrib.auth.mixins
from django.db.models import Q

from .. import models
from . import common, mixins


class ServiceDetailsView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    mixins.WithServiceMixin,
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

    @staticmethod
    async def process_access(access, user, id_part, id_):
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
            "may_apply": await access.access.role.auser_may_apply(user),
        }
        return access

    async def display_accesses(self, user, grants, requests):
        """Process a list of either requests or grants for display."""
        processed = []

        # This ID is used to create CSS ids. Must be unique per access.
        id_part = "".join(random.choice(string.ascii_lowercase) for i in range(5))
        id_ = 0
        # We loop through the list, and add some information which is not otherwise available.
        async for grant in grants:
            processed.append(await self.process_access(grant, user, id_part, id_))
            id_ += 1
        async for request in requests:
            processed.append(await self.process_access(request, user, id_part, id_))
            id_ += 1

        accesses = sorted(processed, key=lambda x: x.frontend["start"], reverse=True)
        return accesses

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

        # If the user holds an active grant in the service
        # get all the current managers and deputies of a services so that
        # we can display this information to users of the service.
        if await grants.aexists():
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
