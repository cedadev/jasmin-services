import logging

import django.db
from django import http
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from ..forms import DecisionForm
from ..models import Request, RequestState
from .common import redirect_to_service

_log = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
@login_required
@django.db.transaction.atomic
def request_decide(request, pk):
    """
    Handler for ``/request/<pk>/decide/``.

    Responds to GET and POST. The user must have the ``decide_request``
    permission for the role that the request is for. The request must be active
    and pending.

    Presents information about the request along with a form to collect a decision.
    """
    # Try to find the specified request
    try:
        pending = Request.objects.get(pk=pk)
    except Request.DoesNotExist:
        raise http.Http404("Request does not exist")
    # The current user must have permission to grant the role
    permission = "jasmin_services.decide_request"
    if (
        not request.user.has_perm(permission)
        and not request.user.has_perm(permission, pending.access.role.service)
        and not request.user.has_perm(permission, pending.access.role)
    ):
        messages.error(request, "Request does not exist")
        return redirect_to_service(pending.access.role.service, "service_details")
    # If the request is not pending, redirect to the list of pending requests
    if not pending.active or pending.state != RequestState.PENDING:
        messages.info(request, "This request has already been resolved")
        return redirect(
            "jasmin_services:service_requests",
            category=pending.access.role.service.category.name,
            service=pending.access.role.service.name,
        )
    # If the user requesting access has an active grant, find it
    grant = pending.previous_grant
    # Find all the rejected requests for the role/user since the active grant
    rejected = Request.objects.filter(
        access=pending.access,
        state=RequestState.REJECTED,
        previous_grant=pending.previous_grant,
    ).order_by("requested_at")
    # Process the form if this is a POST request, otherwise just set it up
    if request.method == "POST":
        form = DecisionForm(pending, request.user, data=request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            return redirect_to_service(pending.access.role.service, "service_requests")
        else:
            messages.error(request, "Error with one or more fields")
    else:
        form = DecisionForm(pending, request.user)
    templates = [
        "jasmin_services/{}/{}/request_decide.html".format(
            pending.access.role.service.category.name, pending.access.role.service.name
        ),
        "jasmin_services/{}/request_decide.html".format(pending.access.role.service.category.name),
        "jasmin_services/request_decide.html",
    ]
    return render(
        request,
        templates,
        {
            "service": pending.access.role.service,
            "pending": pending,
            "rejected": rejected,
            "grant": grant,
            # The list of approvers to show here is any user who has the correct
            # permission for either the role or the service
            "approvers": pending.access.role.approvers.exclude(pk=request.user.pk),
            "form": form,
        },
    )
