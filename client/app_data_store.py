"""Persistence helpers for Streamlit client OAuth data."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from streamlit_cookies_controller import CookieController as StreamlitCookieController

CURRENT_USER_KEY: Optional[str] = None
USER_COOKIE_NAME = "streamlit-client-user"
USER_COOKIE_SESSION_KEY = "streamlit-client-user-session"
USER_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
_CLIENT_DIR = Path(__file__).resolve().parent
_UNSET = object()


@dataclass
class ClientAppData:
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    client_redirect_uris: Optional[List[str]] = None
    oauth_access_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    registration_client_uri: Optional[str] = None
    registration_client_payload: Optional[Dict[str, Any]] = None

    """Manage persistence of :class:`AppData` objects."""

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "ClientAppData":
        known_fields = {
            "client_id": payload.get("client_id"),
            "client_name": payload.get("client_name"),
            "client_redirect_uris": payload.get("client_redirect_uris"),
            "oauth_access_token": payload.get("oauth_access_token"),
            "oauth_refresh_token": payload.get("oauth_refresh_token"),
            "registration_client_uri": payload.get("registration_client_uri"),
        }
        registration_payload = payload.get("registration_client_payload")
        if isinstance(registration_payload, dict):
            known_fields["registration_client_payload"] = registration_payload
        else:
            known_fields["registration_client_payload"] = None
        return cls(**known_fields)

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def client(self) -> "ClientAppState":
        return ClientAppState(
            client_id=self.client_id,
            client_name=self.client_name,
            client_redirect_uris=self.client_redirect_uris,
            access_token=self.oauth_access_token,
            refresh_token=self.oauth_refresh_token,
            registration_client_uri=self.registration_client_uri,
        )


class ClientAppDataStore:
    _instance: ClientAppDataStore = None
    _app_data: ClientAppData = None
    _user_session_key: str = None
    _session_file_path: Path = None
    _cookies: StreamlitCookieController = None

    def __init__(self, cookies: StreamlitCookieController) -> None:
        self._cookies = cookies
        self._load()

    def _load(self):
        if self._cookies.get(USER_COOKIE_NAME):
            self._user_session_key = self._cookies.get(USER_COOKIE_NAME)
        else:
            self._user_session_key = uuid.uuid4().hex
            self._cookies.set(USER_COOKIE_NAME, self._user_session_key)

        self._session_file_path = Path(_CLIENT_DIR / f".session-{self._user_session_key}.json")

        if not self._session_file_path.exists():
            self._app_data = ClientAppData()
            self.save()

        raw = self._session_file_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        self._app_data = ClientAppData.from_json(data)

    @property
    def app_data(self) -> ClientAppData:
        """Return the current app data."""
        if self._app_data is None:
            self._app_data = ClientAppData()
        return self._app_data

    @property
    def user_key(self) -> str:
        return self._user_session_key

    def save(self) -> None:
        if self._app_data is None:
            return
        payload = json.dumps(self._app_data.to_json(), indent=2, sort_keys=True)
        self._session_file_path.write_text(payload, encoding="utf-8")

    def update(
        self,
        *,
        client_id: Optional[str] | object = _UNSET,
        client_name: Optional[str] | object = _UNSET,
        client_redirect_uris: Optional[List[str]] | object = _UNSET,
        oauth_access_token: Optional[str] | object = _UNSET,
        oauth_refresh_token: Optional[str] | object = _UNSET,
        registration_client_uri: Optional[str] | object = _UNSET,
        registration_client_payload: Optional[Dict[str, Any]] | object = _UNSET,
    ) -> ClientAppData:

        payload = {
            "client_id": self._app_data.client_id,
            "client_name": self._app_data.client_name,
            "client_redirect_uris": self._app_data.client_redirect_uris,
            "oauth_access_token": self._app_data.oauth_access_token,
            "oauth_refresh_token": self._app_data.oauth_refresh_token,
            "registration_client_uri": self._app_data.registration_client_uri,
            "registration_client_payload": self._app_data.registration_client_payload,
        }

        if client_id is not _UNSET:
            payload["client_id"] = client_id
        if client_name is not _UNSET:
            payload["client_name"] = client_name
        if client_redirect_uris is not _UNSET:
            payload["client_redirect_uris"] = client_redirect_uris
        if oauth_access_token is not _UNSET:
            payload["oauth_access_token"] = oauth_access_token
        if oauth_refresh_token is not _UNSET:
            payload["oauth_refresh_token"] = oauth_refresh_token
        if registration_client_uri is not _UNSET:
            payload["registration_client_uri"] = registration_client_uri
        if registration_client_payload is not _UNSET:
            payload["registration_client_payload"] = registration_client_payload

        self._app_data = ClientAppData(**payload)
        self.save()

    def delete(self) -> None:
        if self._session_file_path is None:
            return

        self._session_file_path.unlink(missing_ok=True)
        self._app_data = ClientAppData()


@dataclass(frozen=True)
class UserAuthState:
    """Immutable snapshot of bootstrap user authentication tokens."""

    access_token: Optional[str]
    refresh_token: Optional[str]

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)


@dataclass(frozen=True)
class ClientAppState:
    client_id: Optional[str]
    client_name: Optional[str]
    client_redirect_uris: Optional[List[str]]
    access_token: Optional[str]
    refresh_token: Optional[str]
    registration_client_uri: Optional[str]

    @property
    def is_registered(self) -> bool:
        return bool(self.client_id)

    @property
    def is_authorized(self) -> bool:
        return bool(self.access_token)
