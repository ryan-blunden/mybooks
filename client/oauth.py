"""OAuth helper utilities for the Streamlit client."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, is_dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple, TypeVar
from urllib.parse import urlparse

import requests

from mybooks.utils import get_code_verifier, strtobool

_DEFAULT_TIMEOUT_SECONDS = 10
REQUESTS_VERIFY_SSL = strtobool(os.getenv("REQUESTS_VERIFY_SSL", "true"))

T = TypeVar("T")


class OAuthDiscoveryError(RuntimeError):
    """Raised when OAuth metadata cannot be fetched or parsed."""


class DictMixin:
    """Provide ``to_dict`` that drops ``None`` values recursively."""

    def to_dict(self) -> Dict[str, Any]:
        def transform(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, dict):
                return {key: transformed for key, transformed in ((k, transform(v)) for k, v in value.items()) if transformed is not None}
            if isinstance(value, (list, tuple)):
                items = [item for item in (transform(v) for v in value) if item is not None]
                return tuple(items) if isinstance(value, tuple) else items
            if is_dataclass(value):
                if isinstance(value, DictMixin):
                    return value.to_dict()
                return {key: transformed for key, transformed in ((k, transform(v)) for k, v in asdict(value).items()) if transformed is not None}
            return value

        return {key: transformed for key, transformed in ((k, transform(v)) for k, v in asdict(self).items()) if transformed is not None}


@dataclass(frozen=True)
class OAuthProtectedMetadata(DictMixin):
    issuer: str
    authorization_servers: Tuple[str, ...]
    resource_name: Optional[str] = None
    resource: Optional[str] = None
    resource_documentation: Optional[str] = None
    bearer_methods_supported: Optional[Tuple[str, ...]] = None
    scopes_supported: Optional[Tuple[str, ...]] = None


@dataclass(frozen=True)
class OAuthServerMetadata(DictMixin):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    revocation_endpoint: str
    scopes_supported: Tuple[str, ...] = ()
    grant_types_supported: Tuple[str, ...] = ()
    code_challenge_methods_supported: Tuple[str, ...] = ()
    introspection_endpoint: Optional[str] = None


@dataclass(frozen=True)
class OAuthMetadata(DictMixin):
    auth_server_metadata: OAuthServerMetadata
    auth_server_metadata_url: str
    protected_metadata: Optional[OAuthProtectedMetadata] = None
    protected_metadata_url: Optional[str] = None


def _require_text(payload: Mapping[str, Any], field: str) -> str:
    try:
        value = payload[field]
    except KeyError as exc:
        raise OAuthDiscoveryError(f"OAuth metadata missing required field '{field}'.") from exc

    text = str(value).strip()
    if not text:
        raise OAuthDiscoveryError(f"OAuth metadata field '{field}' is empty.")
    return text


def _optional_text(payload: Mapping[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_sequence(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    items = tuple(str(item).strip() for item in value if str(item).strip())
    return items


def _fetch_json_document(url: str) -> Mapping[str, Any] | None:
    try:
        response = requests.get(url, verify=REQUESTS_VERIFY_SSL, timeout=_DEFAULT_TIMEOUT_SECONDS)
    except requests.RequestException as exc:  # pragma: no cover - network failure path
        raise OAuthDiscoveryError(f"OAuth discovery request failed for {url}: {exc}") from exc

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError as exc:
        raise OAuthDiscoveryError(f"OAuth discovery document at {url} is not valid JSON: {exc}") from exc

    if not isinstance(data, Mapping):
        raise OAuthDiscoveryError(f"OAuth discovery document at {url} is not a JSON object.")

    return data


def _discover_from_urls(urls: Iterable[str], parser: Callable[[Mapping[str, Any]], T]) -> Tuple[str, T] | None:
    seen: set[str] = set()
    for url in urls:
        candidate = url.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)

        document = _fetch_json_document(candidate)
        if document is None:
            continue

        metadata = parser(document)
        return candidate, metadata

    return None


def _parse_protected_metadata(payload: Mapping[str, Any]) -> OAuthProtectedMetadata:
    issuer = _require_text(payload, "issuer")
    authorization_servers_value = payload.get("authorization_servers")

    if not isinstance(authorization_servers_value, (list, tuple)):
        raise OAuthDiscoveryError("OAuth protected metadata field 'authorization_servers' must be an array.")

    authorization_servers = _string_sequence(authorization_servers_value)
    if not authorization_servers:
        raise OAuthDiscoveryError("OAuth protected metadata did not include any authorization servers.")

    bearer_methods = _string_sequence(payload.get("bearer_methods_supported"))
    scopes_supported = _string_sequence(payload.get("scopes_supported"))

    return OAuthProtectedMetadata(
        issuer=issuer,
        authorization_servers=authorization_servers,
        resource_name=_optional_text(payload, "resource_name"),
        resource=_optional_text(payload, "resource"),
        resource_documentation=_optional_text(payload, "resource_documentation"),
        bearer_methods_supported=bearer_methods or None,
        scopes_supported=scopes_supported or None,
    )


def _parse_server_metadata(payload: Mapping[str, Any]) -> OAuthServerMetadata:
    scopes_supported = _string_sequence(payload.get("scopes_supported"))
    return OAuthServerMetadata(
        issuer=_require_text(payload, "issuer"),
        authorization_endpoint=_require_text(payload, "authorization_endpoint"),
        token_endpoint=_require_text(payload, "token_endpoint"),
        registration_endpoint=_optional_text(payload, "registration_endpoint"),
        introspection_endpoint=_optional_text(payload, "introspection_endpoint"),
        revocation_endpoint=_optional_text(payload, "revocation_endpoint"),
        scopes_supported=scopes_supported,
        grant_types_supported=_string_sequence(payload.get("grant_types_supported")),
        code_challenge_methods_supported=_string_sequence(payload.get("code_challenge_methods_supported")),
    )


def _build_well_known_urls(*, scheme: str, host: str, resource: str, path: str | None) -> Tuple[str, ...]:
    base = f"{scheme}://{host}/.well-known/{resource.strip('/')}"
    urls = [base]
    if path:
        sanitized_path = path.strip("/")
        if sanitized_path:
            urls.append(f"{base}/{sanitized_path}")
    return tuple(urls)


def _auth_server_hint_urls(authorization_servers: Tuple[str, ...]) -> Tuple[str, ...]:
    urls: list[str] = []
    seen: set[str] = set()

    for server in authorization_servers:
        candidate = server.strip()
        if not candidate:
            continue

        if candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)

        parsed = urlparse(candidate)
        if not parsed.scheme or not parsed.netloc:
            continue

        base = candidate.rstrip("/")
        oauth_url = f"{base}/.well-known/oauth-authorization-server"
        openid_url = f"{base}/.well-known/openid-configuration"

        for url in (oauth_url, openid_url):
            if url not in seen:
                seen.add(url)
                urls.append(url)

    return tuple(urls)


def _discover_protected_metadata(*, scheme: str, host: str, path: str | None) -> Tuple[str, OAuthProtectedMetadata] | None:
    urls = _build_well_known_urls(scheme=scheme, host=host, resource="oauth-protected-resource", path=path)
    return _discover_from_urls(urls, _parse_protected_metadata)


def _discover_auth_server_metadata(
    *,
    scheme: str,
    host: str,
    path: str | None,
    authorization_servers: Tuple[str, ...] | None,
) -> Tuple[str, OAuthServerMetadata] | None:
    urls: list[str] = []
    if authorization_servers:
        urls.extend(_auth_server_hint_urls(authorization_servers))

    urls.extend(_build_well_known_urls(scheme=scheme, host=host, resource="oauth-authorization-server", path=path))
    urls.extend(_build_well_known_urls(scheme=scheme, host=host, resource="openid-configuration", path=path))

    return _discover_from_urls(urls, _parse_server_metadata)


@lru_cache(maxsize=1)
def discover_oauth_metadata(mcp_server_url: str) -> OAuthMetadata | None:
    parsed = urlparse(mcp_server_url)
    scheme = parsed.scheme
    host = parsed.netloc
    path = parsed.path.lstrip("/") if parsed.path else ""

    protected_result = _discover_protected_metadata(scheme=scheme, host=host, path=path)
    authorization_servers = protected_result[1].authorization_servers if protected_result else None

    auth_server_result = _discover_auth_server_metadata(
        scheme=scheme,
        host=host,
        path=path,
        authorization_servers=authorization_servers,
    )

    if auth_server_result is None:
        return None

    protected_url, protected_metadata = protected_result if protected_result else (None, None)
    auth_url, auth_metadata = auth_server_result

    return OAuthMetadata(
        auth_server_metadata=auth_metadata,
        protected_metadata=protected_metadata,
        protected_metadata_url=protected_url,
        auth_server_metadata_url=auth_url,
    )


def generate_pkce_pair() -> Tuple[str, str, str]:
    """Return ``(code_verifier, code_challenge, method)``."""

    code_verifier, code_challenge = get_code_verifier()
    return code_verifier, code_challenge, "S256"


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
        verify=REQUESTS_VERIFY_SSL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        timeout=10,
    )
    response.raise_for_status()
    token_data = response.json()
    if not isinstance(token_data, Mapping):
        raise RuntimeError("Token endpoint returned non-JSON response")
    return dict(token_data)
