import datetime as dt
import functools
from datetime import date

import django.apps
import django.utils.timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import Q
from jasmin_metadata.models import Form

from .behaviours import Behaviour
from .grant import Grant
from .service import Service


class RoleQuerySet(models.QuerySet):
    """Custom queryset that allows filtering of the roles by the permissions granted."""

    def filter_permission(self, permission_name, *objs):
        """
        Returns a new queryset containing only the roles from this queryset
        that grant the given permission for one of the given objects.
        """
        app_label, codename = permission_name.split(".")
        return self.filter(
            object_permission__in=RoleObjectPermission.objects.filter(
                functools.reduce(
                    lambda q, obj: q
                    | Q(
                        permission__content_type__app_label=app_label,
                        permission__codename=codename,
                        content_type=ContentType.objects.get_for_model(obj),
                        object_pk=obj.pk,
                    ),
                    objs,
                    # This is a Q object that is always false
                    Q(pk__isnull=True),
                )
            )
        )


class Role(models.Model):
    """Model representing a role for a service."""

    id = models.AutoField(primary_key=True)

    class Meta:
        ordering = (
            "service__category__position",
            "service__category__long_name",
            "service__position",
            "service__name",
            "position",
            "name",
        )
        unique_together = ("service", "name")
        permissions = (
            ("view_users_role", "Can view users with role"),
            ("send_message_role", "Can send messages to users with role"),
        )

    objects = RoleQuerySet.as_manager()

    #: The service that the role is for.
    service = models.ForeignKey(
        Service, models.CASCADE, related_name="roles", related_query_name="role"
    )
    #: The name of the role.
    name = models.CharField(max_length=50, verbose_name="role name")
    #: A brief description of the role.
    description = models.CharField(max_length=250, blank=True)
    #: Indicates if the role should be hidden by default
    hidden = models.BooleanField(
        default=True,
        help_text="Prevents the role appearing in listings unless the user "
        "has an active grant or request for it.",
    )
    auto_accept = models.BooleanField(
        default=False,
        help_text="Auto accepts all requested access giving users with a 1 "
        "year experation date ",
    )
    #: Determines the order that the roles appear when listed.
    position = models.PositiveIntegerField(
        default=9999,
        help_text="Number defining where the role appears in listings. "
        "Roles are ordered first by their service, then in "
        "ascending order by this field, then alphabetically.",
    )
    #: The form to use for collecting metadata for requests for the role.
    metadata_form = models.ForeignKey(Form, models.CASCADE, related_name="+")
    #: The behaviours associated with the user.
    behaviours = models.ManyToManyField(Behaviour, related_name="roles", related_query_name="role")

    def __str__(self):
        return f"{self.service.category.long_name} : {self.service.name} : {self.name}"

    @property
    def metadata_form_class(self):
        """
        Form class used for collecting metadata for use when approving access.

        The returned form class should extend ``jasmin_metadata.forms.MetadataForm``.

        By default, the form for each role is completely user configurable.
        However, if a service type requires particular information for approval,
        this method can be overridden to insert required fields into the form.
        """
        return self.metadata_form.get_form()

    @property
    def approvers(self):
        """Return a query for the users who can approve requests for this role."""
        # The approvers for a role are all the users who have the decide_request
        # permission for the role
        # It isn't practical to loop through all users and run user.has_perm
        # for each (as that would result in *many* SQL queries)
        # So we assume that we only want to worry about permissions that are
        # assigned through the role/grant system
        # This has the nice corollary that permissions can be allocated to staff
        # through the regular Django system without them being considered as
        # approvers, and so they do not receive notifications or show up in the
        # user interface

        return (
            get_user_model()
            .objects.filter(
                access__grant__in=Grant.objects.filter(
                    access__role__in=Role.objects.filter_permission(
                        "jasmin_services.decide_request", self.service, self
                    ),
                    revoked=False,
                    expires__gte=date.today(),
                ).filter_active()
            )
            .distinct()
        )

    def user_may_apply(self, user):
        """Return true if user is allowed to apply for this role."""
        # If multiple requests are allowed, they are always allowed to apply.
        if settings.MULTIPLE_REQUESTS_ALLOWED:
            return True
        # Otherwise get the valid (and not expiring soon) grants and requests the user has.
        # If they have any, they are not allowed to apply.
        valid_grants_requests = self.accesses.filter(user=user).filter(
            Q(
                Q(grant__revoked=False)  # Valid grants are not revoked.
                & Q(grant__expires__gt=(django.utils.timezone.localdate() + dt.timedelta(days=60)))
            )
            | Q(request__state="PENDING")
            | Q(request__incomplete=True)
        )
        return not valid_grants_requests.exists()

    def enable(self, user):
        """Enable this role for the given user."""
        # During an import, disable all behaviours
        if getattr(settings, "IS_CEDA_IMPORT", False):
            return
        # Only apply behaviours for migrated users
        # If there is no MIGRATED_USERS setting, then assume all users are migrated
        if user.username not in getattr(settings, "MIGRATED_USERS", [user.username]):
            return
        # Apply the behaviours
        for behaviour in self.behaviours.all():
            behaviour.apply(user, self)

    def disable(self, user):
        """Disable this role for the given user."""
        # During an import, disable all behaviours
        if getattr(settings, "IS_CEDA_IMPORT", False):
            return
        # Only unapply behaviours for migrated users
        # If there is no MIGRATED_USERS setting, then assume all users are migrated
        if user.username not in getattr(settings, "MIGRATED_USERS", [user.username]):
            return
        for behaviour in self.behaviours.all():
            # Before unapplying the behaviour, check if it should still be applied
            # because of another service
            #
            # Find all the grants that are:
            #   * Related to this behaviour via the role
            #   * For the same user
            #   * Active and not revoked or expired

            grants = Grant.objects.filter(
                access__role__behaviours=behaviour,
                access__user=user,
                revoked=False,
                expires__gte=date.today(),
            ).filter_active()
            if not grants.exists():
                behaviour.unapply(user, self)


class RoleObjectPermission(models.Model):
    """
    Model mapping a role to a permission on an object.

    These records are consumed by :class:`.backend.RolePermissionsBackend`.
    """

    id = models.AutoField(primary_key=True)

    class Meta:
        unique_together = ("role", "permission", "content_type", "object_pk")

    #: The role that the permission is granted by
    role = models.ForeignKey(
        Role,
        models.CASCADE,
        related_name="object_permissions",
        related_query_name="object_permission",
    )
    #: The permission to grant
    permission = models.ForeignKey(Permission, models.CASCADE)
    #: Content type of the object the permission is granted for
    content_type = models.ForeignKey(
        ContentType,
        models.CASCADE,
        verbose_name="Object content type",
        help_text="Content type of the object to which the permission applies.",
    )
    #: Primary key of the object the permission is granted for
    object_pk = models.CharField(
        max_length=150,
        verbose_name="Object primary key",
        help_text="Primary key of the object to which the permission applies.",
    )
    #: The object the permission is granted for
    content_object = GenericForeignKey("content_type", "object_pk")

    def __str__(self):
        return "{}.{} for {}.{}<{}>".format(
            self.permission.content_type.app_label,
            self.permission.codename,
            self.content_type.app_label,
            self.content_type.model,
            self.content_object,
        )

    def clean(self):
        # Make sure the selected object exists
        if self.content_type and self.object_pk:
            try:
                _ = self.content_type.get_object_for_this_type(pk=self.object_pk)
            except ObjectDoesNotExist:
                raise ValidationError({"object_pk": "Invalid primary key for content type."})
