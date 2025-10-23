import json
import uuid
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST
from oauth2_provider.models import AbstractGrant, Application

from mybooks.utils import build_code_challenge, get_code_verifier


def oauth_server_metadata(request):

    metadata = {
        "issuer": settings.SITE_URL,
        "authorization_endpoint": f"{settings.SITE_URL}{reverse('oauth2_provider:authorize')}",
        "token_endpoint": f"{settings.SITE_URL}{reverse('oauth2_provider:token')}",
        "registration_endpoint": f"{settings.SITE_URL}{reverse('oauth-register')}",
        "introspection_endpoint": f"{settings.SITE_URL}{reverse('oauth2_provider:introspect')}",
        "revocation_endpoint": f"{settings.SITE_URL}{reverse('oauth2_provider:revoke-token')}",
        "scopes_supported": list(settings.OAUTH2_PROVIDER["SCOPES"].keys()),
        "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
        "code_challenge_methods_supported": [key for key, _ in AbstractGrant.CODE_CHALLENGE_METHODS],
    }

    if settings.OAUTH2_PROVIDER.get("OIDC_ENABLED", False):
        metadata.update(
            {
                "userinfo_endpoint": f"{settings.SITE_URL}{reverse('oauth2_provider:user-info')}",
                "jwks_uri": f"{settings.SITE_URL}{reverse('oauth2_provider:jwks-info')}",
            }
        )
    return JsonResponse(metadata)


def oauth_protected_resource_metadata(request):
    metadata = {
        "resource_name": "MyBooks API",
        "resource": f"{settings.SITE_URL}/api",
        "resource_documentation": request.build_absolute_uri(reverse("api-docs")),
        "authorization_servers": [settings.SITE_URL],
        "bearer_methods_supported": ["header"],
        "scopes_supported": list(settings.OAUTH2_PROVIDER["SCOPES"].keys()),
    }

    return JsonResponse(metadata)


def apps(request):
    code_challenge = request.session.get("oauth_code_challenge")

    # Generate PKCE code verifier and challenge if not in existing auth flow
    if not request.GET.get("code") or not code_challenge:
        code_verifier, code_challenge = get_code_verifier()
        state = uuid.uuid4().hex
        request.session["oauth_state"] = state
        request.session["oauth_code_verifier"] = code_verifier
        request.session["oauth_code_challenge"] = code_challenge

    token_request_payload = None
    if request.GET.get("code") and request.GET.get("state"):
        token_request_payload = json.dumps(
            {
                "grant_type": "authorization_code",
                "code": request.GET.get("code"),
                "state": request.GET.get("state"),
                "redirect_uri": request.session.get("oauth_redirect_uri"),
                "client_id": request.session.get("oauth_client_id"),
                "code_verifier": request.session.get("oauth_code_verifier"),
            },
            indent=4,
        )

    register_response = request.session.get("register_response", None)
    if register_response:
        request.session["unauthorized_application_client_id"] = register_response.get("client_id")
        register_response = json.dumps(register_response, indent=4)
        request.session.pop("register_response", None)

    if request.session.get("unauthorized_application_client_id") and request.user.is_authenticated:
        application = Application.objects.get(client_id=request.session["unauthorized_application_client_id"])
        application.user = request.user
        application.save()

    tokens = request.session.get("oauth_tokens")
    if tokens is not None:
        tokens = json.dumps(tokens, indent=4)
        request.session.pop("oauth_tokens", None)
        request.session.pop("unauthorized_application_client_id", None)

    # Pre-fill registration data for new application
    registration_data = {
        "client_name": "My Books Client",
        "redirect_uris": [request.build_absolute_uri(reverse("oauth-apps"))],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": ["read", "write"],
        "client_uri": settings.SITE_URL,
        "contacts": ["test@localhost"],
        "token_endpoint_auth_method": "none",
    }

    applications = Application.objects.filter(user=request.user).order_by("-created") if request.user.is_authenticated else []
    context = {
        "registration_data": registration_data,
        "register_response": register_response,
        "unauthorized_application_client_id": request.session.get("unauthorized_application_client_id"),
        "oauth_metadata_url": request.build_absolute_uri(reverse("oauth-discovery-info")),
        "oauth_oidc_metadata_url": request.build_absolute_uri(reverse("oauth2_provider:oidc-connect-discovery-info")),
        "oauth_state": request.session.get("oauth_state"),
        "token_request_payload": token_request_payload,
        "applications": applications,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "oauth_tokens": tokens,
    }
    return render(request, "oauth_apps.html", context)


