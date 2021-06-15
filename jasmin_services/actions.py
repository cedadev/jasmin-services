"""
Actions for the JASMIN services app that can be run via the admin or as management
commands.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import logging
import re
from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import RequestState
from .notifications import notify_approvers


def synchronise_service_access(grant_queryset):
    """
    Ensures that the roles enabled for each service are consistent with the active
    grants, for the grants in the given queryset.
    """
    logger = logging.getLogger(__name__)
    for grant in grant_queryset.filter_active():
        try:
            if grant.revoked or grant.expired:
                grant.role.disable(grant.user)
            else:
                grant.role.enable(grant.user)
        except Exception:
            logger.exception(
                'Error synchronising access to {} for {}'.format(
                    grant.role,
                    grant.user
                )
            )


def send_expiry_notifications(grant_queryset):
    """
    Sends expiry notifications (both expired and expiring) for the active grants
    in the given queryset.
    """
    for grant in grant_queryset.filter_active():
        if grant.expired and re.match(r'train\d{3}', grant.user.username):
            grant.user.notify_if_not_exists(
                'grant_expired',
                grant,
                reverse('jasmin_services:service_details', kwargs = {
                    'category' : grant.role.service.category.name,
                    'service' : grant.role.service.name,
                })
            )
        elif grant.expiring and re.match(r'train\d{3}', grant.user.username):
            grant.user.notify_pending_deadline(
                grant.expires,
                settings.JASMIN_SERVICES['NOTIFY_EXPIRE_DELTAS'],
                'grant_expiring',
                grant,
                reverse('jasmin_services:service_details', kwargs = {
                    'category' : grant.role.service.category.name,
                    'service' : grant.role.service.name,
                })
            )


def remind_pending(request_queryset):
    """
    Sends notifications to approvers for requests that have been pending for too long.
    """
    remind_delta = getattr(settings, 'JASMIN_SERVICES', {}).get(
        'REMIND_DELTA',
        relativedelta(weeks = 1)
    )
    request_queryset = request_queryset \
        .filter(
            state = RequestState.PENDING,
            requested_at__lt = timezone.now() - remind_delta
        ) \
        .filter_active()
    for req in request_queryset:
        notify_approvers(req)
