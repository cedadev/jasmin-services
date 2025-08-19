from django.contrib import admin
from django.contrib.admin.utils import quote
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.safestring import mark_safe

from jasmin_metadata.admin import HasMetadataModelAdmin
from jasmin_metadata.models import Metadatum

from ..actions import remind_pending
from ..forms import AdminRequestForm
from ..models import Request, RequestState, Role

# Load the admin for behaviours which are turned on.
from . import behaviour  # unimport:skip
from . import filters, request


class RequestAdmin(HasMetadataModelAdmin):
    list_display = (
        "access",
        "decide_link",
        "active",
        "state_html",
        "next_request",
        "previous_grant",
        "requested_at",
    )
    list_display_links = None
    list_filter = (
        filters.ServiceFilter,
        "access__role__name",
        ("access__user", admin.RelatedOnlyFieldListFilter),
        filters.ActiveListFilter,
        filters.StateListFilter,
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
    actions = ("remind_pending",)
    raw_id_fields = (
        "previous_request",
        "previous_grant",
    )
    readonly_fields = (
        "requested_at",
        "resulting_grant",
    )

    def get_form(self, request, obj=None, change=None, **kwargs):
        kwargs["form"] = AdminRequestForm
        return super().get_form(request, obj=obj, change=change, **kwargs)

    def get_queryset(self, request):
        # Annotate with information about active status
        return super().get_queryset(request).annotate_active()

    def remind_pending(self, request, queryset):
        """
        Admin action that sends reminders for requests that have been pending for
        too long.
        """
        remind_pending(queryset)

    remind_pending.short_description = "Send pending reminders"

    def decide_link(self, obj):
        if obj.active and obj.state == RequestState.PENDING:
            url = reverse(
                "jasmin_services:request_decide",
                kwargs={"pk": quote(obj.pk)},
            )
            here = reverse("admin:jasmin_services_request_changelist")
            return mark_safe(f'<a href="{url}?next={here}">Decide</a>')
        else:
            url = reverse(
                "admin:jasmin_services_request_change",
                args=(quote(obj.pk),),
                current_app=self.admin_site.name,
            )
            return mark_safe(f'<a href="{url}">Edit</a>')

    decide_link.short_description = "Actions"

    def state_html(self, obj):
        if obj.state == RequestState.PENDING:
            return "PENDING"
        elif obj.state == RequestState.APPROVED:
            return mark_safe('<span style="color: #00b300;">APPROVED</span>')
        elif obj.incomplete:
            return mark_safe('<span style="color: #e67a00; font-weight: bold;">INCOMPLETE</span>')
        else:
            return mark_safe('<span style="color: #e60000; font-weight: bold;">REJECTED</span>')

    state_html.short_description = "State"

    def active(self, obj):
        """
        Returns ``True`` if the given request is the active request for the
        service/role/user combination.
        """
        return obj.active

    active.boolean = True

    def get_metadata_form_class(self, request, obj=None):
        if not obj:
            return None
        try:
            return obj.access.role.metadata_form_class
        except Role.DoesNotExist:
            return None

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial["requested_by"] = request.user.username
        return initial

    def get_search_results(self, request, queryset, search_term):
        """Override search to include metadata values."""
        # Get the standard search results first
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        if search_term:
            request_content_type = ContentType.objects.get_for_model(Request)
            metadata_objects = Metadatum.objects.filter(content_type=request_content_type)

            matching_ids = []
            for metadata in metadata_objects:
                # Convert pickled value to string and search
                value_str = str(metadata.value) if metadata.value is not None else ""
                if search_term.lower() in value_str.lower():
                    matching_ids.append(metadata.object_id)

            if matching_ids:
                # Combine with existing queryset
                metadata_queryset = self.model.objects.filter(pk__in=matching_ids)
                queryset = queryset | metadata_queryset
                use_distinct = True

        return queryset, use_distinct
