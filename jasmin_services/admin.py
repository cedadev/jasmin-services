"""
Registration of models for the JASMIN services app with the admin interface.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from datetime import date
from urllib.parse import urlparse

from django.contrib import admin
from django.urls import reverse, resolve, Resolver404
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.conf.urls import url
from django.contrib.admin.options import IS_POPUP_VAR
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin.utils import quote
from django import http
from django.utils.safestring import mark_safe
from django.contrib.auth.models import Permission
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from polymorphic.admin import (
    PolymorphicParentModelAdmin,
    PolymorphicChildModelAdmin,
    PolymorphicChildModelFilter
)

from jasmin_metadata.models import Metadatum, Form
from jasmin_metadata.admin import HasMetadataModelAdmin

from .models import (
    Category, Service, Role, RoleObjectPermission,
    Grant, Request, RequestState,
    Behaviour, LdapTagBehaviour, LdapGroupBehaviour, JoinJISCMailListBehaviour
)
from .forms import AdminDecisionForm, AdminRevokeForm, LdapGroupBehaviourAdminForm, admin_message_form_factory
from .actions import (
    synchronise_service_access, send_expiry_notifications, remind_pending
)
from .widgets import AdminGfkContentTypeWidget, AdminGfkObjectIdWidget


class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'num_members')
    search_fields = ('name', 'member_uids')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'member_uids'),
        }),
    )
    superuser_fieldsets = (
        (None, {
            'fields': ('name', 'description', 'member_uids'),
        }),
        ('Derived / Calculated Fields', {
            'fields' : ('gidNumber', ),
            'classes' : ('collapse', )
        })
   )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            num_members = models.Count('member_uids')
        )

    def get_fieldsets(self, request, obj = None):
        if request.user.is_superuser:
            return self.superuser_fieldsets
        else:
            return self.fieldsets

    def get_readonly_fields(self, request, obj = None):
        # Name is readonly unless creating
        return ('name', ) if obj else ()

    def num_members(self, obj):
        return obj.num_members
    num_members.description = 'Number of members'
    num_members.short_description = '# members'
    num_members.admin_order_field = 'num_members'


# Register the LDAP group models defined in settings using this admin
from django.conf import settings
from . import models as service_models
for grp in settings.JASMIN_SERVICES['LDAP_GROUPS']:
    admin.site.register(getattr(service_models, grp['MODEL_NAME']), GroupAdmin)


class ServiceInline(admin.TabularInline):
    model = Service
    fields = ('name_html', 'summary', 'hidden', 'position')
    readonly_fields = fields[:-1]
    max_num = 0
    can_delete = False
    show_change_link = True

    def name_html(self, obj):
        return mark_safe('<code>{}</code>'.format(obj.name))
    name_html.short_description = 'name'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    inlines = (ServiceInline, )
    list_display = ('name', 'long_name', 'position', 'num_services')
    list_editable = ('position', )
    search_fields = ('name', 'long_name', 'service__name')

    def num_services(self, obj):
        return obj.services.count()
    num_services.short_description = '# Services'


class RoleInline(admin.TabularInline):
    model = Role
    fields = ('name_html', 'description', 'hidden', 'position')
    readonly_fields = fields[:-1]
    max_num = 0
    can_delete = False
    show_change_link = True

    def name_html(self, obj):
        return mark_safe('<code>{}</code>'.format(obj.name))
    name_html.short_description = 'name'


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    inlines = (RoleInline, )
    list_display = ('full_name', 'summary', 'hidden', 'position')
    list_editable = ('position', )
    list_filter = ('category', 'hidden')
    search_fields = ('category__long_name', 'category__name', 'name', 'summary')
    list_select_related = ('category', )

    def full_name(self, obj):
        return str(obj)
    full_name.short_description = 'Name'

    def get_role_permissions(self):
        return (
            Permission.objects.get(
                content_type = ContentType.objects.get_for_model(Role),
                codename = 'view_users_role',
            ),
            Permission.objects.get(
                content_type = ContentType.objects.get_for_model(Role),
                codename = 'send_message_role',
            ),
            Permission.objects.get(
                content_type = ContentType.objects.get_for_model(Request),
                codename = 'decide_request',
            ),
        )

    def create_role_object_permissions(self, role, target_role):
        permissions = self.get_role_permissions()
        RoleObjectPermission.objects.bulk_create([
            RoleObjectPermission(
                role = role,
                permission =  permission,
                content_type = ContentType.objects.get_for_model(target_role),
                object_pk = target_role.pk
            )
            for permission in permissions
        ])

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # If creating the service, create the default roles
        from django.conf import settings
        default_form = Form.objects.get(pk = settings.JASMIN_SERVICES['DEFAULT_METADATA_FORM'])
        if not change:
            service = form.instance
            # Create the three default roles
            user_role, _ = service.roles.get_or_create(
                name = 'USER',
                defaults = dict(
                    description = 'Standard user role',
                    hidden = False,
                    position = 100,
                    metadata_form = default_form
                )
            )
            deputy_role, _ = service.roles.get_or_create(
                name = 'DEPUTY',
                defaults = dict(
                    description = 'Service deputy manager role',
                    hidden = True,
                    position = 200,
                    metadata_form = default_form
                )
            )
            self.create_role_object_permissions(deputy_role, user_role)
            manager_role, _ = service.roles.get_or_create(
                name = 'MANAGER',
                defaults = dict(
                    description = 'Service manager role',
                    hidden = True,
                    position = 300,
                    metadata_form = default_form
                )
            )
            self.create_role_object_permissions(manager_role, user_role)
            self.create_role_object_permissions(manager_role, deputy_role)

    def get_urls(self):
        return [
            url(
                r'^(?P<service>[\w-]+)/message/$',
                self.admin_site.admin_view(self.support_message),
                name = 'jasmin_services_support_message'
            ),
        ] + super().get_urls()

    def support_message(self, request, service):
        service = Service.objects.get(pk=service)
        MessageForm = admin_message_form_factory(service)
        if request.method == 'POST':
            form = MessageForm(request.POST)
            if form.is_valid():
                EmailMessage(
                    subject = form.cleaned_data['subject'],
                    body = render_to_string('admin/jasmin_services/service/email_message.txt', {
                        'sender': 'JASMIN Support',
                        'message': form.cleaned_data['message'],
                        'reply_to': settings.JASMIN_SUPPORT_EMAIL,
                    }),
                    bcc = [u.email for u in form.cleaned_data['users']],
                    from_email = settings.JASMIN_SUPPORT_EMAIL,
                    reply_to = [settings.JASMIN_SUPPORT_EMAIL]
                ).send()
                messages.success(request, 'Message sent')
                return redirect('/admin/jasmin_services/service/{}'.format(service.pk))
            else:
                messages.error(request, 'Error with one or more fields')
        else:
            form = MessageForm()
        context = {
            'title' : '{}: Send Support Message'.format(service.name),
            'form': form,
            'opts': self.model._meta,
            'service': service,
            'media' : self.media + form.media,
        }
        context.update(self.admin_site.each_context(request))
        request.current_app = self.admin_site.name
        return render(request, 'admin/jasmin_services/service/message.html', context)


class BehaviourInline(admin.StackedInline):
    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/collapsible_inlines.js', )

    model = Role.behaviours.through
    extra = 0


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    In order to use autocomplete fields for permissions, they need to have an admin view.

    However we don't want permissions to be editable or listed in the index.
    """
    search_fields = ('name', 'codename', 'content_type__app_label', 'content_type__model')

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
        js = ('admin/js/jquery.init.js', 'admin/js/collapsible_inlines.js', )

    model = RoleObjectPermission
    extra = 0
    raw_id_fields = ('permission', )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'content_type':
            kwargs['widget'] = AdminGfkContentTypeWidget
        if db_field.name == 'object_pk':
            kwargs['widget'] = AdminGfkObjectIdWidget(self.admin_site)
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'description', 'hidden', 'position')
    list_editable = ('position', )
    list_filter = (
        'service__category',
        ('service', admin.RelatedOnlyFieldListFilter),
        'name',
    )
    search_fields = (
        'service__category__long_name',
        'service__name',
        'name',
        'description',
    )
    inlines = (RoleObjectPermissionInline, BehaviourInline)
    exclude = ('behaviours', )
    autocomplete_fields = ('service', )

    def full_name(self, obj):
        return str(obj)
    full_name.short_description = 'Name'

    def has_module_permission(self, request):
        # Prevent this admin showing up on the index page
        return False


