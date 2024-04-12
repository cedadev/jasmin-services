import itertools
import random
import string
from datetime import date

import django.views.generic
from django.conf import settings
from django.db.models import OuterRef, Q, Subquery

import jasmin_metadata.models

from .. import models
from . import common, mixins


class ServiceDetailsView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    mixins.WithServiceMixin,
    django.views.generic.TemplateView,
):
    """Handle ``/<category>/<service>/``.

    Responds to GET requests only. The user must be authenticated.

    Displays details for a service, including details of current access and requests.
    """

    @staticmethod
    def get_service_roleholders(service, role_name):
        """Get the holders of a given role for a service."""
        holders = (
            models.Grant.objects.filter(
                access__role__service=service,
                expires__gt=date.today(),
                revoked=False,
            )
            .filter_active()
            .filter(access__role__name=role_name)
        )
        return [x.access.user for x in holders]

    @staticmethod
    def display_accesses(user, *all_accesses):
        """Process a list of either requests or grants for display."""
        accesses = list(itertools.chain.from_iterable(all_accesses))

        # This ID is used to create CSS ids. Must be unique per access.
        id_part = "".join(random.choice(string.ascii_lowercase) for i in range(5))
        id_ = 0
        # We loop through the list, and add some information which is not otherwise available.
        for access in accesses:
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
                "may_apply": access.access.role.user_may_apply(user),
            }
            id_ += 1

        accesses = sorted(accesses, key=lambda x: x.frontend["start"], reverse=True)
        return accesses

    def get_context_data(self, **kwargs):
        """Add information about service to the context."""
        context = super().get_context_data(**kwargs)

        # Get the active grants and requests for the service as a whole
        grants = (
            models.Grant.objects.filter(
                access__role__service=self.service, access__user=self.request.user
            )
            .filter_active()
            .prefetch_related("metadata")
        )
        requests = (
            models.Request.objects.filter(
                access__role__service=self.service, access__user=self.request.user
            )
            .filter_active()
            .prefetch_related("metadata")
        )

        # Get the roles the user is able to apply for.
        # This is any roles which aren't hidden, or any role the user
        # Has an access (request or grant) for.
        may_apply_roles = [
            x
            for x in self.service.roles.filter(
                Q(hidden=False) | Q(access__user=self.request.user)
            ).distinct()
            if x.user_may_apply(self.request.user)
        ]

        # If the user holds an active grant in the service
        # get all the current managers and deputies of a services so that
        # we can display this information to users of the service.
        if grants.exists():
            managers = self.get_service_roleholders(self.service, "MANAGER")
            deputies = self.get_service_roleholders(self.service, "DEPUTY")
        else:
            managers = []
            deputies = []

        # To give pretty name of supporting information, add the fields.
        # But it would be better to annotate the real query.
        metadata_names = jasmin_metadata.models.Field.objects.all()

        context |= {
            "service": self.service,
            "roles": may_apply_roles,
            "managers": managers,
            "deputies": deputies,
            "user_may_apply": common.user_may_apply(self.request.user, self.service),
            "accesses": self.display_accesses(self.request.user, grants, requests),
        }
        return context

    def get_template_names(self):
        """Allow overriding the template at multiple levels."""
        return [
            f"jasmin_services/{self.service.category.name}/{self.service.name}/service_details.html",
            f"jasmin_services/{self.service.category.name}/service_details.html",
            "jasmin_services/service_details.html",
        ]
