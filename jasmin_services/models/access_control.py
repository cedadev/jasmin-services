"""
Django models for access control in the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import inspect
from datetime import date

from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.db import models
from django.db.models.expressions import RawSQL
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from markdown_deux.templatetags.markdown_deux_tags import markdown_allowed

from jasmin_metadata.models import HasMetadata

from .base import Role


class Access(models.Model):
    """
    Represents the join model between the access(role/user pair) and grant.
    """
    id = models.AutoField(primary_key=True)

    class Meta:
        ordering = (
            'role__service__category__position',
            'role__service__category__long_name',
            'role__service__position',
            'role__service__name',
            'role__position',
            'role__name',
        )
        unique_together = ('role', 'user')
        verbose_name_plural = "accesses"

    #: The role that the grant is for
    role = models.ForeignKey(Role, models.CASCADE,
                             related_name = 'accesses',
                             related_query_name = 'access')
    #: The user for whom the role is granted
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE)

    def __str__(self):
        return '{} : {}'.format(self.role, self.user)


class GrantQuerySet(models.QuerySet):
    """
    Custom queryset that allows filtering for the 'active' grants.
    """
    def annotate_active(self):
        """
        Returns a new queryset where each grant is annotated with a boolean
        indicating whether it is 'active' or not.
        """
        return self.annotate(
            active = models.Case(
                models.When(
                    next_grant__isnull = True,
                    then = models.Value(True),
                ),
                default = models.Value(False),
                output_field = models.BooleanField()
            )
        )

    def filter_active(self):
        """
        Returns a new queryset containing only the 'active' grants from this
        queryset.
        """
        return self.filter(next_grant__isnull = True)

    def filter_access(self, role, user):
        """
        Returns a new queryset containing the grant that determines the users
        permision for the given access.
        When there are multiple grants for an access return the grant with the 
        longest expiry, if there are none expiring return the most recent 
        revocation.
        """
        grants = self.filter(access__role = role, access__user=user)
        if grants.count() > 1:
            live_grants = grants.filter(revoked = False)
            if live_grants:
                return live_grants.order_by('expires', 'granted_at').first()
            else:
                return grants.order_by('granted_at').first()
        else:
            return grants


def _default_expiry():
    return date.today() + settings.JASMIN_SERVICES['DEFAULT_EXPIRY_DELTA']


class Grant(HasMetadata):
    """
    Represents the granting of a role to a user.

    There may be many grants for each role/user combination. However, when
    determining whether a user is approved for a role, only grants the head of a
    grant chain (one without a next_grant) for the role/user combination is considered. 
    These are referred to as the 'active' grants.

    A grant can have arbitrary metadata associated with it. That metadata is
    defined by the service.
    """
    id = models.AutoField(primary_key=True)

    class Meta:
        ordering = (
            'access__role__service__category__position',
            'access__role__service__category__long_name',
            'access__role__service__position',
            'access__role__service__name',
            'access__role__position',
            'access__role__name',
            '-granted_at',
        )
        get_latest_by = 'granted_at'
        indexes = [
            models.Index(fields=['access', 'granted_at'])
        ]

    objects = GrantQuerySet.as_manager()

    #: The role/user combination that the grant is for
    access = models.ForeignKey(Access, models.CASCADE,
                               related_name = 'grants',
                               related_query_name = 'grant')
    #: Username of the user who granted the role
    granted_by = models.CharField(max_length = 200)
    #: The datetime at which the role was granted
    granted_at = models.DateTimeField(auto_now_add = True)
    #: The date that the the grant expires
    #:   * Access is assumed to expire at the **end** of the given day
    #:   * Default expiry is one year from now
    expires = models.DateField(default = _default_expiry, verbose_name = 'expiry date')
    #: Indicates whether the grant has been revoked
    #: This overrides any expiry date
    revoked = models.BooleanField(default = False)
    #: If revoked, this is a reason for the user
    user_reason = models.TextField(blank = True,
                                   verbose_name = 'Reason for revocation (user)',
                                   help_text = markdown_allowed())
    #: Optional internal reason, for sensitive details
    internal_reason = models.TextField(blank = True,
                                       verbose_name = 'Reason for revocation (internal)',
                                       help_text = markdown_allowed())
    #: Grant that this grant superceeds
    previous_grant = models.OneToOneField('self', models.SET_NULL,
                                      null = True, blank = True,
                                      related_name = 'next_grant')

    def __str__(self):
        if hasattr(self, 'next_grant'):
            return '{} : old'.format(self.access)
        else:
            return '{} : active'.format(self.access)

    @property
    def active(self):
        """
        Returns ``True`` if this grant is the active grant for the
        service/role/user combination.
        """
        if not hasattr(self, '_active'):
            if not hasattr(self, 'next_grant'):
                self._active = True
            else:
                # Unsaved grants are never active
                self._active = False
        return self._active


    @active.setter
    def active(self, value):
        self._active = value

    @property
    def expired(self):
        """
        Shortcut to check if a grant has expired.
        """
        return self.expires < date.today()

    @property
    def expiring(self):
        """
        Shortcut to check if a grant is expiring in the next 2 months.
        """
        today = date.today()
        return today <= self.expires < (today + relativedelta(months = 2))

    def clean(self):
        errors = {}
        try:
            user = self.access.user
            # Ensure that the user is active
            if not user.is_active:
                errors['user'] = 'User is suspended'
            if not settings.MULTIPLE_REQUESTS_ALLOWED:
                active_grant = Grant.objects.filter(access=self.access, next_grant__isnull = True)
                active_request = Request.objects.filter(access=self.access, resulting_grant__isnull = True, next_request__isnull = True)
                if active_grant and self.previous_grant != active_grant[0] and self != active_grant[0]:
                    errors = 'There is already an existing active grant for this access'
                if active_request:
                    errors = 'There is already an existing active request for this access'

        except ObjectDoesNotExist:
            pass
        # Ensure that at least a user reason is given if the grant is revoked
        if self.revoked and not self.user_reason:
            errors['user_reason'] = 'Please give a reason'
        # Ensure that expires is in the future
        if self.expires < date.today():
            errors['expires'] = 'Expiry date must be in the future'
        if errors:
            raise ValidationError(errors)


class RequestQuerySet(models.QuerySet):
    """
    Custom queryset that allows filtering for the 'active' requests.
    """
    def annotate_active(self):
        """
        Returns a new queryset where each request is annotated with a boolean
        indicating whether it is 'active' or not.
        """
        return self.annotate(
            active = models.Case(
                models.When(
                    resulting_grant__isnull = True,
                    next_request__isnull = True,
                    then = models.Value(True),
                ),
                default = models.Value(False),
                output_field = models.BooleanField()
            )
        )

    def filter_active(self):
        """
        Returns a new queryset containing only the 'active' requests from this
        queryset.
        """
        return self.filter(resulting_grant__isnull = True, next_request__isnull = True)

    def filter_relevant(self, role, user):
        """
        Returns a new queryset containing the most relevant request.
        When there are multiple requests for an access return the most recent
        pending request else return the most recent request.
        """
        requests = self.filter(access__role = role, access__user=user)
        if requests.count() == 1:
            return requests
        elif requests.count() > 0:
            pending_requests = requests.filter(state = RequestState.PENDING)
            if pending_requests:
                return pending_requests.order_by('requested_at').first()
            else:
                return requests.order_by('requested_at').first()
        else:
            return requests

class RequestState:
    """
    Class defining constants for the states that a request can be in.
    """
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'

    @classmethod
    def choices(cls):
        """
        Returns choices for the constants in this class that are suitable for use
        in a Django model or form field.
        """
        return [
            (value, name) for name, value in inspect.getmembers(cls)
            if not name.startswith('__') and not callable(value)
        ]

    @classmethod
    def all(cls):
        """
        Returns a list containing the constants in this class.
        """
        return [name for _, name in cls.choices()]

    @classmethod
    def model_field(cls, **kwargs):
        """
        Returns a Django model field representing one of the constants in this class.
        """
        choices = cls.choices()
        kwargs.update(
            max_length = max(len(s) for s, _ in choices),
            choices = choices
        )
        return models.CharField(**kwargs)


class Request(HasMetadata):
    """
    Represents a request to grant a user a role.

    There may be many requests for each access(role/user combination). A request
    is considered 'active' if:

      1. It is the most recent request for the role/user combination
      2. It was requested after the active grant for the role/user combination

    A can be in one of three states: PENDING, REJECTED or APPROVED. A rejected
    request will have a reason to present to the user, and an approved request
    will have an associated grant.

    A request can have arbitrary metadata associated with it. That metadata is
    defined by the service.
    """
    id = models.AutoField(primary_key=True)

    class Meta:
        ordering = (
            'access__role__service__category__position',
            'access__role__service__category__long_name',
            'access__role__service__position',
            'access__role__service__name',
            'access__role__position',
            'access__role__name',
            '-requested_at',
        )
        get_latest_by = 'requested_at'
        permissions = (('decide_request', 'Can make decisions on requests'), )

    objects = RequestQuerySet.as_manager()

    #: The role/user combination that the request is for
    access = models.ForeignKey(Access, models.CASCADE,
                               related_name = 'requests',
                               related_query_name = 'request')
    #: Username of the user who requested the role
    requested_by = models.CharField(max_length = 200)
    #: The datetime at which the service request was created
    requested_at = models.DateTimeField(auto_now_add = True)
    #: The current state of the request
    state = RequestState.model_field(default = RequestState.PENDING)
    #: True if request requires more information
    incomplete = models.BooleanField(default = False)
    #: If approved, this is the resulting access grant
    resulting_grant = models.OneToOneField(Grant, models.SET_NULL,
                                           null = True, blank = True,
                                           related_name = 'request')
    #: If approved, this is the access grant being superceeded
    previous_grant = models.ForeignKey(Grant, models.SET_NULL,
                                          null = True, blank = True,
                                          related_name = 'next_requests')
    #: Request that this request superceeds
    previous_request = models.OneToOneField('self', models.SET_NULL,
                                            null = True, blank = True,
                                            related_name = 'next_request')
    #: If rejected, this is a reason for the user
    user_reason = models.TextField(
        blank = True,
        verbose_name = 'Reason for rejection (user)',
        help_text = markdown_allowed()
    )
    #: Optional internal reason, for sensitive details
    internal_reason = models.TextField(
        blank = True,
        verbose_name = 'Reason for rejection (internal)',
        help_text = markdown_allowed()
    )

    def __str__(self):
        return '{} : {}'.format(self.access, 'INCOMPETE' if self.incomplete else self.state)

    @property
    def active(self):
        """
        Returns ``True`` if this request is the active request for the
        service/role/user combination.
        """
        if not hasattr(self, '_active'):
            if self.resulting_grant or hasattr(self, 'next_request'):
                # Unsaved requests won't have a resulting grant
                self._active = False
            else:
                self._active = True
        return self._active


    @active.setter
    def active(self, value):
        self._active = value

    @property
    def pending(self):
        """
        ``True`` if the request is in the PENDING state, ``False`` otherwise.
        """
        return self.state == RequestState.PENDING

    @property
    def approved(self):
        """
        ``True`` if the request is in the APPROVED state, ``False`` otherwise.
        """
        return self.state == RequestState.APPROVED

    @property
    def rejected(self):
        """
        ``True`` if the request is in the REJECTED state, ``False`` otherwise.
        """
        return self.state == RequestState.REJECTED

    def clean(self):
        errors = {}
        # If we are approved, we need a grant
        if self.state == RequestState.APPROVED and not self.resulting_grant:
            errors['grant'] = 'Required for state {}'.format(self.state)
        # If we have a grant, we must be approved
        if self.resulting_grant and not self.state == RequestState.APPROVED:
            errors['grant'] = 'Not allowed for state {}'.format(self.state)
        # If the state is rejected, we need a user reason
        if self.state == RequestState.REJECTED and not self.user_reason:
            errors['user_reason'] = 'Please give a reason for rejection'
        # If the request is incomplete, it must be rejected
        if self.incomplete and not self.state == RequestState.REJECTED:
            errors['state'] = 'Incomplete requests must be in the REJECTED state'
        try:
            user = self.access.user
            # Ensure that the user is active
            if not user.is_active:
                errors['user'] = 'User is suspended'
            #
            if not settings.MULTIPLE_REQUESTS_ALLOWED:
                active_grant = Grant.objects.filter(access=self.access, next_grant__isnull = True)
                active_request = Request.objects.filter(access=self.access, resulting_grant__isnull = True, next_request__isnull = True)
                if active_grant and self.previous_grant != active_grant[0]:
                    errors = 'There is already an existing active grant for this access'
                if active_request and self != active_request[0]:
                    errors = 'There is already an existing active request for this access'
        except ObjectDoesNotExist:
            pass
        # Check that the grant is for the same service/role/user combination
        if self.resulting_grant:
            try:
                if self.resulting_grant.access != self.access:
                    errors['grant'] = 'Grant must be for same access as request'
            except ObjectDoesNotExist:
                pass
        if errors:
            raise ValidationError(errors)
