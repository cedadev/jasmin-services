"""Module defining specific category implementations."""

import logging

from .base import Behaviour  # unimport:skip
from .mail import JoinJISCMailListBehaviour  # unimport:skip

__all__ = []
logger = logging.getLogger(__name__)

__all__ += [
    "Behaviour",
    "JoinJISCMailListBehaviour",
]

# Keycloak behaviour is only available if the keycloak optional dependency is installed.
try:
    from .keycloak import KeycloakAttributeBehaviour
except ImportError:
    logger.warning("Keycloak Behaviour is not enabled. Install optional dependencies to activate.")
else:
    __all__ += ["KeycloakAttributeBehaviour"]

# LDAP behaviour is only available if the jamsin-ldap optional dependency is installed.
try:
    from .ldap import LdapGroupBehaviour, LdapTagBehaviour  # unimport:skip
except ImportError:
    logger.warning("LDAP Behaviour is not enabled. Install optional dependencies to activate.")
else:
    __all__ += [
        "LdapTagBehaviour",
        "LdapGroupBehaviour",
    ]
