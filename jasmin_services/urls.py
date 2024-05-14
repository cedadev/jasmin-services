"""URL configuration for the JASMIN services app."""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import django.conf
import django.core.exceptions
import django.utils.module_loading
import django.views
from django.urls import include, path
from django.views.generic.base import RedirectView

from . import views


def swapable_view(setting_name: str, default_view_class: django.views.View) -> django.views.View:
    """Get the correct view class when a view is swappable."""
    setting_value = django.conf.settings.JASMIN_SERVICES.get("SWAPABLE_VIEWS", {}).get(
        setting_name, None
    )
    # If the setting is not present we can send the default.
    if setting_value is None:
        return default_view_class
    # If the setting is a string, try to import it.
    if isinstance(setting_name, str):
        view_class = django.utils.module_loading.import_string(setting_value)
        if not issubclass(view_class, default_view_class):
            raise django.core.exceptions.ImproperlyConfigured(
                f"Swappable view {default_view_class} for {setting_name} must be a subclass of {default_view_class}."
            )
        return view_class
    raise django.core.exceptions.ImproperlyConfigured(
        f"Swappable view for {setting_name} could not be loaded."
    )


# Setup swappable views where required.
ServiceDetailsView = swapable_view("SERVICE_DETAILS", views.ServiceDetailsView)
RoleApplyView = swapable_view("ROLE_APPLY", views.RoleApplyView)


app_name = "jasmin_services"
urlpatterns = [
    # The root pattern redirects to my_services
    path(
        "",
        RedirectView.as_view(pattern_name="jasmin_services:my_services"),
        name="service_root",
    ),
    path("reverse_dns_check/", views.reverse_dns_check, name="reverse_dns_check"),
    path("my_services/", views.my_services, name="my_services"),
    path("<slug:category>/", views.service_list, name="service_list"),
    path(
        "<slug:category>/<slug:service>/",
        include(
            [
                path("", ServiceDetailsView.as_view(), name="service_details"),
                path("requests/", views.service_requests, name="service_requests"),
                path("users/", views.service_users, name="service_users"),
                path("message/", views.service_message, name="service_message"),
                path("grant/", views.grant_role, name="grant_role"),
            ]
        ),
    ),
    path(
        "<slug:category>/<slug:service>/apply/<slug:role>/",
        RoleApplyView.as_view(),
        name="role_apply",
    ),
    path(
        "<slug:category>/<slug:service>/apply/<slug:role>/<int:bool_grant>/<int:previous>/",
        RoleApplyView.as_view(),
        name="role_apply",
    ),
    path("request/<int:pk>/decide/", views.request_decide, name="request_decide"),
    path("grant/<int:pk>/review/", views.grant_review, name="grant_review"),
]
