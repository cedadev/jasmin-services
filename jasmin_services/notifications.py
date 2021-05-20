"""
This module contains signals used by the JASMIN account app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import os
import logging

import requests
import re

from django.conf import settings
from django.db.models import signals
from django.dispatch import receiver
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from jasmin_notifications.models import (
    NotificationLevel,
    NotificationType,
    Notification
)

from .models import Grant, Request, RequestState


_log = logging.getLogger(__name__)


def register_notifications(app_config, verbosity = 2, interactive = True, **kwargs):
    """
    ``post_migrate`` signal handler that registers notification types for this app.
    """
    NotificationType.create(
        name = 'request_confirm',
        level = NotificationLevel.INFO,
        display = False,
    )
    NotificationType.create(
        name = 'request_pending',
        level = NotificationLevel.ATTENTION,
        # Because this was previously set to False, we need to explicitly set
        # it to True to force an update
        display = True
    )
    NotificationType.create(
        name = 'request_rejected',
        level = NotificationLevel.ERROR,
    )
    NotificationType.create(
        name = 'grant_created',
        level = NotificationLevel.SUCCESS,
    )
    NotificationType.create(
        name = 'grant_expiring',
        level = NotificationLevel.WARNING,
    )
    NotificationType.create(
        name = 'grant_expired',
        level = NotificationLevel.ERROR,
    )
    NotificationType.create(
        name = 'grant_revoked',
        level = NotificationLevel.ERROR,
    )
    NotificationType.create(
        name = 'manual_intervention_required',
        level = NotificationLevel.WARNING,
        display = False
    )


@receiver(signals.post_save, sender = Request)
def confirm_request(sender, instance, created, **kwargs):
    """
    Notifies the user that their request was received.
    """
    if created and instance.active and instance.state == RequestState.PENDING:
        instance.user.notify(
            'request_confirm',
            instance,
            reverse('jasmin_services:service_details', kwargs = {
                'category' : instance.role.service.category.name,
                'service' : instance.role.service.name,
            })
        )


def notify_approvers(instance):
    """
    Notifies potential approvers for a request to poke them into action.
    """
    if instance.active and instance.state == RequestState.PENDING:
        approvers = instance.role.approvers.exclude(pk = instance.user.pk)
        # If the role has some approvers, notify them
        if approvers:
            link = reverse(
                'jasmin_services:request_decide',
                kwargs = { 'pk' : instance.pk }
            )
            for approver in approvers:
                approver.notify('request_pending', instance, link)
        else:
            # If there are no approvers, post a message to Slack
            link = settings.BASE_URL + reverse(
                'admin:jasmin_services_request_decide',
                args = (instance.pk, )
            )
            requests.post(
                settings.SLACK_WEBHOOK,
                json = {
                    'username' : os.uname()[1],
                    'attachments' : [
                        {
                            'color' : 'warning',
                            'title' : 'Submitted request requires attention',
                            'mrkdwn_in' : ['text'],
                            'text' : f"Role has no active approvers: "
                                     f"<{link}|Review request>",
                        }
                    ],
                }
            )


@receiver(signals.post_save, sender = Request)
def notify_approvers_created(sender, instance, created, **kwargs):
    """
    Notifies potential approvers to poke them into action.
    """
    if created:
        notify_approvers(instance)


@receiver(signals.post_save, sender = Request)
def request_decided(sender, instance, created, **kwargs):
    """
    When a request is decided, clear any request_pending notifications associated with it.
    """
    if instance.state in [RequestState.APPROVED, RequestState.REJECTED]:
        Notification.objects.filter_target(instance).update(followed_at = timezone.now())


@receiver(signals.post_save, sender = Request)
def request_rejected(sender, instance, created, **kwargs):
    """
    Notifies the user when their request has been decided.
    """
    if instance.active and instance.state == RequestState.REJECTED:
        # Only send the notification once
        instance.user.notify_if_not_exists(
            'request_rejected',
            instance,
            reverse('jasmin_services:service_details', kwargs = {
                'category' : instance.role.service.category.name,
                'service' : instance.role.service.name,
            })
        )


@receiver(signals.post_save, sender = Grant)
def grant_created(sender, instance, created, **kwargs):
    """
    Notifies the user when a grant is created.
    """
    if created and instance.active and not re.match(r'train\d{3}', instance.user.username):
        instance.user.notify(
            'grant_created',
            instance,
            reverse('jasmin_services:service_details', kwargs = {
                'category' : instance.role.service.category.name,
                'service' : instance.role.service.name,
            })
        )


@receiver(signals.post_save, sender = Grant)
def grant_revoked(sender, instance, created, **kwargs):
    """
    Notifies the user when a grant is revoked. Also ensures that access is revoked.
    """
    if instance.active and instance.revoked and not re.match(r'train\d{3}', instance.user.username):
        # Only send the notification once
        instance.user.notify_if_not_exists(
            'grant_revoked',
            instance,
            reverse('jasmin_services:service_details', kwargs = {
                'category' : instance.role.service.category.name,
                'service' : instance.role.service.name,
            })
        )


@receiver(signals.post_save, sender = Grant)
def grant_sync_access(sender, instance, created, **kwargs):
    """
    Synchronises access whenever a grant is saved, if the grant is active.
    """
    if instance.active:
        if instance.revoked or instance.expired:
            instance.role.disable(instance.user)
        else:
            instance.role.enable(instance.user)


@receiver(signals.post_save, sender = get_user_model())
def account_suspended(sender, instance, created, **kwargs):
    """
    When a user account is suspended, revoke all the active grants and reject all
    the pending requests for that user.
    """
    if not instance.is_active:
        for grant in Grant.objects.filter(user = instance, revoked = False)  \
                                  .filter_active():
            grant.revoked = True
            grant.user_reason = 'Account was suspended'
            grant.save()
        for req in Request.objects.filter(user = instance, \
                                          state = RequestState.PENDING):
            req.state = RequestState.REJECTED
            req.user_reason = 'Account was suspended'
            req.save()
