import datetime as dt

import django.contrib.auth
import django.db.models
import django.views.generic

from .. import models as js_models


class AdminDashboardView(django.views.generic.base.TemplateView):
    template_name = "admin/jasmin_services/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get a list of all the roles and annotate with the number of pending requests.
        roles = (
            js_models.Role.objects.all()
            .annotate(
                num_pending=django.db.models.Count(
                    "access",
                    filter=django.db.models.Q(
                        access__request__state=js_models.RequestState.PENDING,
                    ),
                ),
            )
            .filter(num_pending__gt=0)
        )

        #### Queryset of ceda_managed roles with pending requests. ####
        ceda_managed_pending = roles.filter(service__ceda_managed=True)

        #### Queryset of roles with no approver. ####
        # Getting roles with no approver is complicated due to database structure.
        # Subquery to get the role object permissions which can approve the role we are interested in.
        approver_roleobjectperms = js_models.RoleObjectPermission.objects.filter(
            object_pk=django.db.models.functions.Cast(
                django.db.models.OuterRef(django.db.models.OuterRef("pk")),
                django.db.models.CharField(),
            ),
            permission__codename="decide_request",
            permission__content_type__app_label="jasmin_services",
        )
        # Subquery to get any active grants for those roles.
        approver_grants = (
            js_models.Grant.objects.annotate(
                approver_role_count=django.db.models.Count(
                    "access",
                    django.db.models.Q(
                        access__role__object_permission__in=approver_roleobjectperms
                    ),
                )
            )
            .filter(approver_role_count__gt=0, revoked=False, expires__gte=dt.date.today())
            .filter_active()
        )
        # Main query checks if any of the grants exist.
        no_approver_pending = roles.annotate(
            has_approver=django.db.models.Exists(approver_grants)
        ).filter(has_approver=False)

        #### Queryset of pending manager requests. ####
        manager_requests_pending = roles.filter(
            object_permission__permission__codename="decide_request",
            object_permission__permission__content_type__app_label="jasmin_services",
        )

        #### Queryset of roles with requests which have been pending for more than 30 days. ####
        longtime_pending = roles.annotate(
            num_pending_longtime=django.db.models.Count(
                "access",
                filter=django.db.models.Q(
                    access__request__requested_at__lt=(dt.date.today() - dt.timedelta(days=30)),
                ),
            ),
        ).filter(num_pending_longtime__gt=0)

        extra_context = {
            "ceda_managed_pending": ceda_managed_pending,
            "no_approver_pending": [],
            "manager_requests_pending": manager_requests_pending,
            "longtime_pending": longtime_pending,
        }
        return context | extra_context
