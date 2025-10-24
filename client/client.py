import asyncio
import html
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import httpx
import oauth
import oauth_flow
import requests
import streamlit as st
import truststore
from app_data_store import ClientAppData, ClientAppDataStore
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from streamlit_cookies_controller import CookieController as StreamlitCookieController
from utils import first_query_value, flatten_exceptions, truncate

from mybooks.utils import strtobool

if TYPE_CHECKING:  # pragma: no cover - type checking only
    pass

# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent

DOTENV_PATH = BASE_DIR / ".env"
if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)
else:
    load_dotenv()

# APP
CLIENT_URL = os.environ["CLIENT_URL"]
CURRENT_APP_DATA: Optional[ClientAppData] = None
FORCE_RERUN_KEY = "_force_rerun"

MCP_SERVER_URL = os.environ["MCP_SERVER_URL"]

# OAUTH
REDIRECT_URI = CLIENT_URL
OAUTH_SCOPES = "read write"
OAUTH_USER_AUTH_CLIENT_ID = os.environ.get("OAUTH_USER_AUTH_CLIENT_ID")

CLIENT_DCR_REQUIRES_AUTH = strtobool(os.environ.get("CLIENT_DCR_REQUIRES_AUTH", "false"))
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are a helpful assistant. Use tools if needed.")
MODEL_NAME = os.environ["OPENAI_MODEL"]
API_KEY = os.environ["OPENAI_API_KEY"]
os.environ["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
USER_AVATAR = ":material/person_outline:"
ASSISTANT_AVATAR = ":material/smart_toy:"

MODEL_RESPONSE_SPINNER = """
<style>
.model-response-spinner{display:flex;align-items:center;gap:0.5rem;font-size:0.9rem;}
.model-response-spinner__dots{display:flex;gap:0.3rem;}
.model-response-spinner__dot{width:0.6rem;height:0.6rem;border-radius:50%;background:#ffffff;opacity:0.4;
    animation:model-response-spinner-bounce 1s infinite ease-in-out;}
.model-response-spinner__dot:nth-child(2){animation-delay:0.1s;}
.model-response-spinner__dot:nth-child(3){animation-delay:0.2s;}
@keyframes model-response-spinner-bounce{0%,80%,100%{transform:scale(0.6);opacity:0.3;}
    40%{transform:scale(1);opacity:1;}}
</style>
<div class="model-response-spinner">
  <div class="model-response-spinner__dots">
    <div class="model-response-spinner__dot"></div>
    <div class="model-response-spinner__dot"></div>
    <div class="model-response-spinner__dot"></div>
  </div>
</div>
"""


truststore.inject_into_ssl()


def get_oauth_metadata(server_url: str, unauthorized_response: httpx.Response | None = None):
    metadata: oauth.OAuthMetadata | None = None
    header_url: str | None = None

    if unauthorized_response is not None:
        header_value = unauthorized_response.headers.get("WWW-Authenticate")
        header_url = oauth.extract_resource_metadata_url(header_value)
        if header_url:
            try:
                metadata = oauth.get_oauth_metadata_from_resource_url(header_url)
            except oauth.OAuthDiscoveryError:
                metadata = None

    if metadata is None:
        metadata = oauth.get_oauth_metadata(server_url)

    if metadata is None:
        hint = f" (tried resource metadata: {header_url})" if header_url else ""
        raise oauth.OAuthDiscoveryError(f"Unable to discover OAuth metadata for {server_url}{hint}.")

    return metadata


async def list_tools(server: MCPServerStreamableHTTP) -> Tuple[List[Any], Optional[httpx.Response]]:
    try:
        tools = await server.list_tools()
    except httpx.HTTPStatusError as exc:
        return [], exc.response
    except ExceptionGroup as exc:
        for inner in flatten_exceptions(exc):
            if isinstance(inner, httpx.HTTPStatusError):
                return [], inner.response
        raise exc

    return tools, None


def set_oauth_notice(level: str, message: str) -> None:
    st.session_state["oauth_notice"] = {"level": level, "message": message}


def consume_oauth_notice() -> None:
    notice = st.session_state.pop("oauth_notice", None)
    if not isinstance(notice, dict):
        return

    level = notice.get("level", "info")
    message = notice.get("message")
    if not message:
        return

    renderer = {
        "success": st.success,
        "info": st.info,
        "warning": st.warning,
        "error": st.error,
    }.get(level, st.info)
    renderer(message)


def schedule_rerun() -> None:
    """Request a rerun outside of Streamlit callback execution."""

    st.session_state[FORCE_RERUN_KEY] = True


def trigger_browser_redirect(url: str) -> None:
    """Instruct the browser to navigate to ``url`` in the current tab."""

    # Ensure we deliver the redirect payload immediately and halt further rendering.
    safe_url = html.escape(url, quote=True)
    st.session_state.pop(FORCE_RERUN_KEY, None)
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={safe_url}">',
        unsafe_allow_html=True,
    )
    # st.stop()


