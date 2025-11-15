"""
Debugging middleware to log request headers.
Use this temporarily when debugging MCP server authentication issues.
"""

import logging

logger = logging.getLogger(__name__)


class HeaderDebugMiddleware:
    """
    Log all incoming request headers for debugging auth issues.
    Enable by adding to MIDDLEWARE in settings.py. Remove after debugging.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log all headers for API requests
        if request.path.startswith("/api/") or request.path.startswith("/o/"):
            headers = {}
            for key, value in request.META.items():
                if key.startswith("HTTP_"):
                    # Convert HTTP_AUTHORIZATION to Authorization
                    header_name = key[5:].replace("_", "-").title()
                    headers[header_name] = value
                elif key in ["CONTENT_TYPE", "CONTENT_LENGTH"]:
                    headers[key.replace("_", "-").title()] = value

            logger.info(f"🔍 DEBUG HEADERS for {request.method} {request.path}")
            logger.info(f"   Remote IP: {request.META.get('REMOTE_ADDR', 'unknown')}")
            logger.info(f"   User-Agent: {request.META.get('HTTP_USER_AGENT', 'none')}")

            if headers:
                for name, value in headers.items():
                    if name.lower() == "authorization":
                        # Mask the token for security, show only type and first few chars
                        if value.startswith("Bearer "):
                            masked_value = f"Bearer {value[7:15]}***"
                        elif value.startswith("Token "):
                            masked_value = f"Token {value[6:14]}***"
                        else:
                            masked_value = f"{value[:10]}***"
                        logger.info(f"   {name}: {masked_value}")
                    else:
                        logger.info(f"   {name}: {value}")
            else:
                logger.warning("   ⚠️  No HTTP headers found!")

        response = self.get_response(request)
        return response
