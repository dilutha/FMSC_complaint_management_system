from django.urls import path

from . import api

urlpatterns = [
    path("dashboard/summary/", api.DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/trends/", api.DashboardTrendsView.as_view(), name="dashboard-trends"),
    path("dashboard/workload/", api.DashboardWorkloadView.as_view(), name="dashboard-workload"),
    path("dashboard/ageing/", api.DashboardAgeingView.as_view(), name="dashboard-ageing"),
    path("reports/cases/", api.CaseReportView.as_view(), name="report-cases"),
]
