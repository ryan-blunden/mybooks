import base64
import hashlib
import random
import string
from typing import Tuple, TypeVar

from django.conf import settings
from django.db.models import Model
from django.urls import reverse

# Generic type variable for model types
ModelType = TypeVar("ModelType", bound=Model)


def strtobool(value: str) -> bool:
    return value.lower() in ("y", "yes", "t", "true", "on", "1")


def is_path_absolute(path):
    return path.startswith("/") or path.startswith("http")


def build_code_challenge(code_verifier: str) -> str:
    """Derive a PKCE code challenge from a verifier."""
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")


def get_code_verifier() -> Tuple[str, str]:
    """Generate a code verifier and its corresponding code challenge for OAuth 2.0 PKCE."""
    code_verifier = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(random.randint(43, 128)))
    code_challenge = build_code_challenge(code_verifier)
    return code_verifier, code_challenge


def get_oauth_server_metadata() -> dict:
    base_url = settings.SITE_URL.rstrip("/")

    metadata = {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}{reverse('oauth2_provider:authorize')}",
        "token_endpoint": f"{base_url}{reverse('oauth2_provider:token')}",
        "registration_endpoint": f"{base_url}{reverse('oauth-register')}",
        "introspection_endpoint": f"{base_url}{reverse('oauth2_provider:introspect')}",
        "revocation_endpoint": f"{base_url}{reverse('oauth2_provider:revoke-token')}",
    }

    # if settings.OAUTH2_PROVIDER.get("OIDC_ENABLED", False):
    #     metadata.update(
    #         {
    #             "userinfo_endpoint": f"{base_url}{reverse('oauth2_provider:user-info')}",
    #             "jwks_uri": f"{base_url}{reverse('oauth2_provider:jwks-info')}",
    #         }
    #     )

    metadata.update(
        {
            "scopes_supported": ["read", "write"],
            "response_types_supported": ["code"],
            "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
            "code_challenge_methods_supported": ["plain", "S256"],
        }
    )

    return metadata
