"""Module defining specific category implementations."""
from .base import Behaviour
from .ldap import Group, LdapGroupBehaviour, LdapTagBehaviour
from .mail import JoinJISCMailListBehaviour

__all__ = []

try:
    from .keycloak import KeycloakAttributeBehaviour
except ImportError:
    pass
else:
    __all__ += ["KeycloakAttributeBehaviour"]

__all__ += [
    "Behaviour",
    "LdapTagBehaviour",
    "Group",
    "LdapGroupBehaviour",
    "JoinJISCMailListBehaviour",
]
