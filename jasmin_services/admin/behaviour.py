"""Register admin modules for swappable behaviours."""

from django.contrib import admin
from polymorphic.admin import (
    PolymorphicChildModelAdmin,
    PolymorphicChildModelFilter,
    PolymorphicParentModelAdmin,
)

from ..models import Behaviour, JoinJISCMailListBehaviour

# Keep a list of models for which behaviours are activated
register_child_models = []


# JoinJISCMailListBehaviour is always active since sending mail is builtin to django.
@admin.register(JoinJISCMailListBehaviour)
class JoinJISCMailListBehaviourAdmin(PolymorphicChildModelAdmin):
    base_model = JoinJISCMailListBehaviour


register_child_models.append(JoinJISCMailListBehaviour)


# LDAP behaviour is only available if jasmin_ldap_django is installed.
try:
    from ..forms.ldap_admin import LdapGroupBehaviourAdminForm
    from ..models import LdapGroupBehaviour, LdapTagBehaviour
except ImportError:
    pass
else:

    @admin.register(LdapTagBehaviour)
    class LdapTagBehaviourAdmin(PolymorphicChildModelAdmin):
        base_model = LdapTagBehaviour

    register_child_models.append(LdapTagBehaviour)

    @admin.register(LdapGroupBehaviour)
    class LdapGroupBehaviourAdmin(PolymorphicChildModelAdmin):
        base_model = LdapGroupBehaviour
        form = LdapGroupBehaviourAdminForm

    register_child_models.append(LdapGroupBehaviour)


# Now register all the behaviour admins to the polymorphic model.
@admin.register(Behaviour)
class BehaviourAdmin(PolymorphicParentModelAdmin):
    base_model = Behaviour
    child_models = register_child_models
    polymorphic_list = True

    list_display = ("behaviour_as_string",)
    list_filter = (PolymorphicChildModelFilter,)

    def behaviour_as_string(self, obj):
        return str(obj)

    behaviour_as_string.short_description = "Behaviour"

    def has_module_permission(self, request):
        # Prevent this admin showing up on the index page
        return False
