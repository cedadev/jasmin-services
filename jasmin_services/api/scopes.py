"""
Scopes defined for the jasmin_services API.

Designed to be imported into the SCOPES dictionary in settings.py
"""

SCOPES = {
    "jasmin.services.services.all:read": "View basic information about all services.",
    "jasmin.services.userservices.all:read": "View all the services any user is part of.",
    "jasmin.services.serviceroles.all:read": "View all the roleholders for any service.",
    "jasmin.services.categories.all:read": "View basic information about all service categories.",
}
