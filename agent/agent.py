import asyncio
import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional
from urllib.parse import urlencode

import httpx
import logfire
import streamlit as st
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

if TYPE_CHECKING:  # pragma: no cover - type checking only
    pass

# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

for bogus in ["agent", "agent/agent.py"]:
    try:
        sys.path.remove(bogus)
    except ValueError:
        pass

if __package__ in {None, ""}:
    __package__ = "agent"

from .oauth import (  # noqa: E402
    build_pkce_challenge,
    discover_oauth_metadata,
    exchange_code_for_tokens,
    generate_pkce_pair,
)

# ------------------------
# Streamlit + Agent configuration
# ------------------------
# AIDEV-NOTE: MCP_* env vars configure the streamable HTTP server used by the agent.

DOTENV_PATH = BASE_DIR / ".env"
APP_DATA_FILE = Path(__file__).resolve().parent / ".app_data.json"

if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)
else:
    load_dotenv()


def truncate(text: str, length: int) -> str:
    return text if len(text) <= length else text[: length - 3] + "..."


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

  <span>Model is thinking…</span>
</div>
"""


# OAUTH
OAUTH_SERVER = "http://localhost:8080/.well-known/oauth-authorization-server"
REGISTER_FALLBACK_URL = "http://localhost:8080/oauth-apps/register"
REDIRECT_URI = "http://localhost:8501"  # must match app URL
OAUTH_SCOPE = "read write"

# AGENT
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are a helpful assistant. Use tools if needed.")
MODEL_NAME = os.environ["OPENAI_MODEL"]
API_KEY = os.environ["OPENAI_API_KEY"]
os.environ["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

# MCP
MCP_SERVER_URL = os.environ["MCP_URL"]
MCP_AUTH_KEY = os.environ.get("MCP_AUTH_KEY")
MCP_AUTH_VALUE_PREFIX = os.environ.get("MCP_AUTH_VALUE_PREFIX", "")

if os.getenv("LOGFIRE_TOKEN"):
    logfire.configure(token=os.getenv("LOGFIRE_TOKEN"), scrubbing=False)
    logfire.instrument_pydantic_ai()


@dataclass
class AppData:
    oauth_client_id: str = None
    oauth_access_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None


class AppDataManager:
    path: ClassVar[Path] = APP_DATA_FILE

    @classmethod
    def load(cls) -> AppData | None:
        try:
            raw = cls.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return AppData(
                    oauth_client_id=data.get("oauth_client_id"),
                    oauth_access_token=data.get("oauth_access_token"),
                    oauth_refresh_token=data.get("oauth_refresh_token"),
                )
        except json.JSONDecodeError:
            pass

        return None

    @classmethod
    def save(cls, data: AppData) -> None:
        cls.path.write_text(json.dumps(asdict(data), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def update(
        cls,
        current: Optional[AppData],
        *,
        oauth_client_id: Optional[str] = None,
        oauth_access_token: Optional[str] = None,
        oauth_refresh_token: Optional[str] = None,
    ) -> AppData:
        base = current or AppData()
        data = asdict(base)
        if oauth_client_id is not None:
            data["oauth_client_id"] = oauth_client_id
        if oauth_access_token is not None:
            data["oauth_access_token"] = oauth_access_token
        if oauth_refresh_token is not None:
            data["oauth_refresh_token"] = oauth_refresh_token
        updated = AppData(**data)
        cls.save(updated)
        return updated


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


# ------------------------
# Streamlit Setup
# ------------------------
st.set_page_config(page_title="MCP OAuth DCR Test", page_icon="🤖")
st.title("MCP OAuth DCR Test")


def init_state() -> None:
    """Bootstrap Streamlit session state for chat + agent."""

    app_data: Optional[AppData] = AppDataManager.load()
    st.session_state.app_data = app_data

    headers: Dict[str, str] = {}
    token = (app_data.oauth_access_token if app_data else None) or ""
    if token:
        # headers = {"Authorization": f"Bearer {token}"}
        # value = f"{MCP_AUTH_HEADER_PREFIX}{token}" if MCP_AUTH_HEADER_PREFIX else token
        headers[MCP_AUTH_KEY] = f"{MCP_AUTH_VALUE_PREFIX}{token}"
    mcp_server = MCPServerStreamableHTTP(url=MCP_SERVER_URL, headers=headers)
    st.session_state.mcp_server = mcp_server
    if "mcp_server_tools" not in st.session_state:
        st.session_state.mcp_server_tools = None
        st.session_state.mcp_server_tools_error = None

    agent = Agent(
        model=MODEL_NAME,
        toolsets=[mcp_server],
        system_prompt=SYSTEM_PROMPT,
    )
    st.session_state.agent = agent

    oauth_metadata = discover_oauth_metadata(OAUTH_SERVER)
    st.session_state.oauth_metadata = oauth_metadata

    if "messages" not in st.session_state:
        st.session_state.messages = []


init_state()


def render_sidebar() -> None:
    """Display sidebar controls and quick info."""

    with st.sidebar:
        st.subheader("Session")
        # st.caption("Prototype uses hard-coded model & API key. Later steps move these to env vars.")

        if st.button("New conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        st.divider()
        st.subheader("Agent Info")
        st.write({"model": MODEL_NAME, "prompt": SYSTEM_PROMPT})

        st.divider()
        st.subheader("MCP Config")
        tools_state = st.session_state.get("mcp_server_tools")
        tools_error = st.session_state.get("mcp_server_tools_error")
        if tools_state is None:
            with st.spinner("Loading MCP tools list…"):
                try:
                    tools = asyncio.run(st.session_state.mcp_server.list_tools())
                except Exception as exc:  # pragma: no cover - Streamlit UI path
                    tools_state = []
                    tools_error = truncate(str(exc), 120)
                else:
                    tools_state = [tool.name for tool in tools]
                    tools_error = None
            st.session_state.mcp_server_tools = tools_state
            st.session_state.mcp_server_tools_error = tools_error

        if tools_error:
            tools_display: Any = f"Error: {tools_error}"
        else:
            tools_display = tools_state or []

        st.write(
            {
                "url": st.session_state.mcp_server.url,
                "auth_header_key": MCP_AUTH_KEY,
                "auth_header_value": (
                    truncate(st.session_state.app_data.oauth_access_token, 20)
                    if st.session_state.app_data and st.session_state.app_data.oauth_access_token
                    else "unset"
                ),
                "tools": tools_display,
            }
        )

        st.divider()
        st.subheader("App Data")
        app_data = st.session_state.get("app_data")

        st.write(
            {
                "client_id": app_data.oauth_client_id if app_data else "unset",
                "access_token": truncate(app_data.oauth_access_token, 20) if app_data.oauth_access_token else "unset",
                "refresh_token": truncate(app_data.oauth_refresh_token, 20) if app_data.oauth_refresh_token else "unset",
            }
        )


render_sidebar()

# ------------------------
# OAuth Workflow
# ------------------------
metadata_error = st.session_state.get("oauth_metadata_error")
metadata = st.session_state.get("oauth_metadata")

if metadata_error:
    st.error(f"OAuth discovery failed: {metadata_error}")
elif metadata:
    params = st.query_params

    def first_value(raw: Any) -> str | None:
        if raw is None:
            return None
        if isinstance(raw, (list, tuple)):
            return raw[0]
        return str(raw)

    code = first_value(params.get("code"))
    returned_state = first_value(params.get("state"))
    processing_callback = bool(code)

    register_url = metadata.registration_endpoint or REGISTER_FALLBACK_URL
    st.markdown(
        f'<a href="{register_url}" target="_blank" rel="noopener">📝 Register App</a>',
        unsafe_allow_html=True,
    )

    stored_client_id = st.session_state.app_data.oauth_client_id
    with st.form(key="client-id-form"):
        client_id_input = st.text_input(
            "OAuth Client ID",
            stored_client_id or "",
            help="Paste the client identifier generated after registration",
        )
        submitted = st.form_submit_button("Save Client ID")
        if submitted:
            client_id_value = client_id_input.strip() or None
            new_app_data = AppDataManager.update(
                st.session_state.app_data,
                oauth_client_id=client_id_value,
            )
            st.session_state.app_data = new_app_data
            if client_id_value:
                st.session_state["oauth_client_id"] = client_id_value
            else:
                st.session_state.pop("oauth_client_id", None)
            if client_id_value:
                st.success("Client ID saved. Continue with authorization when ready.")
            else:
                st.info("Client ID cleared. Registration must be completed before continuing.")

    client_id = st.session_state.get("oauth_client_id")
    if client_id:
        if "oauth_state" not in st.session_state:
            st.session_state.oauth_state = secrets.token_urlsafe(24)

        if "pkce_verifier" not in st.session_state or "pkce_challenge" not in st.session_state:
            code_verifier, code_challenge, method = generate_pkce_pair()
            st.session_state.pkce_verifier = code_verifier
            st.session_state.pkce_challenge = code_challenge
            st.session_state.pkce_method = method
        elif not processing_callback:
            challenge, method = build_pkce_challenge(st.session_state.pkce_verifier)
            st.session_state.pkce_challenge = challenge
            st.session_state.pkce_method = method

        authorize_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": OAUTH_SCOPE,
            "state": st.session_state.oauth_state,
            "code_challenge": st.session_state.pkce_challenge,
            "code_challenge_method": st.session_state.pkce_method,
        }
        authorize_url = f"{metadata.authorization_endpoint}?{urlencode(authorize_params)}"
        st.markdown(
            f'<a href="{authorize_url}" target="_blank" rel="noopener">🔐 Authorize Agent</a>',
            unsafe_allow_html=True,
        )

    if code and client_id:
        expected_state = st.session_state.get("oauth_state")
        if expected_state and returned_state and returned_state != expected_state:
            st.error(f"State mismatch detected. Expected {expected_state!r}, got {returned_state!r}. Restart the authorization flow.")
        else:
            code_verifier = st.session_state.get("pkce_verifier")
            if not code_verifier:
                st.error("PKCE verifier missing. Restart the authorization flow.")
            else:
                try:
                    tokens = exchange_code_for_tokens(
                        metadata.token_endpoint,
                        authorization_code=code,
                        client_id=client_id,
                        redirect_uri=REDIRECT_URI,
                        code_verifier=code_verifier,
                        state=returned_state,
                    )
                except Exception as exc:  # pragma: no cover - Streamlit UI path
                    st.error(f"Token exchange failed: {exc}")
                else:
                    access_token = tokens.get("access_token")
                    if not access_token:
                        st.error("Token response missing access token. Restart the flow.")
                    else:
                        st.session_state["access_token"] = access_token
                        refresh_token = tokens.get("refresh_token")
                        if refresh_token:
                            st.session_state["refresh_token"] = refresh_token

                        new_app_data = AppDataManager.update(
                            st.session_state.app_data,
                            oauth_client_id=client_id,
                            oauth_access_token=access_token,
                            oauth_refresh_token=refresh_token,
                        )

                        st.success("✅ Access token obtained")

                        for key in [
                            "oauth_state",
                            "pkce_verifier",
                            "pkce_challenge",
                            "pkce_method",
                        ]:
                            st.session_state.pop(key, None)

                        st.experimental_set_query_params()


def render_chat_history(messages: List[Dict[str, str]]) -> None:
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


render_chat_history(st.session_state.messages)


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


if prompt := st.chat_input("Ask me something…"):
    handle_chat_turn(prompt)