@admin.register(JoinJISCMailListBehaviour)
class JoinJISCMailListBehaviourAdmin(PolymorphicChildModelAdmin):
    base_model = JoinJISCMailListBehaviour


@admin.register(LdapTagBehaviour)
class LdapTagBehaviourAdmin(PolymorphicChildModelAdmin):
    base_model = LdapTagBehaviour


@admin.register(LdapGroupBehaviour)
class LdapGroupBehaviourAdmin(PolymorphicChildModelAdmin):
    base_model = LdapGroupBehaviour
    form = LdapGroupBehaviourAdminForm


@admin.register(Behaviour)
class BehaviourAdmin(PolymorphicParentModelAdmin):
    base_model = Behaviour
    child_models = (
        LdapTagBehaviour,
        LdapGroupBehaviour,
        JoinJISCMailListBehaviour
    )
    polymorphic_list = True

    list_display = ('behaviour_as_string', )
    list_filter = (PolymorphicChildModelFilter, )

    def behaviour_as_string(self, obj):
        return str(obj)
    behaviour_as_string.short_description = 'Behaviour'

    def has_module_permission(self, request):
        # Prevent this admin showing up on the index page
        return False


class _ServiceFilter(admin.SimpleListFilter):
    title = 'Service'
    parameter_name = 'service_id'

    def lookups(self, request, model_admin):
        # Fetch the services and the categories at once
        services = Service.objects.all().select_related('category')
        return tuple((s.pk, str(s)) for s in services)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(role__service__pk = self.value())