def process_oauth_callback() -> None:
    """Handle OAuth authorization code callbacks for active flows."""

    params = st.query_params
    if not params:
        return

    oauth_metadata = get_oauth_metadata(MCP_SERVER_URL)

    code = first_query_value(params.get("code"))
    if not code:
        return

    returned_state = first_query_value(params.get("state"))
    if not returned_state:
        set_oauth_notice("error", "OAuth callback missing state; restart the flow.")
        st.query_params.clear()
        oauth_flow.clear_authorization_state()
        st.rerun()

    if not oauth_flow.authorization_state_matches(returned_state):
        set_oauth_notice("error", "Received OAuth callback without an active flow. Start over.")
        st.query_params.clear()
        oauth_flow.clear_authorization_state()
        st.rerun()

    try:
        tokens = oauth_flow.complete_authorization(
            code=code,
            returned_state=returned_state,
            token_endpoint=oauth_metadata.auth_server_metadata.token_endpoint,
        )
    except oauth_flow.OAuthFlowError as exc:
        set_oauth_notice("error", str(exc))
        st.query_params.clear()
        st.rerun()
    except Exception as exc:
        set_oauth_notice("error", f"OAuth exchange failed: {exc}")
        st.query_params.clear()
        st.rerun()

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not access_token:
        set_oauth_notice("error", "Token response missing access token; restart the flow.")
        st.query_params.clear()
        st.rerun()

    st.session_state.app_data_store.update(
        access_token=access_token,
        refresh_token=refresh_token,
    )
    set_oauth_notice("success", "Authorization completed successfully.")

    st.query_params.clear()
    st.rerun()


def reset_client_authorization(*, clear_registration: bool = False) -> None:
    """Clear stored authorization tokens (and optionally registration metadata)."""

    update_kwargs: Dict[str, Any] = {
        "access_token": None,
        "refresh_token": None,
    }
    if clear_registration:
        update_kwargs.update(
            {
                "client_id": None,
                "client_name": None,
                "client_redirect_uris": None,
                "registration_client_payload": None,
            }
        )

    st.session_state.app_data_store.update(
        **update_kwargs,
    )

    if clear_registration:
        set_oauth_notice("info", "Cleared registration and authorization state.")
    else:
        set_oauth_notice("info", "Cleared stored authorization tokens. Re-authorize the client when ready.")

    oauth_flow.clear_authorization_state()
    schedule_rerun()


