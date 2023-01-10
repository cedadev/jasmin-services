from datetime import date

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_safe

from ..models import Grant, Request
from . import common


@require_safe
@login_required
@common.with_service
def service_details(request, service):
    """Handle ``/<category>/<service>/``.

    Responds to GET requests only. The user must be authenticated.

    Displays details for a service, including details of current access and requests.
    """

    # Get the active grants and requests for the service as a whole
    all_grants = Grant.objects.filter(
        access__role__service=service, access__user=request.user
    ).filter_active()
    all_requests = Request.objects.filter(
        access__role__service=service, access__user=request.user
    ).filter_active()

    # roles is a list of the roles of the service that have an active grant
    # or request or aren't hidden
    roles = []
    grants = []
    requests = []
    for role in service.roles.all():
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

        if grants:
            # Get all the current managers and deputies of a services so that
            # we can display this information to users of the service.
            managers = (
                Grant.objects.filter(
                    access__role__service=service,
                    expires__gt=date.today(),
                    revoked=False,
                )
                .filter_active()
                .filter(access__role__name="MANAGER")
            )
            managers = [x.access.user for x in managers]
            deputies = (
                Grant.objects.filter(
                    access__role__service=service,
                    expires__gt=date.today(),
                    revoked=False,
                )
                .filter_active()
                .filter(access__role__name="DEPUTY")
            )
            deputies = [x.access.user for x in deputies]
        else:
            managers = []
            deputies = []

    templates = [
        f"jasmin_services/{service.category.name}/{service.name}/service_details.html",
        f"jasmin_services/{service.category.name}/service_details.html",
        "jasmin_services/service_details.html",
    ]
    return render(
        request,
        templates,
        {
            "service": service,
            "requests": requests,
            "grants": grants,
            "roles": roles,
            "managers": managers,
            "deputies": deputies,
            "user_may_apply": common.user_may_apply(request.user, service),
        },
    )
