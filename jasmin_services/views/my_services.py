import logging
from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render
from django.views.decorators.http import require_safe

from ..models import Category, Grant, Request, RequestState, Service

_log = logging.getLogger(__name__)


@require_safe
@login_required
def my_services(request):
    """
    Handler for ``/my_services/``.

    Responds to GET requests only. The user must be authenticated.

    Displays all of the services for which the user has an active grant or request.
    """
    # Get the visible categories for the user
    # A category is visible if it contains a visible service
    # If a service is hidden, it is visible if the user has a grant or request
    # for one of its roles
    # Because of the way the data model works, it is sufficient to check if the
    # user has ever had a request or grant for a service, rather than
    # specifically an active one - if they have at least one, then they have an
    # active one
    # Django doesn't allow EXISTS subqueries to be used in filters - they must
    # be annotated first
    categories = (
        Category.objects.annotate(
            has_grant=Exists(
                Grant.objects.filter(
                    access__role__service__category=OuterRef("pk"),
                    access__user=request.user,
                )
            ),
            has_request=Exists(
                Request.objects.filter(
                    access__role__service__category=OuterRef("pk"),
                    access__user=request.user,
                )
            ),
        )
        .filter(Q(service__hidden=False) | Q(has_grant=True) | Q(has_request=True))
        .distinct()
        .values_list("name", "long_name")
    )
    # Get the active grants and requests with the longest expiries for the user,
    # as these define the visible services and categories, along with the hidden
    # flag on the service itself
    all_grants = (
        Grant.objects.filter(access__user=request.user).filter_active().select_related("access")
    )
    all_requests = (
        Request.objects.filter(access__user=request.user).filter_active().select_related("access")
    )
    # Apply filters, making sure to maintain a reference to the full lists of
    # grants and requests
    grants = all_grants
    requests = all_requests
    # Only apply filters if _apply_filters is present in the GET params
    if "_apply_filters" in request.GET:
        # Work out if any filters were checked
        checked = {
            f
            for f in ["active", "revoked", "expired", "expiring", "rejected", "pending"]
            if f in request.GET
        }
        # Apply any filters to the grants and requests
        if "active" not in checked:
            # Make sure we don't include expiring grants in active
            grants = grants.exclude(
                revoked=False, expires__gte=date.today() + relativedelta(months=2)
            )
        if "revoked" not in checked:
            grants = grants.exclude(revoked=True)
        if "expired" not in checked:
            grants = grants.exclude(revoked=False, expires__lt=date.today())
        if "expiring" not in checked:
            grants = grants.exclude(
                revoked=False, expires__lt=date.today() + relativedelta(months=2)
            )
        if "rejected" not in checked:
            requests = requests.exclude(state=RequestState.REJECTED)
        if "pending" not in checked:
            requests = requests.exclude(state=RequestState.PENDING)
    else:
        # If not applying filters, check all the filter checkboxes
        checked = {"active", "revoked", "expired", "expiring", "rejected", "pending"}

    # Make the grants and requests queries be evaluated here.
    # This makes the following query less complex and allows a significant speedup.
    grants = list(grants.order_by("id"))
    requests = list(requests.order_by("id"))

    # Get the services that match the grants
    # Since the count for this takes as long as the query, force it to
    # a list now
    services = list(
        Service.objects.filter(disabled=False)
        .filter(Q(role__access__grant__in=grants) | Q(role__access__request__in=requests))
        .distinct()
        .prefetch_related("roles")
        .select_related("category")
    )
    # Get a paginator for the services
    paginator = Paginator(
        services, getattr(settings, "JASMIN_SERVICES", {}).get("SERVICES_PER_PAGE", 5)
    )
    try:
        page = paginator.page(request.GET.get("page"))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    # Only preserve filters if they were applied
    if "_apply_filters" in request.GET:
        preserved_filters = set(checked)
        preserved_filters.add("_apply_filters")
    else:
        preserved_filters = set()
    return render(
        request,
        "jasmin_services/my_services/service_list.html",
        {
            "categories": categories,
            # Pass a dummy 'current category'
            "current_category": {
                "name": "my_services",
                "long_name": "My Services",
            },
            # services is a list of (service, roles) tuples
            # roles is a list of (role, grant or None, request or None) tuples
            # next((g for g in all_grants if g.access.role == role), None),
            # next((r for r in all_requests if r.access.role == role), None)
            "services": [
                (
                    service,
                    [
                        (
                            role,
                            all_grants.filter_access(role, request.user),
                            all_requests.filter_relevant(role, request.user),
                        )
                        for role in service.roles.all()
                    ],
                )
                for service in page
            ],
            "page": page,
            "checked": checked,
            "preserved_filters": "&".join("{}=1".format(f) for f in preserved_filters),
        },
    )
