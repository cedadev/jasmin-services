"""URLs for the jasmin_services api."""

import types

import rest_framework.routers as rf_routers
import rest_framework_nested.routers

from . import views as apiviews

BASE = __package__.rsplit(".", 1)[0]
VERSION = "1"
PREFIX = f"{BASE}/v{VERSION}"

app_name = "jasmin_services_api"

# Setup the main routers for jasmin-services api endpoints.
primary_router = rf_routers.DefaultRouter()

# Create a route for getting service information about users.
# Because the /users/ viewset is not defined here (it is defined in jasmin-account),
# We must trick the router into createing a nested route.
# The dummy router's routes will not be used at the bottom of the page.

# Create a dummy router which knows to lookup the user by username.
dummy_viewset = types.SimpleNamespace()
dummy_viewset.lookup_field = "username"
dummy_router = rf_routers.SimpleRouter()
dummy_router.register("v1/users", dummy_viewset, basename="dummy-user")

# Add a users router so we can add nested routes.
users_router = rest_framework_nested.routers.NestedDefaultRouter(
    parent_router=dummy_router,
    parent_prefix="v1/users",
    lookup="user",
)
# Register route to get user's services.
users_router.register(
    "services",
    apiviews.UserServicesViewSet,
    basename="users-services",
)
# Register route to get user's grants.
users_router.register(
    "grants",
    apiviews.UserGrantsViewSet,
    basename="users-grants",
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
categories_router.register(
    "grants",
    apiviews.GrantsNestedUnderCategoriesViewSet,
    basename="category-grants",
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

# Access grants directly.
primary_router.register(
    "v1/grants",
    apiviews.GrantsViewSet,
    basename="grant",
)


# Combine all the nested routers into one.
def get_nested_router_registry(nested_router):
    """Fix routes to include the prefix from the parent.

    Without this, the route is not nested properly.
    Works around https://github.com/alanjds/drf-nested-routers/issues/292
    """
    return [(f"{nested_router.parent_regex}{x[0]}", x[1], x[2]) for x in nested_router.registry]


router = rf_routers.DefaultRouter()
router.registry.extend(primary_router.registry)

router.registry.extend(get_nested_router_registry(services_router))
router.registry.extend(get_nested_router_registry(users_router))
router.registry.extend(get_nested_router_registry(categories_router))
router.registry.extend(get_nested_router_registry(categories_services_router))
