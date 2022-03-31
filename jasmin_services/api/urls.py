"""URLs for the jasmin_services api."""
import rest_framework.routers as rf_routers

from . import views as apiviews

BASE = __package__.rsplit(".", 1)[0]
VERSION = "1"

PREFIX = f"{BASE}/v{VERSION}"

app_name = "jasmin_services_api"

router = rf_routers.DefaultRouter()
router.register(
    f"{PREFIX}/services",
    apiviews.ServicesViewSet,
    basename="services",
)
