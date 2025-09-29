import asyncio
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Sequence

import logfire
import requests
import streamlit as st
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelMessage,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from pydantic_ai.toolsets import AbstractToolset

# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent

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


# ------------------------
# OAuth2 Config (replace with real values)
# ------------------------
OAUTH_SERVER = "http://localhost:8080/.well-known/oauth-authorization-server"
AUTH_URL = "https://auth.example.com/authorize"
TOKEN_URL = "https://auth.example.com/token"
CLIENT_ID = "my-client-id"
CLIENT_SECRET = "my-client-secret"
REDIRECT_URI = "http://localhost:8501"  # must match app URL


if os.getenv("LOGFIRE_TOKEN"):
    logfire.configure(token=os.getenv("LOGFIRE_TOKEN"), scrubbing=False)
    logfire.instrument_pydantic_ai()


# ------------------------
# Build agent with tool
# ------------------------
def build_agent(
    model_name: str,
    *,
    toolsets: Sequence["AbstractToolset[Any]"] | None = None,
) -> Agent:
    """Instantiate the Pydantic agent with the mock MCP tool."""

    return Agent(
        model=model_name,
        toolsets=tuple(toolsets or ()),
        system_prompt="You are a helpful assistant. Use tools if needed.",
    )


def load_agent_settings() -> Dict[str, Any]:
    """Resolve agent configuration from required environment variables."""

    model_name = os.environ["OPENAI_MODEL"]
    api_key = os.environ["OPENAI_API_KEY"]

    # Ensure downstream OpenAI-compatible clients read the resolved key.
    os.environ["OPENAI_API_KEY"] = api_key

    app_data_obj = st.session_state.get("app_data")
    app_data_dict = asdict(app_data_obj) if isinstance(app_data_obj, AppData) else {}
    mcp_toolsets, mcp_meta = load_mcp_toolsets(app_data_obj if isinstance(app_data_obj, AppData) else None)

    return {
        "model": model_name,
        "api_key": api_key,
        "toolsets": mcp_toolsets,
        "mcp_meta": mcp_meta,
        "app_data": app_data_dict,
    }


@dataclass
class AppData:
    oauth_client_id: Optional[str] = None
    oauth_access_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None


class AppDataManager:
    """Persistence helpers for OAuth client/token state."""

    path: ClassVar[Path] = APP_DATA_FILE

    @classmethod
    def load(cls) -> AppData:
        try:
            raw = cls.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return AppData()

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

        return AppData()

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


def load_mcp_toolsets(app_data: AppData | None) -> tuple[list["AbstractToolset[Any]"], Dict[str, Any]]:
    """Instantiate the streamable HTTP MCP toolset from required env vars."""

    try:
        from pydantic_ai.mcp import MCPServerStreamableHTTP
    except ImportError as exc:  # pragma: no cover - optional dependency missing
        raise RuntimeError("MCP extras are required but missing. Install pydantic-ai with MCP support.") from exc

    url = os.environ["MCP_URL"].strip()
    if not url:
        raise ValueError("MCP_URL cannot be empty")

    token = (app_data.oauth_access_token if app_data else None) or ""
    if not token:
        raise ValueError("MCP OAuth access token missing from app data")

    headers = {"Authorization": f"Bearer {token}"}
    toolset = MCPServerStreamableHTTP(url=url, headers=headers)

    meta = {
        "method": "http",
        "status": "ready",
        "detail": url,
        "token_present": True,
    }

    return [toolset], meta


def extract_tool_activity(messages: List[ModelMessage]) -> List[str]:
    """Return human-readable descriptions of tool activity from model messages."""

    activity: List[str] = []
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue

        for part in message.parts:
            if isinstance(part, (ToolCallPart, BuiltinToolCallPart)):
                args = json.dumps(part.args, ensure_ascii=False) if part.args is not None else "{}"
                activity.append(f"🛠 Tool call • `{part.tool_name}` args={args}")
            elif isinstance(part, (ToolReturnPart, BuiltinToolReturnPart)):
                result = json.dumps(part.content, ensure_ascii=False) if part.content is not None else "null"
                activity.append(f"📥 Tool result • `{part.tool_name}` → {result}")

    return activity


# ------------------------
# Streamlit Setup
# ------------------------
st.set_page_config(page_title="Chat + MCP + OAuth Demo", page_icon="🤖")
st.title("🤖 Chat with MCP + OAuth + Agent Thoughts")


