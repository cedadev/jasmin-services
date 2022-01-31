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
from django.contrib.admin.widgets import FilteredSelectMultiple, AdminDateWidget, AutocompleteSelect
from django.contrib.auth import get_user_model
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.urls import reverse

from markdown_deux.templatetags.markdown_deux_tags import markdown_allowed

from .models import Access, Role, Grant, Request, RequestState, LdapGroupBehaviour

def message_form_factory(sender, *roles):
    """
    Factory function that creates a message form for a set of roles.

    The set of users is those with a valid, active grant for one of the roles.
    """
    # The possible users are those that have an active, non-revoked, non-expired
    # grant for the USER role for the service
    queryset = get_user_model().objects.distinct() \
        .filter(
            access__grant__in = Grant.objects
                .filter(
                    access__role__in = roles,
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
            label = 'Send to',
            widget=forms.SelectMultiple(attrs={
                'class': 'selectpicker',
                'data-actions-box': 'true',
                'data-live-search': 'true',
                'data-live-search-normalize': 'true',
                'data-width': '100%',
                'data-style': '',
                'data-style-base': 'form-control',
                }),
        ),
        'subject' : forms.CharField(max_length = 250, label = 'Subject'),
        'message' : forms.CharField(widget = forms.Textarea, label = 'Message'),
        'reply_to' : forms.BooleanField(
            required = False, initial = False,
            label = 'Use my email address in the Reply-To header',
            help_text = mark_safe(
                'If this box is checked, your email address is attached to the '
                'email sent by the portal, allowing users to reply to you.<br>'
                '<strong style="color:#F39C12">WARNING:</strong> This will reveal your email address '
                'to the selected users.'
            )
        ),
    })


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

    state = forms.TypedChoiceField(
        label = 'Decision',
        choices = [
            (None, '---------'),
            ('APPROVED', 'APPROVED'),
            ('INCOMPLETE', 'INCOMPLETE'),
            ('REJECTED', 'REJECTED')
        ],
        coerce = str,
        empty_value = None
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
                                  help_text = mark_safe(markdown_allowed()))
    internal_reason = forms.CharField(label = 'Reason for rejection (internal)',
                                      required = False,
                                      widget = forms.Textarea(attrs = { 'rows' : 5 }),
                                      help_text = mark_safe(markdown_allowed()))

    def __init__(self, request, approver, *args, **kwargs):
        self._request = request
        self._approver = approver
        super().__init__(*args, **kwargs)

    def clean_state(self):
        state = self.cleaned_data.get('state')
        if state is None:
            raise ValidationError('This field is required')
        return state

    def clean_expires(self):
        state = self.cleaned_data.get('state')
        expires = self.cleaned_data.get('expires')
        if state == 'APPROVED' and not expires:
            raise ValidationError('Please give an expiry date for access')
        return expires

    def clean_expires_custom(self):
        state = self.cleaned_data.get('state')
        expires = self.cleaned_data.get('expires')
        expires_custom = self.cleaned_data.get('expires_custom')
        if state == 'APPROVED' and expires == self.EXPIRES_CUSTOM and not expires_custom:
            raise ValidationError('Please give an expiry date for access')
        if expires_custom and expires_custom < date.today():
            raise ValidationError('Expiry date must be in the future')
        return expires_custom

    def clean_user_reason(self):
        state = self.cleaned_data.get('state')
        user_reason = self.cleaned_data.get('user_reason')
        if state != 'APPROVED' and not user_reason:
            raise ValidationError('Please give a reason for rejection or incompletion')
        return user_reason

    def save(self):
        # Update the request from the form
        if self.cleaned_data['state'] == 'APPROVED':
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
            # If the request has a previous_grant create a new grant
            # and link with the old grant
            previous_grant = self._request.previous_grant
            if previous_grant:
                self._request.resulting_grant = Grant.objects.create(
                    access = self._request.access,
                    granted_by = self._approver.username,
                    expires = expires_date,
                    previous_grant = previous_grant
                )
            else:
            # Else create the access if it does not already exist and
            # then create the new grant
                access, _ = Access.objects.get_or_create(
                    user = self._request.access.user,
                    role = self._request.access.role
                )
                self._request.resulting_grant = Grant.objects.create(
                    access = access,
                    granted_by = self._approver.username,
                    expires = expires_date
                )
            # Copy the metadata from the request to the grant
            self._request.copy_metadata_to(self._request.resulting_grant)
        else:
            self._request.state = RequestState.REJECTED
            self._request.incomplete =  True if self.cleaned_data['state'] == 'INCOMPLETE' else False
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


class AdminRevokeForm(forms.Form):
    user_reason = forms.CharField(
        label = 'Reason for rejection (user)',
        required = False,
        widget = forms.Textarea(attrs = { 'rows' : 5 }),
        help_text = markdown_allowed()
    )
    internal_reason = forms.CharField(
        label = 'Reason for rejection (internal)',
        required = False,
        widget = forms.Textarea(attrs = { 'rows' : 5 }),
        help_text = markdown_allowed()
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

def admin_message_form_factory(service):
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
                    access__role__service = service,
                    expires__gte = date.today(),
                    revoked = False
                )
                .filter_active()
        ) \
        .distinct()
    return type(uuid.uuid4().hex, (forms.Form, ), {
        'users' : forms.ModelMultipleChoiceField(
            queryset = queryset,
            label = 'Send to',
            widget = FilteredSelectMultiple("Users", is_stacked=False),
        ),
        'subject' : forms.CharField(max_length = 250, label = 'Subject'),
        'message' : forms.CharField(widget = forms.Textarea, label = 'Message'),
    })

