from datetime import date

import django.views.generic
import jasmin_metadata.models
from django.conf import settings
from django.db.models import OuterRef, Q, Subquery

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

    def get_context_data(self, **kwargs):
        """Add information about service to the context."""
        context = super().get_context_data(**kwargs)

        roles = self.service.get_user_active_roles(self.request.user)
        for role in roles:
            print(role.id)

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

        # Get the roles the user is able to see.
        # This is any roles which aren't hidden, or any role the user
        # Has an access (request or grant) for.
        visible_roles = self.service.roles.filter(
            Q(hidden=False) | Q(access__user=self.request.user)
        )

        # If the user holds an active grant in the service
        # get all the current managers and deputies of a services so that
        # we can display this information to users of the service.
        if grants:
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
            "requests": requests,
            "grants": grants,
            "roles": visible_roles,
            "managers": managers,
            "deputies": deputies,
            "user_may_apply": common.user_may_apply(self.request.user, self.service),
        }
        return context

    def get_template_names(self):
        """Allow overriding the template at multiple levels."""
        return [
            f"jasmin_services/{self.service.category.name}/{self.service.name}/service_details.html",
            f"jasmin_services/{self.service.category.name}/service_details.html",
            "jasmin_services/service_details.html",
        ]
