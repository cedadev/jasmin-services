"""
Module containing a ``django-admin`` command that will ensure that actual service
access is consistent with the active grants.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from datetime import date

from django.core.management.base import BaseCommand

from ...actions import synchronise_service_access
from ...models import Grant


class Command(BaseCommand):
    help = "Ensures that any access that should be disabled is definitely disabled"

    def handle(self, *args, **kwargs):
        # For the cron, we only consider grants where access should be disabled
        synchronise_service_access(
            Grant.objects.exclude(revoked=False, expires__gte=date.today())
        )
