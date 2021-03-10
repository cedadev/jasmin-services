"""
Django forms for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import uuid
import json
from datetime import date

from dateutil.relativedelta import relativedelta

from django.conf import settings
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.admin.widgets import AdminDateWidget
from django.contrib.auth import get_user_model
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.urls import reverse

from markdown_deux.templatetags.markdown_deux_tags import markdown_allowed

from .models import Grant, RequestState, LdapGroupBehaviour, Role


def message_form_factory(sender, *roles):
    """
    Factory function that creates a message form for a set of roles.

    The set of users is those with a valid, active grant for one of the roles.
    """
    # The possible users are those that have an active, non-revoked, non-expired
    # grant for the USER role for the service
    queryset = get_user_model().objects.distinct() \
        .filter(
            grant__in = Grant.objects
                .filter(
                    role__in = roles,
                    expires__gte = date.today(),
                    revoked = False
                )
                .filter_active()
        ) \
        .exclude(pk = sender.pk) \
        .distinct()
    return type(uuid.uuid4().hex, (forms.Form, ), {
        'users' : forms.ModelMultipleChoiceField(
            queryset = queryset,
            label = 'Send to'
        ),
        'subject' : forms.CharField(max_length = 250, label = 'Subject'),
        'message' : forms.CharField(widget = forms.Textarea, label = 'Message'),
        'reply_to' : forms.BooleanField(
            required = False, initial = False,
            label = 'Use my email address in the Reply-To header',
            help_text = mark_safe(
                'If this box is checked, your email address is attached to the '
                'email sent by the portal, allowing users to reply to you.<br>'
                '<strong>WARNING:</strong> This will reveal your email address '
                'to the selected users.'
            )
        ),
    })


def group_form_factory(service):
    """
    Factory function that creates a group form for a set of roles.
    """
    ROLE_CHOICES = [(role, role.name) for role in service.roles.all()]

    return type(uuid.uuid4().hex, (forms.Form, ), {
        'name' : forms.CharField(label = 'Name', required = True, max_length = 15),
        'description' : forms.CharField(label = 'Description'),
        'approver_roles' : forms.MultipleChoiceField(
            required = False,
            choices = ROLE_CHOICES,
            label = 'Approver roles',
            help_text = mark_safe(
                'The selected roles will be able to approve request for '
                'the created role.'
            )
        ),
    })


class GroupForm(forms.Form):
    """
    Form for creating a key LDAP group for an object store.
    """
    name = forms.CharField(label = 'Name', required = True, max_length = 15)
    description = forms.CharField(label = 'Description')


class DecisionForm(forms.Form):
    """
    Form for making a decision on a request.
    """
    # Constants defining options for the quick expiry selection
    EXPIRES_SIX_MONTHS = 1
    EXPIRES_ONE_YEAR = 2
    EXPIRES_TWO_YEARS = 3
    EXPIRES_THREE_YEARS = 4
    EXPIRES_FIVE_YEARS = 5
    EXPIRES_TEN_YEARS = 6
    EXPIRES_CUSTOM = 7

    approved = forms.NullBooleanField(
        label = 'Decision',
        widget = forms.Select(choices = [(None, '---------'),
                                         (True, 'APPROVED'),
                                         (False, 'REJECTED')])
    )
    expires = forms.TypedChoiceField(
        label = 'Expiry date',
        help_text = 'Pick a duration from the dropdown list, or pick a custom expiry date',
        required = False,
        choices = [
            (0, '---------'),
            (EXPIRES_SIX_MONTHS, 'Six months from now'),
            (EXPIRES_ONE_YEAR, 'One year from now'),
            (EXPIRES_TWO_YEARS, 'Two years from now'),
            (EXPIRES_THREE_YEARS, 'Three years from now'),
            (EXPIRES_FIVE_YEARS, 'Five years from now'),
            (EXPIRES_TEN_YEARS, 'Ten years from now'),
            (EXPIRES_CUSTOM, 'Custom expiry date'),
        ],
        coerce = int,
        empty_value = 0
    )
    expires_custom = forms.DateField(
        label = 'Custom expiry date',
        required = False,
        input_formats = ['%Y-%m-%d', '%d/%m/%Y'],
        widget = forms.DateInput(
            format = '%Y-%m-%d',
            attrs = { 'type' : 'date' }
        )
    )
    user_reason = forms.CharField(label = 'Reason for rejection (user)',
                                  required = False,
                                  widget = forms.Textarea(attrs = { 'rows' : 5 }),
                                  help_text = markdown_allowed())
    internal_reason = forms.CharField(label = 'Reason for rejection (internal)',
                                      required = False,
                                      widget = forms.Textarea(attrs = { 'rows' : 5 }),
                                      help_text = markdown_allowed())

    def __init__(self, request, approver, *args, **kwargs):
        self._request = request
        self._approver = approver
        super().__init__(*args, **kwargs)

    def clean_approved(self):
        approved = self.cleaned_data.get('approved')
        if approved is None:
            raise ValidationError('This field is required')
        return approved

    def clean_expires(self):
        approved = self.cleaned_data.get('approved')
        expires = self.cleaned_data.get('expires')
        if approved and not expires:
            raise ValidationError('Please give an expiry date for access')
        return expires

    def clean_expires_custom(self):
        approved = self.cleaned_data.get('approved')
        expires = self.cleaned_data.get('expires')
        expires_custom = self.cleaned_data.get('expires_custom')
        if approved and expires == self.EXPIRES_CUSTOM and not expires_custom:
            raise ValidationError('Please give an expiry date for access')
        if expires_custom and expires_custom < date.today():
            raise ValidationError('Expiry date must be in the future')
        return expires_custom

    def clean_user_reason(self):
        approved = self.cleaned_data.get('approved')
        user_reason = self.cleaned_data.get('user_reason')
        if approved is False and not user_reason:
            raise ValidationError('Please give a reason for rejection')
        return user_reason

    def save(self):
        # Update the request from the form
        if self.cleaned_data['approved']:
            # Get the expiry date
            expires = self.cleaned_data['expires']
            if expires == self.EXPIRES_SIX_MONTHS:
                expires_date = date.today() + relativedelta(months = 6)
            elif expires == self.EXPIRES_ONE_YEAR:
                expires_date = date.today() + relativedelta(years = 1)
            elif expires == self.EXPIRES_TWO_YEARS:
                expires_date = date.today() + relativedelta(years = 2)
            elif expires == self.EXPIRES_THREE_YEARS:
                expires_date = date.today() + relativedelta(years = 3)
            elif expires == self.EXPIRES_FIVE_YEARS:
                expires_date = date.today() + relativedelta(years = 5)
            elif expires == self.EXPIRES_TEN_YEARS:
                expires_date = date.today() + relativedelta(years = 10)
            else:
                expires_date = self.cleaned_data['expires_custom']
            self._request.state = RequestState.APPROVED
            # If the request was approved, create the grant
            self._request.grant = Grant.objects.create(
                role = self._request.role,
                user = self._request.user,
                granted_by = self._approver.username,
                expires = expires_date
            )
            # Copy the metadata from the request to the grant
            self._request.copy_metadata_to(self._request.grant)
        else:
            self._request.state = RequestState.REJECTED
            self._request.user_reason = self.cleaned_data['user_reason']
            self._request.internal_reason = self.cleaned_data['internal_reason']
        self._request.save()
        return self._request


######
## ADMIN FORMS
######

class AdminDecisionForm(DecisionForm):
    expires_custom = forms.DateField(
        label = 'Custom expiry date',
        required = False,
        input_formats = ['%Y-%m-%d', '%d/%m/%Y'],
        widget = AdminDateWidget
    )


class AdminSwitchableLookupWidget(forms.TextInput):
    """
    Custom widget to allow the lookup of a single model PK using a popup. The model
    to select from is switchable based on the specified field.

    Assumes a single default admin site.

    Heavily influenced by django.contrib.admin raw ID widget.
    """
    def __init__(self, switch_field_name, model_map, attrs = None):
        super().__init__(attrs)
        self.switch_field_name = switch_field_name
        self.model_map = model_map

    def render(self, name, value, attrs = None, renderer = None):
        if attrs is None:
            attrs = {}
        value = force_text(value) if value else ''
        attrs['class'] = 'vForeignKeyRawIdAdminField'
        attrs['style'] = 'width: 20em !important;'
        # Translate the model_map into an href_map
        href_map = {
            k : reverse('admin:{}_{}_changelist'.format(m._meta.app_label,
                                                        m._meta.model_name))
            for k, m in self.model_map.items()
        }
        lookup_link_id = "lookup_id_{}".format(name)
        # Start with the text input
        output = super().render(name, value, attrs)
        # Append the lookup link
        output += '<a href="#" class="related-lookup" id="{}" title="Lookup"></a>'.format(lookup_link_id)
        # Append the Javascript to do the switching
        output += """<script type="text/javascript">
