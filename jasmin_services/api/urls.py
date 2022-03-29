"""URLs for the jasmin_services api."""
from django.urls import include, path, re_path

from . import views as apiviews

app_name = "jasmin_services_api"
urlpatterns = [
    # fmt: off
    path("service-roles/<str:category>/<str:service>/", apiviews.ServiceRolesView.as_view()),
    # fmt: on
]
