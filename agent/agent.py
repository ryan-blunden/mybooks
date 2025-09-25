import asyncio

import requests
import streamlit as st
from pydantic_ai import Agent

# ------------------------
# OAuth2 Config (replace with real values)
# ------------------------
AUTH_URL = "https://auth.example.com/authorize"
TOKEN_URL = "https://auth.example.com/token"
CLIENT_ID = "my-client-id"
CLIENT_SECRET = "my-client-secret"
REDIRECT_URI = "http://localhost:8501"  # must match app URL


# ------------------------
# Example MCP-like tool (secured by token)
# ------------------------
def get_weather(city: str) -> str:
    """Fake MCP tool — would call MCP server with bearer token."""
    token = st.session_state.get("access_token")
    if not token:
        return "❌ No access token — please log in first."
    # Example MCP call (replace with real API)
    headers = {"Authorization": f"Bearer {token}"}
    # resp = requests.get(f"https://mcp.example.com/weather?city={city}", headers=headers)
    # return resp.json()
    return f"(fake) Weather in {city}: Sunny ☀️ with token={token[:6]}..."


# ------------------------
# Build agent with tool
# ------------------------
agent = Agent(
    model="gpt-4o-mini",  # swap with preferred model
    tools=[get_weather],
    system_prompt="You are a helpful assistant. Use tools if needed.",
)

# ------------------------
# Streamlit Setup
# ------------------------
st.set_page_config(page_title="Chat + MCP + OAuth Demo", page_icon="🤖")
st.title("🤖 Chat with MCP + OAuth + Agent Thoughts")

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
            st.success("✅ Access token obtained")
        else:
            st.error(f"Token exchange failed: {tokens}")
    else:
        # Show login link
        login_url = f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}" f"&redirect_uri={REDIRECT_URI}"
        st.markdown(f"[🔑 Login with OAuth]({login_url})")

# ------------------------
# Chat UI
# ------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Chat input
if prompt := st.chat_input("Ask me something…"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Placeholder for assistant response
    with st.chat_message("assistant"):
        resp_placeholder = st.empty()

        async def run_agent():
            # Run the agent, capturing tool steps
            result = await agent.run(prompt, return_steps=True)

            # Show assistant reply
            resp_placeholder.markdown(result.output_text)

            # Show agent thoughts
            with st.expander("🤔 Agent Thoughts", expanded=False):
                for step in result.steps:
                    if step.type == "tool_call":
                        st.markdown(f"🛠 **Tool call**: `{step.tool}` args={step.args}")
                    elif step.type == "tool_result":
                        st.markdown(f"📥 **Tool result**: `{step.result}`")
                    else:
                        st.markdown(f"💭 {step}")

            # Save assistant message
            st.session_state.messages.append({"role": "assistant", "content": result.output_text})

        asyncio.run(run_agent())