(function($) {{
    var href_map = {href_map};
    var $lookup_link = $('#{lookup_link_id}');
    var $switch_field = $('[name="{switch_field_name}"]');
    $switch_field.on('change', function() {{
        $lookup_link.attr('href', href_map[$(this).val()]);
    }});
    $lookup_link.attr('href', href_map[$switch_field.val()]);
}})(django.jQuery);
</script>""".format(href_map = json.dumps(href_map),
                    lookup_link_id = lookup_link_id,
                    switch_field_name = self.switch_field_name)
        return mark_safe(output)

class LdapGroupBehaviourAdminForm(forms.ModelForm):
    class Meta:
        model = LdapGroupBehaviour
        exclude = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use a select for ldap_model choice
        self.fields['ldap_model'].widget = forms.Select(
            choices = [
                (g['MODEL_NAME'], g['VERBOSE_NAME'])
                for g in settings.JASMIN_SERVICES['LDAP_GROUPS']
            ]
        )
        # Use a switchable lookup widget for group_name with the model we found,
        # switching on the value of ldap_model
        from . import models as models_module
        self.fields['group_name'].widget = AdminSwitchableLookupWidget(
            'ldap_model',
            {
                g['MODEL_NAME'] : getattr(models_module, g['MODEL_NAME'])
                for g in settings.JASMIN_SERVICES['LDAP_GROUPS']
            }
        )
