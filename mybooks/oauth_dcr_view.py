import logging

from oauth2_provider.models import Application
from oauth_dcr.views import DynamicClientRegistrationView as BaseDCRView

logger = logging.getLogger(__name__)


class DynamicClientRegistrationView(BaseDCRView):
    """
    Extended DCR view that fixes client type determination for PKCE flows.

    Overrides oauth_dcr to ensure authorization_code grants with PKCE
    register as PUBLIC clients instead of CONFIDENTIAL.
    """

    def _validate_client_metadata(self, metadata):
        """
        Override parent to fix client type determination.

        The oauth_dcr package incorrectly checks mapped grant types (Django constants)
        instead of the original grant_types from the request, causing authorization_code
        flows to default to CONFIDENTIAL instead of PUBLIC.
        """
        processed = super()._validate_client_metadata(metadata)
        grant_types = metadata.get("grant_types", ["authorization_code"])
        token_endpoint_auth_method = metadata.get("token_endpoint_auth_method", "client_secret_basic")

        # RFC 7591: Clients using "none" are public clients (PKCE-only, no secret)
        if token_endpoint_auth_method == "none" or "authorization_code" in grant_types:
            processed["client_type"] = Application.CLIENT_PUBLIC
        if "client_credentials" in grant_types:
            processed["client_type"] = Application.CLIENT_CONFIDENTIAL
        elif "implicit" in grant_types:
            processed["client_type"] = Application.CLIENT_PUBLIC
        else:
            processed["client_type"] = Application.CLIENT_PUBLIC

        return processed
