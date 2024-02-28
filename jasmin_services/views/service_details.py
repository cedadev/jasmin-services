from datetime import date

import django.views.generic
from django.conf import settings

from ..models import Grant, Request
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
            Grant.objects.filter(
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

        # Get the active grants and requests for the service as a whole
        all_grants = Grant.objects.filter(
            access__role__service=self.service, access__user=self.request.user
        ).filter_active()
        all_requests = Request.objects.filter(
            access__role__service=self.service, access__user=self.request.user
        ).filter_active()

        # roles is a list of the roles of the service that have an active grant
        # or request or aren't hidden
        roles = []
        grants = []
        requests = []
        for role in self.service.roles.all():
            role_grants = all_grants.filter(access__role=role)
            role_requests = all_requests.filter(access__role=role)
            if role_grants:
                # Add metadata so users can tell grants apart
                role_grants = [
                    (
                        rg,
                        getattr(
                            rg.metadata.filter(key="supporting_information").first(),
                            "value",
                            None,
                        ),
                        rg.next_requests.all(),
                    )
                    for rg in role_grants
                ]
                grants.append((role, role_grants))
            if role_requests:
                # Add metadata so users can tell requests apart
                role_requests = [
                    (
                        rr,
                        getattr(
                            rr.metadata.filter(key="supporting_information").first(),
                            "value",
                            None,
                        ),
                    )
                    for rr in role_requests
                ]
                requests.append((role, role_requests))
            if not role.hidden or role_requests or role_grants:
                # if multiple requests aren't allowed only add to "apply list"
                # if there isn't an existing request or grant
                if not settings.MULTIPLE_REQUESTS_ALLOWED and (role_requests or role_grants):
                    continue
                roles.append(role)

        # If the user holds an active grant in the service
        # get all the current managers and deputies of a services so that
        # we can display this information to users of the service.
        if grants:
            managers = self.get_service_roleholders(self.service, "MANAGER")
            deputies = self.get_service_roleholders(self.service, "DEPUTY")
        else:
            managers = []
            deputies = []

        context |= {
            "service": self.service,
            "requests": requests,
            "grants": grants,
            "roles": roles,
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
