"""
Django auth backends for the ``jasmin_services`` app.
"""

from datetime import date

from django.contrib.contenttypes.models import ContentType

from .models import RoleObjectPermission, Grant


class RoleObjectPermissionsBackend:
    """
    Authentication backend that implements permissions granted by roles.
    """
    def authenticate(self, request, **credentials):
        # We don't attempt any authentication
        return None

    def get_user(self, user_id):
        # We don't attempt to find any users
        return None

    def has_perm(self, user, perm, obj = None):
        # Check the grants for a role that has the permission
        return perm in self.get_all_permissions(user, obj)

    def get_all_permissions(self, user, obj = None):
        # If no object was given, there are no role-based permissions for it
        if obj is None:
            return ()
        # Load all the role-object-permissions for the user and cache them
        # This isn't much more expensive than finding one at a time...
        if not hasattr(user, "_role_perm_cache"):
            obj_perms = RoleObjectPermission.objects \
                .filter(
                    role__grant__in = Grant.objects \
                        .filter_active() \
                        .filter(
                            user = user,
                            revoked = False,
                            expires__gte = date.today()
                        )
                ) \
                .values_list(
                    'content_type_id',
                    'object_pk',
                    'permission__content_type__app_label',
                    'permission__codename'
                ) \
                .order_by()  # Clear any ordering as it might increase DB load
            user._role_perm_cache = {}
            for ct_id, obj_pk, perm_app, perm_name in obj_perms:
                user._role_perm_cache \
                    .setdefault(ct_id, {}) \
                    .setdefault(obj_pk, set()) \
                    .add(f"{perm_app}.{perm_name}")
        return user._role_perm_cache \
            .get(ContentType.objects.get_for_model(obj).pk, {}) \
            .get(str(obj.pk), set())
