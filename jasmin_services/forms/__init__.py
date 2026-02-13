"""
Django forms for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import json
import uuid
from datetime import date

import django.contrib.auth
import django.utils.encoding
from django import forms
from django.conf import settings
from django.contrib.admin.widgets import AdminDateWidget, FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.safestring import mark_safe
from markdown_deux.templatetags.markdown_deux_tags import markdown_allowed

from ..models import Access, Grant, Request, Role
from .decision_form import DecisionForm  # unimport: skip


def message_form_factory(sender, *roles):
    """
    Factory function that creates a message form for a set of roles.

    The set of users is those with a valid, active grant for one of the roles.
    """
    # The possible users are those that have an active, non-revoked, non-expired
    # grant for the USER role for the service
    queryset = (
        get_user_model()
        .objects.distinct()
        .filter(
            access__grant__in=Grant.objects.filter(
                access__role__in=roles, expires__gte=date.today(), revoked=False
            ).filter_active()
        )
        .exclude(pk=sender.pk)
        .distinct()
    )
    return type(
        uuid.uuid4().hex,
        (forms.Form,),
        {
            "users": forms.ModelMultipleChoiceField(
                queryset=queryset,
                label="Send to",
                widget=forms.SelectMultiple(
                    attrs={
                        "class": "selectpicker",
                        "data-actions-box": "true",
                        "data-live-search": "true",
                        "data-live-search-normalize": "true",
                        "data-width": "100%",
                        "data-style": "",
                        "data-style-base": "form-control",
                    }
                ),
            ),
            "subject": forms.CharField(max_length=250, label="Subject"),
            "message": forms.CharField(widget=forms.Textarea, label="Message"),
            "reply_to": forms.BooleanField(
                required=False,
                initial=False,
                label="Use my email address in the Reply-To header",
                help_text=mark_safe(
                    "If this box is checked, your email address is attached to the "
                    "email sent by the portal, allowing users to reply to you.<br>"
                    '<strong style="color:#F39C12">WARNING:</strong> This will reveal your email address '
                    "to the selected users."
                ),
            ),
        },
    )


def grant_form_factory(roles):
    """
    Factory function that creates a message form for a set of roles.

    The set of users is those with a valid, active grant for one of the roles.
    """
    # The possible users are those that have an active, non-revoked, non-expired
    # grant for the USER role for the service
    role_choices = [(role.id, role.name) for role in roles]

    EXPIRES_SIX_MONTHS = 1
    EXPIRES_ONE_YEAR = 2
    EXPIRES_TWO_YEARS = 3
    EXPIRES_THREE_YEARS = 4
    EXPIRES_FIVE_YEARS = 5
    EXPIRES_TEN_YEARS = 6
    EXPIRES_CUSTOM = 7

    return type(
        uuid.uuid4().hex,
        (forms.Form,),
        {
            "username": forms.CharField(
                max_length=254,
                label="Username",
                validators=[validate_grant_username],
                help_text="The JASMIN username of the user you wish to grant a role to.",
            ),
            "role": forms.ChoiceField(
                choices=role_choices,
                label="Role",
            ),
            "expires": forms.TypedChoiceField(
                label="Expiry date",
                help_text="Pick a duration from the dropdown list, or pick a custom expiry date",
                required=False,
                choices=[
                    (0, "---------"),
                    (EXPIRES_SIX_MONTHS, "Six months from now"),
                    (EXPIRES_ONE_YEAR, "One year from now"),
                    (EXPIRES_TWO_YEARS, "Two years from now"),
                    (EXPIRES_THREE_YEARS, "Three years from now"),
                    (EXPIRES_FIVE_YEARS, "Five years from now"),
                    (EXPIRES_TEN_YEARS, "Ten years from now"),
                    (EXPIRES_CUSTOM, "Custom expiry date"),
                ],
                coerce=int,
                empty_value=0,
            ),
            "expires_custom": forms.DateField(
                label="Custom expiry date",
                required=False,
                input_formats=["%Y-%m-%d", "%d/%m/%Y"],
                widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            ),
        },
    )


def validate_grant_username(value):
    # validator to check account exists for given email.
    user_model = django.contrib.auth.get_user_model()
    try:
        user_model.objects.get(username=value)
    except user_model.DoesNotExist:
        raise ValidationError(f"user ({value}) does not exist.")


class GrantReviewForm(forms.Form):
    """
    Form for revoking a grant.
    """

    user_reason = forms.CharField(
        label="Reason for revocation (user)",
        required=True,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=markdown_allowed(),
    )
    internal_reason = forms.CharField(
        label="Reason for revocation (internal)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=markdown_allowed(),
    )

    def __init__(self, grant, *args, **kwargs):
        self._grant = grant
        super().__init__(*args, **kwargs)

    def save(self):
        # Update the grant from the form
        self._grant.revoked = True
        self._grant.user_reason = self.cleaned_data["user_reason"]
        self._grant.internal_reason = self.cleaned_data["internal_reason"]
        self._grant.save()
        return self._grant


######
## ADMIN FORMS
######


class AdminRevokeForm(forms.Form):
    user_reason = forms.CharField(
        label="Reason for rejection (user)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=markdown_allowed(),
    )
    internal_reason = forms.CharField(
        label="Reason for rejection (internal)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=markdown_allowed(),
    )


class AdminSwitchableLookupWidget(forms.TextInput):
    """
    Custom widget to allow the lookup of a single model PK using a popup. The model
    to select from is switchable based on the specified field.

    Assumes a single default admin site.

    Heavily influenced by django.contrib.admin raw ID widget.
    """

    def __init__(self, switch_field_name, model_map, attrs=None):
        super().__init__(attrs)
        self.switch_field_name = switch_field_name
        self.model_map = model_map

    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        value = django.utils.encoding.force_str(value) if value else ""
        attrs["class"] = "vForeignKeyRawIdAdminField"
        attrs["style"] = "width: 20em !important;"
        # Translate the model_map into an href_map
        href_map = {
            k: reverse("admin:{}_{}_changelist".format(m._meta.app_label, m._meta.model_name))
            for k, m in self.model_map.items()
        }
        lookup_link_id = "lookup_id_{}".format(name)
        # Start with the text input
        output = super().render(name, value, attrs)
        # Append the lookup link
        output += '<a href="#" class="related-lookup" id="{}" title="Lookup"></a>'.format(
            lookup_link_id
        )
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
</script>""".format(
            href_map=json.dumps(href_map),
            lookup_link_id=lookup_link_id,
            switch_field_name=self.switch_field_name,
        )
        return mark_safe(output)


