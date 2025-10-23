"""Persistence helpers for Streamlit agent OAuth data."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from streamlit_cookies_controller import CookieController as StreamlitCookieController

CURRENT_USER_KEY: Optional[str] = None
USER_COOKIE_NAME = "mybooks-agent-user"
USER_COOKIE_SESSION_KEY = "agent_user_identifier"
USER_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
_AGENT_DIR = Path(__file__).resolve().parent
_UNSET = object()


@dataclass
class AppData:
    user_refresh_token: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_access_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    registration_access_token: Optional[str] = None
    registration_client_uri: Optional[str] = None
    registration_client_payload: Optional[Dict[str, Any]] = None

    """Manage persistence of :class:`AppData` objects."""

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "AppData":
        known_fields = {
            "oauth_client_id": payload.get("oauth_client_id"),
            "oauth_access_token": payload.get("oauth_access_token"),
            "oauth_refresh_token": payload.get("oauth_refresh_token"),
            "registration_access_token": payload.get("registration_access_token"),
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
    def app_auth(self) -> "AppAuthState":
        return AppAuthState(
            client_id=self.oauth_client_id,
            access_token=self.oauth_access_token,
            refresh_token=self.oauth_refresh_token,
            registration_access_token=self.registration_access_token,
            registration_client_uri=self.registration_client_uri,
        )


class AppDataStore:
    _instance: AppDataStore = None
    _app_data: AppData = None
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

        self._session_file_path = Path(_AGENT_DIR / f".session-{self._user_session_key}.json")

        if not self._session_file_path.exists():
            self._app_data = AppData()
            self.save()

        raw = self._session_file_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        self._app_data = AppData.from_json(data)

    @property
    def app_data(self) -> AppData:
        """Return the current app data."""
        if self._app_data is None:
            self._app_data = AppData()
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
        oauth_client_id: Optional[str] | object = _UNSET,
        oauth_access_token: Optional[str] | object = _UNSET,
        oauth_refresh_token: Optional[str] | object = _UNSET,
        registration_access_token: Optional[str] | object = _UNSET,
        registration_client_uri: Optional[str] | object = _UNSET,
        registration_client_payload: Optional[Dict[str, Any]] | object = _UNSET,
    ) -> AppData:

        payload = {
            "oauth_client_id": self._app_data.oauth_client_id,
            "oauth_access_token": self._app_data.oauth_access_token,
            "oauth_refresh_token": self._app_data.oauth_refresh_token,
            "registration_access_token": self._app_data.registration_access_token,
            "registration_client_uri": self._app_data.registration_client_uri,
            "registration_client_payload": self._app_data.registration_client_payload,
        }

        if oauth_client_id is not _UNSET:
            payload["oauth_client_id"] = oauth_client_id
        if oauth_access_token is not _UNSET:
            payload["oauth_access_token"] = oauth_access_token
        if oauth_refresh_token is not _UNSET:
            payload["oauth_refresh_token"] = oauth_refresh_token
        if registration_access_token is not _UNSET:
            payload["registration_access_token"] = registration_access_token
        if registration_client_uri is not _UNSET:
            payload["registration_client_uri"] = registration_client_uri
        if registration_client_payload is not _UNSET:
            payload["registration_client_payload"] = registration_client_payload

        self._app_data = AppData(**payload)
        self.save()

    def delete(self) -> None:
        if self._session_file_path is None:
            return

        self._session_file_path.unlink(missing_ok=True)
        self._app_data = AppData()


@dataclass(frozen=True)
class UserAuthState:
    """Immutable snapshot of bootstrap user authentication tokens."""

    access_token: Optional[str]
    refresh_token: Optional[str]

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)


@dataclass(frozen=True)
class AppAuthState:
    """Immutable snapshot of registered client credentials and tokens."""

    client_id: Optional[str]
    access_token: Optional[str]
    refresh_token: Optional[str]
    registration_access_token: Optional[str]
    registration_client_uri: Optional[str]

    @property
    def is_registered(self) -> bool:
        return bool(self.client_id)

    @property
    def is_authorized(self) -> bool:
        return bool(self.access_token)
