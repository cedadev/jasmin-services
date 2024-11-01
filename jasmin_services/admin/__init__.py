"""
Registration of models for the JASMIN services app with the admin interface.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import django.shortcuts
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from django.db import models
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import path, re_path
from django.utils.safestring import mark_safe
from jasmin_metadata.models import Form

from .. import models as service_models
from ..forms import admin_message_form_factory
from ..models import (
    Access,
    Category,
    Grant,
    Request,
    Role,
    RoleObjectPermission,
    Service
)
from ..widgets import AdminGfkContentTypeWidget, AdminGfkObjectIdWidget

# Load the admin for behaviours which are turned on.
from . import behaviour  # unimport:skip
from . import grant, request

# Register admins from submodules.
admin.site.register(Grant, grant.GrantAdmin)
admin.site.register(Request, request.RequestAdmin)


class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "num_members")
    search_fields = ("name", "member_uids")
    fieldsets = (
        (
            None,
            {"fields": ("name", "description", "member_uids")},
        ),
    )
    superuser_fieldsets = (
        (
            None,
            {"fields": ("name", "description", "member_uids")},
        ),
        (
            "Derived / Calculated Fields",
            {"fields": ("gidNumber",), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_members=models.Count("member_uids"))

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return self.superuser_fieldsets
        else:
            return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        # Name is readonly unless creating
        return ("name",) if obj else ()

    def num_members(self, obj):
        return obj.num_members

    num_members.description = "Number of members"
    num_members.short_description = "# members"
    num_members.admin_order_field = "num_members"


# Register the LDAP group models defined in settings using this admin
for grp in settings.JASMIN_SERVICES["LDAP_GROUPS"]:
    admin.site.register(getattr(service_models, grp["MODEL_NAME"]), GroupAdmin)


class ServiceInline(admin.TabularInline):
    model = Service
    fields = ("name_html", "summary", "hidden", "position")
    readonly_fields = fields[:-1]
    max_num = 0
    can_delete = False
    show_change_link = True

    def name_html(self, obj):
        return mark_safe("<code>{}</code>".format(obj.name))

    name_html.short_description = "name"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    inlines = (ServiceInline,)
    list_display = ("name", "long_name", "position", "num_services")
    list_editable = ("position",)
    search_fields = ("name", "long_name", "service__name")

    def num_services(self, obj):
        return obj.services.count()

    num_services.short_description = "# Services"


class RoleInline(admin.TabularInline):
    model = Role
    fields = ("name_html", "description", "hidden", "position")
    readonly_fields = fields[:-1]
    max_num = 0
    can_delete = False
    show_change_link = True

    def name_html(self, obj):
        return mark_safe("<code>{}</code>".format(obj.name))

    name_html.short_description = "name"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    inlines = (RoleInline,)
    list_display = (
        "full_name",
        "summary",
        "hidden",
        "disabled",
        "position",
        "details_link",
    )
    list_editable = ("position",)
    list_filter = ("category", "hidden", "disabled")
    search_fields = ("category__long_name", "category__name", "name", "summary")
    list_select_related = ("category",)
    ordering = ("disabled", "category__position", "-id")

    def full_name(self, obj):
        return str(obj)

    full_name.short_description = "Name"

    def get_role_permissions(self):
        return (
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Role),
                codename="view_users_role",
            ),
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Role),
                codename="send_message_role",
            ),
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Request),
                codename="decide_request",
            ),
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Role),
                codename="grant_role",
            ),
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Role),
                codename="revoke_role",
            ),
        )

    def create_role_object_permissions(self, role, target_role):
        permissions = self.get_role_permissions()
        RoleObjectPermission.objects.bulk_create(
            [
                RoleObjectPermission(
                    role=role,
                    permission=permission,
                    content_type=ContentType.objects.get_for_model(target_role),
                    object_pk=target_role.pk,
                )
                for permission in permissions
            ]
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # If creating the service, create the default roles
        from django.conf import settings

        default_form = Form.objects.get(pk=settings.JASMIN_SERVICES["DEFAULT_METADATA_FORM"])
        if not change:
            service = form.instance
            # Create the three default roles
            user_role, _ = service.roles.get_or_create(
                name="USER",
                defaults=dict(
                    description="Standard user role",
                    hidden=False,
                    position=100,
                    metadata_form=default_form,
                ),
            )
            deputy_role, _ = service.roles.get_or_create(
                name="DEPUTY",
                defaults=dict(
                    description="Service deputy manager role",
                    hidden=True,
                    position=200,
                    metadata_form=default_form,
                ),
            )
            self.create_role_object_permissions(deputy_role, user_role)
            manager_role, _ = service.roles.get_or_create(
                name="MANAGER",
                defaults=dict(
                    description="Service manager role",
                    hidden=True,
                    position=300,
                    metadata_form=default_form,
                ),
            )
            self.create_role_object_permissions(manager_role, user_role)
            self.create_role_object_permissions(manager_role, deputy_role)

    def get_urls(self):
        return [
            re_path(
                r"^(?P<service>[\w-]+)/message/$",
                self.admin_site.admin_view(self.support_message),
                name="jasmin_services_support_message",
            ),
            path(
                "<service>/retire",
                self.admin_site.admin_view(self.retire),
                name="jasmin_services_retire",
            ),
        ] + super().get_urls()

    def support_message(self, request, service):
        service = Service.objects.get(pk=service)
        MessageForm = admin_message_form_factory(service)
        if request.method == "POST":
            form = MessageForm(request.POST)
            if form.is_valid():
                EmailMessage(
                    subject=form.cleaned_data["subject"],
                    body=render_to_string(
                        "admin/jasmin_services/service/email_message.txt",
                        {
                            "sender": "JASMIN Support",
                            "message": form.cleaned_data["message"],
                            "reply_to": settings.JASMIN_SUPPORT_EMAIL,
                        },
                    ),
                    bcc=[u.email for u in form.cleaned_data["users"]],
                    from_email=settings.JASMIN_SUPPORT_EMAIL,
                    reply_to=[settings.JASMIN_SUPPORT_EMAIL],
                ).send()
                messages.success(request, "Message sent")
                return redirect("/admin/jasmin_services/service/{}".format(service.pk))
            else:
                messages.error(request, "Error with one or more fields")
        else:
            form = MessageForm()
        context = {
            "title": "{}: Send Support Message".format(service.name),
            "form": form,
            "opts": self.model._meta,
            "service": service,
            "media": self.media + form.media,
        }
        context.update(self.admin_site.each_context(request))
        request.current_app = self.admin_site.name
        return render(request, "admin/jasmin_services/service/message.html", context)

    def retire(self, request, service):
        """
        Admin action to retire a service.

        Retireing a service hides is from all user accessible interfaces, and
        """
        service = Service.objects.get(pk=service)
        if (
            request.method == "POST"
            and request.user.is_superuser
            and int(request.POST["service_id"]) == service.id
        ):
            # Disable the service.
            service.disabled = True
            service.save()

            # Find a list of current grants for the service.
            current_grants = Grant.objects.filter_active().filter(
                access__role__service=service,
                revoked=False,
            )
            # And revoke them en-masse.
            current_grants.update(
                revoked=True,
                user_reason="This service has been retired.",
                internal_reason=f"Service was retired by {request.user.username}.",
            )
            return django.shortcuts.redirect(f"/admin/jasmin_services/service/{service.id}/change")

        context = {
            "title": f"{service.name}: Retire",
            "opts": self.model._meta,
            "service": service,
        }
        return render(request, "admin/jasmin_services/service/retire.html", context)


class BehaviourInline(admin.StackedInline):
    class Media:
        js = (
            "admin/js/jquery.init.js",
            "admin/js/collapsible_inlines.js",
        )

    model = Role.behaviours.through
    extra = 0


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    In order to use autocomplete fields for permissions, they need to have an admin view.

    However we don't want permissions to be editable or listed in the index.
    """

    search_fields = (
        "name",
        "codename",
        "content_type__app_label",
        "content_type__model",
    )

    def has_module_permission(self, *args, **kwargs):
        return False

    def has_view_permission(self, *args, **kwargs):
        return True

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False


