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
    class Meta:
        ordering = (
            'role__service__category__position',
            'role__service__category__long_name',
            'role__service__position',
            'role__service__name',
            'role__position',
            'role__name',
        )
        unique_together = ['role', 'user']

    #: The role that the grant is for
    role = models.ForeignKey(Role, models.CASCADE,
                             related_name = 'accesses',
                             related_query_name = 'access')
    #: The user for whom the role is granted
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE)


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
    #: Grant that superceeds this grant
    next_grant = models.OneToOneField('self', models.SET_NULL,
                                      null = True, blank = True,
                                      related_name = 'previous_grant')

    def __str__(self):
        return '{} : {}'.format(self.role, self.user)

    @property
    def active(self):
        """
        Returns ``True`` if this grant is the active grant for the
        service/role/user combination.
        """
        if not hasattr(self, '_active'):
            if self.pk:
                self._active = self.__class__.objects  \
                    .filter_active()  \
                    .filter(pk = self.pk)  \
                    .exists()
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
                    resulting_grant__is_null = True,
                    next_request__is_null = True,
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
        return self.filter(resulting_grant__is_null = True, next_request__is_null = True)


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
    #: If approved, this is the resulting access grant
    resulting_grant = models.OneToOneField(Grant, models.SET_NULL,
                                           null = True, blank = True,
                                           related_name = 'request')
    #: If approved, this is the access grant being superceeded
    previous_grant = models.OneToOneField(Grant, models.SET_NULL,
                                          null = True, blank = True,
                                          related_name = 'request')
    #: Request that superceeds this request
    next_request = models.OneToOneField('self', models.SET_NULL,
                                      null = True, blank = True,
                                      related_name = 'previous_request')
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
        return '{} : {} : {}'.format(self.role, self.user, self.state)

    @property
    def active(self):
        """
        Returns ``True`` if this request is the active request for the
        service/role/user combination.
        """
        if not hasattr(self, '_active'):
            if self.pk:
                self._active = self.__class__.objects  \
                    .filter_active()  \
                    .filter(pk = self.pk)  \
                    .exists()
            else:
                # Unsaved grants are never active
                self._active = False
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
        try:
            user = self.access.user
            # Ensure that the user is active
            if not user.is_active:
                errors['user'] = 'User is suspended'
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