class _ExpiredListFilter(admin.SimpleListFilter):
    title = 'Expired'
    parameter_name = 'expired'

    def lookups(self, request, model_admin):
        return (('1', 'Yes'), ('0', 'No'))

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(expires__lt = date.today())
        elif self.value() == '0':
            return queryset.filter(expires__gte = date.today())


class _ActiveListFilter(admin.SimpleListFilter):
    title = 'Active'
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        return (('1', 'Active only'), )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter_active()


@admin.register(Grant)
class GrantAdmin(HasMetadataModelAdmin):
    list_display = ('role', 'user', 'active',
                    'revoked', 'expired', 'expires', 'granted_at')
    list_filter = (
        _ServiceFilter,
        'role__name',
        ('user', admin.RelatedOnlyFieldListFilter),
        _ActiveListFilter,
        'revoked',
        _ExpiredListFilter
    )
    # This is expensive and unnecessary
    show_full_result_count = False
    search_fields = (
        'role__service__name',
        'role__name',
        'user__username',
        'user__email',
        'user__last_name'
    )
    actions = ('synchronise_service_access', 'send_expiry_notifications', 'revoke_grants')
    list_select_related = (
        'role',
        'role__service',
        'role__service__category',
        'user',
    )
    # Allow "Save as new" for quick duplication of grants
    save_as = True

    change_form_template = "admin/jasmin_services/grant/change_form.html"

    fields = ('role', 'user', 'granted_by',
              'expires', 'revoked', 'user_reason', 'internal_reason')
    autocomplete_fields = ('role', 'user')

    def get_queryset(self, request):
        # Annotate with information about active status
        return super().get_queryset(request).annotate_active()

    def synchronise_service_access(self, request, queryset):
        """
        Admin action that synchronises actual service access with the selected grants.
        """
        synchronise_service_access(queryset)
    synchronise_service_access.short_description = 'Synchronise service access'

    def send_expiry_notifications(self, request, queryset):
        """
        Admin action that sends expiry notifications, where required, for the selected grants.
        """
        send_expiry_notifications(queryset)
    send_expiry_notifications.short_description = 'Send expiry notifications'

    def revoke_grants(self, request, queryset):
        """
        Admin action that revokes the selected grants.
        """
        selected = queryset.values_list('pk', flat=True)
        selected_ids = '_'.join(str(pk) for pk in selected)

        return redirect(reverse(
                'admin:jasmin_services_bulk_revoke',
                kwargs = {'ids': selected_ids},
                current_app=self.admin_site.name)
            )
    revoke_grants.short_description = 'Revoke selected grants'

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

    def get_referring_request(self, request):
        """
        Tries to get the request which referred the user to the grant page.
        """
        # If the request is not a GET request, don't bother
        if request.method != 'GET':
            return None
        referrer = request.META.get('HTTP_REFERER')
        if not referrer:
            return None
        req_change_url_name = '{}_{}_change'.format(
            Request._meta.app_label, Request._meta.model_name
        )
        try:
            match = resolve(urlparse(referrer).path)
            if match.url_name == req_change_url_name:
                return Request.objects.get(pk = match.args[0])
        except (ValueError, Resolver404, Request.DoesNotExist):
            # These are expected errors
            return None

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial['granted_by'] = request.user.username
        # If there is data from a referring request to populate, do that
        referring = self.get_referring_request(request)
        if referring:
            initial.update(role = referring.role, user = referring.user)
        return initial

    def add_view(self, request, form_url = '', extra_context = None):
        # When adding a grant, add the ID of the referring request to the context if present
        if request.method == 'GET':
            referring = self.get_referring_request(request)
            if referring:
                extra_context = extra_context or {}
                extra_context.update(from_request = referring.pk)
        elif "_from_request" in request.POST:
            extra_context = extra_context or {}
            extra_context.update(from_request = request.POST["_from_request"])
        return super().add_view(request, form_url, extra_context)

    def get_metadata_form_class(self, request, obj = None):
        if not obj:
            return None
        try:
            return obj.role.metadata_form_class
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
            referring = Request.objects \
                .filter(pk = request.POST["_from_request"]) \
                .first()
        else:
            referring = self.get_referring_request(request)
        if referring:
            ctype = ContentType.objects.get_for_model(referring)
            metadata = Metadatum.objects.filter(
                content_type = ctype,
                object_id = referring.pk
            )
            return { d.key : d.value for d in metadata.all() }
        return super().get_metadata_form_initial_data(request, obj)

    def get_urls(self):
        return [
            url(
                r'^bulk_revoke/(?P<ids>[0-9_]+)/$',
                self.admin_site.admin_view(self.bulk_revoke),
                name = 'jasmin_services_bulk_revoke'
            ),
        ] + super().get_urls()

    def bulk_revoke(self, request, ids):
        ids = ids.split('_')
        if request.method == 'POST':
            form = AdminRevokeForm(data = request.POST)
            if form.is_valid():
                user_reason = form.cleaned_data['user_reason']
                internal_reason = form.cleaned_data['internal_reason']

                Grant.objects.filter(pk__in = ids).update(
                    revoked = True,
                    user_reason = user_reason,
                    internal_reason = internal_reason,
                )
                return redirect(
                    f'{self.admin_site.name}:jasmin_services_grant_changelist'
                )
        else:
            form = AdminRevokeForm()
        context = {
            'title' : 'Bulk Revoke Grants',
            'form': form,
            'opts': self.model._meta,
            'media' : self.media + form.media,
        }
        context.update(self.admin_site.each_context(request))
        request.current_app = self.admin_site.name
        return render(
            request,
            'admin/jasmin_services/grant/bulk_revoke.html',
            context
        )