def init_state() -> None:
    """Bootstrap Streamlit session state for chat + agent."""

    if "app_data" not in st.session_state:
        app_data = AppDataManager.load()
        st.session_state.app_data = app_data
    else:
        app_data = st.session_state.app_data

    if isinstance(app_data, AppData):
        for attr, session_key in (
            ("oauth_access_token", "access_token"),
            ("oauth_refresh_token", "refresh_token"),
            ("oauth_client_id", "oauth_client_id"),
        ):
            value = getattr(app_data, attr)
            if value:
                st.session_state[session_key] = value
            else:
                st.session_state.pop(session_key, None)

    if "agent_config" not in st.session_state:
        st.session_state.agent_config = load_agent_settings()

    if "agent" not in st.session_state:
        st.session_state.agent = build_agent(
            st.session_state.agent_config["model"],
            toolsets=st.session_state.agent_config.get("toolsets"),
        )

    if "messages" not in st.session_state:
        st.session_state.messages = []


init_state()


def render_sidebar(agent_config: Dict[str, Any]) -> None:
    """Display sidebar controls and quick info."""

    with st.sidebar:
        st.subheader("Session Controls")
        st.caption("Prototype uses hard-coded model & API key. Later steps move these to env vars.")

        if st.button("🔄 Reset conversation", use_container_width=True):
            st.session_state.messages = []
            st.experimental_rerun()

        st.divider()
        st.subheader("Model Info")
        st.write(
            {
                "model": agent_config.get("model"),
                "api_key_source": "env" if os.getenv("OPENAI_API_KEY") else "missing",
            }
        )

        st.divider()
        st.subheader("MCP Toolset")
        mcp_meta = agent_config.get("mcp_meta", {})
        st.write(
            {
                "method": mcp_meta.get("method", "off"),
                "status": mcp_meta.get("status", "disabled"),
                "detail": mcp_meta.get("detail", ""),
                "token": "set" if mcp_meta.get("token_present") else "missing",
            }
        )
        if mcp_meta.get("status") == "error":
            st.warning(mcp_meta.get("detail"))

        st.divider()
        st.subheader("App Data")
        app_data_obj = st.session_state.get("app_data")
        app_data = asdict(app_data_obj) if isinstance(app_data_obj, AppData) else {}
        st.write(
            {
                "client_id": "set" if app_data.get("oauth_client_id") else "missing",
                "access_token": "set" if app_data.get("oauth_access_token") else "missing",
                "refresh_token": "set" if app_data.get("oauth_refresh_token") else "missing",
            }
        )


render_sidebar(st.session_state.agent_config)

# ------------------------
# OAuth Workflow
# ------------------------
if "access_token" not in st.session_state:
    params = st.query_params
    code = params.get("code", [None])[0]

    if code:
        # Exchange code for tokens
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        tokens = resp.json()
        if "access_token" in tokens:
            st.session_state["access_token"] = tokens["access_token"]
            st.session_state["refresh_token"] = tokens.get("refresh_token")
            new_app_data = AppDataManager.update(
                st.session_state.get("app_data"),
                oauth_client_id=st.session_state.get("oauth_client_id") or CLIENT_ID,
                oauth_access_token=tokens["access_token"],
                oauth_refresh_token=tokens.get("refresh_token"),
            )
            st.session_state.app_data = new_app_data
            if "agent_config" in st.session_state:
                st.session_state.agent_config["app_data"] = asdict(new_app_data)
            st.success("✅ Access token obtained")
        else:
            st.error(f"Token exchange failed: {tokens}")
    else:
        # Show login link
        login_url = f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}" f"&redirect_uri={REDIRECT_URI}"
        st.markdown(f"[🔑 Login with OAuth]({login_url})")


def render_chat_history(messages: List[Dict[str, str]]) -> None:
    """Display prior chat messages in conversational bubbles."""

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


render_chat_history(st.session_state.messages)


def handle_chat_turn(prompt: str) -> None:
    """Process a single chat turn, updating history and agent traces."""

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    agent: Agent = st.session_state.agent

    with st.chat_message("assistant"):
        response_placeholder = st.empty()

        async def run_agent() -> None:
            try:
                result = await agent.run(prompt)
            except Exception as exc:  # pragma: no cover - Streamlit UI path
                response_placeholder.error(f"Agent run failed: {exc}")
                return

            response_text = result.output if isinstance(result.output, str) else str(result.output)
            response_placeholder.markdown(response_text)

            tool_activity = extract_tool_activity(result.new_messages())
            if tool_activity:
                with st.expander("🤔 Agent Activity", expanded=False):
                    for entry in tool_activity:
                        st.markdown(entry)

            st.session_state.messages.append({"role": "assistant", "content": response_text})

        asyncio.run(run_agent())


if prompt := st.chat_input("Ask me something…"):
    handle_chat_turn(prompt)
