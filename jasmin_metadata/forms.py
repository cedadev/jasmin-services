"""
Django forms for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django import forms
from django.contrib.contenttypes.models import ContentType

from .models import Metadatum


class MetadataForm(forms.Form):
    """
    Form that can attach the collected data as metadata on an object.
    """

    def save(self, obj):
        """
        Saves the form's cleaned_data as metadata on the given object.

        .. warning::

            The object must be saved before calling this method.
        """
        content_type = ContentType.objects.get_for_model(obj)
        # Remove any existing metadata for the object
        Metadatum.objects.filter(content_type=content_type, object_id=obj.pk).delete()
        for key, value in self.cleaned_data.items():
            Metadatum.objects.create(
                content_type=content_type, object_id=obj.pk, key=key, value=value
            )
