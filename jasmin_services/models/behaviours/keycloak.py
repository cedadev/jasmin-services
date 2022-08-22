"""Behaviours to allow integration with KeyCloak."""

import django.conf
import keycloak

from .base import Behaviour


class KeycloakAttributeBehaviour(Behaviour):
    """Behaviour to add keycloak attributes to a user."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        settings = django.conf.settings["JASMIN_SERVICES"]["KEYCLOAK"]

        self.keycloak = keycloak.KeycloakAdmin(
            server_url=settings.get("server_url"),
            realm_name=settings.get("realm_name"),
            username=settings.get("username"),
            password=settings.get("password"),
            user_realm_name=settings.get("user_realm_name", settings.get("realm_name")),
            verify=settings.get("verify", True),
        )

    def apply(self, user, service):
        """Add the user to the specified keycloak groups."""
        kc_group = self.keycloak.get_group(service.name)
        kc_user_id = self.keycloak.get_user_id(user.username)
        self.keycloak.group_user_add(kc_user_id, kc_group.get("id"))

    def unapply(self, user, service):
        """Remove the user from the specified keycloak groups."""
        kc_group = self.keycloak.get_group(service.name)
        kc_user_id = self.keycloak.get_user_id(user.username)
        self.keycloak.group_user_remove(kc_user_id, kc_group.get("id"))