class RoleObjectPermissionInline(admin.StackedInline):
    class Media:
        js = (
            "admin/js/jquery.init.js",
            "admin/js/collapsible_inlines.js",
        )

    model = RoleObjectPermission
    extra = 0
    raw_id_fields = ("permission",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "content_type":
            kwargs["widget"] = AdminGfkContentTypeWidget
        if db_field.name == "object_pk":
            kwargs["widget"] = AdminGfkObjectIdWidget(self.admin_site)
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("full_name", "description", "hidden", "position")
    list_editable = ("position",)
    list_filter = (
        "service__category",
        ("service", admin.RelatedOnlyFieldListFilter),
        "name",
    )
    search_fields = (
        "service__category__long_name",
        "service__name",
        "name",
        "description",
    )
    inlines = (RoleObjectPermissionInline, BehaviourInline)
    exclude = ("behaviours",)
    autocomplete_fields = ("service",)

    def full_name(self, obj):
        return str(obj)

    full_name.short_description = "Name"

    def has_module_permission(self, request):
        # Prevent this admin showing up on the index page
        return False


class GrantInline(admin.TabularInline):
    model = Grant
    fields = ("active", "revoked", "expired", "expires")
    readonly_fields = fields[:-1]
    max_num = 0
    can_delete = False
    show_change_link = True


class RequestInline(admin.TabularInline):
    model = Request
    fields = ("active", "state")
    readonly_fields = fields[:-1]
    max_num = 0
    can_delete = False
    show_change_link = True


@admin.register(Access)
class AccessAdmin(admin.ModelAdmin):
    list_display = ("role", "user")
    fields = ("role", "user")
    autocomplete_fields = ("role", "user")
    search_fields = (
        "role__name",
        "role__service__name",
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
