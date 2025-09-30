"""Persistence helpers for Streamlit agent OAuth data."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_AGENT_DIR = Path(__file__).resolve().parent
_DEFAULT_FILE = _AGENT_DIR / ".app_data.json"
_USER_FILE_TEMPLATE = ".app_user_data-{slug}.json"
_UNSET = object()


def _slugify_user_id(user_id: str) -> str:
    """Return a filesystem-friendly slug for storing user-specific data."""

    normalized = user_id.strip()
    if not normalized:
        return "default"

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", normalized)
    slug = slug.strip("-")
    return slug.lower() or "default"


@dataclass
class AppData:
    user_id: Optional[str] = None
    user_access_token: Optional[str] = None
    user_refresh_token: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_access_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    registration_access_token: Optional[str] = None
    registration_client_uri: Optional[str] = None

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "AppData":
        known_fields = {
            "user_id": payload.get("user_id"),
            "user_access_token": payload.get("user_access_token"),
            "user_refresh_token": payload.get("user_refresh_token"),
            "oauth_client_id": payload.get("oauth_client_id"),
            "oauth_access_token": payload.get("oauth_access_token"),
            "oauth_refresh_token": payload.get("oauth_refresh_token"),
            "registration_access_token": payload.get("registration_access_token"),
            "registration_client_uri": payload.get("registration_client_uri"),
        }
        return cls(**known_fields)

    def to_json(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    def user_auth(self) -> "UserAuthState":
        return UserAuthState(
            user_id=self.user_id,
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
    """Manage persistence of :class:`AppData` objects per user."""

    @staticmethod
    def _path_for_user(user_id: Optional[str]) -> Path:
        if not user_id:
            return _DEFAULT_FILE

        slug = _slugify_user_id(user_id)
        return _AGENT_DIR / _USER_FILE_TEMPLATE.format(slug=slug)

    @staticmethod
    def _pointer_path() -> Path:
        return _AGENT_DIR / ".app_data.meta.json"

    @classmethod
    def _read_last_user_id(cls) -> Optional[str]:
        path = cls._pointer_path()
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            path.unlink(missing_ok=True)
            return None

        if not isinstance(data, dict):
            path.unlink(missing_ok=True)
            return None

        hinted = data.get("active_user_id")
        if isinstance(hinted, str) and hinted.strip():
            return hinted.strip()
        return None

    @classmethod
    def _write_last_user_id(cls, user_id: Optional[str]) -> None:
        path = cls._pointer_path()
        if not user_id:
            path.unlink(missing_ok=True)
            return

        payload = json.dumps({"active_user_id": user_id}, indent=2, sort_keys=True)
        path.write_text(payload, encoding="utf-8")

    @classmethod
    def load(cls, user_id: Optional[str] = None) -> Optional[AppData]:
        path = cls._path_for_user(user_id)

        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            if user_id is None:
                # Fallback: if the default file is missing but we stored a user pointer elsewhere,
                # attempt to resolve using the last-known user slug.
                pointer = cls._read_last_user_id()
                if pointer:
                    return cls.load(pointer)
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        # Legacy pointer-only payloads may only carry ``active_user_id`` to hint at the last session.
        if "user_id" not in data:
            hinted_user = data.get("active_user_id")
            if isinstance(hinted_user, str) and hinted_user.strip():
                return cls.load(hinted_user.strip())
            return None

        return AppData.from_json(data)

    @classmethod
    def save(cls, data: AppData) -> None:
        path = cls._path_for_user(data.user_id)
        payload = json.dumps(data.to_json(), indent=2, sort_keys=True)
        path.write_text(payload, encoding="utf-8")

        if data.user_id:
            cls._write_last_user_id(data.user_id)
            # Mirror the latest snapshot into the default file so a fresh session can recover quickly.
            _DEFAULT_FILE.write_text(payload, encoding="utf-8")
        else:
            # If ``user_id`` is cleared, drop the pointer metadata and default snapshot.
            cls._write_last_user_id(None)
            _DEFAULT_FILE.write_text(payload, encoding="utf-8")

    @classmethod
    def update(
        cls,
        current: Optional[AppData],
        *,
        user_id: Optional[str] | object = _UNSET,
        user_access_token: Optional[str] | object = _UNSET,
        user_refresh_token: Optional[str] | object = _UNSET,
        oauth_client_id: Optional[str] | object = _UNSET,
        oauth_access_token: Optional[str] | object = _UNSET,
        oauth_refresh_token: Optional[str] | object = _UNSET,
        registration_access_token: Optional[str] | object = _UNSET,
        registration_client_uri: Optional[str] | object = _UNSET,
    ) -> AppData:
        base = current or AppData()

        payload = {
            "user_id": base.user_id,
            "user_access_token": base.user_access_token,
            "user_refresh_token": base.user_refresh_token,
            "oauth_client_id": base.oauth_client_id,
            "oauth_access_token": base.oauth_access_token,
            "oauth_refresh_token": base.oauth_refresh_token,
            "registration_access_token": base.registration_access_token,
            "registration_client_uri": base.registration_client_uri,
        }

        if user_id is not _UNSET:
            payload["user_id"] = user_id
        if user_access_token is not _UNSET:
            payload["user_access_token"] = user_access_token
        if user_refresh_token is not _UNSET:
            payload["user_refresh_token"] = user_refresh_token
        if oauth_access_token is not _UNSET:
            payload["oauth_access_token"] = oauth_access_token
        if oauth_refresh_token is not _UNSET:
            payload["oauth_refresh_token"] = oauth_refresh_token
        if registration_access_token is not _UNSET:
            payload["registration_access_token"] = registration_access_token
        if registration_client_uri is not _UNSET:
            payload["registration_client_uri"] = registration_client_uri

        old_user_id = base.user_id
        new_user_id = payload["user_id"]
        if old_user_id and new_user_id != old_user_id:
            cls.delete(old_user_id)

        updated = AppData(**payload)
        cls.save(updated)
        return updated

    @classmethod
    def delete(cls, user_id: Optional[str] = None) -> None:
        path = cls._path_for_user(user_id)
        try:
            path.unlink()
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class UserAuthState:
    """Immutable snapshot of bootstrap user authentication tokens."""

    user_id: Optional[str]
    access_token: Optional[str]
    refresh_token: Optional[str]

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    def effective_user_id(self) -> str:
        identifier = (self.user_id or "").strip()
        return identifier or "default"


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
