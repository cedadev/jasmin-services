"""
Module defining views for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import logging
import functools
import socket
from datetime import date

from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_safe
from django import http
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, OuterRef, Exists
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.http import urlquote
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test

from django.contrib.auth.decorators import login_required

from .models import Grant, Request, RequestState, Category, Service, Role
from .forms import DecisionForm, message_form_factory


_log = logging.getLogger(__name__)


@require_safe
@login_required
def service_list(request, category):
    """
    Handler for ``/<category>/``.

    Responds to GET requests only. The user must be authenticated.

    Lists the available services for the given category, along with some basic info
    about the current user's access.
    """
    try:
        category = Category.objects.get(name = category)
    except Category.DoesNotExist:
        raise http.Http404('Category does not exist')
    # Get the visible categories for the user
    # A category is visible if it contains a visible service
    # We include the current category, even if it would not normally be visible
    # Because of the way the data model works, it is sufficient to check if the
    # user has ever had a request or grant for a service, rather than
    # specifically an active one - if they have at least one, then they have an
    # active one
    # Django doesn't allow EXISTS subqueries to be used in filters - they must
    # be annotated first
    categories = Category.objects  \
        .annotate(
            has_grant = Exists(
                Grant.objects.filter(
                    role__service__category = OuterRef('pk'),
                    user = request.user
                )
            ),
            has_request = Exists(
                Request.objects.filter(
                    role__service__category = OuterRef('pk'),
                    user = request.user
                )
            )
        )  \
        .filter(
            Q(pk = category.pk) |
            Q(service__hidden = False) |
            Q(has_grant = True) |
            Q(has_request = True)
        )  \
        .distinct()  \
        .values_list('name', 'long_name')
    # Get the services in this category that are visible to the user
    services = category.services  \
        .annotate(
            has_grant = Exists(
                Grant.objects.filter(
                    role__service = OuterRef('pk'),
                    user = request.user
                )
            ),
            has_request = Exists(
                Request.objects.filter(
                    role__service = OuterRef('pk'),
                    user = request.user
                )
            )
        )  \
        .filter(
            Q(hidden = False) |
            Q(has_grant = True) |
            Q(has_request = True)
        )
    # If there is a search term, factor that in
    query = request.GET.get('query', '')
    if query:
        services = services.filter(
            Q(name__icontains = query) |
            Q(summary__icontains = query) |
            Q(description__icontains = query)
        )
    # A count of this queryset is almost as expensive as the query, so force it
    services = list(services.distinct().prefetch_related('roles'))
    # Get a paginator for the services
    paginator = Paginator(
        services,
        getattr(settings, 'JASMIN_SERVICES', {}).get('SERVICES_PER_PAGE', 5)
    )
    try:
        page = paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    # Get the active grants and requests for the user, as these define the visible
    # services and categories, along with the hidden flag on the service itself
    grants = Grant.objects  \
        .filter(user = request.user)  \
        .filter_active()  \
        .select_related('role')
    requests = Request.objects  \
        .filter(user = request.user)  \
        .filter_active()  \
        .select_related('role')
    return render(request, 'jasmin_services/service_list.html', {
        'categories': categories,
        'current_category': category,
        # services is a list of (service, roles) tuples
        # roles is a list of (role, grant or None, request or None) tuples
        'services': [
            (
                service,
                [
                    (
                        role,
                        next((g for g in grants if g.role == role), None),
                        next((r for r in requests if r.role == role), None)
                    )
                    for role in service.roles.all()
                ]
            )
            for service in page
        ],
        'page': page,
        'preserved_filters': 'query={}'.format(urlquote(request.GET['query']))
                             if 'query' in request.GET else ''
    })


@require_safe
@login_required
def my_services(request):
    """
    Handler for ``/my_services/``.

    Responds to GET requests only. The user must be authenticated.

    Displays all of the services for which the user has an active grant or request.
    """
    # Get the visible categories for the user
    # A category is visible if it contains a visible service
    # If a service is hidden, it is visible if the user has a grant or request
    # for one of its roles
    # Because of the way the data model works, it is sufficient to check if the
    # user has ever had a request or grant for a service, rather than
    # specifically an active one - if they have at least one, then they have an
    # active one
    # Django doesn't allow EXISTS subqueries to be used in filters - they must
    # be annotated first
    categories = Category.objects  \
        .annotate(
            has_grant = Exists(
                Grant.objects.filter(
                    role__service__category = OuterRef('pk'),
                    user = request.user
                )
            ),
            has_request = Exists(
                Request.objects.filter(
                    role__service__category = OuterRef('pk'),
                    user = request.user
                )
            )
        )  \
        .filter(
            Q(service__hidden = False) |
            Q(has_grant = True) |
            Q(has_request = True)
        )  \
        .distinct()  \
        .values_list('name', 'long_name')
    # Get the active grants and requests for the user, as these define the visible
    # services and categories, along with the hidden flag on the service itself
    all_grants = Grant.objects  \
        .filter(user = request.user)  \
        .filter_active()  \
        .select_related('role')
    all_requests = Request.objects  \
        .filter(user = request.user)  \
        .filter_active()  \
        .select_related('role')
    # Apply filters, making sure to maintain a reference to the full lists of
    # grants and requests
    grants = all_grants
    requests = all_requests
    # Only apply filters if _apply_filters is present in the GET params
    if '_apply_filters' in request.GET:
        # Work out if any filters were checked
        checked = {
            f
            for f in [
                'active',
                'revoked',
                'expired',
                'expiring',
                'rejected',
                'pending'
            ]
            if f in request.GET
        }
        # Apply any filters to the grants and requests
        if 'active' not in checked:
            # Make sure we don't include expiring grants in active
            grants = grants.exclude(
                revoked = False,
                expires__gte = date.today() + relativedelta(months = 2)
            )
        if 'revoked' not in checked:
            grants = grants.exclude(revoked = True)
        if 'expired' not in checked:
            grants = grants.exclude(revoked = False, expires__lt = date.today())
        if 'expiring' not in checked:
            grants = grants.exclude(
                revoked = False,
                expires__lt = date.today() + relativedelta(months = 2)
            )
        if 'rejected' not in checked:
            requests = requests.exclude(state = RequestState.REJECTED)
        if 'pending' not in checked:
            requests = requests.exclude(state = RequestState.PENDING)
    else:
        # If not applying filters, check all the filter checkboxes
        checked = {
            'active',
            'revoked',
            'expired',
            'expiring',
            'rejected',
            'pending'
        }
    # Get the services that match the grants
    # Since the count for this takes as long as the query, force it to
    # a list now
    services = list(
        Service.objects
            .filter(
                Q(role__grant__in = grants) |
                Q(role__request__in = requests)
            )
            .distinct()
            .prefetch_related('roles')
            .select_related('category')
    )
    # Get a paginator for the services
    paginator = Paginator(
        services,
        getattr(settings, 'JASMIN_SERVICES', {}).get('SERVICES_PER_PAGE', 5)
    )
    try:
        page = paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    # Only preserve filters if they were applied
    if '_apply_filters' in request.GET:
        preserved_filters = set(checked)
        preserved_filters.add('_apply_filters')
    else:
        preserved_filters = set()
    return render(request, 'jasmin_services/my_services/service_list.html', {
        'categories': categories,
        # Pass a dummy 'current category'
        'current_category': {
            'name': 'my_services',
            'long_name': 'My Services',
        },
        # services is a list of (service, roles) tuples
        # roles is a list of (role, grant or None, request or None) tuples
        'services': [
            (
                service,
                [
                    (
                        role,
                        next((g for g in all_grants if g.role == role), None),
                        next((r for r in all_requests if r.role == role), None)
                    )
                    for role in service.roles.all()
                ]
            )
            for service in page
        ],
        'page': page,
        'checked': checked,
        'preserved_filters': '&'.join(
            '{}=1'.format(f) for f in preserved_filters
        ),
    })


def with_service(view):
    """
    View decorator that takes a service type and service name and turns them
    into a service for the underlying view.

    If the service is not a valid service, a 404 is raised.
    """
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            kwargs['service'] = Service.objects.get(
                category__name = kwargs.pop('category'),
                name = kwargs.pop('service')
            )
        except ObjectDoesNotExist:
            raise http.Http404("Service does not exist")
        return view(*args, **kwargs)
    return wrapper


def redirect_to_service(service, view_name = 'service_details'):
    """
    Returns a redirect response to the given service on the service list page.
    """
    return redirect('jasmin_services:{}'.format(view_name),
                    category = service.category.name, service = service.name)


@require_safe
@login_required
@with_service
def service_details(request, service):
    """
    Handler for ``/<category>/<service>/``.

    Responds to GET requests only. The user must be authenticated.

    Displays details for a service, including details of current access and requests.
    """
    # Get the active grants and requests for the service as a whole
    grants = Grant.objects \
        .filter(role__service = service, user = request.user) \
        .filter_active()
    requests = Request.objects \
        .filter(role__service = service, user = request.user) \
        .filter_active()
    # access is a list of (role, grant, has_request) tuples for the roles of
    # the service
    # NOTE: Since we filtered for active, we know there is a maximum of one
    #       grant and one request per role
    access = []
    for role in service.roles.all():
        grant = next((g for g in grants if g.role == role), None)
        has_request = any(r for r in requests if r.role == role)
        if not role.hidden or has_request or grant:
            access.append((role, grant, has_request))
    templates = [
        'jasmin_services/{}/{}/service_details.html'.format(
            service.category.name,
            service.name
        ),
        'jasmin_services/{}/service_details.html'.format(service.category.name),
        'jasmin_services/service_details.html',
    ]
    return render(request, templates, {
        'service': service,
        'requests': requests,
        'access': access,
    })


@require_http_methods(['GET', 'POST'])
@login_required
@with_service
def role_apply(request, service, role):
    """
    Handler for ``/<category>/<service>/apply/<role>/``.

    Responds to GET and POST requests. The user must be authenticated.

    Collects the necessary information to raise a request for a role.
    """
    try:
        role = Role.objects.get(service = service, name = role)
    except Role.DoesNotExist:
        messages.error(request, "Role does not exist")
        return redirect_to_service(service)
    # If the user has an active grant, it must be revoked, expired or expiring
    grant = role.grants.filter(user = request.user).filter_active().first()
    if grant and not (grant.revoked or grant.expired or grant.expiring):
        messages.info(
            request,
            "You have already been granted the specified role"
        )
        return redirect_to_service(service)
    # If the user has an active request, it must be rejected
    req = role.requests.filter(user = request.user).filter_active().first()
    if req and not req.state == RequestState.REJECTED:
        messages.info(
            request,
            "You already have a pending request for the specified role"
        )
        return redirect_to_service(service)
    # Otherwise, attempt to do something
    form_class = role.metadata_form_class
    if request.method == 'POST':
        form = form_class(data = request.POST)
        if form.is_valid():
            with transaction.atomic():
                # If the role is set to auto accept, grant before saving
                if role.auto_accept:
                    request = Request.objects.create(
                        role = role,
                        user = request.user,
                        requested_by = request.user.username
                    )
                    request.grant = Grant.objects.create(
                        role = role,
                        user = request.user,
                        granted_by = request.user.username,
                        expires = date.today() + relativedelta(years = 1)
                    )
                    request.copy_metadata_to(request.grant)

                    form.save(
                        request
                    )
                else:
                    form.save(
                        Request.objects.create(
                            role = role,
                            user = request.user,
                            requested_by = request.user.username
                        )
                    )
            messages.success(request, 'Request submitted successfully')
            return redirect_to_service(service)
        else:
            messages.error(request, 'Error with one or more fields')
    else:
        # Set the initial data to the metadata attached to the active request
        initial = {}
        if req:
            for datum in req.metadata.all():
                initial[datum.key] = datum.value
        form = form_class(initial = initial)
    templates = [
        'jasmin_services/{}/{}/{}/role_apply.html'.format(
            service.category.name,
            service.name,
            role.name
        ),
        'jasmin_services/{}/{}/role_apply.html'.format(
            service.category.name,
            service.name
        ),
        'jasmin_services/{}/role_apply.html'.format(service.category.name),
        'jasmin_services/role_apply.html',
    ]
    return render(request, templates, {
        'role': role,
        'grant': grant,
        'req': req,
        'form': form,
    })


@require_safe
@login_required
@with_service
def service_users(request, service):
    """
    Handler for ``/<category>/<service>/users/``.

    Responds to GET requests only. The user must have the permission
    ``jasmin_services.view_users_role`` for at least one role in the service.

    Displays the active grants for a service. The grants that a user sees
    depends on the permissions they have been granted.
    """
    # Get the roles for the service for which the user has permission to view
    # grants. We allow the permission to be allocated for all services,
    # per-service or per-role.
    permission = 'jasmin_services.view_users_role'
    if request.user.has_perm(permission) or \
       request.user.has_perm(permission, service):
        user_roles = list(service.roles.all())
    else:
        user_roles = [
            role
            for role in service.roles.all()
            if request.user.has_perm(permission, role)
        ]
        # If the user has no permissions, send them back to the service details
        # Note that we don't show this message if the user has been granted the
        # permission for the service but there are no roles - in that case we
        # just show nothing
        if not user_roles:
            messages.error(request, 'Insufficient permissions')
            return redirect_to_service(service)
    # Start with the active grants for the roles that the user has permission for
    grants = Grant.objects.filter_active().filter(role__in = user_roles)
    all_statuses = ('active', 'expiring', 'expired', 'revoked')
    # Only apply filters if _apply_filters is present in the GET params
    if '_apply_filters' in request.GET:
        # Start by getting the roles to display from the GET filters
        selected_roles = set(
            role
            for role in user_roles
            if role.name in request.GET
        )
        # Then filter by those roles
        grants = grants.filter(role__in = selected_roles)
        # Then get the statuses to display from the GET filters
        selected_statuses = set(
            status
            for status in all_statuses
            if status in request.GET
        )
        # Apply any filters to the grants and requests
        if 'active' not in selected_statuses:
            # Make sure we don't include expiring grants in active
            grants = grants.exclude(
                revoked = False,
                expires__gte = date.today() + relativedelta(months = 2)
            )
        if 'revoked' not in selected_statuses:
            grants = grants.exclude(revoked = True)
        if 'expired' not in selected_statuses:
            grants = grants.exclude(revoked = False, expires__lt = date.today())
        if 'expiring' not in selected_statuses:
            grants = grants.exclude(
                revoked = False,
                expires__lt = date.today() + relativedelta(months = 2)
            )
    else:
        # If not applying filters, check all the filter checkboxes
        selected_roles = user_roles
        selected_statuses = all_statuses
    # Order the grants by user and then by the natural ordering
    grants = grants  \
        .select_related('role', 'user', 'user__institution')  \
        .order_by('user', *Grant._meta.ordering)
    # Get a paginator for the grants
    paginator = Paginator(
        grants,
        getattr(settings, 'JASMIN_SERVICES', {}).get('GRANTS_PER_PAGE', 20)
    )
    try:
        page = paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    # Only preserve filters if they were applied
    if '_apply_filters' in request.GET:
        preserved_filters = set(r.name for r in selected_roles) \
            .union(selected_statuses)
        preserved_filters.add('_apply_filters')
    else:
        preserved_filters = set()
    templates = [
        'jasmin_services/{}/{}/service_users.html'.format(
            service.category.name,
            service.name
        ),
        'jasmin_services/{}/service_users.html'.format(service.category.name),
        'jasmin_services/service_users.html',
    ]
    return render(request, templates, {
        'service': service,
        'statuses': tuple(
            dict(name = s, checked = s in selected_statuses)
            for s in all_statuses
        ),
        'roles': tuple(
            dict(name = r.name, checked = r in selected_roles)
            for r in user_roles
        ),
        'grants': page,
        'n_users': grants.values('user').distinct().count(),
        'preserved_filters': '&'.join(
            '{}=1'.format(f) for f in preserved_filters
        ),
    })


@require_safe
@login_required
@with_service
def service_requests(request, service):
    """
    Handler for ``/<category>/<service>/requests/``.

    Responds to GET requests only. The user must have the permission
    ``decide_request`` for at least one role in the service.

    Displays the pending requests for a service. The requests that a user sees
    depends on the permissions they have been granted.
    """
    # Get the roles for which the user is allowed to decide requests
    # We allow the permission to be allocated for all services, per-service or per-role
    permission = 'jasmin_services.decide_request'
    if request.user.has_perm(permission) or \
       request.user.has_perm(permission, service):
        user_roles = list(service.roles.all())
    else:
        user_roles = [
            role
            for role in service.roles.all()
            if request.user.has_perm(permission, role)
        ]
        # If the user has no permissions, send them back to the service details
        # Note that we don't show this message if the user has been granted the
        # permission for the service but there are no roles - in that case we
        # just show nothing
        if not user_roles:
            messages.error(request, 'Insufficient permissions')
            return redirect_to_service(service)
    templates = [
        'jasmin_services/{}/{}/service_requests.html'.format(
            service.category.name,
            service.name
        ),
        'jasmin_services/{}/service_requests.html'.format(
            service.category.name
        ),
        'jasmin_services/service_requests.html',
    ]
    return render(request, templates, {
        'service': service,
        # Get the pending requests for the discovered roles
        'requests': Request.objects \
            .filter_active() \
            .filter(role__in = user_roles, state = RequestState.PENDING),
        # The list of approvers to show here is any user who can approve at
        # least one of the visible roles
        'approvers': get_user_model().objects \
            .filter(
                grant__in = Grant.objects
                    .filter(
                        role__in = Role.objects.filter_permission(
                            permission,
                            service,
                            *user_roles
                        ),
                        revoked = False,
                        expires__gte = date.today()
                    )
                    .filter_active()
            ) \
            .exclude(pk = request.user.pk) \
            .distinct(),
    })


@require_http_methods(['GET', 'POST'])
@login_required
def request_decide(request, pk):
    """
    Handler for ``/request/<pk>/decide/``.

    Responds to GET and POST. The user must have the ``decide_request``
    permission for the role that the request is for. The request must be active
    and pending.

    Presents information about the request along with a form to collect a decision.
    """
    # Try to find the specified request
    try:
        pending = Request.objects.get(pk = pk)
    except Request.DoesNotExist:
        raise http.Http404("Request does not exist")
    # The current user must have permission to grant the role
    permission = 'jasmin_services.decide_request'
    if not request.user.has_perm(permission) and \
       not request.user.has_perm(permission, pending.role.service) and \
       not request.user.has_perm(permission, pending.role):
        messages.error(request, 'Request does not exist')
        return redirect_to_service(pending.role.service, 'service_details')
    # If the request is not pending, redirect to the list of pending requests
    if not pending.active or pending.state != RequestState.PENDING:
        messages.info(request, 'This request has already been resolved')
        return redirect(
            'jasmin_services:service_requests',
            category = pending.role.service.category.name,
            service = pending.role.service.name
        )
    # If the user requesting access has an active grant, find it
    grant = pending.role.grants \
        .filter(user = pending.user) \
        .filter_active() \
        .first()
    # Find all the rejected requests for the role/user since the active grant
    rejected = pending.role.requests \
        .filter(user = pending.user, state = RequestState.REJECTED)
    if grant:
        rejected = rejected.filter(requested_at__gt = grant.granted_at)
    rejected = rejected.order_by('requested_at')
    # Process the form if this is a POST request, otherwise just set it up
    if request.method == 'POST':
        form = DecisionForm(pending, request.user, data = request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            return redirect_to_service(pending.role.service, 'service_requests')
        else:
            messages.error(request, 'Error with one or more fields')
    else:
        form = DecisionForm(pending, request.user)
    templates = [
        'jasmin_services/{}/{}/request_decide.html'.format(
            pending.role.service.category.name,
            pending.role.service.name
        ),
        'jasmin_services/{}/request_decide.html'.format(
            pending.role.service.category.name
        ),
        'jasmin_services/request_decide.html',
    ]
    return render(request, templates, {
        'service' : pending.role.service,
        'pending' : pending,
        'rejected' : rejected,
        'grant' : grant,
        # The list of approvers to show here is any user who has the correct
        # permission for either the role or the service
        'approvers': pending.role.approvers.exclude(pk = request.user.pk),
        'form' : form,
    })


@require_http_methods(['GET', 'POST'])
@login_required
@with_service
def service_message(request, service):
    """
    Handler for ``/<category>/<service>/message/``.

    Responds to GET and POST. The user must have the ``send_message_role``
    permission for at least one role for the service.

    Allows a user with suitable permissions to send messages to other users of
    the service, depending which permissions they have been granted.
    """
    # Get the roles for which the user is allowed to send messages
    # We allow the permission to be allocated for all services, per-service or per-role
    permission = 'jasmin_services.send_message_role'
    if request.user.has_perm(permission) or \
       request.user.has_perm(permission, service):
        user_roles = list(service.roles.all())
    else:
        user_roles = [
            role
            for role in service.roles.all()
            if request.user.has_perm(permission, role)
        ]
        # If the user has no permissions, send them back to the service details
        # Note that we don't show this message if the user has been granted the
        # permission for the service but there are no roles - in that case we
        # just show nothing
        if not user_roles:
            messages.error(request, 'Insufficient permissions')
            return redirect_to_service(service)
    MessageForm = message_form_factory(request.user, *user_roles)
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            reply_to = form.cleaned_data['reply_to']
            EmailMessage(
                subject = form.cleaned_data['subject'],
                body = render_to_string('jasmin_services/email_message.txt', {
                    'sender': request.user,
                    'message': form.cleaned_data['message'],
                    'reply_to': reply_to,
                }),
                bcc = [u.email for u in form.cleaned_data['users']],
                reply_to = [request.user.email] if reply_to else []
            ).send()
            messages.success(request, 'Message sent')
            return redirect_to_service(service, view_name = 'service_users')
        else:
            messages.error(request, 'Error with one or more fields')
    else:
        form = MessageForm()
    templates = [
        'jasmin_services/{}/{}/service_message.html'.format(
            service.category.name,
            service.name
        ),
        'jasmin_services/{}/service_message.html'.format(service.category.name),
        'jasmin_services/service_message.html',
    ]
    return render(request, templates, {
        'service': service,
        'form': form,
    })


@require_safe
def reverse_dns_check(request):
    """
    Handler for /reverse_dns_check/.

    Just returns some plain-text information about the reverse DNS status of the
    client.
    """
    response = http.HttpResponse(content_type = 'text/plain')
    # Use the X-Real-Ip header if present (for reverse proxy), otherwise use 'REMOTE_ADDR'
    remote_ip = request.META.get('HTTP_X_REAL_IP', request.META['REMOTE_ADDR'])
    response.write('External IP address: {}\r\n'.format(remote_ip))
    # Attempt a reverse DNS lookup
    try:
        host = socket.gethostbyaddr(remote_ip)[0]
    except Exception:
        response.write('Reverse DNS lookup failed\r\n')
    else:
        response.write('Resolved to host: {}'.format(host))
    return response
