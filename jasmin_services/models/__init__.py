"""Module defining models for the JASMIN services app."""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import logging
import sys

import django.conf

from .access import Access
from .behaviours import *
from .category import Category
from .grant import Grant
from .request import Request, RequestState
from .role import Role, RoleObjectPermission
from .service import Service

logger = logging.getLogger(__name__)

__all__ = [
    "Access",
    "Category",
    "Grant",
    "Request",
    "RequestState",
    "Role",
    "RoleObjectPermission",
    "Service",
]

# LDAP behaviour is only available if the jamsin-ldap optional dependency is installed.
try:
    from .ldap import Group
except ImportError:
    logger.warning("LDAP is not enabled. Install optional dependencies to activate.")
else:
    __all__.append("Group")
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
                            "managed": False,
                        },
                    ),
                    "base_dn": grp["BASE_DN"],
                    "gid_number_min": grp["GID_NUMBER_MIN"],
                    "gid_number_max": grp["GID_NUMBER_MAX"],
                },
            ),
        )
