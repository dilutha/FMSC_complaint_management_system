"""Server-rendered (Django template) management report: a printable one-page
summary for staff who use a desktop browser. It uses the same metrics as the
API and the same permission (view_dashboard)."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from rest_framework.exceptions import ValidationError

from apps.cases.models import Authority, Category

from . import metrics
from .api import DashboardFilterSerializer


@login_required(login_url="admin:login")
def management_report(request):
    if not request.user.can_view_dashboard:
        raise PermissionDenied
    params = {k: v for k, v in request.GET.items() if v}
    ser = DashboardFilterSerializer(data=params)
    errors = None
    try:
        ser.is_valid(raise_exception=True)
        filters = ser.to_filters()
    except ValidationError as exc:
        errors, filters = exc.detail, metrics.DashboardFilters()
    summary = metrics.summary(filters)
    return render(request, "manage/report.html", {
        "summary": summary,
        "workload": metrics.workload(filters),
        "ageing": metrics.ageing(filters, limit=15),
        "params": params,
        "errors": errors,
        "categories": Category.objects.order_by("name"),
        "authorities": Authority.objects.order_by("name"),
    })