def render_metadata_authorization() -> None:

    consume_oauth_notice()

    client = st.session_state.app_data_store.app_data.client
    oauth_metadata = st.session_state.oauth_metadata
    client_registered = client.is_registered
    client_authorized = client.is_authorized

    with st.expander("Metadata Discovery", expanded=client.client_id is None):
        st.markdown("##### OAuth 2.0 Protected Resource Metadata")
        st.text(f"Discovered URL: {oauth_metadata.protected_metadata_url}\n")
        protected_payload = json.dumps(oauth_metadata.protected_metadata.to_dict(), indent=2) if oauth_metadata.protected_metadata else "{}"
        st.code(protected_payload, language="json")

        st.markdown("##### OAuth 2.0 Authorization Server Metadata")
        st.text(f"Discovered URL: {oauth_metadata.auth_server_metadata_url}\n")
        st.code(json.dumps(oauth_metadata.auth_server_metadata.to_dict(), indent=2), language="json")

    with st.expander("Registration and Authorization", expanded=client.access_token is None):
        st.markdown("##### Dynamic Client Registration")
        st.text("Register a new client application")

        if client_registered:
            st.success(f"Client ID: {client.client_id}.")
        else:
            client_name = st.session_state.get("pending_client_name")
            if not isinstance(client_name, str):
                client_name = "Streamlit MCP Client"
                st.session_state.pending_client_name = client_name
                st.session_state["pending_client_name_input"] = client_name

            input_key = "pending_client_name_input"
            if input_key not in st.session_state:
                st.session_state[input_key] = client_name

            name_input = st.text_input("Client Name", key=input_key)
            cleaned_name = name_input.strip()
            effective_name = cleaned_name or client_name
            st.session_state.pending_client_name = effective_name
            client_name = effective_name

            def register_client(client_name: str) -> None:
                try:
                    client_data = oauth_flow.register_dynamic_client(
                        registration_endpoint=oauth_metadata.auth_server_metadata.registration_endpoint,
                        client_name=client_name,
                        redirect_uri=REDIRECT_URI,
                        scope=OAUTH_SCOPES,
                    )
                except requests.HTTPError as exc:
                    response = exc.response
                    status = response.status_code if response is not None else "?"
                    reason = response.reason if response is not None else ""
                    snippet = ""
                    if response is not None:
                        body = (response.text or "").strip()
                        snippet = body[:150] + ("…" if len(body) > 150 else "")
                    message = f"Registration failed: {status} {reason}".rstrip()
                    if snippet:
                        message += f" — {snippet}"
                    set_oauth_notice("error", message)
                    return
                except oauth_flow.OAuthFlowError as exc:
                    set_oauth_notice("error", str(exc))
                    return
                except Exception as exc:
                    set_oauth_notice("error", f"Registration failed: {exc}")
                    return

                client_id = client_data["client_id"]
                client_name = client_data["client_name"]
                client_redirect_uris = client_data["redirect_uris"]

                st.session_state.app_data_store.update(
                    client_id=client_id,
                    client_name=client_name,
                    client_redirect_uris=client_redirect_uris,
                    registration_client_payload=client_data,
                )

                st.session_state.pop("pending_client_name", None)
                st.session_state.pop("pending_client_name_input", None)
                set_oauth_notice("success", "Client registered successfully.")
                schedule_rerun()

            st.button("Register", on_click=lambda: register_client(client_name), use_container_width=True)

        st.markdown("##### Authorize Registered Client")
        st.text("Use authorization code flow with PKCE to authorize client.")
        if not client_registered:
            st.info("Waiting for client to be registered...")
        elif client_authorized:
            st.success("Client authorized and tokens cached.")
            st.button(
                "Reset authorization tokens",
                on_click=reset_client_authorization,
                use_container_width=True,
            )
        else:
            authorize_url = oauth_flow.start_authorization(
                client_id=client.client_id,
                scope=OAUTH_SCOPES,
                redirect_uri=REDIRECT_URI,
                authorization_endpoint=oauth_metadata.auth_server_metadata.authorization_endpoint,
                reuse_existing=True,
            )
            if st.button("Authorize", use_container_width=True):
                trigger_browser_redirect(authorize_url)


