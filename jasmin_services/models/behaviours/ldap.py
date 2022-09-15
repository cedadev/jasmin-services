"""Behavious to apply changes to LDAP."""
import sys

import django.conf
import django.core.exceptions
import django.core.validators
import django.db.models
import jasmin_ldap_django.models

from .base import Behaviour


class LdapTagBehaviour(Behaviour):
    """Behaviour for applying an LDAP tag to a user's account."""

    class Meta:
        verbose_name = "LDAP Tag Behaviour"

    tag = django.db.models.CharField(
        unique=True,
        max_length=100,
        verbose_name="LDAP Tag",
        validators=[django.core.validators.RegexValidator(regex="^[a-zA-Z0-9_:-]+$")],
    )

    def apply(self, user, _role):
        account = user.account
        if self.tag not in account.tags:
            account.tags.append(self.tag)
            account.save()

    def unapply(self, user, _role):
        account = user.account
        if self.tag in account.tags:
            account.tags = [t for t in account.tags if t != self.tag]
            account.save()

    def __str__(self):
        return f"LDAP Tag <{self.tag}>"


class Group(jasmin_ldap_django.models.LDAPModel):
    """Abstract base class for a posixGroup in LDAP."""

    class GidAllocationFailed(RuntimeError):
        """Raised when a gid allocation fails."""

    class Meta(jasmin_ldap_django.models.LDAPModel.Meta):
        abstract = True
        ordering = ["name"]

    object_classes = ["top", "posixGroup"]
    search_classes = ["posixGroup"]

    # User visible fields
    name = jasmin_ldap_django.models.CharField(
        db_column="cn",
        primary_key=True,
        max_length=50,
        validators=[
            django.core.validators.RegexValidator(
                regex="^[a-zA-Z]",
                message="Name must start with a letter.",
            ),
            django.core.validators.RegexValidator(
                regex="[a-zA-Z0-9]$",
                message="Name must end with a letter or number.",
            ),
            django.core.validators.RegexValidator(
                regex="^[a-zA-Z0-9_-]+$",
                message="Name must contain letters, numbers, _ and -.",
            ),
        ],
        error_messages={
            "unique": "Name is already in use.",
            "max_length": "Name must have at most %(limit_value)d characters.",
        },
    )
    description = jasmin_ldap_django.models.TextField(
        db_column="description", blank=True
    )
    member_uids = jasmin_ldap_django.models.ListField(db_column="memberUid", blank=True)

    # blank = True is set here for the field validation, but a blank gidNumber is
    # not allowed by the save method
    gidNumber = jasmin_ldap_django.models.PositiveIntegerField(unique=True, blank=True)

    def __str__(self):
        return f"cn={self.name},{self.base_dn}"

    def save(self, *args, **kwargs):
        # If there is no gidNumber, try to allocate one
        if self.gidNumber is None:
            # Get the max gidNumber in our allowed range that is currently in use
            max_gid = (
                self.__class__.objects.filter(gidNumber__isnull=False)
                .filter(gidNumber__lt=self.gid_number_max)
                .aggregate(max_gid=django.db.models.Max("gidNumber"))
                .get("max_gid")
            )
            if max_gid is not None:
                # Use the next gidNumber, but make sure we are in the current range
                next_gid = max(max_gid + 1, self.gid_number_min)
            else:
                # If there is no max, then this is the first record with a gidNumber
                # so use the minimum
                next_gid = self.gid_number_min
            # If we were unable to allocate a gid in the range, report it
            # We use a non-field error in case the gidNumber field is not being
            # displayed
            if next_gid >= self.gid_number_max:
                raise self.GidAllocationFailed()
            self.gidNumber = next_gid
        return super().save(*args, **kwargs)


class LdapGroupBehaviour(Behaviour):
    """Behaviour for adding a user to an LDAP group."""

    class Meta:
        verbose_name = "LDAP Group Behaviour"

    ldap_model = django.db.models.CharField(
        max_length=100,
        verbose_name="LDAP model",
        help_text="The LDAP group model to use.",
    )
    group_name = django.db.models.CharField(
        max_length=100,
        verbose_name="LDAP group name",
        help_text="The name of the LDAP group to use.",
    )

    def clean(self):
        # LDAP model must be a valid MODEL_NAME for a group in settings
        if self.ldap_model:
            try:
                _ = self.get_group_model()
            except AttributeError:
                raise django.core.exceptions.ValidationError(
                    {"ldap_model": "Not a valid LDAP model."}
                )
        # Group name must be a valid group for the selected model
        if self.ldap_model and self.group_name:
            try:
                _ = self.get_ldap_group()
            except django.core.exceptions.ObjectDoesNotExist:
                raise django.core.exceptions.ValidationError(
                    {"group_name": "Not a valid group name for selected LDAP model."}
                )
            # ldap_model and group_name are unique-together, but with a case-insensitive name
            q = self.__class__.objects.filter(
                ldap_model=self.ldap_model, group_name__iexact=self.group_name
            )
            if self.pk:
                q = q.exclude(pk=self.pk)
            if q.exists():
                raise django.core.exceptions.ValidationError(
                    "LDAP Group Behaviour already exists with this LDAP model and LDAP group name."
                )

    def get_group_model(self):
        return getattr(sys.modules[__name__], self.ldap_model)

    def get_ldap_group(self):
        return self.get_group_model().objects.get(name=self.group_name)

    def apply(self, user, _role):
        group = self.get_ldap_group()
        if user.username not in group.member_uids:
            group.member_uids.append(user.username)
            group.save()

    def unapply(self, user, _role):
        group = self.get_ldap_group()
        if user.username in group.member_uids:
            group.member_uids = [m for m in group.member_uids if m != user.username]
            group.save()

    def __str__(self):
        try:
            base_dn = self.get_group_model().base_dn
        except AttributeError:
            base_dn = self.ldap_model
        return f"LDAP Group <cn={self.group_name},{base_dn}>"
