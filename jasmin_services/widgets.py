"""
Custom form widgets for the ``jasmin_services`` app.
"""

import json

import django.urls
from django import forms
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.encoding import force_text


#####
# The AdminGfkObjectIdWidget widget wants an admin URL to convert a content type
# id and object id into a text representation of the object
#####
def generic_object_text(request):
    """
    Takes ``ct_id`` and ``pk`` as GET parameters and returns a text
    representation of the object.
    """
    try:
        ct_id = request.GET["ct_id"]
        pk = request.GET["pk"]
    except KeyError:
        return HttpResponse(
            status=400, content="Missing GET parameter(s).", content_type="text/plain"
        )
    try:
        obj = ContentType.objects.get_for_id(ct_id).get_object_for_this_type(pk=pk)
    except ObjectDoesNotExist:
        content = "Object does not exist."
    else:
        content = force_text(obj)
    return HttpResponse(content=content, content_type="text/plain")


# Monkey-patch AdminSite to include the view in all admins
admin_site_get_urls = admin.sites.AdminSite.get_urls
admin.sites.AdminSite.get_urls = lambda model_admin, *args, **kwargs: [
    *admin_site_get_urls(model_admin, *args, **kwargs),
    django.urls.re_path(
        r"^generic_object_text/$",
        model_admin.admin_view(generic_object_text),
        name="generic_object_text",
    ),
]


class AdminGfkContentTypeWidget(forms.Select):
    """
    Custom widget for selecting a content type for a generic foreign key.

    All this widget does is add a known class to the select.
    """

    def build_attrs(self, *args, **kwargs):
        attrs = super().build_attrs(*args, **kwargs)
        class_to_add = "gfk-contenttype"
        if "class" in attrs:
            attrs["class"] += " " + class_to_add
        else:
            attrs["class"] = class_to_add
        return attrs


class AdminGfkObjectIdWidget(forms.TextInput):
    """
    Custom widget for selecting an object id for a generic foreign key.

    This widget is designed to work in tandem with :py:class:`AdminGfkContentTypeWidget`.

    It piggy-backs on the Javascript already in place for raw id fields, but
    switches the model type for lookup depending on the selected content type.
    """

    class Media:
        js = (
            "admin/js/jquery.init.js",
            "admin/js/admin_gfk_objectid_widget.js",
        )

    def __init__(self, admin_site, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin_site = admin_site

    def build_attrs(self, *args, **kwargs):
        attrs = super().build_attrs(*args, **kwargs)
        class_to_add = "vForeignKeyRawIdAdminField gfk-objectid"
        if "class" in attrs:
            attrs["class"] += " " + class_to_add
        else:
            attrs["class"] = class_to_add
        # Get a map of content type id to lookup URL for all content types in
        # the current admin site
        ctype_url_map = {}
        for ctype in ContentType.objects.all():
            try:
                ctype_url_map[force_text(ctype.pk)] = reverse(
                    "admin:{}_{}_changelist".format(ctype.app_label, ctype.model),
                    current_app=self.admin_site.name,
                )
            except NoReverseMatch:
                pass
        # Set the map as a data attribute
        attrs["data-ctype-url-map"] = json.dumps(ctype_url_map)
        # This URL allows us to pass a content type id and object pk and get a text
        # representation back
        attrs["data-object-text-url"] = reverse(
            "admin:generic_object_text", current_app=self.admin_site.name
        )
        return attrs
