import logging
from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render
from django.views.decorators.http import require_safe

from ..models import Grant
from .common import redirect_to_service, with_service

_log = logging.getLogger(__name__)


@require_safe
@login_required
@with_service
def service_users(request, service):
    """
    Handler for ``/<category>/<service>/users/``.

    Responds to GET requests only. The user must have the permission
    ``jasmin_services.view_users_role`` for at least one role in the service.

    Displays the active grants for a service. The grants that a user sees
    depends on the permissions they have been granted.
    """
    # Get the roles for the service for which the user has permission to view
    # grants. We allow the permission to be allocated for all services,
    # per-service or per-role.
    permission = "jasmin_services.view_users_role"
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
    # Start with the active grants for the roles that the user has permission for
    grants = Grant.objects.filter_active().filter(access__role__in=user_roles)
    all_statuses = ("active", "expiring", "expired", "revoked")
    # Only apply filters if _apply_filters is present in the GET params
    if "_apply_filters" in request.GET:
        # Start by getting the roles to display from the GET filters
        selected_roles = set(role for role in user_roles if role.name in request.GET)
        # Then filter by those roles
        grants = grants.filter(access__role__in=selected_roles)
        # Then get the statuses to display from the GET filters
        selected_statuses = set(status for status in all_statuses if status in request.GET)
        # Apply any filters to the grants and requests
        if "active" not in selected_statuses:
            # Make sure we don't include expiring grants in active
            grants = grants.exclude(
                revoked=False, expires__gte=date.today() + relativedelta(months=2)
            )
        if "revoked" not in selected_statuses:
            grants = grants.exclude(revoked=True)
        if "expired" not in selected_statuses:
            grants = grants.exclude(revoked=False, expires__lt=date.today())
        if "expiring" not in selected_statuses:
            grants = grants.exclude(
                revoked=False, expires__lt=date.today() + relativedelta(months=2)
            )
    else:
        # If not applying filters, check all the filter checkboxes
        selected_roles = user_roles
        selected_statuses = all_statuses
    # Order the grants by user and then by the natural ordering
    grants = grants.select_related(
        "access__role", "access__user", "access__user__institution"
    ).order_by("access__user", *Grant._meta.ordering)
    # Get a paginator for the grants
    paginator = Paginator(
        grants, getattr(settings, "JASMIN_SERVICES", {}).get("GRANTS_PER_PAGE", 20)
    )
    try:
        page = paginator.page(request.GET.get("page"))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    # Only preserve filters if they were applied
    if "_apply_filters" in request.GET:
        preserved_filters = set(r.name for r in selected_roles).union(selected_statuses)
        preserved_filters.add("_apply_filters")
    else:
        preserved_filters = set()
    templates = [
        "jasmin_services/{}/{}/service_users.html".format(service.category.name, service.name),
        "jasmin_services/{}/service_users.html".format(service.category.name),
        "jasmin_services/service_users.html",
    ]
    return render(
        request,
        templates,
        {
            "service": service,
            "statuses": tuple(dict(name=s, checked=s in selected_statuses) for s in all_statuses),
            "roles": tuple(dict(name=r.name, checked=r in selected_roles) for r in user_roles),
            "grants": page,
            "n_users": grants.values("access__user").distinct().count(),
            "preserved_filters": "&".join("{}=1".format(f) for f in preserved_filters),
        },
    )
