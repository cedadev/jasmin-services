from django import http
from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.utils import quote
from django.shortcuts import redirect, render
from django.urls import re_path, reverse
from django.utils.safestring import mark_safe

from jasmin_metadata.admin import HasMetadataModelAdmin
from ..actions import remind_pending
from ..forms import AdminDecisionForm, AdminRequestForm
from ..models import (
    Grant,
    Request,
    RequestState,
    Role
)

# Load the admin for behaviours which are turned on.
from . import behaviour  # unimport:skip
from . import filters, request


class RequestAdmin(HasMetadataModelAdmin):
    list_display = (
        "role_link",
        "access",
        "active",
        "state_html",
        "next_request",
        "previous_grant",
        "requested_at",
    )
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

    def role_link(self, obj):
        if obj.active and obj.state == RequestState.PENDING:
            url = reverse(
                "admin:jasmin_services_request_decide",
                args=(quote(obj.pk),),
                current_app=self.admin_site.name,
            )
        else:
            url = reverse(
                "admin:jasmin_services_request_change",
                args=(quote(obj.pk),),
                current_app=self.admin_site.name,
            )
        return mark_safe('<a href="{}">{}</a>'.format(url, obj.access.role))

    role_link.short_description = "Service"

    def state_html(self, obj):
        if obj.state == RequestState.PENDING:
            return "PENDING"
        elif obj.state == RequestState.APPROVED:
            return '<span style="color: #00b300;">APPROVED</span>'
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

    def get_urls(self):
        return [
            re_path(
                r"^(.+)/decide/$",
                self.admin_site.admin_view(self.decide_request),
                name="jasmin_services_request_decide",
            ),
        ] + super().get_urls()

    def decide_request(self, request, pk):
        if not self.has_change_permission(request):
            raise PermissionDenied
        # Try to find the specified request amongst the pending, active requests
        try:
            pending = Request.objects.filter(state=RequestState.PENDING).filter_active().get(pk=pk)
        except Request.DoesNotExist:
            raise http.Http404(f"Request with primary key {pk} does not exist")
        # Process the form if this is a POST request, otherwise just set it up
        if request.method == "POST":
            form = AdminDecisionForm(pending, request.user, data=request.POST)
            if form.is_valid():
                form.save()
                self.message_user(request, "Decision made on request", messages.SUCCESS)
                return redirect(
                    "{}:jasmin_services_request_changelist".format(self.admin_site.name)
                )
        else:
            form = AdminDecisionForm(pending, request.user)
        # If the user requesting access has an active grant, find it
        previous_grant = pending.previous_grant

        grants = Grant.objects.filter(access=pending.access).filter_active()

        # Find all the rejected requests for this request chain.
        rejected = Request.objects.filter(
            access=pending.access,
            state=RequestState.REJECTED,
            previous_grant=pending.previous_grant,
        ).order_by("requested_at")

        context = {
            "title": "Decide Service Request",
            "form": form,
            "is_popup": (IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET),
            "add": True,
            "change": False,
            "has_delete_permission": False,
            "has_change_permission": True,
            "has_absolute_url": False,
            "opts": self.model._meta,
            "original": pending,
            "save_as": False,
            "show_save": True,
            "media": self.media + form.media,
            "rejected": rejected,
            "previous_grant": previous_grant,
            "grants": grants,
        }
        context.update(self.admin_site.each_context(request))
        request.current_app = self.admin_site.name
        return render(request, "admin/jasmin_services/request/decide.html", context)
