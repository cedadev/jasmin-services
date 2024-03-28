"""
Custom template filters for inspecting a user's roles for a service.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import itertools
import random
import string

import django.conf
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
def display_accesses(accesses):
    """Template tag to display a list of accesses (requests and or grants)."""
    return {"accesses": accesses}
