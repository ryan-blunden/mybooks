"""OAuth helper utilities for the Streamlit agent."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Mapping, MutableMapping, Tuple

import requests

from mybooks.utils import build_code_challenge, get_code_verifier


class OAuthDiscoveryError(RuntimeError):
    """Raised when the OAuth server metadata cannot be fetched or parsed."""


@dataclass(frozen=True)
class OAuthMetadata:
    """Resolved OAuth discovery document."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None


# def build_code_challenge(code_verifier: str) -> str:
#     """Derive a PKCE code challenge from a verifier."""
#     digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
#     return base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")


# def get_code_verifier() -> Tuple[str, str]:
#     """Generate a code verifier and its corresponding code challenge for OAuth 2.0 PKCE."""
#     code_verifier = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(random.randint(43, 128)))
#     code_challenge = build_code_challenge(code_verifier)
#     return code_verifier, code_challenge


def _normalize_registration_endpoint(data: Mapping[str, Any]) -> str | None:
    endpoint = data.get("registration_endpoint")
    if isinstance(endpoint, str) and endpoint.strip():
        return endpoint.strip()
    return None


@lru_cache(maxsize=1)
def discover_oauth_metadata(oauth_server_url: str) -> OAuthMetadata:
    """Retrieve the OAuth discovery metadata and cache the result."""

    oauth_metadata_endpoint = f"{oauth_server_url}/.well-known/oauth-authorization-server"
    try:
        response = requests.get(oauth_metadata_endpoint, timeout=10)
    except requests.RequestException as exc:  # pragma: no cover - network failure path
        raise OAuthDiscoveryError(f"OAuth discovery failed for {oauth_server_url}: {exc}") from exc

    if response.status_code != 200:
        raise OAuthDiscoveryError(
            f"OAuth discovery failed for {oauth_server_url}: {response.status_code} {response.reason}"
        )  # pragma: no cover - unexpected status

    data = response.json()
    if not isinstance(data, Mapping):
        raise OAuthDiscoveryError("OAuth discovery document is not a JSON object")

    try:
        issuer = str(data["issuer"]).strip()
        authorization_endpoint = str(data["authorization_endpoint"]).strip()
        token_endpoint = str(data["token_endpoint"]).strip()
    except KeyError as exc:
        raise OAuthDiscoveryError(f"OAuth discovery document missing field: {exc.args[0]}") from exc

    if not issuer or not authorization_endpoint or not token_endpoint:
        raise OAuthDiscoveryError("OAuth discovery document returned empty endpoints")

    registration_endpoint = _normalize_registration_endpoint(data)
    return OAuthMetadata(
        issuer=issuer,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        registration_endpoint=registration_endpoint,
    )


def generate_pkce_pair() -> Tuple[str, str, str]:
    """Return ``(code_verifier, code_challenge, method)``."""

    code_verifier, code_challenge = get_code_verifier()
    return code_verifier, code_challenge, "S256"


def build_pkce_challenge(code_verifier: str) -> Tuple[str, str]:
    """Compute the PKCE challenge for a pre-existing verifier."""

    return build_code_challenge(code_verifier), "S256"


def exchange_code_for_tokens(
    token_endpoint: str,
    *,
    authorization_code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
    state: str | None = None,
    session: requests.Session | None = None,
) -> Dict[str, Any]:
    """Exchange an authorization code for tokens using PKCE."""

    payload: MutableMapping[str, Any] = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if state:
        payload["state"] = state

    transport = session or requests
    response = transport.post(
        token_endpoint,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        timeout=10,
    )
    response.raise_for_status()
    token_data = response.json()
    if not isinstance(token_data, Mapping):
        raise RuntimeError("Token endpoint returned non-JSON response")
    return dict(token_data)
