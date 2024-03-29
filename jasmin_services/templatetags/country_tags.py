"""
Custom template filters for inspecting a user's roles for a service.
"""

__author__ = "Rhys Evans"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django import template

register = template.Library()


@register.simple_tag
def get_country(user):
    return user.institution.country
