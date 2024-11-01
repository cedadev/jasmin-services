from datetime import date

from dateutil.relativedelta import relativedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from markdown_deux.templatetags.markdown_deux_tags import markdown_allowed

from ..models import Access, Grant, RequestState


class DecisionForm(forms.Form):
    """Form for making a decision on a request."""

    # Constants defining options for the quick expiry selection
    EXPIRES_SIX_MONTHS = 1
    EXPIRES_ONE_YEAR = 2
    EXPIRES_TWO_YEARS = 3
    EXPIRES_THREE_YEARS = 4
    EXPIRES_FIVE_YEARS = 5
    EXPIRES_TEN_YEARS = 6
    EXPIRES_CUSTOM = 7

    state = forms.TypedChoiceField(
        label="Decision",
        choices=[
            (None, "---------"),
            ("APPROVED", "APPROVED"),
            ("INCOMPLETE", "INCOMPLETE"),
            ("REJECTED", "REJECTED"),
        ],
        coerce=str,
        empty_value=None,
        required=False,
    )
    expires = forms.TypedChoiceField(
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
    )
    expires_custom = forms.DateField(
        label="Custom expiry date",
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    user_reason = forms.CharField(
        label="Reason for rejection (user)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=mark_safe(markdown_allowed()),
    )
    internal_reason = forms.CharField(
        label="Reason for rejection (internal)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=mark_safe(markdown_allowed()),
    )

    def __init__(self, request, approver, *args, **kwargs):
        self._request = request
        self._approver = approver
        super().__init__(*args, **kwargs)

        if self._approver.is_staff:
            self.fields["internal_comment"] = forms.CharField(
                label="Internal comment (shown only to CEDA staff)",
                required=False,
                widget=forms.Textarea(attrs={"rows": 5}),
                help_text=mark_safe(markdown_allowed()),
            )

    def clean_state(self):
        state = self.cleaned_data.get("state")
        if (not self._approver.is_staff) and (state is None):
            raise ValidationError("This field is required")
        return state

    def clean_expires(self):
        state = self.cleaned_data.get("state")
        expires = self.cleaned_data.get("expires")
        if state == "APPROVED" and not expires:
            raise ValidationError("Please give an expiry date for access")
        return expires

    def clean_expires_custom(self):
        state = self.cleaned_data.get("state")
        expires = self.cleaned_data.get("expires")
        expires_custom = self.cleaned_data.get("expires_custom")
        if state == "APPROVED" and expires == self.EXPIRES_CUSTOM and not expires_custom:
            raise ValidationError("Please give an expiry date for access")
        if expires_custom and expires_custom < date.today():
            raise ValidationError("Expiry date must be in the future")
        return expires_custom

    def clean_user_reason(self):
        state = self.cleaned_data.get("state")
        user_reason = self.cleaned_data.get("user_reason")
        if (state is not None) and (state != "APPROVED") and (not user_reason):
            raise ValidationError(
                "Please give a reason for rejection or incompletion", code="no_user_reason"
            )
        return user_reason

    def save(self):
        # Update the request from the form
        if self.cleaned_data["state"] == "APPROVED":
            # Get the expiry date
            expires = self.cleaned_data["expires"]
            if expires == self.EXPIRES_SIX_MONTHS:
                expires_date = date.today() + relativedelta(months=6)
            elif expires == self.EXPIRES_ONE_YEAR:
                expires_date = date.today() + relativedelta(years=1)
            elif expires == self.EXPIRES_TWO_YEARS:
                expires_date = date.today() + relativedelta(years=2)
            elif expires == self.EXPIRES_THREE_YEARS:
                expires_date = date.today() + relativedelta(years=3)
            elif expires == self.EXPIRES_FIVE_YEARS:
                expires_date = date.today() + relativedelta(years=5)
            elif expires == self.EXPIRES_TEN_YEARS:
                expires_date = date.today() + relativedelta(years=10)
            else:
                expires_date = self.cleaned_data["expires_custom"]
            self._request.state = RequestState.APPROVED
            # If the request has a previous_grant create a new grant
            # and link with the old grant
            previous_grant = self._request.previous_grant
            if previous_grant:
                self._request.resulting_grant = Grant.objects.create(
                    access=self._request.access,
                    granted_by=self._approver.username,
                    expires=expires_date,
                    previous_grant=previous_grant,
                )
            else:
                # Else create the access if it does not already exist and
                # then create the new grant
                access, _ = Access.objects.get_or_create(
                    user=self._request.access.user, role=self._request.access.role
                )
                self._request.resulting_grant = Grant.objects.create(
                    access=access,
                    granted_by=self._approver.username,
                    expires=expires_date,
                )
            # Copy the metadata from the request to the grant
            self._request.copy_metadata_to(self._request.resulting_grant)
        if self.cleaned_data["state"] in ["INCOMPLETE", "REJECTED"]:
            self._request.state = RequestState.REJECTED
            self._request.incomplete = True if self.cleaned_data["state"] == "INCOMPLETE" else False
            self._request.user_reason = self.cleaned_data["user_reason"]
            self._request.internal_reason = self.cleaned_data["internal_reason"]

        # Set the internal comment if the user is staff.
        if self._approver.is_staff and self.cleaned_data.get("internal_comment", False):
            self._request.internal_comment = self.cleaned_data["internal_comment"]

        self._request.save()
        return self._request
