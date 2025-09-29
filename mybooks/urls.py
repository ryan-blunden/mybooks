from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from oauth2_provider import urls as oauth2_urls
from oauth_dcr.views import DynamicClientRegistrationView

from mybooks import core_views, oauth_views

urlpatterns = [
    path(r"health-check/", include("health_check.urls")),
    path("signin/", core_views.signin, name="signin"),
    path("signout/", core_views.signout, name="signout"),
    # Core API endpoints (users, groups)
    path("api/", include("mybooks.api_urls")),
    # Book Collection API endpoints
    path("api/", include("books.urls")),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Custom app views
    path("", core_views.home, name="home"),
    path("oauth-flow-test/", oauth_views.oauth_flow_test, name="oauth-flow-test"),
    path("oauth-flow-register/", oauth_views.oauth_flow_register_app, name="oauth-flow-register"),
    path("oauth-flow-authorize/", oauth_views.authorize_app, name="oauth-flow-authorize"),
    path("oauth-flow-tokens/", oauth_views.oauth_exchange_code_for_tokens, name="oauth-flow-tokens"),
    path("oauth/", include(oauth2_urls)),
    path("oauth/register/", DynamicClientRegistrationView.as_view(), name="oauth2_dcr"),
    path(".well-known/oauth-authorization-server", oauth_views.oauth_metadata, name="oauth-metadata"),
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
