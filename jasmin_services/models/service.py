from django.db import models
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django_countries.fields import CountryField

from .category import Category


class Service(models.Model):
    """Model representing a service."""

    id = models.AutoField(primary_key=True)

    class Meta:
        unique_together = ("category", "name")
        ordering = ("category__position", "category__long_name", "position", "name")
        indexes = [models.Index(fields=["position", "name"])]

    @property
    def details_link(self):
        """Html anchor tag linking to the service details page."""
        details_url = reverse_lazy(
            "jasmin_services:service_details",
            kwargs={"category": self.category.name, "service": self.name},
        )

        anchor = f'<a href="{details_url}">Details</a>'
        return mark_safe(anchor)

    #: The category that the service belongs to
    category = models.ForeignKey(
        Category, models.CASCADE, related_name="services", related_query_name="service"
    )
    #: The name of the service
    name = models.SlugField(
        max_length=50, help_text="The name of the service. This is also used in URLs."
    )
    #: A brief description of the service, shown in listings
    summary = models.TextField(
        help_text="One-line description of the service, shown in listings. "
        "No special formatting allowed."
    )
    #: A full description of the service, show on the details page
    description = models.TextField(
        blank=True,
        null=True,
        default="",
        help_text="Full description of the service, shown on the details page. "
        "Markdown formatting is allowed.",
    )
    #: Additional text to send to approvers of the service
    approver_message = models.TextField(
        blank=True,
        null=True,
        default="",
        help_text="Service specific instructions to be added to the external "
        "approver message.",
    )
    #: Countries a users institution must be from to gain access
    instution_countries = CountryField(
        multiple=True,
        blank=True,
        help_text="Coutries a user's institute must be located to begin "
        "approval. Hold ctrl or cmd for mac to select multiple "
        "countries. Leave blank for any country.",
    )
    #: Indicates if the service should be shown in listings
    hidden = models.BooleanField(
        default=True,
        help_text="Prevents the service appearing in listings unless the user "
        "has an active grant or request for it. "
        "The service details page will still be accessible to anybody "
        "who knows the URL.",
    )
    #: Defines the order that the services appear
    position = models.PositiveIntegerField(
        default=9999,
        help_text="Number defining where the service appears in listings. "
        "Services are ordered in ascending order by category, then by "
        "this field, then alphabetically by name.",
    )
    #: Indicates if the service is managed by CEDA
    ceda_managed = models.BooleanField(
        default=False, help_text="Whether the service is managed by CEDA."
    )

    # Indicates the service is no longer used.
    disabled = models.BooleanField(
        default=False,
        help_text="Whether this service is disabled. Disabled services are hidden, and impossible to apply for.",
    )

    def __str__(self):
        return f"{self.category} : {self.name}"
