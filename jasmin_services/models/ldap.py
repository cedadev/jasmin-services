"""Model to use LDAP groups."""
import django.core.validators
import django.db.models
import jasmin_ldap_django.models


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
    description = jasmin_ldap_django.models.TextField(db_column="description", blank=True)
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
