from django.db import models


class Category(models.Model):
    """Model representing a category of services, a grouping of related services."""

    id = models.AutoField(primary_key=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ("position", "long_name")
        indexes = [models.Index(fields=["position", "long_name"])]

    #: A short name for the category
    name = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Short name for the category, used in URLs",
    )
    #: A human readable name for the category
    long_name = models.CharField(
        max_length=250, help_text="Long name for the category, used for display"
    )
    #: Defines the order that the categories appear
    position = models.PositiveIntegerField(
        default=9999,
        help_text="Number defining where the category appears in listings. "
        "Categories are ordered in ascending order by this field, "
        "then alphabetically by name within that.",
    )

    def __str__(self):
        return str(self.long_name)
