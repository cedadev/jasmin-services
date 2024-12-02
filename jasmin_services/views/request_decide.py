import asgiref.sync
import django.contrib.auth.mixins
import django.contrib.messages
import django.db
import django.http
import django.urls
import django.views.generic.edit

from .. import forms, models
from . import mixins


class RequestDecideView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.contrib.auth.mixins.UserPassesTestMixin,
    mixins.WithServiceMixin,
    mixins.AccessListMixin,
    django.views.generic.UpdateView,
):
    model = models.Request
    form_class = forms.DecisionForm

    PERMISSION = "jasmin_services.decide_request"

    def setup(self, request, *args, **kwargs):
        """Set up extra class attributes depending on the service and role we are dealing with.

        These are needed throughout and not just in the context.
        """
        # pylint: disable=attribute-defined-outside-init
        super().setup(request, *args, **kwargs)
        self.object = self.get_object()
        self.service = self.get_service(
            self.object.access.role.service.category.name, self.object.access.role.service.name
        )

    def get(self, request, *args, **kwargs):
        """If the grant has already been approved, send the user away."""
        if self.object.state != "PENDING":
            django.contrib.messages.add_message(
                request, django.contrib.messages.INFO, "The request has already been approved."
            )
            return django.http.HttpResponseRedirect(
                f"/services/{self.service.category.name}/{self.service.name}/requests/"
            )
        return super().get(request, *args, **kwargs)

    def test_func(self):
        """Define the test for the UserPassesTestMixin.

        Return True if access should be allowed, false otherwise.
        """
        return self.request.user.has_perm(
            self.PERMISSION, self.service
        ) or self.request.user.has_perm(self.PERMISSION, self.object.access.role)

    def get_template_names(self):
        """Define template to be used by the TemplateResponseMixin."""
        return [
            f"jasmin_services/{self.service.category.name}/{self.service.name}/request_decide.html",
            f"jasmin_services/{self.service.category.name}/request_decide.html",
            "jasmin_services/request_decide.html",
        ]

    def get_form_kwargs(self):
        """Get kwargs for building the form for FormMixin."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = kwargs.pop(
            "instance"
        )  # Since the form is not a ModelForm, it expects the instance to be named "request"
        # If the user is CEDA staff, inject the internal comment back to the form.
        if self.request.user.is_staff:
            kwargs["initial"]["internal_comment"] = kwargs["request"].internal_comment
        return kwargs | {"approver": self.request.user}

    def form_valid(self, form):
        """Make the transtaction atomic. Form does lots of complicated stuff."""
        with django.db.transaction.atomic():
            return super().form_valid(form)

    def get_success_url(self):
        """Define the url to redirect to on success."""
        # If the is a next url, and it resolves to a place on the site, go there.
        next = self.request.GET.get("next", None)
        if next is not None:
            try:
                django.urls.resolve(next)
            except django.urls.Resolver404:
                pass
            else:
                return next
        # Else redirect to the service.
        return f"/services/{self.service.category.name}/{self.service.name}/requests/"

    def get_context_data(self, **kwargs):
        """Add to the template context."""
        context = super().get_context_data(**kwargs)

        grants = models.Grant.objects.filter(
            access__role__service=self.service, access__user=self.object.access.user
        ).prefetch_related("metadata", "access__role__service__category")
        requests = (
            models.Request.objects.filter(
                access__role__service=self.service,
                access__user=self.object.access.user,
                resulting_grant__isnull=True,
            )
            .exclude(pk=self.object.pk)
            .prefetch_related("metadata", "access__role__service__category")
        )

        # If the user is staff, show them any request and grant the user has ever had
        # from any service.
        if self.request.user.is_staff:
            all_grants = (
                models.Grant.objects.filter(access__user=self.object.access.user)
                .exclude(access__role__service=self.service)
                .prefetch_related("metadata", "access__role__service__category")
            )
            all_requests = (
                models.Request.objects.filter(
                    access__user=self.object.access.user,
                    resulting_grant__isnull=True,
                )
                .exclude(access__role__service=self.service)
                .prefetch_related("metadata", "access__role__service__category")
            )
            all_accesses = asgiref.sync.async_to_sync(self.display_accesses)(
                self.request.user, all_grants, all_requests, may_apply_override=False
            )
        else:
            all_accesses = None

        context |= {
            "accesses": asgiref.sync.async_to_sync(self.display_accesses)(
                self.request.user, grants, requests, may_apply_override=False
            ),
            "all_accesses": all_accesses,
            "service": self.service,
            # The list of approvers to show here is any user who has the correct
            # permission for either the role or the service
            "approvers": self.object.access.role.approvers.exclude(pk=self.request.user.pk),
        }
        return context
