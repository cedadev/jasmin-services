from django import forms
from django.conf import settings

from ..models import LdapGroupBehaviour


class LdapGroupBehaviourAdminForm(forms.ModelForm):
    class Meta:
        model = LdapGroupBehaviour
        exclude = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use a select for ldap_model choice
        self.fields["ldap_model"].widget = forms.Select(
            choices=[
                (g["MODEL_NAME"], g["VERBOSE_NAME"])
                for g in settings.JASMIN_SERVICES["LDAP_GROUPS"]
            ]
        )
        # Use a switchable lookup widget for group_name with the model we found,
        # switching on the value of ldap_model
        from . import models as models_module

        self.fields["group_name"].widget = AdminSwitchableLookupWidget(
            "ldap_model",
            {
                g["MODEL_NAME"]: getattr(models_module, g["MODEL_NAME"])
                for g in settings.JASMIN_SERVICES["LDAP_GROUPS"]
            },
        )
