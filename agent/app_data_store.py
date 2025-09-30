"""Persistence helpers for Streamlit agent OAuth data."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_AGENT_DIR = Path(__file__).resolve().parent
_DEFAULT_FILE = _AGENT_DIR / ".app_data.json"
_UNSET = object()


@dataclass
class AppData:
    user_access_token: Optional[str] = None
    user_refresh_token: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_access_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    registration_access_token: Optional[str] = None
    registration_client_uri: Optional[str] = None
    registration_client_payload: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "AppData":
        known_fields = {
            "user_access_token": payload.get("user_access_token"),
            "user_refresh_token": payload.get("user_refresh_token"),
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

    def user_auth(self) -> "UserAuthState":
        return UserAuthState(
            access_token=self.user_access_token,
            refresh_token=self.user_refresh_token,
        )

    def app_auth(self) -> "AppAuthState":
        return AppAuthState(
            client_id=self.oauth_client_id,
            access_token=self.oauth_access_token,
            refresh_token=self.oauth_refresh_token,
            registration_access_token=self.registration_access_token,
            registration_client_uri=self.registration_client_uri,
        )


class AppDataStore:
    """Manage persistence of :class:`AppData` objects."""

    @staticmethod
    def _data_path() -> Path:
        return _DEFAULT_FILE

    @classmethod
    def load(cls) -> Optional[AppData]:
        path = cls._data_path()
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        return AppData.from_json(data)

    @classmethod
    def save(cls, data: AppData) -> None:
        payload = json.dumps(data.to_json(), indent=2, sort_keys=True)
        cls._data_path().write_text(payload, encoding="utf-8")

    @classmethod
    def update(
        cls,
        current: Optional[AppData],
        *,
        user_access_token: Optional[str] | object = _UNSET,
        user_refresh_token: Optional[str] | object = _UNSET,
        oauth_client_id: Optional[str] | object = _UNSET,
        oauth_access_token: Optional[str] | object = _UNSET,
        oauth_refresh_token: Optional[str] | object = _UNSET,
        registration_access_token: Optional[str] | object = _UNSET,
        registration_client_uri: Optional[str] | object = _UNSET,
        registration_client_payload: Optional[Dict[str, Any]] | object = _UNSET,
    ) -> AppData:
        base = current or AppData()

        payload = {
            "user_access_token": base.user_access_token,
            "user_refresh_token": base.user_refresh_token,
            "oauth_client_id": base.oauth_client_id,
            "oauth_access_token": base.oauth_access_token,
            "oauth_refresh_token": base.oauth_refresh_token,
            "registration_access_token": base.registration_access_token,
            "registration_client_uri": base.registration_client_uri,
            "registration_client_payload": base.registration_client_payload,
        }

        if user_access_token is not _UNSET:
            payload["user_access_token"] = user_access_token
        if user_refresh_token is not _UNSET:
            payload["user_refresh_token"] = user_refresh_token
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

        updated = AppData(**payload)
        cls.save(updated)
        return updated

    @classmethod
    def delete(cls) -> None:
        cls._data_path().unlink(missing_ok=True)


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
