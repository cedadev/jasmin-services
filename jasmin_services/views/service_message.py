import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from ..forms import message_form_factory
from .common import redirect_to_service, with_service

_log = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
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
    permission = "jasmin_services.send_message_role"
    if request.user.has_perm(permission) or request.user.has_perm(permission, service):
        user_roles = list(service.roles.all())
    else:
        user_roles = [
            role for role in service.roles.all() if request.user.has_perm(permission, role)
        ]
        # If the user has no permissions, send them back to the service details
        # Note that we don't show this message if the user has been granted the
        # permission for the service but there are no roles - in that case we
        # just show nothing
        if not user_roles:
            messages.error(request, "Insufficient permissions")
            return redirect_to_service(service)
    MessageForm = message_form_factory(request.user, *user_roles)
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            reply_to = form.cleaned_data["reply_to"]
            EmailMessage(
                subject=form.cleaned_data["subject"],
                body=render_to_string(
                    "jasmin_services/email_message.txt",
                    {
                        "sender": request.user,
                        "message": form.cleaned_data["message"],
                        "reply_to": reply_to,
                    },
                ),
                bcc=[u.email for u in form.cleaned_data["users"]],
                reply_to=[request.user.email] if reply_to else [],
            ).send()
            messages.success(request, "Message sent")
            return redirect_to_service(service, view_name="service_users")
        else:
            messages.error(request, "Error with one or more fields")
    else:
        form = MessageForm()
    templates = [
        "jasmin_services/{}/{}/service_message.html".format(service.category.name, service.name),
        "jasmin_services/{}/service_message.html".format(service.category.name),
        "jasmin_services/service_message.html",
    ]
    return render(
        request,
        templates,
        {
            "service": service,
            "form": form,
        },
    )
