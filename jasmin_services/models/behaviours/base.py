"""Base behaiviour from which others inherit."""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import django.db.models
from polymorphic.models import PolymorphicModel


class Behaviour(PolymorphicModel):
    """Model defining a behaviour configuration."""

    id = django.db.models.AutoField(primary_key=True)

    def apply(self, user, role):
        """Apply the behaviour for the given user."""
        raise NotImplementedError

    def unapply(self, user, role):
        """Un-apply the behaviour for the given user."""
        raise NotImplementedError
