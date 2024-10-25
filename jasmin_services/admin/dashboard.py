import django.db.models
import django.views.generic

from .. import models as js_models


class AdminDashboardView(django.views.generic.base.TemplateView):
    template_name = "admin/jasmin_services/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        roles_with_pending_requests = (
            js_models.Role.objects.all()
            .annotate(
                num_pending=django.db.models.Count(
                    "access",
                    filter=django.db.models.Q(
                        access__request__state=js_models.RequestState.PENDING
                    ),
                )
            )
            .filter(num_pending__gt=0)
        )
        ceda_managed_pending = roles_with_pending_requests  # .filter(service__ceda_managed=True) # TODO: Reinstate this check.
        longer_than_a_week_pending = roles_with_pending_requests  # TODO: write this check.
        no_approver_pending = roles_with_pending_requests  # TODO: write this check.

        extra_context = {
            "ceda_managed_pending": ceda_managed_pending,
            "longer_than_a_week_pending": longer_than_a_week_pending,
            "no_approver_pending": no_approver_pending,
        }
        return context | extra_context
