"""Lightweight OAuth flow helpers storing transient state on disk."""

from __future__ import annotations

import json
import secrets
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlencode

import requests
from oauth import exchange_code_for_tokens, generate_pkce_pair

APP_AUTHORIZATION_NAME = "app_authorize"


class OAuthFlowError(RuntimeError):
    """Raised when an OAuth flow encounters an unrecoverable error."""


def _flow_path(name: str) -> Path:
    safe = name.replace("/", "-")
    return Path(tempfile.gettempdir()) / f"client-oauth-{safe}.json"


@dataclass
class OAuthFlowState:
    """Structured snapshot of transient OAuth flow data."""

    client_id: str
    redirect_uri: str
    scope: str
    code_verifier: str
    code_challenge: str
    code_challenge_method: str
    state: str

    @classmethod
    def new(cls, *, client_id: str, redirect_uri: str, scope: str) -> "OAuthFlowState":
        verifier, challenge, method = generate_pkce_pair()
        return cls(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_verifier=verifier,
            code_challenge=challenge,
            code_challenge_method=method,
            state=secrets.token_urlsafe(24),
        )

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> Optional["OAuthFlowState"]:
        try:
            client_id = str(payload["client_id"])
            redirect_uri = str(payload["redirect_uri"])
            scope = str(payload["scope"])
            code_verifier = str(payload["code_verifier"])
            code_challenge = str(payload["code_challenge"])
            code_challenge_method = str(payload["code_challenge_method"])
            state = str(payload["state"])
        except KeyError:
            return None

        if not all((client_id, redirect_uri, scope, code_verifier, code_challenge, code_challenge_method, state)):
            return None

        return cls(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            state=state,
        )

    def to_json(self) -> Dict[str, str]:
        return {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "code_verifier": self.code_verifier,
            "code_challenge": self.code_challenge,
            "code_challenge_method": self.code_challenge_method,
            "state": self.state,
        }

    def with_context(self, *, client_id: str, redirect_uri: str, scope: str) -> "OAuthFlowState":
        return replace(self, client_id=client_id, redirect_uri=redirect_uri, scope=scope)


class OAuthFlowStore:
    """Disk-backed storage for transient :class:`OAuthFlowState`."""

    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def path(self) -> Path:
        return _flow_path(self.name)

    def load(self) -> Optional[OAuthFlowState]:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self.clear()
            return None

        if not isinstance(payload, Mapping):
            self.clear()
            return None

        state = OAuthFlowState.from_json(payload)
        if state is None:
            self.clear()
        return state

    def save(self, state: OAuthFlowState) -> None:
        self.path.write_text(json.dumps(state.to_json(), indent=2, sort_keys=True), encoding="utf-8")

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


_APP_FLOW_STORE = OAuthFlowStore(APP_AUTHORIZATION_NAME)


def start_authorization(
    *,
    client_id: str,
    scope: str,
    redirect_uri: str,
    authorization_endpoint: str,
    reuse_existing: bool = False,
) -> str:
    """Start the single supported OAuth authorization-code flow."""

    state = _APP_FLOW_STORE.load() if reuse_existing else None
    if state is None:
        state = OAuthFlowState.new(client_id=client_id, redirect_uri=redirect_uri, scope=scope)
    else:
        state = state.with_context(client_id=client_id, redirect_uri=redirect_uri, scope=scope)

    _APP_FLOW_STORE.save(state)

    params = {
        "response_type": "code",
        "client_id": state.client_id,
        "redirect_uri": state.redirect_uri,
        "scope": state.scope,
        "state": state.state,
        "code_challenge": state.code_challenge,
        "code_challenge_method": state.code_challenge_method,
    }

    return f"{authorization_endpoint}?{urlencode(params)}"


def complete_authorization(
    *,
    code: str,
    returned_state: Optional[str],
    token_endpoint: str,
    client_id_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Complete the active authorization flow and exchange the code for tokens."""

    state = _APP_FLOW_STORE.load()
    if state is None:
        raise OAuthFlowError("OAuth flow state missing.")

    if state.state and returned_state and returned_state != state.state:
        raise OAuthFlowError("State mismatch detected.")

    client_id = client_id_override or state.client_id
    if not client_id:
        raise OAuthFlowError("OAuth flow client_id missing.")

    tokens = exchange_code_for_tokens(
        token_endpoint,
        authorization_code=code,
        client_id=client_id,
        redirect_uri=state.redirect_uri,
        code_verifier=state.code_verifier,
    )

    clear_authorization_state()
    return tokens


def authorization_state_matches(state_value: str) -> bool:
    """Return True when the persisted authorization state matches ``state_value``."""

    state = _APP_FLOW_STORE.load()
    return bool(state and state.state == state_value)


def clear_authorization_state() -> None:
    """Remove any persisted authorization flow state."""

    _APP_FLOW_STORE.clear()


def register_dynamic_client(
    *,
    registration_endpoint: str,
    client_name: str,
    redirect_uri: str,
    scope: str,
    token_endpoint_auth_method: str = "none",
) -> Dict[str, Any]:
    payload = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": scope,
        "token_endpoint_auth_method": token_endpoint_auth_method,
    }

    headers = {
        "Content-Type": "application/json",
    }

    response = requests.post(registration_endpoint, json=payload, headers=headers, timeout=10)
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover - depends on remote payload
        body = (response.text or "").strip()
        snippet = body[:2000] + ("…" if len(body) > 2000 else "")
        content_type = response.headers.get("Content-Type", "")
        if "html" in content_type.lower():
            detail = "Registration endpoint responded with HTML instead of JSON. "
            detail += "Ensure the request is authorized and the endpoint URL is correct."
        else:
            detail = f"Registration endpoint returned invalid JSON ({exc})."
        if snippet:
            detail += f" Body preview: {snippet}"
        raise OAuthFlowError(detail) from exc

    if not isinstance(data, dict):
        raise OAuthFlowError("Registration endpoint returned invalid payload")
    return data
