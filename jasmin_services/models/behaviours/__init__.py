"""Module defining specific category implementations."""

import logging
import sys

import django.conf

from .base import Behaviour  # unimport:skip
from .mail import JoinJISCMailListBehaviour  # unimport:skip

__all__ = []
logger = logging.getLogger(__name__)

# Keycloak behaviour is only available if the keycloak optional dependency is installed.
try:
    from .keycloak import KeycloakAttributeBehaviour
except ImportError:
    logger.warning("Keycloak Behaviour is not enabled. Install optional dependencies to activate.")
else:
    __all__ += ["KeycloakAttributeBehaviour"]

__all__ += [
    "Behaviour",
    "JoinJISCMailListBehaviour",
]

# LDAP behaviour is only available if the jamsin-ldap optional dependency is installed.
try:
    from .ldap import Group, LdapGroupBehaviour, LdapTagBehaviour  # unimport:skip
except ImportError:
    logger.warning("LDAP Behaviour is not enabled. Install optional dependencies to activate.")
else:
    __all__ += [
        "LdapTagBehaviour",
        "Group",
        "LdapGroupBehaviour",
    ]

    # Concrete models for the LDAP groups as defined in settings
    this_module = sys.modules[__name__]
    for grp in django.conf.settings.JASMIN_SERVICES["LDAP_GROUPS"]:
        __all__.append(grp["MODEL_NAME"])
        setattr(
            this_module,
            grp["MODEL_NAME"],
            type(
                grp["MODEL_NAME"],
                (Group,),
                {
                    "__module__": __name__,
                    "Meta": type(
                        "Meta",
                        (Group.Meta,),
                        {
                            "verbose_name": grp["VERBOSE_NAME"],
                            "verbose_name_plural": grp.get("VERBOSE_NAME_PLURAL"),
                        },
                    ),
                    "base_dn": grp["BASE_DN"],
                    "gid_number_min": grp["GID_NUMBER_MIN"],
                    "gid_number_max": grp["GID_NUMBER_MAX"],
                },
            ),
        )
