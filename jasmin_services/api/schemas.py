"""
Custom schemas for the jasmin_services api.

These are only required if the rest_framework cannot correctly infer a schema.
"""

import rest_framework.schemas.openapi as rf_schemas


class ServiceRolesListSchema(rf_schemas.AutoSchema):
    def get_component_name(self, _serializer):
        return "ServiceRoles"

    def get_components(self, _path, _method):
        """Return schema components."""
        return {
            "ServiceRoles": {
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
                "example": {
                    "fry": ["USER"],
                    "professor": ["USER", "MANAGER"],
                    "leela": ["USER"],
                },
            }
        }
