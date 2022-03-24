"""
Service-related Django models for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import functools
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.urls import reverse_lazy
from django.utils.html import mark_safe
from django_countries.fields import CountryField
from jasmin_metadata.models import Form

from .behaviours import Behaviour


class Category(models.Model):
    """
    Model representing a category of services, i.e. a grouping of related services.
    """

    id = models.AutoField(primary_key=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ("position", "long_name")
        indexes = [models.Index(fields=["position", "long_name"])]

    #: A short name for the category
    name = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Short name for the category, used in URLs",
    )
    #: A human readable name for the category
    long_name = models.CharField(
        max_length=250, help_text="Long name for the category, used for display"
    )
    #: Defines the order that the categories appear
    position = models.PositiveIntegerField(
        default=9999,
        help_text="Number defining where the category appears in listings. "
        "Categories are ordered in ascending order by this field, "
        "then alphabetically by name within that.",
    )

    def __str__(self):
        return self.long_name


class Service(models.Model):
    """
    Model representing a service.
    """

    id = models.AutoField(primary_key=True)

    class Meta:
        unique_together = ("category", "name")
        ordering = ("category__position", "category__long_name", "position", "name")
        indexes = [models.Index(fields=["position", "name"])]

    @property
    def details_link(self):

        details_url = reverse_lazy(
            "jasmin_services:service_details",
            kwargs={"category": self.category.name, "service": self.name},
        )

        anchor = f'<a href="{details_url}">Details</a>'
        return mark_safe(anchor)

    #: The category that the service belongs to
    category = models.ForeignKey(
        Category, models.CASCADE, related_name="services", related_query_name="service"
    )
    #: The name of the service
    name = models.SlugField(
        max_length=50, help_text="The name of the service. This is also used in URLs."
    )
    #: A brief description of the service, shown in listings
    summary = models.TextField(
        help_text="One-line description of the service, shown in listings. "
        "No special formatting allowed."
    )
    #: A full description of the service, show on the details page
    description = models.TextField(
        blank=True,
        null=True,
        default="",
        help_text="Full description of the service, shown on the details page. "
        "Markdown formatting is allowed.",
    )
    #: Additional text to send to approvers of the service
    approver_message = models.TextField(
        blank=True,
        null=True,
        default="",
        help_text="Service specific instructions to be added to the external "
        "approver message.",
    )
    #: Countries a users institution must be from to gain access
    instution_countries = CountryField(
        multiple=True,
        blank=True,
        help_text="Coutries a user's institute must be located to begin "
        "approval. Hold ctrl or cmd for mac to select multiple "
        "countries. Leave blank for any country.",
    )
    #: Indicates if the service should be shown in listings
    hidden = models.BooleanField(
        default=True,
        help_text="Prevents the service appearing in listings unless the user "
        "has an active grant or request for it. "
        "The service details page will still be accessible to anybody "
        "who knows the URL.",
    )
    #: Defines the order that the services appear
    position = models.PositiveIntegerField(
        default=9999,
        help_text="Number defining where the service appears in listings. "
        "Services are ordered in ascending order by category, then by "
        "this field, then alphabetically by name.",
    )
    #: Indicates if the service is managed by CEDA
    ceda_managed = models.BooleanField(
        default=False, help_text="Whether the service is managed by CEDA."
    )

    def __str__(self):
        return "{} : {}".format(self.category, self.name)


class RoleQuerySet(models.QuerySet):
    """
    Custom queryset that allows filtering of the roles by the permissions they
    grant.
    """

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
                    | models.Q(
                        permission__content_type__app_label=app_label,
                        permission__codename=codename,
                        content_type=ContentType.objects.get_for_model(obj),
                        object_pk=obj.pk,
                    ),
                    objs,
                    # This is a Q object that is always false
                    models.Q(pk__isnull=True),
                )
            )
        )


class Role(models.Model):
    """
    Model representing a role for a service.
    """

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
    behaviours = models.ManyToManyField(
        Behaviour, related_name="roles", related_query_name="role"
    )

    def __str__(self):
        return "{} : {} : {}".format(
            self.service.category.long_name, self.service.name, self.name
        )

    @property
    def metadata_form_class(self):
        """
        The form class used for collecting metadata for use when approving
        access. The returned form class should extend
        ``jasmin_metadata.forms.MetadataForm``.

        By default, the form for each role is completely user configurable.
        However, if a service type requires particular information for approval,
        this method can be overridden to insert required fields into the form.
        """
        return self.metadata_form.get_form()

    @property
    def approvers(self):
        """
        Returns a query for the users who can approve requests for this role.
        """
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
        from .access_control import Grant

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

    def enable(self, user):
        """
        Enables this role for the given user.
        """
        # During an import, disable all behaviours
        if getattr(settings, "IS_CEDA_IMPORT", False):
            return
        # Only apply behaviours for migrated users
        # If there is no MIGRATED_USERS setting, then assume all users are migrated
        if user.username not in getattr(settings, "MIGRATED_USERS", [user.username]):
            return
        # Apply the behaviours
        for behaviour in self.behaviours.all():
            behaviour.apply(user)

    def disable(self, user):
        """
        Disables this role for the given user.
        """
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
            from .access_control import Grant

            grants = Grant.objects.filter(
                access__role__behaviours=behaviour,
                access__user=user,
                revoked=False,
                expires__gte=date.today(),
            ).filter_active()
            if not grants.exists():
                behaviour.unapply(user)


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
                raise ValidationError(
                    {"object_pk": "Invalid primary key for content type."}
                )
