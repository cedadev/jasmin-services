"""
Module containing classes for integration of metadata with the Django admin site.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import django.utils.encoding
from django import forms
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.contenttypes.models import ContentType
from polymorphic.admin import PolymorphicInlineSupportMixin, StackedPolymorphicInline

from .models import *


@admin.register(UserChoice)
class UserChoiceAdmin(admin.ModelAdmin):
    prepopulated_fields = {"display": ("value",)}


class FieldInline(StackedPolymorphicInline):
    model = Field
    child_inlines = []


class BooleanFieldInline(StackedPolymorphicInline.Child):
    model = BooleanField


FieldInline.child_inlines.append(BooleanFieldInline)


class SingleLineTextFieldInline(StackedPolymorphicInline.Child):
    model = SingleLineTextField


FieldInline.child_inlines.append(SingleLineTextFieldInline)


class MultiLineTextFieldInline(StackedPolymorphicInline.Child):
    model = MultiLineTextField


FieldInline.child_inlines.append(MultiLineTextFieldInline)


class EmailFieldInline(StackedPolymorphicInline.Child):
    model = EmailField


FieldInline.child_inlines.append(EmailFieldInline)


class IPv4FieldInline(StackedPolymorphicInline.Child):
    model = IPv4Field


FieldInline.child_inlines.append(IPv4FieldInline)


class RegexFieldInline(StackedPolymorphicInline.Child):
    model = RegexField


FieldInline.child_inlines.append(RegexFieldInline)


class SlugFieldInline(StackedPolymorphicInline.Child):
    model = SlugField


FieldInline.child_inlines.append(SlugFieldInline)


class URLFieldInline(StackedPolymorphicInline.Child):
    model = URLField


FieldInline.child_inlines.append(URLFieldInline)


class IntegerFieldInline(StackedPolymorphicInline.Child):
    model = IntegerField


FieldInline.child_inlines.append(IntegerFieldInline)


class FloatFieldInline(StackedPolymorphicInline.Child):
    model = FloatField


FieldInline.child_inlines.append(FloatFieldInline)


class DateFieldInline(StackedPolymorphicInline.Child):
    model = DateField


FieldInline.child_inlines.append(DateFieldInline)


class DateTimeFieldInline(StackedPolymorphicInline.Child):
    model = DateTimeField


FieldInline.child_inlines.append(DateTimeFieldInline)


class TimeFieldInline(StackedPolymorphicInline.Child):
    model = TimeField


FieldInline.child_inlines.append(TimeFieldInline)


class ChoiceFieldInline(StackedPolymorphicInline.Child):
    model = ChoiceField
    filter_horizontal = ("choices",)


FieldInline.child_inlines.append(ChoiceFieldInline)


class MultipleChoiceFieldInline(StackedPolymorphicInline.Child):
    model = MultipleChoiceField
    filter_horizontal = ("choices",)


FieldInline.child_inlines.append(MultipleChoiceFieldInline)


@admin.register(Form)
class FormAdmin(PolymorphicInlineSupportMixin, admin.ModelAdmin):
    class Media:
        js = (
            # mutationobserver polyfill from cloudflare CDN
            "https://cdnjs.cloudflare.com/ajax/libs/webcomponentsjs/0.7.23/MutationObserver.min.js",
            # mutationobserver plugin for jQuery
            "admin/metadata/jquery.initialize.js",
            "admin/metadata/formfield_inlines.js",
        )

    inlines = (FieldInline,)
    list_display = ("name", "n_fields")
    # Allow "Save as new" for quick duplication of forms
    save_as = True

    def n_fields(self, obj):
        return obj.fields.count()

    n_fields.short_description = "# fields"


################################################################################
################################################################################


class HasMetadataModelAdmin(admin.ModelAdmin):
    """
    ``ModelAdmin`` for use with models that may have metadata attached.
    """

    #: The metadata form class to use
    #: Must inherit from :py:class:`~.models.MetadataForm`
    metadata_form_class = None

    change_form_template = "admin/change_form_metadata.html"

    def get_metadata_form_class(self, request, obj):
        """
        Returns the metadata form to use for the given object.

        The returned form must inherit from :py:class:`~.forms.MetadataForm`.
        """
        return self.metadata_form_class

    def get_metadata_form_initial_data(self, request, obj):
        """
        Gets the initial data for the metadata form. By default, this just
        returns the metadata currently attached to the object.
        """
        ctype = ContentType.objects.get_for_model(obj)
        metadata = Metadatum.objects.filter(content_type=ctype, object_id=obj.pk)
        return {d.key: d.value for d in metadata.all()}

    def save_model(self, request, obj, form, change):
        #####
        ## Override save_model to only save the model if the metadata is also valid
        #####
        metadata_form_class = self.get_metadata_form_class(request, obj)
        # If there is no metadata form, behave as normal
        if not metadata_form_class:
            return super().save_model(request, obj, form, change)
        # If the metadata is valid, save the object and the metadata
        if "_has_metadata" in request.POST:
            metadata_form = metadata_form_class(data=request.POST, prefix="metadata")
            if metadata_form.is_valid():
                super().save_model(request, obj, form, change)
                metadata_form.save(obj)

    def response_add(self, request, obj, post_url_continue=None):
        #####
        ## Override response_add to collect metadata after the object is fully
        ## specified
        ##
        ## This is primarily to allow us to deal with the situation where the
        ## required metadata is dependent on an objects state in an intuitive way
        #####
        # If there is no metadata form, behave as normal
        metadata_form_class = self.get_metadata_form_class(request, obj)
        # If there is no metadata form, behave as normal
        if not metadata_form_class:
            return super().response_add(request, obj, post_url_continue)
        if "_has_metadata" in request.POST:
            # If the submit supposedly has metadata, validate it
            # If the metadata is valid (and hence has been saved), behave as normal
            metadata_form = metadata_form_class(data=request.POST, prefix="metadata")
            if metadata_form.is_valid():
                return super().response_add(request, obj, post_url_continue)
        else:
            # If there is no metadata in the submit, create the form
            metadata_form = metadata_form_class(
                initial=self.get_metadata_form_initial_data(request, obj),
                prefix="metadata",
            )
        #######
        ## THIS CODE IS SIMILAR TO changeform_view
        #######
        # When rendering the metadata form, we also render the object form with
        # all the elements hidden
        parent_form_class = self.get_form(request)
        parent_form = parent_form_class(request.POST, request.FILES)
        # Make all the fields in the parent form hidden
        for field in parent_form.fields:
            parent_form.fields[field].widget = forms.HiddenInput()
        admin_form = helpers.AdminForm(
            parent_form,
            list(self.get_fieldsets(request, obj)),
            self.get_prepopulated_fields(request, obj),
            self.get_readonly_fields(request, obj),
            model_admin=self,
        )
        media = self.media + admin_form.media
        metadata_admin_form = helpers.AdminForm(
            metadata_form,
            # Put all the fields in one fieldset
            [(None, {"fields": list(metadata_form.fields.keys())})],
            # No pre-populated fields
            {},
        )
        errors = helpers.AdminErrorList(parent_form, [])
        if metadata_form.errors:
            errors.extend(metadata_form.errors.values())
        context = dict(
            self.admin_site.each_context(request),
            title="Set metadata for {}".format(
                django.utils.encoding.force_str(self.model._meta.verbose_name)
            ),
            adminform=admin_form,
            metadata_form=metadata_admin_form,
            object_id=obj.pk,
            original=obj,
            is_popup=("_popup" in request.POST or "_popup" in request.GET),
            to_field=request.POST.get("_to_field", request.GET.get("_to_field")),
            media=media,
            inline_admin_formsets=[],
            errors=errors,
            preserved_filters=self.get_preserved_filters(request),
        )
        return self.render_change_form(request, context, add=True, change=False, obj=obj)

    def response_change(self, request, obj):
        #####
        ## Override response_change to ensure that the metadata is valid before
        ## proceeding with the normal action
        #####
        # If there is no metadata form, behave as normal
        metadata_form_class = self.get_metadata_form_class(request, obj)
        # If there is no metadata form, behave as normal
        if not metadata_form_class:
            return super().response_change(request, obj)
        if "_has_metadata" in request.POST:
            # If the submit supposedly has metadata, validate it
            # If the metadata is valid (and hence has been saved), behave as normal
            metadata_form = metadata_form_class(data=request.POST, prefix="metadata")
            if metadata_form.is_valid():
                return super().response_change(request, obj)
        #######
        ## If metadata is invalid, we essentially need to replicate part of
        ## changeform_view to re-display the form
        #######
        parent_form_class = self.get_form(request)
        parent_form = parent_form_class(request.POST, request.FILES, instance=obj)
        admin_form = helpers.AdminForm(
            parent_form,
            list(self.get_fieldsets(request, obj)),
            self.get_prepopulated_fields(request, obj),
            self.get_readonly_fields(request, obj),
            model_admin=self,
        )
        media = self.media + admin_form.media
        context = dict(
            self.admin_site.each_context(request),
            title="Change {}".format(
                django.utils.encoding.force_str(self.model._meta.verbose_name)
            ),
            adminform=admin_form,
            object_id=obj.pk,
            original=obj,
            is_popup=("_popup" in request.POST or "_popup" in request.GET),
            to_field=request.POST.get("_to_field", request.GET.get("_to_field")),
            media=media,
            inline_admin_formsets=[],
            errors=helpers.AdminErrorList(parent_form, []),
            preserved_filters=self.get_preserved_filters(request),
        )
        return self.render_change_form(request, context, add=False, change=True, obj=obj)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        #####
        ## Override render_change_form to show the metadata form as an additional
        ## fieldset on change pages
        #####
        if change:
            metadata_form_class = self.get_metadata_form_class(request, obj)
            if metadata_form_class:
                if request.method == "POST":
                    metadata_form = metadata_form_class(data=request.POST, prefix="metadata")
                    # Force a validation - we don't really care about the result here
                    metadata_form.is_valid()
                else:
                    # If there is no metadata in the submit, create the form
                    metadata_form = metadata_form_class(
                        initial=self.get_metadata_form_initial_data(request, obj),
                        prefix="metadata",
                    )
                context["metadata_form"] = helpers.AdminForm(
                    metadata_form,
                    # Put all the fields in one fieldset
                    [("Metadata", {"fields": list(metadata_form.fields.keys())})],
                    # No pre-populated fields
                    {},
                )
                context["errors"].extend(metadata_form.errors.values())
        return super().render_change_form(request, context, add, change, form_url, obj)