@require_POST
def register(request):
    dcr_url = request.build_absolute_uri(reverse("oauth-register"))
    client_name = request.POST.get("client_name", "").strip()
    redirect_uris = [uri.strip() for uri in request.POST.get("redirect_uris", "").split(",") if uri.strip()] or [dcr_url]

    registration_data = {
        "client_name": client_name,
        "redirect_uris": redirect_uris,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": ",".join([s.strip() for s in request.POST.get("scope", "").split(",") if s.strip()]),
        "client_uri": request.POST.get("client_uri", "").strip(),
        "contacts": [c.strip() for c in request.POST.get("contacts", "").split(",") if c.strip()],
        "token_endpoint_auth_method": "none",
    }
    try:
        response = requests.post(
            dcr_url,
            json=registration_data,
            headers={"Content-Type": "application/json"},
            cookies=request.COOKIES,
        )

        if response.status_code == 201:
            client_data = response.json()
            request.session["oauth_client_id"] = client_data["client_id"]
            request.session["oauth_redirect_uri"] = redirect_uris[0]

            messages.success(request, f"Application {client_name} registered successfully!")
            request.session["register_response"] = response.json()
        else:
            snippet = response.text.strip()
            truncated = snippet[:200] + ("…" if len(snippet) > 200 else "")
            suffix = " Sign in before registering a new OAuth application." if response.status_code in {401, 403} else ""
            messages.error(
                request,
                (f"Registration of '{client_name}' failed: " f"{response.status_code} {response.reason}: {truncated}.{suffix}"),
            )
    except Exception as exc:
        messages.error(request, f"Registration of '{client_name}' failed: {str(exc)}")
    finally:
        return HttpResponseRedirect(reverse("oauth-apps"))


@login_required
def authorize(request):
    """Start the authorization redirect for the selected OAuth application."""
    client_id = request.GET.get("client_id")

    if not client_id:
        client_id = request.session.get("unauthorized_application_client_id")

    if not client_id:
        messages.error(request, "Missing application identifier for authorization.")
        return HttpResponseRedirect(reverse("oauth-apps"))

    try:
        application = Application.objects.get(client_id=client_id)
    except Application.DoesNotExist:
        messages.error(request, "The selected application could not be found.")
        return HttpResponseRedirect(reverse("oauth-apps"))

    redirect_uri_candidates = [uri for uri in application.redirect_uris.split() if uri]
    if not redirect_uri_candidates:
        messages.error(request, "The selected application has no configured redirect URIs.")
        return HttpResponseRedirect(reverse("oauth-apps"))

    redirect_uri = redirect_uri_candidates[0]
    client_id = application.client_id
    request.session["oauth_client_id"] = client_id
    request.session["oauth_redirect_uri"] = redirect_uri

    state = request.session.get("oauth_state")
    if not state:
        state = uuid.uuid4().hex
        request.session["oauth_state"] = state

    code_verifier = request.session.get("oauth_code_verifier")
    if not code_verifier:
        code_verifier, code_challenge = get_code_verifier()
        request.session["oauth_code_verifier"] = code_verifier
    else:
        code_challenge = build_code_challenge(code_verifier)

    request.session["oauth_code_challenge"] = code_challenge

    authorize_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read write",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    authorize_url = f"{request.build_absolute_uri(reverse('oauth2_provider:authorize'))}?{urlencode(authorize_params)}"
    return HttpResponseRedirect(authorize_url)


@login_required
@require_POST
def get_tokens(request):
    """Exchange the authorization code for access tokens."""
    code = request.POST.get("code")
    posted_state = request.POST.get("state")

    client_id = request.session.get("oauth_client_id")
    code_verifier = request.session.get("oauth_code_verifier")
    redirect_uri = request.session.get("oauth_redirect_uri")
    expected_state = request.session.get("oauth_state")

    if not code:
        messages.error(request, "Authorization code missing; restart the OAuth flow.")
        return HttpResponseRedirect(reverse("oauth-apps"))

    if expected_state and posted_state and posted_state != expected_state:
        messages.error(request, "State mismatch detected; restart the OAuth flow.")
        return HttpResponseRedirect(reverse("oauth-apps"))

    if not all([client_id, code_verifier, redirect_uri]):
        messages.error(request, "Missing OAuth session data; restart the OAuth flow.")
        return HttpResponseRedirect(reverse("oauth-apps"))

    token_url = request.build_absolute_uri(reverse("oauth2_provider:token"))
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "state": posted_state or expected_state,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }

    response = requests.post(
        token_url,
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
    )

    if response.status_code == 200:
        request.session["oauth_tokens"] = response.json()
        for key in ["oauth_code_verifier", "oauth_state", "oauth_code_challenge"]:
            request.session.pop(key, None)
        messages.success(request, "Token exchange successful!")
    else:
        messages.error(request, f"Token exchange failed: {response.status_code} {response.reason}: {response.text}")

    return HttpResponseRedirect(reverse("oauth-apps"))
