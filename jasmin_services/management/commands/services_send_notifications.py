"""
Module containing a ``django-admin`` command that will send notifications for
expiring or expired grants.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.core.management.base import BaseCommand

from ...actions import send_expiry_notifications
from ...models import Grant


class Command(BaseCommand):
    help = "Sends notifications for expiring or expired grants"

    def handle(self, *args, **kwargs):
        send_expiry_notifications(Grant.objects.all())
