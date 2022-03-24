"""
URL configuration for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.urls import include, path
from django.views.generic.base import RedirectView

from . import views

app_name = 'jasmin_services'
urlpatterns = [
    # The root pattern redirects to my_services
    path('',
        RedirectView.as_view(pattern_name = 'jasmin_services:my_services'),
        name = 'service_root'),
    path('reverse_dns_check/',
        views.reverse_dns_check,
        name = 'reverse_dns_check'),
    path('my_services/', views.my_services, name = 'my_services'),
    path('<slug:category>/', views.service_list, name = 'service_list'),
    path('<slug:category>/<slug:service>/', include([
        path('', views.service_details, name = 'service_details'),
        path('requests/', views.service_requests, name = 'service_requests'),
        path('users/', views.service_users, name = 'service_users'),
        path('message/', views.service_message, name = 'service_message'),
        path('grant/', views.grant_role, name = 'grant_role'),
    ])),
    path('<slug:category>/<slug:service>/apply/<slug:role>/',
        views.role_apply,
        name = 'role_apply'),
    path('<slug:category>/<slug:service>/apply/<slug:role>/<int:bool_grant>/<int:previous>/',
        views.role_apply,
        name = 'role_apply'),
    path('request/<int:pk>/decide/',
        views.request_decide,
        name = 'request_decide'),
    path('grant/<int:pk>/review/',
        views.grant_review,
        name = 'grant_review'),
]
