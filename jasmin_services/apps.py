"""
Module containing custom application configuration for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.apps import AppConfig as BaseAppConfig
from django.db.models.signals import post_migrate


class AppConfig(BaseAppConfig):
    """
    Application configuration object for the JASMIN services app.
    """
    name = '.'.join(__name__.split('.')[:-1])
    verbose_name = 'JASMIN Services'

    def ready(self):
        from . import notifications
        # Connect the post_migrate handler that registers notification types
        # to this instance
        post_migrate.connect(notifications.register_notifications, sender = self)
