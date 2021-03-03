"""
URL configuration for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.conf.urls import url, include
from django.views.generic.base import RedirectView

from . import views

app_name = 'jasmin_services'
urlpatterns = [
    # The root pattern redirects to my_services
    url(r'^$',
        RedirectView.as_view(pattern_name = 'jasmin_services:my_services'),
        name = 'service_root'),
    url(r'^reverse_dns_check/$',
        views.reverse_dns_check,
        name = 'reverse_dns_check'),
    url(r'^my_services/$', views.my_services, name = 'my_services'),
    url(r'^(?P<category>[\w-]+)/$', views.service_list, name = 'service_list'),
    url(r'^(?P<category>[\w-]+)/(?P<service>[\w-]+)/', include([
        url(r'^$', views.service_details, name = 'service_details'),
        url(r'^requests/$', views.service_requests, name = 'service_requests'),
        url(r'^users/$', views.service_users, name = 'service_users'),
        url(r'^message/$', views.service_message, name = 'service_message'),
        url(r'^groups/$', views.service_groups, name = 'service_groups'),
    ])),
    url(r'^(?P<category>[\w-]+)/(?P<service>[\w-]+)/apply/(?P<role>[\w-]+)/$',
        views.role_apply,
        name = 'role_apply'),
    url(r'^request/(?P<pk>\d+)/decide/$',
        views.request_decide,
        name = 'request_decide'),
]
