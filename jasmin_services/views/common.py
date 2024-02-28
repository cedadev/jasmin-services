"""Common functions for jasmin_services views."""

import functools
import logging

from django import http
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect

from ..models import Service

_log = logging.getLogger(__name__)


def with_service(view):
    """Take a service type and service name and turns them into a service for the underlying view.

    If the service is not a valid service, a 404 is raised.
    """

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            kwargs["service"] = Service.objects.get(
                category__name=kwargs.pop("category"), name=kwargs.pop("service")
            )
        except ObjectDoesNotExist as err:
            raise http.Http404("Service does not exist.") from err
        if kwargs["service"].disabled:
            raise http.Http404("Service has been retired.")
        return view(*args, **kwargs)

    return wrapper


def redirect_to_service(service, view_name="service_details"):
    """Return a redirect response to the given service on the service list page."""
    return redirect(
        f"jasmin_services:{view_name}",
        category=service.category.name,
        service=service.name,
    )


def user_may_apply(user, service: Service) -> tuple[bool, str]:
    """Return wether a user is permitted to apply for a service."""
    # Check if the user's institution country matches the country requirements of the service.
    if (
        service.institution_countries
        and user.institution.country not in service.institution_countries
    ):
        return (
            False,
            "Your institution is not on the list of allowed institutions for this service.",
        )
    return (True, "")
