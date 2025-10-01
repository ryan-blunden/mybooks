import asyncio
import html
import json
import os
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx
import oauth_flow
import requests
import streamlit as st
from app_data_store import AppData, AppDataStore
from dotenv import load_dotenv
from oauth import OAuthDiscoveryError, discover_oauth_metadata
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
from utils import first_query_value, truncate

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
APP_URL = os.environ["APP_URL"]
CURRENT_APP_DATA: Optional[AppData] = None
FORCE_RERUN_KEY = "_force_rerun"

# OAUTHhttps://mybooks.ngrok.app
OAUTH_SERVER_URL = os.environ["OAUTH_SERVER_URL"]
REDIRECT_URI = APP_URL
AUTH_OAUTH_SCOPE = "read write openid profile email"
APP_OAUTH_SCOPE = "read write"
OAUTH_USER_AUTH_CLIENT_ID = os.environ.get("OAUTH_USER_AUTH_CLIENT_ID")

try:
    OAUTH_METADATA = discover_oauth_metadata(OAUTH_SERVER_URL)
except OAuthDiscoveryError as e:
    OAUTH_METADATA = None
    st.error(str(e))
    st.stop()

# AGENT
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are a helpful assistant. Use tools if needed.")
MODEL_NAME = os.environ["OPENAI_MODEL"]
API_KEY = os.environ["OPENAI_API_KEY"]
os.environ["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

# MCP
MCP_SERVER_URL = os.environ["MCP_URL"]
MCP_AUTH_KEY = os.environ.get("MCP_AUTH_KEY")
MCP_AUTH_VALUE_PREFIX = os.environ.get("MCP_AUTH_VALUE_PREFIX", "")

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

    code = first_query_value(params.get("code"))
    if not code:
        return

    returned_state = first_query_value(params.get("state"))
    if not returned_state:
        set_oauth_notice("error", "OAuth callback missing state; restart the flow.")
        st.query_params.clear()
        oauth_flow.clear_all_flows()
        st.rerun()

    pending_flow = oauth_flow.find_flow_by_state(returned_state)
    if not pending_flow:
        set_oauth_notice("error", "Received OAuth callback without an active flow. Start over.")
        st.query_params.clear()
        oauth_flow.clear_all_flows()
        st.rerun()

    try:
        tokens = oauth_flow.handle_authorization_callback(
            name=pending_flow,
            code=code,
            returned_state=returned_state,
            token_endpoint=OAUTH_METADATA.token_endpoint,
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

    if pending_flow == oauth_flow.FLOW_USER_LOGIN:
        st.session_state.app_data_store.update(
            user_access_token=access_token,
            user_refresh_token=refresh_token,
        )
        set_oauth_notice("success", "Signed in successfully. You can now register a client application.")
    elif pending_flow == oauth_flow.FLOW_APP_AUTHORIZE:
        st.session_state.app_data_store.update(
            oauth_access_token=access_token,
            oauth_refresh_token=refresh_token,
        )
        set_oauth_notice("success", "Agent application authorized and tokens cached.")
    else:
        set_oauth_notice("warning", "OAuth callback handled but flow type was unrecognized.")

    st.query_params.clear()
    st.rerun()


def reset_login_tokens() -> None:
    """Clear cached login tokens and rerun the app."""

    st.session_state.app_data_store.update(
        user_access_token=None,
        user_refresh_token=None,
    )

    set_oauth_notice("info", "Cleared stored login tokens.")
    oauth_flow.clear_all_flows()
    schedule_rerun()


def reset_agent_authorization(*, clear_registration: bool = False) -> None:
    """Clear stored authorization tokens (and optionally registration metadata)."""

    update_kwargs: Dict[str, Any] = {
        "oauth_access_token": None,
        "oauth_refresh_token": None,
    }
    if clear_registration:
        update_kwargs.update(
            {
                "oauth_client_id": None,
                "registration_access_token": None,
                "registration_client_uri": None,
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

    oauth_flow.clear_all_flows()
    schedule_rerun()


def render_connection_setup() -> None:
    """Render the guided OAuth setup flow for the agent."""

    consume_oauth_notice()

    user_state = st.session_state.app_data_store.app_data.user_auth
    app_state = st.session_state.app_data_store.app_data.app_auth

    registration_endpoint = OAUTH_METADATA.registration_endpoint

    user_authenticated = user_state.is_authenticated
    client_registered = app_state.is_registered
    client_authorized = app_state.is_authorized

    with st.expander("Authentication and Authorization", expanded=True):
        st.markdown("##### 1. Sign In")
        st.text("Uses an OAuth 2.0 authorization code flow to authenticate the user.")
        if not user_authenticated:
            authorize_url = oauth_flow.start_authorization_flow(
                name=oauth_flow.FLOW_USER_LOGIN,
                client_id=OAUTH_USER_AUTH_CLIENT_ID,
                scope=AUTH_OAUTH_SCOPE,
                redirect_uri=REDIRECT_URI,
                authorization_endpoint=OAUTH_METADATA.authorization_endpoint,
                reuse_existing=True,
            )
            if st.button("Sign in with OAuth", use_container_width=True):
                print("Authorization URL:", authorize_url)
                trigger_browser_redirect(authorize_url)
        else:
            st.success("Signed in successfully.")
            st.button("Sign Out", on_click=reset_login_tokens, use_container_width=True)

        st.markdown("##### 2. Dynamic Client Registration")
        st.text("Dynamically register a new client application if one doesn't exist.")
        if not user_authenticated:
            st.info("Sign in first to enable dynamic client registration.")
        elif client_registered:
            st.success(f"Client ID: {app_state.client_id}.")
        else:
            client_name = st.session_state.get("pending_client_name")
            if not isinstance(client_name, str):
                client_name = f"MyBooks Agent {uuid.uuid4().hex[:6]}"
                st.session_state.pending_client_name = client_name
                st.session_state["pending_client_name_input"] = client_name

            input_key = "pending_client_name_input"
            if input_key not in st.session_state:
                st.session_state[input_key] = client_name

            name_input = st.text_input("Client name", key=input_key)
            cleaned_name = name_input.strip()
            effective_name = cleaned_name or client_name
            st.session_state.pending_client_name = effective_name
            client_name = effective_name

            def register_client() -> None:
                access_token = st.session_state.app_data_store.app_data.user_auth.access_token
                if not access_token:
                    set_oauth_notice("error", "Login expired; sign in again before registering.")
                    return

                try:
                    client_data = oauth_flow.register_dynamic_client(
                        registration_endpoint=registration_endpoint,
                        access_token=access_token,
                        client_name=client_name,
                        redirect_uri=REDIRECT_URI,
                        scope=APP_OAUTH_SCOPE,
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

                client_id = client_data.get("client_id")
                if not client_id:
                    set_oauth_notice("error", "Registration response missing client_id.")
                    return

                st.session_state.app_data_store.update(
                    oauth_client_id=client_id,
                    registration_access_token=client_data.get("registration_access_token"),
                    registration_client_uri=client_data.get("registration_client_uri"),
                    registration_client_payload=client_data,
                )

                st.session_state.pop("pending_client_name", None)
                st.session_state.pop("pending_client_name_input", None)
                set_oauth_notice("success", "Client registered successfully.")
                schedule_rerun()

            st.button("Register OAuth client", on_click=register_client, use_container_width=True)

        st.markdown("##### 3. Authorize Registered Application")
        st.text("Uses an OAuth 2.0 authorization code with the dynamically registered application.")
        if not client_registered:
            st.info("Register the client before requesting authorization.")
        elif client_authorized:
            st.success("Client authorized successfully.")
            st.button(
                "Reset authorization tokens",
                on_click=reset_agent_authorization,
                use_container_width=True,
            )
        else:
            authorize_url = oauth_flow.start_authorization_flow(
                name=oauth_flow.FLOW_APP_AUTHORIZE,
                client_id=app_state.client_id,
                scope=APP_OAUTH_SCOPE,
                redirect_uri=REDIRECT_URI,
                authorization_endpoint=OAUTH_METADATA.authorization_endpoint,
                reuse_existing=True,
            )
            if st.button("Authorize registered client", use_container_width=True):
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


def flatten_exceptions(exc: BaseException) -> List[BaseException]:
    """Recursively flatten ExceptionGroup hierarchies for human-friendly error reporting."""

    if isinstance(exc, BaseExceptionGroup):
        flattened: List[BaseException] = []
        for inner in exc.exceptions:  # type: ignore[attr-defined]
            flattened.extend(flatten_exceptions(inner))
        return flattened

    return [exc]


def init() -> None:
    """Bootstrap Streamlit session state for chat + agent."""

    st.set_page_config(page_title="MCP OAuth 2.1 PKCE and DCR", page_icon="🤖")
    st.title("MCP OAuth 2.1 PKCE and DCR")
    cookies = StreamlitCookieController()

    while len(cookies.getAll()) == 0:
        time.sleep(1)

    app_data_store: AppDataStore = AppDataStore(cookies=cookies)
    st.session_state.app_data_store = app_data_store

    headers: Dict[str, str] = {}
    app_state = app_data_store.app_data.app_auth
    token = app_state.access_token or ""
    mcp_server: Optional[MCPServerStreamableHTTP] = None
    if token:
        headers[MCP_AUTH_KEY] = f"{MCP_AUTH_VALUE_PREFIX}{token}"
        mcp_server = MCPServerStreamableHTTP(url=MCP_SERVER_URL, headers=headers)
        st.session_state.mcp_server = mcp_server

    if mcp_server is None:
        agent = Agent(
            model=MODEL_NAME,
            system_prompt=SYSTEM_PROMPT,
        )
    else:
        agent = Agent(
            model=MODEL_NAME,
            toolsets=[mcp_server],
            system_prompt=SYSTEM_PROMPT,
        )
    st.session_state.agent = agent

    if "messages" not in st.session_state:
        st.session_state.messages = []


def render_sidebar() -> None:
    """Display sidebar controls and quick info."""
    app_data = st.session_state.app_data_store.app_data
    with st.sidebar:
        st.subheader("Session")
        # st.caption("Prototype uses hard-coded model & API key. Later steps move these to env vars.")

        if st.button("New conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        st.divider()
        st.subheader("Agent Config")
        st.write({"prompt": SYSTEM_PROMPT, "model": MODEL_NAME})

        st.divider()
        st.subheader("MCP Config")
        mcp_server = st.session_state.get("mcp_server")
        tools: List[str] = []
        tools_error = None
        if mcp_server is not None:
            with st.spinner("Loading MCP tools list…"):
                try:
                    tools = asyncio.run(st.session_state.mcp_server.list_tools())
                except Exception as exc:  # pragma: no cover - Streamlit UI path
                    tools_error = truncate(str(exc), 120)
                else:
                    tools = [tool.name for tool in tools]
                    tools_error = None

        tools_display: Any = f"Error: {tools_error}" if tools_error else tools
        app_state = app_data.app_auth
        st.write(
            {
                "url": MCP_SERVER_URL,
                "enabled": mcp_server is not None,
                "auth_header_key": MCP_AUTH_KEY,
                "auth_header_value": app_state.access_token if app_state.access_token else None,
                "tools": tools_display,
            }
        )

        if app_state.client_id:
            st.divider()
            st.subheader("Client Application")
            client_payload = app_data.registration_client_payload or {}
            client_info = {
                "name": client_payload.get("client_name") or "unknown",
                "client_id": app_state.client_id,
                "redirect_uris": client_payload.get("redirect_uris") or app_data.registration_client_uri,
                "grant_types": client_payload.get("grant_types"),
            }
            st.write(client_info)

        st.divider()
        st.subheader("App Data")
        user_state = app_data.user_auth
        app_state = app_data.app_auth
        st.write(
            {
                "user_access_token": user_state.access_token if user_state.access_token else None,
                "user_refresh_token": user_state.refresh_token if user_state.refresh_token else None,
                "app_client_id": app_state.client_id or None,
                "app_access_token": app_state.access_token if app_state.access_token else None,
                "app_refresh_token": app_state.refresh_token if app_state.refresh_token else None,
            }
        )


def render_chat_history(messages: List[Dict[str, str]]) -> None:
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def handle_chat_turn(prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    agent: Agent = st.session_state.agent

    with st.chat_message("assistant"):
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
                    message = str(exc)
                response_placeholder.error(f"Agent run failed: {message}")
                return

            response_text = result.output if isinstance(result.output, str) else str(result.output)

            tool_activity, tool_call_detected = extract_tool_activity(result.new_messages())
            if tool_call_detected and tool_activity:
                with st.expander("Agent Activity", expanded=False):
                    for entry in tool_activity:
                        st.markdown(entry)

            response_placeholder.markdown(response_text)

            st.session_state.messages.append({"role": "assistant", "content": response_text})

        asyncio.run(run_agent())


init()

process_oauth_callback()

render_sidebar()

render_connection_setup()

render_chat_history(st.session_state.messages)

if st.session_state.pop(FORCE_RERUN_KEY, False):
    st.rerun()

if prompt := st.chat_input("Ask me something…"):
    handle_chat_turn(prompt)
