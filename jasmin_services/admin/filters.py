from datetime import date

from django.contrib import admin

from ..models import RequestState, Service


class ServiceFilter(admin.SimpleListFilter):
    title = "Service"
    parameter_name = "service_id"

    def lookups(self, request, model_admin):
        # Fetch the services and the categories at once
        services = Service.objects.all().select_related("category")
        return tuple((s.pk, str(s)) for s in services)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(access__role__service__pk=self.value())


class ActiveListFilter(admin.SimpleListFilter):
    title = "Active"
    parameter_name = "active"

    def lookups(self, request, model_admin):
        return (("1", "Active only"),)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter_active()


class ExpiredListFilter(admin.SimpleListFilter):
    title = "Expired"
    parameter_name = "expired"

    def lookups(self, request, model_admin):
        return (("1", "Yes"), ("0", "No"))

    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.filter(expires__lt=date.today())
        elif self.value() == "0":
            return queryset.filter(expires__gte=date.today())


class StateListFilter(admin.SimpleListFilter):
    title = "State"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return RequestState.choices()

    def queryset(self, request, queryset):
        value = self.value()
        if value in RequestState.all():
            return queryset.filter(state=value)
