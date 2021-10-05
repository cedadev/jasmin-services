"""
Module containing a ``django-admin`` command that will send notifications for
expiring or expired grants.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.core.management.base import BaseCommand

from jasmin_registration.models import Application

from ...models import Request, RequestState
from ...actions import *
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


class Command(BaseCommand):
    help = 'Ensures that users confirm their email address periodically, or their account is suspended'

    def handle(self, *args, **kwargs):
        pending_requests = Request.objects.filter(state = RequestState.PENDING).filter_active()
        applications = Application.objects.filter(decision__isnull = True)
        manager_requests = {}
        user_requests = {'length':0}
        for request in pending_requests:
            role = request.role
            if role.name == 'MANAGER':
                if role.service.category in manager_requests:
                    manager_requests[role.service.category].append(request)
                else:
                    manager_requests[role.service.category] = [request]
            elif role.service.ceda_managed or role.approvers == []:
                user_requests['length'] += 1
                if role.service.category in user_requests:
                    user_requests[role.service.category].append(request)
                else:
                    user_requests[role.service.category] = [request]
        
        if len(manager_requests) + len(user_requests) + len(applications) > 0:
            context = {
                'email' : settings.JASMIN_SUPPORT_EMAIL,
                'manager_requests': manager_requests,
                'user_requests': user_requests,
                'applications': applications,
                'url': settings.BASE_URL
            }
            content = render_to_string('jasmin_notifications/mail/pending_summary/content.txt', context)
            send_mail(
                subject = 'Current Pending Requests and Applications',
                message = content,
                from_email = settings.DEFAULT_FROM_EMAIL,
                recipient_list = [settings.JASMIN_SUPPORT_EMAIL],
                fail_silently = True
            )
