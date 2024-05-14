"""URLs for the jasmin_services api."""

import django.urls
import rest_framework.routers as rf_routers
import rest_framework_nested.routers

from . import views as apiviews

BASE = __package__.rsplit(".", 1)[0]
VERSION = "1"
PREFIX = f"{BASE}/v{VERSION}"

app_name = "jasmin_services_api"

# Setup the main routers for jasmin-services api endpoints.
primary_router = rf_routers.DefaultRouter()

# Route viewsets on the main router.
primary_router.register(
    "v1/users",
    apiviews.UsersViewSet,
    basename="user",
)

# Create a route for accesing service by id.
primary_router.register(
    "v1/services",
    apiviews.ServicesViewSet,
    basename="service",
)
# Create a route for accessing roles under services.
services_router = rest_framework_nested.routers.NestedDefaultRouter(
    parent_router=primary_router,
    parent_prefix="v1/services",
    lookup="service",
)
services_router.register(
    "roles",
    apiviews.RolesNestedUnderServicesViewSet,
    basename="services-roles",
)

# Create a nested router for accessing services by name.
primary_router.register(
    "v1/categories",
    apiviews.CategoriesViewSet,
    basename="category",
)
categories_router = rest_framework_nested.routers.NestedDefaultRouter(
    parent_router=primary_router,
    parent_prefix="v1/categories",
    lookup="category",
)
categories_router.register(
    "services",
    apiviews.ServicesNestedUnderCategoriesViewSet,
    basename="category-services",
)
# Create a nested router for accessing roles under categories under services..
categories_services_router = rest_framework_nested.routers.NestedDefaultRouter(
    parent_router=categories_router,
    parent_prefix="services",
    lookup="service",
)
categories_services_router.register(
    "roles",
    apiviews.RolesNestedUnderServicesViewSet,
    basename="category-services-roles",
)

# Combine all the nested routers into one.
router = rf_routers.DefaultRouter()
router.registry.extend(primary_router.registry)
# Fiddle the routes to include the prefix from the parent.
# Without this, the route is not nested properly.
# Works around https://github.com/alanjds/drf-nested-routers/issues/292
router.registry.extend(
    [(f"{services_router.parent_regex}{x[0]}", x[1], x[2]) for x in services_router.registry]
)
router.registry.extend(
    [(f"{categories_router.parent_regex}{x[0]}", x[1], x[2]) for x in categories_router.registry]
)
router.registry.extend(
    [
        (f"{categories_services_router.parent_regex}{x[0]}", x[1], x[2])
        for x in categories_services_router.registry
    ]
)
