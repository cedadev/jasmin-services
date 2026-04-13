"""Base behaiviour from which others inherit."""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import django.db.models
from polymorphic.models import PolymorphicModel


class Behaviour(PolymorphicModel):
    """Model defining a behaviour configuration."""

    id = django.db.models.AutoField(primary_key=True)

    def active_grant_filter(self, role):
        """Return extra filter kwargs used by Role.disable() to check for active grants.

        By default, grants are checked across all roles sharing this behaviour. Override
        to restrict the check to a narrower scope (e.g. a specific service).
        """
        return {}

    def apply(self, user, role):
        """Apply the behaviour for the given user."""
        raise NotImplementedError

    def unapply(self, user, role):
        """Un-apply the behaviour for the given user."""
        raise NotImplementedError