def admin_message_form_factory(service):
    """
    Factory function that creates a message form for a set of roles.

    The set of users is those with a valid, active grant for one of the roles.
    """
    # The possible users are those that have an active, non-revoked, non-expired
    # grant for the USER role for the service
    queryset = (
        get_user_model()
        .objects.distinct()
        .filter(
            grant__in=Grant.objects.filter(
                access__role__service=service, expires__gte=date.today(), revoked=False
            ).filter_active()
        )
        .distinct()
    )
    return type(
        uuid.uuid4().hex,
        (forms.Form,),
        {
            "users": forms.ModelMultipleChoiceField(
                queryset=queryset,
                label="Send to",
                widget=FilteredSelectMultiple("Users", is_stacked=False),
            ),
            "subject": forms.CharField(max_length=250, label="Subject"),
            "message": forms.CharField(widget=forms.Textarea, label="Message"),
        },
    )


# When moving this out of a custom form, we should tidy with fieldsets, e.g. hide revoked_at when revoked is False
class AdminGrantForm(forms.ModelForm):
    class Meta:
        model = Grant
        fields = (
            "access",
            "user",
            "role",
            "granted_by",
            "previous_grant",
            "expires",
            "revoked",
            "revoked_at",
            "user_reason",
            "internal_reason",
            "internal_comment",
        )
        widgets = {"access": forms.HiddenInput()}

    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=True,
        label="Role",
    )

    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.all(),
        required=True,
        label="User",
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
        role = self.cleaned_data["role"]
        user = self.cleaned_data["user"]
        previous_grant = self.cleaned_data.get("previous_grant")

        if not settings.MULTIPLE_REQUESTS_ALLOWED:
            existing_grant = Grant.objects.filter(
                access__role=role, access__user=user
            ).filter_active()
            if (
                len(existing_grant) > 0
                and existing_grant[0] != previous_grant
                and self._active
                and self._id
                and self._id != existing_grant[0].id
            ):
                raise ValidationError(
                    f"An active grant ({existing_grant[0].id}) for this user and role already exists, select it here to overwrite"
                )

        return previous_grant

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data["role"]
        user = cleaned_data["user"]

        if not settings.MULTIPLE_REQUESTS_ALLOWED:
            existing_request = Request.objects.filter(
                access__role=role, access__user=user
            ).filter_active()
            if len(existing_request) > 0 and self._active:
                raise ValidationError(
                    f"An active request ({existing_request[0].id}) for this user and role already exists, please decide this request before creating a grant"
                )

        access, _ = Access.objects.get_or_create(role=role, user=user)
        cleaned_data["access"] = access

        return cleaned_data


class AdminRequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = (
            "user",
            "role",
            "access",
            "requested_by",
            "state",
            "resulting_grant",
            "previous_grant",
            "previous_request",
            "incomplete",
            "internal_comment",
            "user_reason",
            "internal_reason",
        )
        widgets = {"access": forms.HiddenInput()}

    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=True,
        label="Role",
    )

    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.all(),
        required=True,
        label="User",
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
        role = self.cleaned_data["role"]
        user = self.cleaned_data["user"]
        previous_request = self.cleaned_data.get("previous_request")

        if not settings.MULTIPLE_REQUESTS_ALLOWED:
            existing_request = Request.objects.filter(
                access__role=role, access__user=user
            ).filter_active()
            if (
                len(existing_request) > 0
                and existing_request[0] != previous_request
                and self._active
                and self._id
                and self._id != existing_request[0].id
            ):
                raise ValidationError(
                    f"An active request ({existing_request[0].id}) for this user and role already exists, select it here to overwrite"
                )

        return previous_request

    def clean_previous_grant(self):
        role = self.cleaned_data["role"]
        user = self.cleaned_data["user"]
        previous_grant = self.cleaned_data.get("previous_grant")

        if not settings.MULTIPLE_REQUESTS_ALLOWED:
            existing_grant = Grant.objects.filter(
                access__role=role, access__user=user
            ).filter_active()
            if len(existing_grant) > 0 and existing_grant[0] != previous_grant and self._active:
                raise ValidationError(
                    f"An active grant ({existing_grant[0].id}) for this user and role already exists, select it here to overwrite"
                )

        return previous_grant

    def clean(self):
        cleaned_data = super().clean()
        access, _ = Access.objects.get_or_create(
            role=cleaned_data["role"], user=cleaned_data["user"]
        )
        cleaned_data["access"] = access

        return cleaned_data
