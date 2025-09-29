import json
import uuid
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST
from oauth2_provider.models import Application

from mybooks.utils import build_code_challenge, get_code_verifier, get_oauth_server_metadata


def oauth_metadata(request):
    """Provide OAuth2 provider metadata."""
    return JsonResponse(get_oauth_server_metadata())


def oauth_flow_test(request):
    code_challenge = request.session.get("oauth_code_challenge")

    # Generate PKCE code verifier and challenge if not in existing auth flow
    if not request.GET.get("code") or not code_challenge:
        code_verifier, code_challenge = get_code_verifier()
        state = uuid.uuid4().hex
        request.session["oauth_state"] = state
        request.session["oauth_code_verifier"] = code_verifier
        request.session["oauth_code_challenge"] = code_challenge

    applications = Application.objects.all().order_by("-created")

    tokens = request.session.get("oauth_tokens")
    if tokens is not None:
        request.session.pop("oauth_tokens", None)

    # Pre-fill registration data for new application
    registration_data = {
        "client_name": f"OAuth App {uuid.uuid4().hex[:4]}",
        "redirect_uris": [request.build_absolute_uri(reverse("oauth-flow-test"))],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": ["read", "write"],
        "client_uri": settings.SITE_URL,
        "contacts": ["test@localhost"],
        "token_endpoint_auth_method": "none",
    }

    context = {
        "registration_data": registration_data,
        "oauth_metadata_url": request.build_absolute_uri(reverse("oauth-metadata")),
        "oauth_state": request.session.get("oauth_state"),
        "applications": applications,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "oauth_tokens": tokens,
        "oauth_server_metadata": json.dumps(get_oauth_server_metadata(), indent=2),
    }
    return render(request, "oauth_flow_test.html", context)


@require_POST
def oauth_flow_register_app(request):
    dcr_url = request.build_absolute_uri(reverse("oauth2_dcr"))
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
        response = requests.post(dcr_url, json=registration_data, headers={"Content-Type": "application/json"})

        if response.status_code == 201:
            client_data = response.json()
            request.session["oauth_client_id"] = client_data["client_id"]
            request.session["oauth_redirect_uri"] = redirect_uris[0]

            messages.success(request, f"Application {client_name} registered successfully!")
        else:
            messages.error(request, f"Registration of '{client_name}' failed: {response.status_code} {response.reason}: {response.text}")
    except Exception as exc:
        messages.error(request, f"Registration of '{client_name}' failed: {str(exc)}")
    finally:
        return HttpResponseRedirect(reverse("oauth-flow-test"))


@require_POST
def authorize_app(request):
    app_id = request.POST.get("app_id")
    if not app_id:
        messages.error(request, "Missing application identifier for authorization.")
        return HttpResponseRedirect(reverse("oauth-flow-test"))

    try:
        application = Application.objects.get(pk=app_id)
    except Application.DoesNotExist:
        messages.error(request, "The selected application could not be found.")
        return HttpResponseRedirect(reverse("oauth-flow-test"))

    redirect_uri_candidates = [uri for uri in application.redirect_uris.split() if uri]
    if not redirect_uri_candidates:
        messages.error(request, "The selected application has no configured redirect URIs.")
        return HttpResponseRedirect(reverse("oauth-flow-test"))

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
        "scope": "read write groups",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    authorize_url = f"{request.build_absolute_uri(reverse('oauth2_provider:authorize'))}?{urlencode(authorize_params)}"
    return HttpResponseRedirect(authorize_url)


@require_POST
def oauth_exchange_code_for_tokens(request):
    """Exchange the authorization code for access tokens."""
    code = request.POST.get("code")
    posted_state = request.POST.get("state")

    client_id = request.session.get("oauth_client_id")
    code_verifier = request.session.get("oauth_code_verifier")
    redirect_uri = request.session.get("oauth_redirect_uri")
    expected_state = request.session.get("oauth_state")

    if not code:
        messages.error(request, "Authorization code missing; restart the OAuth flow.")
        return HttpResponseRedirect(reverse("oauth-flow-test"))

    if expected_state and posted_state and posted_state != expected_state:
        messages.error(request, "State mismatch detected; restart the OAuth flow.")
        return HttpResponseRedirect(reverse("oauth-flow-test"))

    if not all([client_id, code_verifier, redirect_uri]):
        messages.error(request, "Missing OAuth session data; restart the OAuth flow.")
        return HttpResponseRedirect(reverse("oauth-flow-test"))

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
    else:
        messages.error(request, f"Token exchange failed: {response.status_code} {response.reason}: {response.text}")

    return HttpResponseRedirect(reverse("oauth-flow-test"))
