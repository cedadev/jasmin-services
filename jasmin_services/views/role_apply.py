import logging
from datetime import date

import django.http
import requests as reqs
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from ..models import Access, Grant, Group, Request, RequestState, Role
from . import common

_log = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
@login_required
@common.with_service
def role_apply(request, service, role, bool_grant=None, previous=None):
    """Handle for ``/<category>/<service>/apply/<role>/``.

    Responds to GET and POST requests. The user must be authenticated.

    Collects the necessary information to raise a request for a role.
    """
    # Prevent users who are not allowed to apply for this service from doing so.
    user_may_apply = common.user_may_apply(request.user, service)
    if not user_may_apply[0]:
        return django.http.HttpResponseForbidden(
            "You do not have permission to apply for this service."
        )

    try:
        role = Role.objects.get(service=service, name=role)
    except Role.DoesNotExist:
        messages.error(request, "Role does not exist")
        return common.redirect_to_service(service)

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
        messages.info(request, "Please use the most recent request or grant")
        return common.redirect_to_service(service)

    # If the user has an active request for this chain it must be rejected
    if previous_request and previous_request.state != RequestState.REJECTED:
        messages.info(request, "You have already have an active request for the specified grant")
        return common.redirect_to_service(service)

    # ONLY FOR CEDA SERVICES: Get licence url
    licence_url = None
    if settings.LICENCE_REQUIRED:
        groups = [b for b in role.behaviours.all() if isinstance(b, Group)]
        if groups:
            group = groups[0]
            response = reqs.get(
                settings.licence_url,
                params={"group": group.name},
            )
            json_response = response.json()
            licence_url = json_response["licence"]

    # Otherwise, attempt to do something
    form_class = role.metadata_form_class
    if request.method == "POST":
        form = form_class(data=request.POST)
        if form.is_valid():
            with transaction.atomic():
                access, _ = Access.objects.get_or_create(
                    role=role,
                    user=request.user,
                )
                # If the role is set to auto accept, grant before saving
                if role.auto_accept:
                    req = Request.objects.create(
                        access=access,
                        requested_by=request.user.username,
                        state=RequestState.APPROVED,
                    )
                    req.resulting_grant = Grant.objects.create(
                        access=access,
                        granted_by="automatic",
                        expires=date.today() + relativedelta(years=1),
                    )

                    if previous_request:
                        req.previous_request = previous_request
                        req.save()

                    if previous_grant:
                        req.resulting_grant.previous_grant = previous_grant
                        req.previous_grant = previous_grant
                        req.resulting_grant.save()

                    req.save()
                    form.save(req)
                    req.copy_metadata_to(req.resulting_grant)
                else:
                    req = Request.objects.create(access=access, requested_by=request.user.username)

                    if previous_request:
                        previous_request.next_request = req
                        previous_request.save()

                    if previous_grant:
                        req.previous_grant = previous_grant

                    req.save()
                    form.save(req)
            messages.success(request, "Request submitted successfully")
            return common.redirect_to_service(service)
        else:
            messages.error(request, "Error with one or more fields")
    else:
        # Set the initial data to the metadata attached to the active request
        initial = {}
        if previous_request:
            for datum in previous_request.metadata.all():
                initial[datum.key] = datum.value
        form = form_class(initial=initial)
    templates = [
        "jasmin_services/{}/{}/{}/role_apply.html".format(
            service.category.name, service.name, role.name
        ),
        "jasmin_services/{}/{}/role_apply.html".format(service.category.name, service.name),
        "jasmin_services/{}/role_apply.html".format(service.category.name),
        "jasmin_services/role_apply.html",
    ]
    return render(
        request,
        templates,
        {
            "role": role,
            "grant": previous_grant,
            "req": previous_request,
            "form": form,
            "licence_url": licence_url,
        },
    )
