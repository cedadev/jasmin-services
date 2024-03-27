"""
Base models for the JASMIN dynamic forms app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import socket
import uuid
from collections import OrderedDict
from ipaddress import IPv4Address

from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import RegexValidator
from django.db import models
from markdown_deux.templatetags.markdown_deux_tags import markdown_filter
from polymorphic.models import PolymorphicModel

from ..forms import MetadataForm


class Form(models.Model):
    """
    Model representing a form.
    """

    id = models.AutoField(primary_key=True)

    #: The name of the form
    name = models.CharField(
        max_length=200, help_text="A name for the form, to identify " "it in listings"
    )

    def __str__(self):
        return self.name

    def get_form(self):
        """
        Returns a :py:class:`~..forms.MetadataForm` for the configuration specified
        by this model.
        """
        return type(
            uuid.uuid4().hex,
            (MetadataForm,),
            OrderedDict((f.name, f.get_field()) for f in self.fields.all()),
        )


class Field(PolymorphicModel):
    """
    Model representing a form field.
    """

    id = models.AutoField(primary_key=True)

    class Meta:
        unique_together = ("form", "name")
        ordering = ("position", "name")

    #: The form field class to use for fields of this type
    form_field_class = None

    #: The form that the field belongs to
    form = models.ForeignKey(
        Form, models.CASCADE, related_name="fields", related_query_name="field"
    )
    #: The name of the field
    name = models.CharField(
        max_length=50,
        help_text="Short name for the field (as used in code)",
        validators=[
            RegexValidator(
                regex="^[a-zA-Z_][a-zA-Z0-9_]*$",
                message="Must be usable as a Python variable name",
            )
        ],
    )
    #: The label for the field
    label = models.CharField(
        max_length=250, help_text="Label for the field (displayed to the user)"
    )
    #: Whether the field is required
    required = models.BooleanField(default=True, help_text="Is the field required?")
    #: Help text for the field
    help_text = models.TextField(
        help_text="Help text for the field. Markdown syntax is permitted.", blank=True
    )
    #: Used for ordering
    position = models.PositiveIntegerField(
        default=0,
        help_text="Defines the order in which fields appear in the form. "
        "Fields are ordered in ascending order by this number, "
        "then alphabetically by name within that.",
    )

    def field_info(self):
        """
        Provides extra information about the field as a string for display in the admin.
        """
        return self._meta.verbose_name

    def __str__(self):
        return self.name

    def get_field(self):
        """
        Returns a Django form field configured as specified by this model.
        """
        if not self.form_field_class:
            raise ImproperlyConfigured(
                "form_field_class must be set to a subclass of django.forms.Field"
            )
        return self.form_field_class(**self.get_field_kwargs())

    def get_field_kwargs(self):
        """
        The kwargs to pass to the form field constructor.
        """
        return {
            "required": self.required,
            "label": self.label,
            # Render the help text as markdown
            "help_text": markdown_filter(self.help_text),
        }


class BooleanField(Field):
    """
    Model for a boolean field.
    """

    class Meta:
        verbose_name = "Boolean field"

    form_field_class = forms.BooleanField


class UserChoice(models.Model):
    """
    Model for a choice for :py:class:`ChoiceField`.
    """

    id = models.AutoField(primary_key=True)

    value = models.CharField(
        unique=True, max_length=250, help_text="The value that the choice represents"
    )
    display = models.CharField(
        max_length=250, help_text="How the value will be displayed to the user"
    )

    def __str__(self):
        return "{} : {}".format(self.value, self.display)


class ChoiceFieldBase(Field):
    """
    Base model for fields that allow selection from a number of choices.
    """

    choices = models.ManyToManyField(UserChoice)

    def get_choices(self):
        return [(c.value, c.display) for c in self.choices.all()]

    def get_field_kwargs(self):
        return dict(super().get_field_kwargs(), choices=self.get_choices())


class ChoiceField(ChoiceFieldBase):
    """
    Model for a choice field, i.e. a field that allows the user to select from a
    set of pre-defined choices.
    """

    class Meta:
        verbose_name = "Choice field"

    form_field_class = forms.ChoiceField

    def get_choices(self):
        # For a single-choice field, include a null choice
        choices = super().get_choices()
        choices.insert(0, ("", "---------"))
        return choices


class MultipleChoiceField(ChoiceFieldBase):
    """
    Model for a multiple-choice field, i.e. a field that allows the user to select
    many values from a set of pre-defined choices.
    """

    class Meta:
        verbose_name = "Multiple choice field"

    form_field_class = forms.MultipleChoiceField

    def get_field_kwargs(self):
        # Use checkboxes as the default widget for multiple-select
        return dict(super().get_field_kwargs(), widget=forms.CheckboxSelectMultiple)


class DateField(Field):
    """
    Model for a date field.
    """

    class Meta:
        verbose_name = "Date field"

    form_field_class = forms.DateField

    def get_field_kwargs(self):
        return dict(
            super().get_field_kwargs(),
            input_formats=["%Y-%m-%d"],
            widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        )


class DateTimeField(Field):
    """
    Model for a date-time field.
    """

    class Meta:
        verbose_name = "Date-time field"

    form_field_class = forms.DateTimeField

    def get_field_kwargs(self):
        return dict(
            super().get_field_kwargs(),
            input_formats=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"],
            widget=forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M:%S", attrs={"type": "datetime-local"}
            ),
        )


class TimeField(Field):
    """
    Model for a time field.
    """

    class Meta:
        verbose_name = "Time field"

    form_field_class = forms.TimeField

    def get_field_kwargs(self):
        return dict(
            super().get_field_kwargs(),
            widget=forms.TimeInput(format="%H:%M:%S", attrs={"type": "time"}),
        )


class IntegerField(Field):
    """
    Model for an integer field.
    """

    class Meta:
        verbose_name = "Integer field"

    form_field_class = forms.IntegerField

    min_value = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Minimum value",
        help_text="Minimum value allowed for input, or blank for no minimum",
    )
    max_value = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Maximum value",
        help_text="Maximum value allowed for input, or blank for no maximum",
    )

    def get_field_kwargs(self):
        kwargs = super().get_field_kwargs()
        if self.min_value is not None:
            kwargs.update(min_value=self.min_value)
        if self.max_value is not None:
            kwargs.update(max_value=self.max_value)
        return kwargs


class FloatField(Field):
    """
    Model for a float field.
    """

    class Meta:
        verbose_name = "Float field"

    form_field_class = forms.FloatField

    min_value = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Minimum value",
        help_text="Minimum value allowed for input, or blank for no minimum",
    )
    max_value = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Maximum value",
        help_text="Maximum value allowed for input, or blank for no maximum",
    )

    def get_field_kwargs(self):
        kwargs = super().get_field_kwargs()
        if self.min_value is not None:
            kwargs.update(min_value=self.min_value)
        if self.max_value is not None:
            kwargs.update(max_value=self.max_value)
        return kwargs


class TextFieldBase(Field):
    """
    Base model for text fields.
    """

    min_length = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Minimum length",
        help_text="Minimum length allowed for input, or blank for no minimum",
    )
    max_length = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Maximum length",
        help_text="Maximum length allowed for input, or blank for no maximum",
    )

    def get_field_kwargs(self):
        kwargs = super().get_field_kwargs()
        if self.min_length is not None:
            kwargs.update(min_length=self.min_length)
        if self.max_length is not None:
            kwargs.update(max_length=self.max_length)
        return kwargs


class SingleLineTextField(TextFieldBase):
    """
    Model for a single-line text field (i.e. an ``input``).
    """

    class Meta:
        verbose_name = "Single-line text field"

    form_field_class = forms.CharField


class MultiLineTextField(TextFieldBase):
    """
    Model for a single-line text field (i.e. an ``input``).
    """

    class Meta:
        verbose_name = "Multi-line text field"

    form_field_class = forms.CharField

    def get_field_kwargs(self):
        return dict(super().get_field_kwargs(), widget=forms.Textarea(attrs={"rows": 5}))


class EmailField(TextFieldBase):
    """
    Model for an email field.
    """

    class Meta:
        verbose_name = "Email field"

    form_field_class = forms.EmailField


class IPv4Field(TextFieldBase):
    """
    Model for a field that accepts IPv4 addresses.
    """

    class Meta:
        verbose_name = "IPv4 address field"

    form_field_class = forms.GenericIPAddressField

    require_reverse_dns_lookup = models.BooleanField(default=False)

    def get_field_kwargs(self):
        return dict(
            super().get_field_kwargs(),
            protocol="IPv4",
            validators=[self.validate_reverse_dns],
        )

    def validate_reverse_dns(self, value):
        if self.require_reverse_dns_lookup:
            # If the value is not a valid IPv4 address, do nothing
            try:
                _ = IPv4Address(value)
            except ValueError:
                return
            try:
                _ = socket.gethostbyaddr(value)[0]
            except Exception:
                raise ValidationError("Reverse DNS lookup failed")


class RegexField(TextFieldBase):
    """
    Model for a field that accepts values that pass a regex.
    """

    class Meta:
        verbose_name = "Regex field"

    form_field_class = forms.RegexField

    regex = models.CharField(
        max_length=250, help_text="The Python-formatted regular expression to match"
    )
    error_message = models.CharField(
        default="Not a valid value.",
        max_length=250,
        help_text="The error message returned to the user if the supplied value " "fails the regex",
    )

    def get_field_kwargs(self):
        return dict(
            super().get_field_kwargs(),
            regex=self.regex,
            error_messages={"invalid": self.error_message},
        )


class SlugField(TextFieldBase):
    """
    Model for a field that accepts valid slugs (i.e. for URLs).
    """

    class Meta:
        verbose_name = "Slug field"

    form_field_class = forms.SlugField


class URLField(TextFieldBase):
    """
    Model for a field that accepts valid URLs.
    """

    class Meta:
        verbose_name = "URL field"

    form_field_class = forms.URLField
