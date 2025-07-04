import csv
import datetime as dt
from urllib.parse import urlparse

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
import django.db.models.fields.related
import django.db.models.fields.reverse_related
from django.shortcuts import redirect, render
from django.urls import Resolver404, re_path, resolve, reverse

from jasmin_metadata.admin import HasMetadataModelAdmin
from jasmin_metadata.models import Metadatum

from ..actions import send_expiry_notifications, synchronise_service_access
from ..forms import AdminGrantForm, AdminRevokeForm
from ..models import Grant, Request, Role
from . import filters


class GrantAdmin(HasMetadataModelAdmin):
    list_display = ("access", "active", "revoked", "expired", "expires", "granted_at")
    list_filter = (
        filters.ServiceFilter,
        "access__role__name",
        ("access__user", admin.RelatedOnlyFieldListFilter),
        filters.ActiveListFilter,
        "revoked",
        filters.ExpiredListFilter,
    )
    # This is expensive and unnecessary
    show_full_result_count = False
    search_fields = (
        "access__role__service__name",
        "access__role__name",
        "access__user__username",
        "access__user__email",
        "access__user__last_name",
    )
    actions = (
        "synchronise_service_access",
        "send_expiry_notifications",
        "revoke_grants",
        "export_to_csv",
    )
    list_select_related = (
        "access__role",
        "access__role__service",
        "access__role__service__category",
        "access__user",
    )
    # Allow "Save as new" for quick duplication of grants
    save_as = True

    change_form_template = "admin/jasmin_services/grant/change_form.html"

    raw_id_fields = (
        "access",
        "previous_grant",
    )

    def get_form(self, request, obj=None, change=None, **kwargs):
        kwargs["form"] = AdminGrantForm
        return super().get_form(request, obj=obj, change=change, **kwargs)

    def get_queryset(self, request):
        # Annotate with information about active status
        return super().get_queryset(request).annotate_active()

    def synchronise_service_access(self, request, queryset):
        """
        Admin action that synchronises actual service access with the selected grants.
        """
        synchronise_service_access(queryset)

    synchronise_service_access.short_description = "Synchronise service access"

    def send_expiry_notifications(self, request, queryset):
        """
        Admin action that sends expiry notifications, where required, for the selected grants.
        """
        send_expiry_notifications(queryset)

    send_expiry_notifications.short_description = "Send expiry notifications"

    def revoke_grants(self, request, queryset):
        """
        Admin action that revokes the selected grants.
        """
        selected = queryset.values_list("pk", flat=True)
        selected_ids = "_".join(str(pk) for pk in selected)

        return redirect(
            reverse(
                "admin:jasmin_services_bulk_revoke",
                kwargs={"ids": selected_ids},
                current_app=self.admin_site.name,
            )
        )

    revoke_grants.short_description = "Revoke selected grants"

    def active(self, obj):
        """
        Returns ``True`` if the given grant is the active grant for the
        service/role/user combination.
        """
        return obj.active

    active.boolean = True

    def expired(self, obj):
        """
        Returns ``True`` if the given grant has expired, ``False`` otherwise.
        """
        return obj.expired

    expired.boolean = True

    def export_to_csv(self, request, queryset):
        """Admin action to export the grant list to CSV."""
        opts = self.model._meta
        response = django.http.HttpResponse(content_type="text/plain")
        response["Content-Disposition"] = f"filename={opts.verbose_name}.csv"
        writer = csv.writer(response)
        # This is the list of fields which will be exported.
        export_fields = ["id", "access", "active", "revoked", "expired", "expires", "granted_at"]
        fields = [field for field in opts.get_fields() if field.name in export_fields]
        # Write a first row with header information
        writer.writerow([field.name for field in fields])
        # Write data rows
        for obj in queryset:
            data_row = []
            for field in fields:
                value = getattr(obj, field.name)
                if isinstance(value, dt.datetime):
                    value = value.strftime("%d/%m/%Y")
                data_row.append(value)
            writer.writerow(data_row)

        return response

    def get_referring_request(self, request):
        """
        Tries to get the request which referred the user to the grant page.
        """
        # If the request is not a GET request, don't bother
        if request.method != "GET":
            return None
        referrer = request.META.get("HTTP_REFERER")
        if not referrer:
            return None
        req_change_url_name = "{}_{}_change".format(
            Request._meta.app_label, Request._meta.model_name
        )
        try:
            match = resolve(urlparse(referrer).path)
            if match.url_name == req_change_url_name:
                return Request.objects.get(pk=match.args[0])
        except (ValueError, Resolver404, Request.DoesNotExist):
            # These are expected errors
            return None

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial["granted_by"] = request.user.username
        # If there is data from a referring request to populate, do that
        referring = self.get_referring_request(request)
        if referring:
            initial.update(role=referring.access.role, user=referring.access.user)
        return initial

    def add_view(self, request, form_url="", extra_context=None):
        # When adding a grant, add the ID of the referring request to the context if present
        if request.method == "GET":
            referring = self.get_referring_request(request)
            if referring:
                extra_context = extra_context or {}
                extra_context.update(from_request=referring.pk)
        elif "_from_request" in request.POST:
            extra_context = extra_context or {}
            extra_context.update(from_request=request.POST["_from_request"])
        return super().add_view(request, form_url, extra_context)

    def get_metadata_form_class(self, request, obj=None):
        if not obj:
            return None
        try:
            return obj.access.role.metadata_form_class
        except Role.DoesNotExist:
            return None

    def get_metadata_form_initial_data(self, request, obj):
        """
        Gets the initial data for the metadata form. By default, this just
        returns the metadata currently attached to the object.
        """
        if obj.pk:
            return super().get_metadata_form_initial_data(request, obj)
        # If the object has not been saved, try to get initial metadata from a
        # referring request
        if "_from_request" in request.POST:
            referring = Request.objects.filter(pk=request.POST["_from_request"]).first()
        else:
            referring = self.get_referring_request(request)
        if referring:
            ctype = ContentType.objects.get_for_model(referring)
            metadata = Metadatum.objects.filter(content_type=ctype, object_id=referring.pk)
            return {d.key: d.value for d in metadata.all()}
        return super().get_metadata_form_initial_data(request, obj)

    def get_urls(self):
        return [
            re_path(
                r"^bulk_revoke/(?P<ids>[0-9_]+)/$",
                self.admin_site.admin_view(self.bulk_revoke),
                name="jasmin_services_bulk_revoke",
            ),
        ] + super().get_urls()

    def bulk_revoke(self, request, ids):
        ids = ids.split("_")
        if request.method == "POST":
            form = AdminRevokeForm(data=request.POST)
            if form.is_valid():
                user_reason = form.cleaned_data["user_reason"]
                internal_reason = form.cleaned_data["internal_reason"]

                Grant.objects.filter(pk__in=ids).update(
                    revoked=True,
                    user_reason=user_reason,
                    internal_reason=internal_reason,
                )
                return redirect(f"{self.admin_site.name}:jasmin_services_grant_changelist")
        else:
            form = AdminRevokeForm()
        context = {
            "title": "Bulk Revoke Grants",
            "form": form,
            "opts": self.model._meta,
            "media": self.media + form.media,
        }
        context.update(self.admin_site.each_context(request))
        request.current_app = self.admin_site.name
        return render(request, "admin/jasmin_services/grant/bulk_revoke.html", context)
