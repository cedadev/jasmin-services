"""
Scopes defined for the jasmin_services API.

Designed to be imported into the SCOPES dictionary in settings.py
"""

SCOPES = {
    "jasmin.services.services.all:view": "View basic information about all services.",
    "jasmin.services.userservices.all:view": "View all the services any user is part of.",
    "jasmin.services.serviceroles.all:view": "View all the roleholders for any service.",
}
