from django.urls import include, path
from rest_framework.routers import DefaultRouter

from mybooks.api_views import GroupViewSet, UserViewSet

# DRF Router configuration for core API endpoints
router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"groups", GroupViewSet, basename="group")

urlpatterns = [
    # Core API endpoints (users, groups)
    path("", include(router.urls)),
    # Book Collection API endpoints
    path("", include("books.urls")),
]
