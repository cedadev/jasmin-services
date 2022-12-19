import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_safe

from ..models import Grant, Request, RequestState, Role
from .common import redirect_to_service, with_service

_log = logging.getLogger(__name__)


@require_safe
@login_required
@with_service
def service_requests(request, service):
    """
    Handler for ``/<category>/<service>/requests/``.

    Responds to GET requests only. The user must have the permission
    ``decide_request`` for at least one role in the service.

    Displays the pending requests for a service. The requests that a user sees
    depends on the permissions they have been granted.
    """
    # Get the roles for which the user is allowed to decide requests
    # We allow the permission to be allocated for all services, per-service or per-role
    permission = "jasmin_services.decide_request"
    if request.user.has_perm(permission) or request.user.has_perm(permission, service):
        user_roles = list(service.roles.all())
    else:
        user_roles = [
            role for role in service.roles.all() if request.user.has_perm(permission, role)
        ]
        # If the user has no permissions, send them back to the service details
        # Note that we don't show this message if the user has been granted the
        # permission for the service but there are no roles - in that case we
        # just show nothing
        if not user_roles:
            messages.error(request, "Insufficient permissions")
            return redirect_to_service(service)
    templates = [
        "jasmin_services/{}/{}/service_requests.html".format(service.category.name, service.name),
        "jasmin_services/{}/service_requests.html".format(service.category.name),
        "jasmin_services/service_requests.html",
    ]
    return render(
        request,
        templates,
        {
            "service": service,
            # Get the pending requests for the discovered roles
            "requests": Request.objects.filter_active().filter(
                access__role__in=user_roles, state=RequestState.PENDING
            ),
            # The list of approvers to show here is any user who can approve at
            # least one of the visible roles
            "approvers": get_user_model()
            .objects.filter(
                access__grant__in=Grant.objects.filter(
                    access__role__in=Role.objects.filter_permission(
                        permission, service, *user_roles
                    ),
                    revoked=False,
                    expires__gte=date.today(),
                ).filter_active()
            )
            .exclude(pk=request.user.pk)
            .distinct(),
        },
    )
