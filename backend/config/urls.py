from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import SimpleRouter

from apps.accounts.views import AuthorityAdminViewSet, UserAdminViewSet
from apps.audit.api import AuditEventViewSet
from apps.dashboard.views import management_report
from apps.notifications.api import NotificationViewSet
from apps.suggestions.api import SuggestionViewSet

# Member B platform endpoints (see docs/API.md, "Platform endpoints").
platform = SimpleRouter()
platform.register("notifications", NotificationViewSet, basename="notification")
platform.register("suggestions", SuggestionViewSet, basename="suggestion")
platform.register("audit-events", AuditEventViewSet, basename="audit-event")
platform.register("manage/users", UserAdminViewSet, basename="manage-user")
platform.register("manage/authorities", AuthorityAdminViewSet, basename="manage-authority")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.cases.api.urls")),
    path("api/v1/", include("apps.dashboard.urls")),
    path("api/v1/", include(platform.urls)),
    path("manage/report/", management_report, name="management-report"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
