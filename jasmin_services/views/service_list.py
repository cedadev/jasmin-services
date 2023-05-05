import logging
import urllib.parse

from django import http
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render
from django.views.decorators.http import require_safe

from ..models import Category, Grant, Request

_log = logging.getLogger(__name__)


@require_safe
@login_required
def service_list(request, category):
    """Handle ``/<category>/``.

    Responds to GET requests only. The user must be authenticated.

    Lists the available services for the given category, along with some basic info
    about the current user's access.
    """
    try:
        category = Category.objects.get(name=category)
    except Category.DoesNotExist:
        raise http.Http404("Category does not exist")
    # Get the visible categories for the user
    # A category is visible if it contains a visible service
    # We include the current category, even if it would not normally be visible
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
        .filter(
            Q(pk=category.pk) | Q(service__hidden=False) | Q(has_grant=True) | Q(has_request=True)
        )
        .distinct()
        .values_list("name", "long_name")
    )

    # Get the services in this category that are visible to the user
    # Split into two to make the database query less complex and more efficient.
    request_services = (
        category.services.annotate(
            has_request=Exists(
                Request.objects.filter(
                    access__role__service=OuterRef("pk"), access__user=request.user
                )
            ),
        )
        .filter(disabled=False)
        .filter(Q(hidden=False) | Q(has_request=True))
    )
    grant_services = (
        category.services.annotate(
            has_grant=Exists(
                Grant.objects.filter(
                    access__role__service=OuterRef("pk"), access__user=request.user
                )
            ),
        )
        .filter(disabled=False)
        .filter(Q(hidden=False) | Q(has_grant=True))
    )

    # If there is a search term, factor that in
    query = request.GET.get("query", "")
    if query:
        request_services = request_services.filter(
            Q(name__icontains=query) | Q(summary__icontains=query) | Q(description__icontains=query)
        )
        grant_services = grant_services.filter(
            Q(name__icontains=query) | Q(summary__icontains=query) | Q(description__icontains=query)
        )

    # Force execution of the services query now.
    request_services = set(request_services.distinct().prefetch_related("roles"))
    grant_services = set(grant_services.distinct().prefetch_related("roles"))

    # Combine services with requests and with grants together.
    services = list(grant_services | request_services)

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
    # Get the active grants and requests for the user, as these define the visible
    # services and categories, along with the hidden flag on the service itself
    all_grants = (
        Grant.objects.filter(access__user=request.user).filter_active().select_related("access")
    )
    all_requests = (
        Request.objects.filter(access__user=request.user).filter_active().select_related("access")
    )
    return render(
        request,
        "jasmin_services/service_list.html",
        {
            "categories": categories,
            "current_category": category,
            # services is a list of (service, roles) tuples
            # roles is a list of (role, grant or None, request or None) tuples
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
            "preserved_filters": "query={}".format(urllib.parse.quote(request.GET["query"]))
            if "query" in request.GET
            else "",
        },
    )
