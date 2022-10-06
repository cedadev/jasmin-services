from django.conf import settings
from django.db import models


class Access(models.Model):
    """
    Represents the join model between the access(role/user pair) and grant.
    """

    id = models.AutoField(primary_key=True)

    class Meta:
        ordering = (
            "role__service__category__position",
            "role__service__category__long_name",
            "role__service__position",
            "role__service__name",
            "role__position",
            "role__name",
        )
        unique_together = ("role", "user")
        verbose_name_plural = "accesses"

    #: The role that the grant is for
    role = models.ForeignKey(
        "Role", models.CASCADE, related_name="accesses", related_query_name="access"
    )
    #: The user for whom the role is granted
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE)

    def __str__(self):
        return f"{self.role} : {self.user}"