def extract_tool_activity(messages: List[ModelMessage]) -> tuple[List[str], bool]:
    """Return activity entries plus whether any tool call was observed."""

    def format_payload(value: Any, *, max_chars: int = 2000) -> tuple[str, str]:
        """Return a clipped string representation and a suggested language for code blocks."""

        if value is None:
            return "null", "text"

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return "", "text"
            try:
                parsed = json.loads(stripped)
            except ValueError:
                text = stripped
                language = "text"
            else:
                text = json.dumps(parsed, ensure_ascii=False, indent=2, default=str)
                language = "json"
        else:
            text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
            language = "json"

        if len(text) > max_chars:
            text = text[: max_chars - 3] + "..."

        return text, language

    def payload_block(value: Any) -> str:
        text, language = format_payload(value)
        if not text:
            return ""
        return f"```{language}\n{text}\n```"

    context_activity: List[str] = []
    tool_activity: List[str] = []
    post_call_activity: List[str] = []
    tool_call_detected = False

    for message in messages:
        if isinstance(message, ModelRequest):
            if message.instructions:
                block = payload_block(message.instructions)
                label = "📨 Model request instructions"
                context_activity.append(f"{label}\n\n{block}" if block else label)

            for part in message.parts:
                if isinstance(part, (ToolReturnPart, BuiltinToolReturnPart)):
                    tool_call_detected = True
                    block = payload_block(part.content)
                    label = f"📤 Tool return to model • `{part.tool_name}`"
                    post_call_activity.append(f"{label}\n\n{block}" if block else label)
                elif isinstance(part, RetryPromptPart):
                    tool_call_detected = True
                    block = payload_block(part.content)
                    base = "🔁 Retry prompt"
                    if part.tool_name:
                        base += f" • `{part.tool_name}`"
                    post_call_activity.append(f"{base}\n\n{block}" if block else base)

            continue

        if not isinstance(message, ModelResponse):
            continue

        for part in message.parts:
            if isinstance(part, (ToolCallPart, BuiltinToolCallPart)):
                tool_call_detected = True
                payload = part.args if part.args is not None else {}
                block = payload_block(payload)
                label = f"🛠 Tool call • `{part.tool_name}`"
                tool_activity.append(f"{label}\n\n{block}" if block else label)
            elif isinstance(part, (ToolReturnPart, BuiltinToolReturnPart)):
                tool_call_detected = True
                block = payload_block(part.content)
                label = f"📥 Tool result • `{part.tool_name}`"
                tool_activity.append(f"{label}\n\n{block}" if block else label)

    if tool_call_detected:
        combined = context_activity + tool_activity + post_call_activity
        return combined, True

    return [], False


def init() -> None:
    cookies = StreamlitCookieController()
    while len(cookies.getAll()) == 0:
        time.sleep(1)

    if not st.session_state.get("app_data_store"):
        app_data_store: ClientAppDataStore = ClientAppDataStore(cookies=cookies)
        st.session_state.app_data_store = app_data_store

    app_data_store: ClientAppDataStore = st.session_state.app_data_store

    if st.session_state.get("oauth_metadata") is None:
        st.session_state.oauth_metadata = None

    if st.query_params:
        process_oauth_callback()

    if not st.session_state.get("_page_configured"):
        st.set_page_config(
            page_title="MCP OAuth Playground",
            layout="wide",
            page_icon=Path("../mybooks/static/mybooks/img/favicon.png"),
        )
        st.session_state._page_configured = True

    st.title("MCP OAuth Playground")
    st.text("Uses OAuth protected resource and auth server discovery, Dynamic Client Registration, and PKCE authorization code flow.")

    client_state = app_data_store.app_data.client
    token = client_state.access_token or ""
    previous_token = st.session_state.get("_mcp_token")
    # AIDEV-NOTE: Cache MCP server/agent; only rebuild when the OAuth token changes.
    needs_server_refresh = "mcp_server" not in st.session_state or token != previous_token

    def ensure_oauth_metadata(response: httpx.Response | None = None, *, force: bool = False) -> None:
        if st.session_state.oauth_metadata is not None and not force:
            return
        st.session_state.oauth_metadata = get_oauth_metadata(server_url=MCP_SERVER_URL, unauthorized_response=response)

    if needs_server_refresh:
        headers: Dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with st.spinner(f"Initializing MCP Server {MCP_SERVER_URL}"):
            mcp_server = MCPServerStreamableHTTP(url=MCP_SERVER_URL, headers=headers)
            st.session_state.mcp_server = mcp_server
            st.session_state._mcp_token = token

            try:
                tools, response = asyncio.run(list_tools(mcp_server))
            except (oauth.OAuthDiscoveryError, ExceptionGroup) as exc:
                st.session_state.tools_error = truncate(str(exc), 120)
                st.session_state.tools = []
                ensure_oauth_metadata(None)
            else:
                if response is not None and response.status_code == 401:
                    st.session_state.tools = []
                    st.session_state.tools_error = "Cannot list tools without authorization."
                    ensure_oauth_metadata(response, force=True)
                else:
                    st.session_state.tools_error = None
                    st.session_state.tools = [tool.name for tool in tools]
                    ensure_oauth_metadata(None)

            st.session_state.agent = Agent(
                model=MODEL_NAME,
                toolsets=[mcp_server],
                system_prompt=SYSTEM_PROMPT,
            )

    else:
        if not st.session_state.get("agent"):
            st.session_state.agent = Agent(
                model=MODEL_NAME,
                toolsets=[st.session_state.mcp_server],
                system_prompt=SYSTEM_PROMPT,
            )
        ensure_oauth_metadata(None)

    if not st.session_state.get("messages"):
        st.session_state.messages = []


