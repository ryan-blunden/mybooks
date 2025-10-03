from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from oauth2_provider import urls as oauth2_urls
from oauth_dcr.views import DynamicClientRegistrationView

from mybooks import core_views, oauth_views

urlpatterns = [
    # Core views
    path("", core_views.home, name="home"),
    path(r"health-check/", include("health_check.urls")),
    path("signup/", core_views.signup, name="signup"),
    path("signin/", core_views.signin, name="signin"),
    path("signout/", core_views.signout, name="signout"),
    # API
    path("api/", include("mybooks.api_urls")),
    path("api/", include("books.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    # OAuth
    path("oauth/", include(oauth2_urls)),
    path("oauth/register/", DynamicClientRegistrationView.as_view(), name="oauth-register"),
    path(".well-known/oauth-authorization-server", oauth_views.oauth_server_metadata, name="oauth-discovery-info"),
    path(
        ".well-known/oauth-protected-resource",
        oauth_views.oauth_protected_resource_metadata,
        name="oauth-resource-info",
    ),
    # App views
    path("oauth-apps/", oauth_views.apps, name="oauth-apps"),
    path("oauth-apps-register/", oauth_views.register, name="oauth-apps-register"),
    path("oauth-apps-authorize/", oauth_views.authorize, name="oauth-apps-authorize"),
    path("oauth-apps-get-tokens/", oauth_views.get_tokens, name="oauth-apps-get-tokens"),
    # Admin
    path("manage/", admin.site.urls),
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
    # Media
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

if settings.ENV == "development":
    urlpatterns.insert(0, path("components/", include("django_components.urls")))
    if settings.DEBUG and settings.DEBUG_TOOLBAR_ENABLED:
        urlpatterns.append(path("__debug__/", include("debug_toolbar.urls")))
