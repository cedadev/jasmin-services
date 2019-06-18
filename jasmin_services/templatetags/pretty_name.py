"""
Custom template filter wrapping ``django.forms.utils.pretty_name``.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django import template
from django.forms.utils import pretty_name


register = template.Library()

# Register a filter for each role
register.filter(pretty_name)
