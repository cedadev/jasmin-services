import django.contrib.auth.mixins
import django.db
import django.views.generic.edit

from .. import forms, models
from . import mixins


class RequestDecideView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.contrib.auth.mixins.UserPassesTestMixin,
    mixins.WithServiceMixin,
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
        return kwargs | {"approver": self.request.user}

    def form_valid(self, form):
        """Make the transtaction atomic. Form does lots of complicated stuff."""
        with django.db.transaction.atomic():
            super().form_valid(form)

    def get_success_url(self):
        """Define the url to redirect to on success."""
        return f"/services/{self.service.category.name}/{self.service.name}/"

    def get_context_data(self, **kwargs):
        """Add to the template context."""
        context = super().get_context_data(**kwargs)

        rejected = models.Request.objects.filter(
            access=self.object.access,
            state=models.RequestState.REJECTED,
            previous_grant=self.object.previous_grant,
        ).order_by("requested_at")

        context |= {
            "service": self.service,
            "pending": self.object,
            "rejected": rejected,
            "grant": self.object.previous_grant,  # The previous grant.
            # The list of approvers to show here is any user who has the correct
            # permission for either the role or the service
            "approvers": self.object.access.role.approvers.exclude(pk=self.request.user.pk),
        }
        return context
