from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuthorityViewSet, CaseOptionsView, CaseViewSet, CategoryViewSet

router = DefaultRouter()
router.register("cases", CaseViewSet, basename="case")
router.register("categories", CategoryViewSet, basename="category")
router.register("authorities", AuthorityViewSet, basename="authority")

urlpatterns = [
    path("case-options/", CaseOptionsView.as_view(), name="case-options"),
    path("", include(router.urls)),
]
