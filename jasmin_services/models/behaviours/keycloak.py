"""Behaviours to allow integration with KeyCloak."""

import logging

import django.conf
import keycloak

from .base import Behaviour

logger = logging.getLogger(__name__)


class KeycloakAttributeBehaviour(Behaviour):
    """Behaviour to add keycloak attributes to a user."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        settings = django.conf.settings.JASMIN_SERVICES["KEYCLOAK"]

        self.keycloak = keycloak.KeycloakAdmin(
            server_url=settings.get("SERVER_URL"),
            realm_name=settings.get("REALM_NAME"),
            username=settings.get("USERNAME"),
            password=settings.get("PASSWORD"),
            user_realm_name=settings.get("USER_REALM_NAME", settings.get("REALM_NAME")),
            verify=settings.get("VERIFY", True),
        )

    def apply(self, user, role):
        """Add the user to the specified keycloak groups."""
        logger.info("Applying keycloak group %s to user %s.", role.service.name, user.username)
        kc_group = self.keycloak.get_group_by_path(f"/{role.service.name}")
        kc_user_id = self.keycloak.get_user_id(user.username)
        self.keycloak.group_user_add(kc_user_id, kc_group.get("id"))

    def unapply(self, user, role):
        """Remove the user from the specified keycloak groups."""
        logger.info("Removing keycloak group %s from user %s.", role.service.name, user.username)
        kc_group = self.keycloak.get_group_by_path(f"/{role.service.name}")
        kc_user_id = self.keycloak.get_user_id(user.username)
        self.keycloak.group_user_remove(kc_user_id, kc_group.get("id"))
