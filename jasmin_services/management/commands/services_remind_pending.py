"""
Module containing a ``django-admin`` command that will send notifications reminding
approvers about pending requests.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.core.management.base import BaseCommand

from ...actions import remind_pending
from ...models import Request


class Command(BaseCommand):
    help = 'Sends reminders to approvers for all requests that have been pending '
           'for too long'

    def handle(self, *args, **kwargs):
        remind_pending(Request.objects.all())