class _StateListFilter(admin.SimpleListFilter):
    title = 'State'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return RequestState.choices()

    def queryset(self, request, queryset):
        value = self.value()
        if value in RequestState.all():
            return queryset.filter(state = value)


@admin.register(Request)
class RequestAdmin(HasMetadataModelAdmin):
    list_display = ('role_link', 'user', 'active', 'state_html', 'requested_at')
    list_filter = (
        _ServiceFilter,
        'role__name',
        ('user', admin.RelatedOnlyFieldListFilter),
        _ActiveListFilter,
        _StateListFilter
    )
    # This is expensive and unnecessary
    show_full_result_count = False
    search_fields = (
        'role__service__name',
        'role__name',
        'user__username',
        'user__email',
        'user__last_name'
    )
    fields = (
        'role',
        'user',
        'requested_by',
        'requested_at',
        'state',
        'incomplete',
        'grant',
        'user_reason',
        'internal_reason'
    )
    actions = ('remind_pending', )
    autocomplete_fields = ('role', 'user')
    raw_id_fields = ('grant', )
    readonly_fields = ('requested_at', )

    def get_queryset(self, request):
        # Annotate with information about active status
        return super().get_queryset(request).annotate_active()

    def remind_pending(self, request, queryset):
        """
        Admin action that sends reminders for requests that have been pending for
        too long.
        """
        remind_pending(queryset)
    remind_pending.short_description = 'Send pending reminders'

    def role_link(self, obj):
        if obj.active and obj.state == RequestState.PENDING:
            url = reverse('admin:jasmin_services_request_decide',
                          args = (quote(obj.pk), ),
                          current_app=self.admin_site.name)
        else:
            url = reverse('admin:jasmin_services_request_change',
                          args = (quote(obj.pk), ),
                          current_app=self.admin_site.name)
        return mark_safe('<a href="{}">{}</a>'.format(url, obj.role))
    role_link.short_description = 'Service'

    def state_html(self, obj):
        if obj.state == RequestState.PENDING:
            return 'PENDING'
        elif obj.state == RequestState.APPROVED:
            return mark_safe('<span style="color: #00b300;">APPROVED</span>')
        elif obj.incomplete:
            return mark_safe(
                '<span style="color: #e67a00; font-weight: bold;">INCOMPLETE</span>'
            )
        else:
            return mark_safe(
                '<span style="color: #e60000; font-weight: bold;">REJECTED</span>'
            )
    state_html.short_description = 'State'

    def active(self, obj):
        """
        Returns ``True`` if the given request is the active request for the
        service/role/user combination.
        """
        return obj.active
    active.boolean = True

    def get_metadata_form_class(self, request, obj = None):
        if not obj:
            return None
        try:
            return obj.role.metadata_form_class
        except Role.DoesNotExist:
            return None

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial['requested_by'] = request.user.username
        return initial

    def get_urls(self):
        return [
            url(
                r'^(.+)/decide/$',
                self.admin_site.admin_view(self.decide_request),
                name = 'jasmin_services_request_decide'
            ),
        ] + super().get_urls()

    def decide_request(self, request, pk):
        if not self.has_change_permission(request):
            raise PermissionDenied
        # Try to find the specified request amongst the pending, active requests
        try:
            pending = Request.objects  \
                .filter(state = RequestState.PENDING)  \
                .filter_active()  \
                .get(pk = pk)
        except Request.DoesNotExist:
            raise http.Http404(f"Request with primary key {pk} does not exist")
        # Process the form if this is a POST request, otherwise just set it up
        if request.method == 'POST':
            form = AdminDecisionForm(pending, request.user, data = request.POST)
            if form.is_valid():
                form.save()
                self.message_user(
                    request,
                    'Decision made on request',
                    messages.SUCCESS
                )
                return redirect(
                    '{}:jasmin_services_request_changelist'.format(
                        self.admin_site.name
                    )
                )
        else:
            form = AdminDecisionForm(pending, request.user)
        # If the user requesting access has an active grant, find it
        grant = pending.role.grants \
            .filter(user = pending.user)  \
            .filter_active()  \
            .first()
        # Find all the rejected requests for the role/user since the active grant
        rejected = pending.role.requests.filter(
            user = pending.user,
            state = RequestState.REJECTED
        )
        if grant:
            rejected = rejected.filter(requested_at__gt = grant.granted_at)
        rejected = rejected.order_by('requested_at')
        context = {
            'title': 'Decide Service Request',
            'form': form,
            'is_popup': (IS_POPUP_VAR in request.POST or
                         IS_POPUP_VAR in request.GET),
            'add': True,
            'change': False,
            'has_delete_permission': False,
            'has_change_permission': True,
            'has_absolute_url': False,
            'opts': self.model._meta,
            'original': pending,
            'save_as': False,
            'show_save': True,
            'media': self.media + form.media,
            'rejected': rejected,
            'grant': grant,
        }
        context.update(self.admin_site.each_context(request))
        request.current_app = self.admin_site.name
        return render(
            request,
            'admin/jasmin_services/request/decide.html',
            context
        )
