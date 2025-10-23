"""Lightweight OAuth flow helpers storing transient state on disk."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlencode

import requests
from oauth import exchange_code_for_tokens, generate_pkce_pair

from mybooks.utils import strtobool

FLOW_USER_LOGIN = "user_login"
FLOW_APP_AUTHORIZE = "app_authorize"
REQUESTS_VERIFY_SSL = strtobool(os.getenv("REQUESTS_VERIFY_SSL", "true"))


class OAuthFlowError(RuntimeError):
    """Raised when an OAuth flow encounters an unrecoverable error."""


def _flow_path(name: str) -> Path:
    safe = name.replace("/", "-")
    return Path(tempfile.gettempdir()) / f"agent-oauth-{safe}.json"


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


class AuthorizationFlow:
    """Handle starting and completing a single OAuth authorization-code flow."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._store = OAuthFlowStore(name)

    def start(
        self,
        *,
        client_id: str,
        scope: str,
        redirect_uri: str,
        authorization_endpoint: str,
        reuse_existing: bool = False,
    ) -> str:
        state = self._store.load() if reuse_existing else None
        if state is None:
            state = OAuthFlowState.new(client_id=client_id, redirect_uri=redirect_uri, scope=scope)
        else:
            state = state.with_context(client_id=client_id, redirect_uri=redirect_uri, scope=scope)

        self._store.save(state)

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

    def complete(
        self,
        *,
        code: str,
        returned_state: Optional[str],
        token_endpoint: str,
        client_id_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        state = self._store.load()
        if state is None:
            raise OAuthFlowError("OAuth flow state missing; restart the authorization process.")

        if state.state and returned_state and returned_state != state.state:
            raise OAuthFlowError("State mismatch detected; restart the authorization process.")

        client_id = client_id_override or state.client_id
        if not client_id:
            raise OAuthFlowError("OAuth flow client_id missing; restart the authorization process.")

        tokens = exchange_code_for_tokens(
            token_endpoint,
            authorization_code=code,
            client_id=client_id,
            redirect_uri=state.redirect_uri,
            code_verifier=state.code_verifier,
            state=returned_state,
        )

        self.clear()
        return tokens

    def clear(self) -> None:
        self._store.clear()

    def matches_state(self, state_value: str) -> bool:
        state = self._store.load()
        return bool(state and state.state == state_value)


USER_AUTH_FLOW = AuthorizationFlow(FLOW_USER_LOGIN)
APP_AUTH_FLOW = AuthorizationFlow(FLOW_APP_AUTHORIZE)
_ALL_FLOWS = (USER_AUTH_FLOW, APP_AUTH_FLOW)


def get_flow(name: str) -> AuthorizationFlow:
    if name == FLOW_USER_LOGIN:
        return USER_AUTH_FLOW
    if name == FLOW_APP_AUTHORIZE:
        return APP_AUTH_FLOW
    return AuthorizationFlow(name)


def start_authorization_flow(
    *,
    name: str,
    client_id: str,
    scope: str,
    redirect_uri: str,
    authorization_endpoint: str,
    reuse_existing: bool = False,
) -> str:
    flow = get_flow(name)
    return flow.start(
        client_id=client_id,
        scope=scope,
        redirect_uri=redirect_uri,
        authorization_endpoint=authorization_endpoint,
        reuse_existing=reuse_existing,
    )


def handle_authorization_callback(
    *,
    name: str,
    code: str,
    returned_state: Optional[str],
    token_endpoint: str,
    client_id_override: Optional[str] = None,
) -> Dict[str, Any]:
    flow = get_flow(name)
    return flow.complete(
        code=code,
        returned_state=returned_state,
        token_endpoint=token_endpoint,
        client_id_override=client_id_override,
    )


def find_flow_by_state(state: str) -> Optional[str]:
    for flow in _ALL_FLOWS:
        if flow.matches_state(state):
            return flow.name
    return None


def clear_flow(name: str) -> None:
    get_flow(name).clear()


def clear_all_flows() -> None:
    for flow in _ALL_FLOWS:
        flow.clear()


def register_dynamic_client(
    *,
    registration_endpoint: str,
    client_name: str,
    redirect_uri: str,
    scope: str,
    contacts: Optional[list[str]] = None,
) -> Dict[str, Any]:
    payload = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": scope,
        "token_endpoint_auth_method": "none",
    }
    if contacts:
        payload["contacts"] = contacts

    headers = {
        "Content-Type": "application/json",
    }

    response = requests.post(registration_endpoint, verify=REQUESTS_VERIFY_SSL, json=payload, headers=headers, timeout=10)
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
