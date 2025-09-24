from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve
from oauth2_provider import urls as oauth2_urls
from oauth_dcr.views import DynamicClientRegistrationView
from rest_framework.routers import DefaultRouter

from .api import UserViewSet, GroupViewSet

# Create DRF router and register ViewSets
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'groups', GroupViewSet)

urlpatterns = [
    path(r"health-check/", include("health_check.urls")),
    # API
    path("api/", include(router.urls)),
    path("oauth/", include(oauth2_urls)),
    path("oauth/register/", DynamicClientRegistrationView.as_view(), name="oauth2_dcr"),
    
    path(
        "manage/password_reset/",
        auth_views.PasswordResetView.as_view(extra_context={"site_header": admin.site.site_header}),
        name="admin_password_reset",
    ),
    path(
        "manage/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(extra_context={"site_header": admin.site.site_header}),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(extra_context={"site_header": admin.site.site_header}),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(extra_context={"site_header": admin.site.site_header}),
        name="password_reset_complete",
    ),
    path("manage/", admin.site.urls),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

if settings.ENV == "development":
    urlpatterns.insert(0, path("components/", include("django_components.urls")))
    if settings.DEBUG and settings.DEBUG_TOOLBAR_ENABLED:
        urlpatterns.append(path("__debug__/", include("debug_toolbar.urls")))
