"""
Custom template filters for inspecting a user's roles for a service.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import itertools
import random
import string

import django.urls
from django import template

from ..models import Request, RequestState

register = template.Library()


@register.simple_tag
def user_has_service_perm(service, user, perm):
    return (
        user.has_perm(perm)
        or user.has_perm(perm, service)
        or any(user.has_perm(perm, role) for role in service.roles.all())
    )


@register.simple_tag(takes_context=True)
def pending_req_count(context, service):
    # Find the role that the user in the context has permission to decide
    permission = "jasmin_services.decide_request"
    if context["user"].has_perm(permission) or context["user"].has_perm(permission, service):
        user_roles = list(service.roles.all())
    else:
        user_roles = [
            role for role in service.roles.all() if context["user"].has_perm(permission, role)
        ]
    return (
        Request.objects.filter_active()
        .filter(access__role__in=user_roles, state=RequestState.PENDING)
        .count()
    )


@register.inclusion_tag("jasmin_services/includes/display_accesses.html")
def display_accesses(*all_accesses):
    """Process a list of either requests or grants for display."""

    accesses = list(itertools.chain.from_iterable(all_accesses))

    # This ID is used to create CSS ids. Must be unique per access.
    id_part = "".join(random.choice(string.ascii_lowercase) for i in range(5))
    id_ = 0
    # We loop through the list, and add some information which is not otherwise available.
    for access in accesses:
        print(access)
        access.frontend = {
            "start": (access.requested_at if isinstance(access, Request) else access.granted_at),
            "id": f"{id_part}_{id_}",
            "type": ("REQUEST" if isinstance(access, Request) else "GRANT"),
            "apply_url": django.urls.reverse(
                "jasmin_services:role_apply",
                kwargs={
                    "category": access.access.role.service.category.name,
                    "service": access.access.role.service.name,
                    "role": access.access.role.name,
                    "bool_grant": 0 if isinstance(access, Request) else 1,
                    "previous": access.id,
                },
            ),
        }
        id_ += 1

    accesses = sorted(accesses, key=lambda x: x.frontend["start"])

    return {"accesses": accesses}