from django.contrib.admin.sites import site
class AdminGrantForm(forms.ModelForm):
    class Meta:
        model = Grant
        fields = ('access', 'user', 'role', 'granted_by', 'previous_grant',
              'expires', 'revoked', 'user_reason', 'internal_reason')
        widgets = {'access': forms.HiddenInput()}
        
    role = forms.ModelChoiceField(
        queryset = Role.objects.all(),
        required = True,
        label = 'Role',
        widget = AutocompleteSelect(Access._meta.get_field('role').remote_field, site),
    )

    user = forms.ModelChoiceField(
        queryset = get_user_model().objects.all(),
        required = True,
        label = 'User',
        widget = AutocompleteSelect(Access._meta.get_field('user').remote_field, site),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # an access is required but is filled by the user and role fields so required must be false
        self.fields["access"].required = False

        self._id = True
        self._active = True
        if "instance" in kwargs and isinstance(kwargs["instance"], Grant):
            self._id = kwargs["instance"].id
            self._active = kwargs["instance"].active
            self.fields["user"].initial = kwargs["instance"].access.user
            self.fields["role"].initial = kwargs["instance"].access.role

    def clean_previous_grant(self):
        role = self.cleaned_data['role']
        user = self.cleaned_data['user']
        previous_grant = self.cleaned_data.get('previous_grant')

        if not settings.MULTIPLE_REQUESTS_ALLOWED:
            existing_grant = Grant.objects.filter(access__role = role, access__user = user).filter_active()
            if len(existing_grant) > 0 and existing_grant[0] != previous_grant and \
              self._active and self._id and self._id != existing_grant[0].id:
                raise ValidationError(f"An active grant ({existing_grant[0].id}) for this user and role already exists, select it here to overwrite")

        return previous_grant

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data['role']
        user = cleaned_data['user']

        if not settings.MULTIPLE_REQUESTS_ALLOWED:
            existing_request = Request.objects.filter(access__role = role, access__user = user).filter_active()
            if len(existing_request) > 0 and self._active:
                raise ValidationError(f"An active request ({existing_request[0].id}) for this user and role already exists, please decide this request before creating a grant")

        access, _ = Access.objects.get_or_create(role = role, user = user)
        cleaned_data["access"] = access

        return cleaned_data


class AdminRequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ('user', 'role', 'access', 'requested_by', 'state', 'resulting_grant',
                'previous_grant', 'previous_request', 'incomplete',)
        widgets = {'access': forms.HiddenInput()}
        
    role = forms.ModelChoiceField(
        queryset = Role.objects.all(),
        required = True,
        label = 'Role',
        widget = AutocompleteSelect(Access._meta.get_field('role').remote_field, site),
    )

    user = forms.ModelChoiceField(
        queryset = get_user_model().objects.all(),
        required = True,
        label = 'User',
        widget = AutocompleteSelect(Access._meta.get_field('user').remote_field, site),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # an access is required but is filled by the user and role fields so required must be false
        self.fields["access"].required = False

        self._id = True
        self._active = True
        if "instance" in kwargs and isinstance(kwargs["instance"], Request):
            self._id = kwargs["instance"].id
            self._active = kwargs["instance"].active
            self.fields["user"].initial = kwargs["instance"].access.user
            self.fields["role"].initial = kwargs["instance"].access.role

    def clean_previous_request(self):
        role = self.cleaned_data['role']
        user = self.cleaned_data['user']
        previous_request = self.cleaned_data.get('previous_request')

        if not settings.MULTIPLE_REQUESTS_ALLOWED:
            existing_request = Request.objects.filter(access__role = role, access__user = user).filter_active()
            if len(existing_request) > 0 and existing_request[0] != previous_request and \
              self._active and self._id and self._id != existing_request[0].id:
                raise ValidationError(f"An active request ({existing_request[0].id}) for this user and role already exists, select it here to overwrite")

        return previous_request
    
    def clean_previous_grant(self):
        role = self.cleaned_data['role']
        user = self.cleaned_data['user']
        previous_grant = self.cleaned_data.get('previous_grant')

        if not settings.MULTIPLE_REQUESTS_ALLOWED:
            existing_grant = Grant.objects.filter(access__role = role, access__user = user).filter_active()
            if len(existing_grant) > 0 and existing_grant[0] != previous_grant and self._active:
                raise ValidationError(f"An active grant ({existing_grant[0].id}) for this user and role already exists, select it here to overwrite")

        return previous_grant

    def clean(self):
        cleaned_data = super().clean()
        access, _ = Access.objects.get_or_create(role = cleaned_data['role'], user = cleaned_data['user'])
        cleaned_data["access"] = access

        return cleaned_data
