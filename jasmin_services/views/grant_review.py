import logging

import django.db
from django import http
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from ..forms import GrantReviewForm
from ..models import Grant
from .common import redirect_to_service

_log = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
@login_required
@django.db.transaction.atomic
def grant_review(request, pk):
    """
    Handler for ``/grant/<pk>/review/``.

    Responds to GET and POST. The user must have the ``revoke_role``
    permission for the role that the grant is for. The grant must be active
    and not expired or revoked.

    Presents information about the grant along with a form to collect a decision.
    """
    # Try to find the specified grant
    try:
        grant = Grant.objects.get(pk=pk)
    except Grant.DoesNotExist:
        raise http.Http404("Request does not exist")
    # The current user must have permission to grant the role
    permission = "jasmin_services.revoke_role"
    if (
        not request.user.has_perm(permission)
        and not request.user.has_perm(permission, grant.access.role.service)
        and not request.user.has_perm(permission, grant.access.role)
    ):
        messages.error(request, "Grant does not exist")
        return redirect_to_service(grant.role.service, "service_details")
    # If the grant is expired or revoked, redirect to the list of users
    if not grant.active or grant.expired or grant.revoked:
        messages.info(request, "This grant has already been rekoved or expired")
        return redirect(
            "jasmin_services:service_users",
            category=grant.access.role.service.category.name,
            service=grant.access.role.service.name,
        )
    if request.method == "POST":
        form = GrantReviewForm(grant, data=request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            messages.success(
                request,
                "{} revoked for {}".format(grant.access.role.name, grant.access.user.username),
            )
            return redirect_to_service(grant.access.role.service, "service_users")
        else:
            messages.error(request, "Error with one or more fields")
    else:
        form = GrantReviewForm(grant)
    templates = [
        "jasmin_services/{}/{}/grant_review.html".format(
            grant.access.role.service.category.name, grant.access.role.service.name
        ),
        "jasmin_services/{}/grant_review.html".format(grant.access.role.service.category.name),
        "jasmin_services/grant_review.html",
    ]
    return render(
        request,
        templates,
        {
            "service": grant.access.role.service,
            "grant": grant,
            "form": form,
        },
    )
