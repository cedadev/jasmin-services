"""
Module containing custom application configuration for the JASMIN metadata app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.apps import AppConfig as BaseAppConfig


class AppConfig(BaseAppConfig):
    """
    Application configuration object for the JASMIN metadata app.
    """

    name = ".".join(__name__.split(".")[:-1])
    verbose_name = "JASMIN Metadata"
