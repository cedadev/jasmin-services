from datetime import date

import django.db.models.signals
import django.dispatch
import django.utils.timezone
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from markdown_deux.templatetags.markdown_deux_tags import markdown_allowed

import jasmin_services.models
from jasmin_metadata.models import HasMetadata


class GrantQuerySet(models.QuerySet):
    """Custom queryset that allows filtering for the 'active' grants."""

    def annotate_active(self):
        """
        Return a new queryset where each grant is annotated with a
        boolean indicating whether it is 'active' or not.
        """
        return self.annotate(
            active=models.Case(
                models.When(
                    next_grant__isnull=True,
                    then=models.Value(True),
                ),
                default=models.Value(False),
                output_field=models.BooleanField(),
            )
        )

    def filter_active(self):
        """
        Returns a new queryset containing only the 'active' grants from this
        queryset.
        """
        return self.filter(next_grant__isnull=True)

    def filter_access(self, role, user):
        """
        Returns a new queryset containing the grant that determines the users
        permision for the given access.
        When there are multiple grants for an access return the grant with the
        longest expiry, if there are none expiring return the most recent
        revocation.
        """
        grants = self.filter(access__role=role, access__user=user)
        if grants.count() > 1:
            live_grants = grants.filter(revoked=False)
            if live_grants:
                return live_grants.order_by("expires", "granted_at").first()
            else:
                return grants.order_by("granted_at").first()
        else:
            return grants


def _default_expiry():
    return date.today() + settings.JASMIN_SERVICES["DEFAULT_EXPIRY_DELTA"]


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
            "access__role__service__category__position",
            "access__role__service__category__long_name",
            "access__role__service__position",
            "access__role__service__name",
            "access__role__position",
            "access__role__name",
            "-granted_at",
        )
        get_latest_by = "granted_at"
        indexes = [models.Index(fields=["access", "granted_at"])]

    objects = GrantQuerySet.as_manager()

    #: The role/user combination that the grant is for
    access = models.ForeignKey(
        "Access", models.CASCADE, related_name="grants", related_query_name="grant"
    )
    #: Username of the user who granted the role
    granted_by = models.CharField(max_length=200)
    #: The datetime at which the role was granted
    granted_at = models.DateTimeField(auto_now_add=True)
    #: The date that the the grant expires
    #:   * Access is assumed to expire at the **end** of the given day
    #:   * Default expiry is one year from now
    expires = models.DateField(default=_default_expiry, verbose_name="expiry date")

    # Indicates whether the grant has been revoked
    # This overrides any expiry date
    revoked = models.BooleanField(default=False)
    # Date at which this grant was revoked.
    revoked_at = models.DateTimeField(
        default=None,
        null=True,
        blank=True,
        help_text="Date on which this grant was revoked.",
    )

    #: If revoked, this is a reason for the user
    user_reason = models.TextField(
        blank=True,
        verbose_name="Reason for revocation (user)",
        help_text=markdown_allowed(),
    )
    #: Optional internal reason, for sensitive details
    internal_reason = models.TextField(
        blank=True,
        verbose_name="Reason for revocation (internal)",
        help_text=markdown_allowed(),
    )
    #: Grant that this grant superceeds
    previous_grant = models.OneToOneField(
        "self", models.SET_NULL, null=True, blank=True, related_name="next_grant"
    )

    @property
    def user(self):
        return self.access.user

    def __str__(self):
        if hasattr(self, "next_grant"):
            return "{} : old".format(self.access)
        else:
            return "{} : active".format(self.access)

    @property
    def active(self):
        """
        Returns ``True`` if this grant is the active grant for the
        service/role/user combination.
        """
        if not hasattr(self, "_active"):
            if not hasattr(self, "next_grant"):
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
        return today <= self.expires < (today + relativedelta(months=2))

    @property
    def status(self):
        """Shortcut to get the status of this grant."""
        if self.revoked:
            status = "REVOKED"
        elif self.expired:
            status = "EXPIRED"
        elif self.expiring:
            status = "EXPIRING"
        else:
            status = "ACTIVE"
        return status

    def clean(self):
        errors = {}
        try:
            user = self.access.user
            # Ensure that the user is active
            if not user.is_active:
                errors["user"] = "User is suspended"
            if not settings.MULTIPLE_REQUESTS_ALLOWED:
                active_grant = Grant.objects.filter(access=self.access, next_grant__isnull=True)
                active_request = jasmin_services.models.Request.objects.filter(
                    access=self.access,
                    resulting_grant__isnull=True,
                    next_request__isnull=True,
                )
                if (
                    self.active
                    and active_grant
                    and self.previous_grant != active_grant[0]
                    and self != active_grant[0]
                ):
                    errors = "There is already an existing active grant for this access"
                if self.active and active_request:
                    errors = "There is already an existing active request for this access"

        except ObjectDoesNotExist:
            pass
        # Ensure that at least a user reason is given if the grant is revoked
        if self.revoked and not self.user_reason:
            errors["user_reason"] = "Please give a reason"
        # Ensure that expires is in the future
        if self.expires < date.today():
            errors["expires"] = "Expiry date must be in the future"
        if errors:
            raise ValidationError(errors)


@django.dispatch.receiver(django.db.models.signals.pre_save, sender=Grant)
def populate_revoked_at(sender, instance, **kwargs):
    """Populate revoked_at timestamp when a grant is revoked."""
    if (not instance.revoked) and instance.revoked_at:
        instance.revoked_at = None
    elif instance.revoked and (instance.revoked_at is None):
        instance.revoked_at = django.utils.timezone.now()