def render_sidebar() -> None:
    """Display sidebar controls and quick info."""
    app_data = st.session_state.app_data_store.app_data
    with st.sidebar:
        st.subheader("Session")

        if st.button("New Conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        if st.button("Clear Session", use_container_width=True):
            st.session_state.app_data_store.delete()
            st.session_state.pop("messages", None)
            st.rerun()

        st.divider()
        st.subheader("Model Config")
        st.write({"prompt": SYSTEM_PROMPT, "model": MODEL_NAME})

        st.divider()
        st.subheader("MCP Server")
        with st.spinner("Loading MCP tools list…"):
            mcp_server = st.session_state.mcp_server
            tools_error = st.session_state.tools_error
            tools: Any = st.session_state.tools

            tools_display: Any = tools_error if tools_error else tools
            client = app_data.client
            st.write(
                {
                    "url": mcp_server.url,
                    "tools": tools_display,
                }
            )

        if client.client_id:
            st.divider()
            st.subheader("Client Application")
            st.text("Tokens in shown in plain text for debugging purposes.")

            client_info = {
                "client_name": client.client_name,
                "client_id": client.client_id,
                "client_redirect_uris": client.client_redirect_uris,
                "access_token": client.access_token if client.access_token else None,
                "refresh_token": client.refresh_token if client.refresh_token else None,
            }
            st.write(client_info)


def render_chat_history(messages: List[Dict[str, str]]) -> None:
    for message in messages:
        role = message["role"]
        avatar = USER_AVATAR if role == "user" else ASSISTANT_AVATAR if role == "assistant" else None
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])


def handle_chat_turn(prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    agent: Agent = st.session_state.agent

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        response_placeholder = st.empty()

        async def run_agent() -> None:
            response_placeholder.markdown(MODEL_RESPONSE_SPINNER, unsafe_allow_html=True)
            try:
                result = await agent.run(prompt)
            except Exception as exc:  # pragma: no cover - Streamlit UI path
                flattened = flatten_exceptions(exc)
                http_error = next((err for err in flattened if isinstance(err, httpx.HTTPStatusError)), None)
                if http_error is not None:
                    response = http_error.response
                    info = ""
                    if response is not None:
                        reader = getattr(response, "aread", None)
                        try:
                            if callable(reader):
                                await reader()
                            else:
                                response.read()  # type: ignore[func-returns-value]
                        except Exception:  # pragma: no cover - best effort to read body
                            pass
                        else:
                            try:
                                info = truncate(response.text or "", 120)
                            except httpx.ResponseNotRead:  # pragma: no cover - should be rare
                                info = ""

                    status = response.status_code if response is not None else "?"
                    reason = response.reason_phrase if response is not None else ""
                    message = f"MCP request failed: {status} {reason}".rstrip()

                    if info:
                        message += f" — {info}"
                else:
                    message_parts: list[str] = []
                    for err in flattened:
                        text = str(err).strip()
                        if not text:
                            text = err.__class__.__name__
                        if text not in message_parts:
                            message_parts.append(text)

                    if not message_parts:
                        message_parts.append(exc.__class__.__name__)

                    message = " — ".join(message_parts)
                response_placeholder.error(f"Agent run failed: {message}")
                return

            response_text = result.output if isinstance(result.output, str) else str(result.output)

            tool_activity, tool_call_detected = extract_tool_activity(result.new_messages())
            if tool_call_detected and tool_activity:
                with st.expander("Model Activity", expanded=False):
                    for entry in tool_activity:
                        st.markdown(entry)

            response_placeholder.markdown(response_text)

            st.session_state.messages.append({"role": "assistant", "content": response_text})

        asyncio.run(run_agent())


init()

render_sidebar()

render_metadata_authorization()

render_chat_history(st.session_state.messages)

if st.session_state.pop(FORCE_RERUN_KEY, False):
    st.rerun()

if prompt := st.chat_input("Ask me something…"):
    handle_chat_turn(prompt)
