"""OAuth helper utilities for the Streamlit client."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple, TypeVar
from urllib.parse import urlparse

import requests

from mybooks.utils import get_code_verifier

_DEFAULT_TIMEOUT_SECONDS = 10


T = TypeVar("T")

_RESOURCE_METADATA_RE = re.compile(
    r"resource_metadata=(?:\"(?P<quoted>[^\"]+)\"|(?P<token>[^,\s]+))",
    re.IGNORECASE,
)

# Cache of discovered OAuth metadata
OAUTH_METADATA: Optional["OAuthMetadata"] = None


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
    registration_endpoint: str | None = None
    revocation_endpoint: str | None = None
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
        response = requests.get(url, timeout=_DEFAULT_TIMEOUT_SECONDS)
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


def extract_resource_metadata_url(www_authenticate: str | None) -> str | None:
    """Return the resource metadata URL embedded in a WWW-Authenticate header."""

    if not www_authenticate:
        return None

    match = _RESOURCE_METADATA_RE.search(www_authenticate)
    if not match:
        return None

    value = match.group("quoted") or match.group("token")
    return value.strip() if value else None


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


def _sanitize_path(path: str | None) -> str:
    return path.strip("/") if path else ""


def _append_unique_url(urls: list[str], candidate: str | None) -> None:
    if not candidate:
        return
    sanitized = candidate.strip()
    if sanitized and sanitized not in urls:
        urls.append(sanitized)


def _discover_protected_metadata(url: str) -> Tuple[str, OAuthProtectedMetadata] | None:
    parsed = urlparse(url)
    sanitized_path = _sanitize_path(parsed.path)
    base = f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource"
    urls: list[str] = []
    if sanitized_path:
        urls.append(f"{base}/{sanitized_path}")
    urls.append(base)

    return _discover_from_urls(urls, _parse_protected_metadata)


def _discover_auth_server_metadata(url: str) -> Tuple[str, OAuthServerMetadata] | None:
    parsed = urlparse(url)
    sanitized_path = _sanitize_path(parsed.path)
    root_base = f"{parsed.scheme}://{parsed.netloc}"

    # AIDEV-NOTE: URL order follows spec priority for issuers with and without path components.
    urls: list[str] = []
    if sanitized_path:
        _append_unique_url(urls, f"{root_base}/.well-known/oauth-authorization-server/{sanitized_path}")
        _append_unique_url(urls, f"{root_base}/.well-known/openid-configuration/{sanitized_path}")
        _append_unique_url(urls, f"{root_base}/{sanitized_path}/.well-known/openid-configuration")

    _append_unique_url(urls, f"{root_base}/.well-known/oauth-authorization-server")
    _append_unique_url(urls, f"{root_base}/.well-known/openid-configuration")

    return _discover_from_urls(urls, _parse_server_metadata)


def get_oauth_metadata_from_resource_url(resource_metadata_url: str) -> OAuthMetadata | None:
    global OAUTH_METADATA

    if OAUTH_METADATA is not None:
        return OAUTH_METADATA

    document = _fetch_json_document(resource_metadata_url)
    if document is None:
        return None

    protected_metadata = _parse_protected_metadata(document)

    auth_server_result = _discover_auth_server_metadata(protected_metadata.authorization_servers[0])

    if auth_server_result is None:
        raise OAuthDiscoveryError("OAuth authorization server metadata could not be resolved from protected metadata hints.")

    auth_url, auth_metadata = auth_server_result

    oauth_metadata = OAuthMetadata(
        auth_server_metadata=auth_metadata,
        auth_server_metadata_url=auth_url,
        protected_metadata=protected_metadata,
        protected_metadata_url=resource_metadata_url,
    )

    OAUTH_METADATA = oauth_metadata

    return oauth_metadata


def get_oauth_metadata(mcp_server_url: str) -> OAuthMetadata | None:
    global OAUTH_METADATA

    if OAUTH_METADATA is not None:
        return OAUTH_METADATA

    protected_result = _discover_protected_metadata(mcp_server_url)
    if protected_result is None:
        return None

    protected_url, protected_metadata = protected_result

    authorization_servers = protected_metadata.authorization_servers
    authorization_server = authorization_servers[0] if authorization_servers else None
    if not authorization_server:
        return None

    auth_server_result = _discover_auth_server_metadata(authorization_server)
    if auth_server_result is None:
        return None

    auth_url, auth_server_metadata = auth_server_result

    oauth_metadata = OAuthMetadata(
        auth_server_metadata=auth_server_metadata,
        protected_metadata=protected_metadata,
        protected_metadata_url=protected_url,
        auth_server_metadata_url=auth_url,
    )

    OAUTH_METADATA = oauth_metadata

    return oauth_metadata


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

    transport = session or requests
    response = transport.post(
        token_endpoint,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        timeout=_DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    token_data = response.json()
    if not isinstance(token_data, Mapping):
        raise TypeError("Token endpoint returned non-JSON response")
    return dict(token_data)
