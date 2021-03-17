"""
Module containing a ``django-admin`` command that will send notifications for
expiring or expired grants.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.core.management.base import BaseCommand, CommandError

from jasmin_auth.models import JASMINUser
from jasmin_registration.models import Application

from ...models import Request, RequestState
from ...actions import *
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


class Command(BaseCommand):
    help = 'Ensures that users confirm their email address periodically, or their account is suspended'

    def handle(self, *args, **kwargs):
        pending_requests = Request.objects.filter(state = RequestState.PENDING)
        applications = Application.objects.filter(decision__isnull = True)
        manager_requests = []
        no_app_requests = []
        ceda_requests = []
        for request in pending_requests:
            role = request.role
            if role.name == 'MANAGER':
                manager_requests.append(request)
            elif role.approvers == []:
                no_app_requests.append(request)
            elif role.service.ceda_managed:
                ceda_requests.append(request)

        context = {
            'email' : 'support@jasmin.ac.uk',
            'manager_requests': manager_requests,
            'no_app_requests': no_app_requests,
            'ceda_requests': ceda_requests,
            'applications': applications,
            'url': 'https://accounts.jasmin.ac.uk'
        }
        content = render_to_string('jasmin_notifications/mail/pending_summary/content.txt', context)
        send_mail(
            subject = 'Current Pending Requests and Applications',
            message = content,
            from_email = settings.DEFAULT_FROM_EMAIL,
            recipient_list = ['support@jasmin.ac.uk'],
            fail_silently = True
        )
