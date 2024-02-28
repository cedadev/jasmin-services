import datetime as dt
import logging
from datetime import date

import django.conf
import django.contrib.auth.mixins
import django.core.exceptions
import django.views.generic
import django.views.generic.edit
from django.contrib import messages
from django.db import transaction

from ..models import Access, Grant, Request, RequestState, Role
from . import common, mixins

_log = logging.getLogger(__name__)


class RoleApplyView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    mixins.WithServiceMixin,
    django.views.generic.edit.FormView,
):
    """Handle for ``/<category>/<service>/apply/<role>/``.

    Collects the necessary information to raise a request for a role.
    """

    @staticmethod
    def get_previous_request_and_grant(bool_grant, previous):
        """Get the previous request or grant from the id supplied."""
        error = None
        previous_grant = None
        previous_request = None
        # bool_grant = 1 if the new request is being made from a previous grant
        if bool_grant == 1:
            previous_grant = Grant.objects.get(pk=previous)
            previous_request = (
                Request.objects.filter_active().filter(previous_grant=previous_grant).first()
            )
        # bool_grant = 0 if the new request is being made from a previous request
        elif bool_grant == 0:
            previous_request = Request.objects.get(pk=previous)
            if previous_request.previous_grant:
                previous_grant = previous_request.previous_grant

        # If the user has a more recent request or grant for this chain they must use that
        if (previous_request and hasattr(previous_request, "next_request")) or (
            previous_grant and hasattr(previous_grant, "next_grant")
        ):
            error = "Please use the most recent request or grant"

        # If the user has an active request for this chain it must be rejected
        elif previous_request and previous_request.state != RequestState.REJECTED:
            error = "You have already have an active request for the specified grant"

        return error, previous_grant, previous_request

    def setup(self, request, *args, **kwargs):
        """Set up extra class attributes depending on the service and role we are dealing with.

        These are needed throughout and not just in the context.
        """
        # pylint: disable=attribute-defined-outside-init
        super().setup(request, *args, **kwargs)
        self.redirect_to_service = True

        # Prevent users who are not allowed to apply for this service from doing so.
        user_may_apply = common.user_may_apply(request.user, self.service)
        if not user_may_apply[0]:
            raise django.core.exceptions.PermissionDenied(
                "You do not have permission to apply for this service."
            )

        # Get the role we are applying for from the request.
        try:
            self.role = Role.objects.get(service=self.service, name=kwargs["role"])
        except Role.DoesNotExist:
            messages.error(request, "Role does not exist")
            self.redirect_to_service = True
            return

        # Get the previous request or grant, if it is supplies.
        error, self.previous_request, self.previous_grant = self.get_previous_request_and_grant(
            kwargs.get("bool_grant", None), kwargs.get("previous", None)
        )
        if error is not None:
            messages.info(request, error)
            self.redirect_to_service = True
            return

        # If we have sucessfuly got all the info, we do not need to redirect to the service.
        self.redirect_to_service = False

    def dispatch(self, request, *args, **kwargs):
        """Check the user may apply for the role before dispatching."""
        if self.redirect_to_service:
            return common.redirect_to_service(self.service)

        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        """Use the form class for the role being applied for.

        This includes the correct metadata forms for the role.
        """
        return self.role.metadata_form_class

    def get_initial(self):
        """Add previous requests to inital form data."""
        initial = {}
        if self.previous_request is not None:
            for datum in self.previous_request.metadata.all():
                initial[datum.key] = datum.value
        return initial

    def get_template_names(self):
        """Allow overriding the template at multiple levels."""
        return [
            f"jasmin_services/{self.service.category.name}/{self.service.name}/{self.role.name}/role_apply.html",
            f"jasmin_services/{self.service.category.name}/{self.service.name}/role_apply.html",
            f"jasmin_services/{self.service.category.name}/role_apply.html",
            "jasmin_services/role_apply.html",
        ]

    def get_context_data(self, **kwargs):
        """Add the role, grant and request to the context."""
        context = super().get_context_data(**kwargs)
        context |= {
            "role": self.role,
            "grant": self.previous_grant,
            "req": self.previous_request,
        }
        return context

    def form_valid(self, form):
        """Handle the form and create the role request."""
        with transaction.atomic():
            access, _ = Access.objects.get_or_create(
                role=self.role,
                user=self.request.user,
            )
            # If the role is set to auto accept, grant before saving
            if self.role.auto_accept:
                req = Request.objects.create(
                    access=access,
                    requested_by=self.request.user.username,
                    state=RequestState.APPROVED,
                )
                req.resulting_grant = Grant.objects.create(
                    access=access,
                    granted_by="automatic",
                    expires=date.today()
                    + dt.timedelta(
                        days=django.conf.settings.JASMIN_SERVICES.get("AUTO_ACCEPT_GRANT_TIME", 365)
                    ),
                )

                if self.previous_request is not None:
                    req.previous_request = self.previous_request
                    req.save()

                if self.previous_grant is not None:
                    req.resulting_grant.previous_grant = self.previous_grant
                    req.previous_grant = self.previous_grant
                    req.resulting_grant.save()

                req.save()
                form.save(req)
                req.copy_metadata_to(req.resulting_grant)
            else:
                req = Request.objects.create(access=access, requested_by=self.request.user.username)

                if self.previous_request is not None:
                    self.previous_request.next_request = req
                    self.previous_request.save()

                if self.previous_grant is not None:
                    req.previous_grant = self.previous_grant
                req.save()
                form.save(req)

        messages.success(self.request, "Request submitted successfully")
        return common.redirect_to_service(self.service)
