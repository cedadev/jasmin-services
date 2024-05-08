import logging
from datetime import date

import django.contrib.auth
import django.db
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from ..forms import grant_form_factory
from ..models import Access, Grant, Role
from .common import redirect_to_service, with_service

_log = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
@login_required
@django.db.transaction.atomic
@with_service
def grant_role(request, service):
    """Handle ``/<category>/<service>/grant/``.

    Responds to GET and POST. The user must have the permission
    ``decide_request`` for at least one role in the service.

    Allows the user to create grants without a request. The roles that a user sees
    depends on the permissions they have been granted.
    """
    # Get the roles for which the user is allowed to decide requests
    # We allow the permission to be allocated for all services, per-service or per-role
    permission = "jasmin_services.grant_role"
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

    GrantForm = grant_form_factory(user_roles)
    if request.method == "POST":
        form = GrantForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Error with one or more fields")
        elif form.cleaned_data["username"] == request.user.username:
            messages.error(request, "You cannot grant a role to yourself.")
        else:
            username = form.cleaned_data["username"]
            role_id = form.cleaned_data["role"]
            expires = form.cleaned_data["expires"]
            if expires == 1:
                expires_date = date.today() + relativedelta(months=6)
            elif expires == 2:
                expires_date = date.today() + relativedelta(years=1)
            elif expires == 3:
                expires_date = date.today() + relativedelta(years=2)
            elif expires == 4:
                expires_date = date.today() + relativedelta(years=3)
            elif expires == 5:
                expires_date = date.today() + relativedelta(years=5)
            elif expires == 6:
                expires_date = date.today() + relativedelta(years=10)
            else:
                expires_date = form.cleaned_data["expires_custom"]

            user = django.contrib.auth.get_user_model().objects.get(username=username)
            role = Role.objects.get(id=role_id)
            access, _ = Access.objects.get_or_create(user=user, role=role)

            existing_grant = Grant.objects.filter(
                access=access,
            ).filter_active()

            new_grant = Grant(
                access=access,
                granted_by=request.user.username,
                expires=expires_date,
            )

            if len(existing_grant) > 0:
                new_grant.previous_grant = existing_grant[0]

            new_grant.save()
            messages.success(request, f"{access.role.name} granted to {username}")
            return redirect_to_service(service, view_name="service_users")
    else:
        form = GrantForm()
    templates = [
        f"jasmin_services/{service.category.name}/{service.name}/service_grant.html",
        f"jasmin_services/{service.category.name}/service_grant.html",
        "jasmin_services/service_grant.html",
    ]
    return render(
        request,
        templates,
        {
            "service": service,
            "form": form,
        },
    )
