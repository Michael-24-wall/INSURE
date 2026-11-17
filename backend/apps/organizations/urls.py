from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MyOrganizationsView, OrganizationViewSet

router = DefaultRouter()
router.register("", OrganizationViewSet, basename="organizations")
router.register("mine/list", MyOrganizationsView, basename="my-organizations")

urlpatterns = [path("", include(router.urls))]
