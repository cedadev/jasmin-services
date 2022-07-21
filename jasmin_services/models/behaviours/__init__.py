"""Module defining specific category implementations."""
import logging
import sys

import django.conf

from .base import Behaviour
from .ldap import Group, LdapGroupBehaviour, LdapTagBehaviour
from .mail import JoinJISCMailListBehaviour

__all__ = []
logger = logging.getLogger(__name__)

try:
    from .keycloak import KeycloakAttributeBehaviour
except ImportError:
    logger.warning(
        "Keycloak Behaviour is not enabled. Install optional dependencies to activate."
    )
else:
    __all__ += ["KeycloakAttributeBehaviour"]

__all__ += [
    "Behaviour",
    "LdapTagBehaviour",
    "Group",
    "LdapGroupBehaviour",
    "JoinJISCMailListBehaviour",
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
