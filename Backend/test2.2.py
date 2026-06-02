"""
MCP + LLM agent-style test using direct HTTP for MCP tool calls.

Flow:
1. Fetch MCP tool schemas once.
2. Bind those tools to the LLM once.
3. First LLM call decides whether tools are needed.
4. If tools are needed, call them directly with HTTP.
5. Second LLM call uses the tool output and gives the final answer.

run ->
cd Backend
.venv/scripts/activate
uv run python test2.2.py
"""

import asyncio
import json
import os
import sys
import uuid

import httpx
from dotenv import load_dotenv
from langchain_core.callbacks import StreamingStdOutCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import AzureChatOpenAI


load_dotenv()


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

MCP_SERVER_URL = os.getenv("STARGUIDE_MCP_SERVER_URL")
API_KEY = os.getenv("STARGUIDE_API_KEY")

AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

if AZURE_ENDPOINT and "/openai/v1" in AZURE_ENDPOINT:
    AZURE_ENDPOINT = AZURE_ENDPOINT.replace("/openai/v1", "")


# --------------------------------------------------
# GLOBALS
# --------------------------------------------------

ALL_TOOL_NAMES = []
NAMED_TOOLS = {}
LLM_WITH_TOOLS = None
CHAT_HISTORY = []
FIRST_SYSTEM_PROMPT = """
You are a professional astronomy assistant.
You receive the chat history and the current user message.
Always prioritize the current user message over older context.
Use chat history only when the current message clearly depends on it.
Do not repeat older tool results unless they are directly relevant to the current question.
If the user asks about the conversation itself, answer from the chat history directly.
Only use MCP tools when the current question truly needs live astronomy data.
When using a tool, use only the exact latitude, longitude, time, and altitude values provided by the user.
Do not invent, change, normalize, or guess tool arguments.
If a tool is needed, return tool_calls with the correct tool name and exact args.
If no tool is needed, answer naturally in plain text.
Keep the tone clear, helpful, and concise.
""".strip()

SECOND_SYSTEM_PROMPT = """
You are the final-answer pass of a professional astronomy assistant.
You receive the chat history, the current user message, and any tool results.
Answer only the current user message, using chat history only when it is genuinely needed for context.
Do not infer a hidden request from older turns if the current message is brief or ambiguous.
Do not call tools.
Do not output tool_calls.
Do not mention internal reasoning, prompt structure, or tool-selection steps.
If the first pass already answered directly, preserve that answer and make it read naturally.
If tools were used, summarize only the useful result in a clean, user-facing way.
Keep the response polished, accurate, and concise unless the user explicitly asks for detail.
""".strip()


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def _print_header(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _safe_json(value):
    try:
        return json.dumps(value, indent=2, default=str)
    except Exception:
        return str(value)


async def _post_mcp(payload):
    async with httpx.AsyncClient(
        timeout=120.0,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    ) as client:
        response = await client.post(MCP_SERVER_URL, json=payload)
        response.raise_for_status()
        return response


def _extract_mcp_result(response_text):
    for line in response_text.splitlines():
        if line.startswith("data:"):
            data = json.loads(line.replace("data:", "").strip())
            return data.get("result", {})
    return {}


# --------------------------------------------------
# TOOL DISCOVERY
# --------------------------------------------------

async def fetch_all_tool_names():
    """Fetch tool names and schemas once from the MCP server."""

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/list",
        "params": {},
    }

    response = await _post_mcp(payload)
    result = _extract_mcp_result(response.text)
    tools = result.get("tools", []) or []

    global ALL_TOOL_NAMES, NAMED_TOOLS
    ALL_TOOL_NAMES = [tool["name"] for tool in tools]
    NAMED_TOOLS = {tool["name"]: tool for tool in tools}

    return tools


def _build_openai_tools(mcp_tools):
    """Convert MCP tool schemas into LangChain/OpenAI tool schemas."""

    openai_tools = []
    for tool in mcp_tools:
        openai_tools.append(
            convert_to_openai_tool(
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
                }
            )
        )
    return openai_tools


# --------------------------------------------------
# DIRECT TOOL CALL
# --------------------------------------------------

async def call_tool_fun(tool_name, params):
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params,
        },
    }

    response = await _post_mcp(payload)
    result = _extract_mcp_result(response.text)

    if not result or result.get("isError"):
        return {"error": f"Tool call failed for {tool_name}"}

    if result.get("structuredContent") is not None:
        return result["structuredContent"]

    content = result.get("content", [])
    if content:
        text = content[0].get("text")
        if text is not None:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}

    return None


# --------------------------------------------------
# LLM SETUP
# --------------------------------------------------

def build_llm():
    if not AZURE_ENDPOINT or not AZURE_API_KEY or not AZURE_DEPLOYMENT_NAME:
        raise RuntimeError("Missing Azure OpenAI credentials in environment variables.")

    return AzureChatOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
        deployment_name=AZURE_DEPLOYMENT_NAME,
        api_version="2024-08-01-preview",
        streaming=True,
        callbacks=[StreamingStdOutCallbackHandler()],
        temperature=0,
    )


async def initialize_once():
    """Fetch tools and bind them to the LLM one time at startup."""

    global LLM_WITH_TOOLS

    mcp_tools = await fetch_all_tool_names()
    openai_tools = _build_openai_tools(mcp_tools)

    llm = build_llm()
    LLM_WITH_TOOLS = llm.bind_tools(openai_tools)


def _merge_chunk_text(text_chunks):
    return "".join(text_chunks).strip()


def _history_messages():
    return CHAT_HISTORY.copy()


def _append_turn(user_text, assistant_text):
    CHAT_HISTORY.append(HumanMessage(content=user_text))
    CHAT_HISTORY.append(AIMessage(content=assistant_text))


# --------------------------------------------------
# TWO-STEP LLM FLOW
# --------------------------------------------------

async def LLM_flow(user_prompt, lat, lon, time, alti):
    """Run the two-call LLM flow.

    First call: decide whether tools are needed.
    Second call: use the tool output and return the final answer.
    """

    if LLM_WITH_TOOLS is None:
        raise RuntimeError("LLM is not initialized. Call initialize_once() first.")

    prompt_text = (
        f"User prompt: {user_prompt}\n"
        f"latitude: {lat}\n"
        f"longitude: {lon}\n"
        f"time: {time}\n"
        f"altitude: {alti}"
    )

    messages = [
        SystemMessage(content=FIRST_SYSTEM_PROMPT),
        *_history_messages(),
        HumanMessage(content=prompt_text),
    ]

    # First LLM call with streaming
    first_response = None
    first_chunks = []
    async for chunk in LLM_WITH_TOOLS.astream(messages):
        if getattr(chunk, "content", None):
            first_chunks.append(chunk.content)
        if first_response is None:
            first_response = chunk
        else:
            
            first_response = first_response + chunk

    if first_response is None:
        return ""

    first_text = _merge_chunk_text(first_chunks)

    if not getattr(first_response, "tool_calls", None):
        answer_text = first_text or first_response.content or ""
        _append_turn(user_prompt, answer_text)
        return answer_text

    # If tools are needed, execute them directly over HTTP
    tool_messages = []
    for tool_call in first_response.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        tool_id = tool_call["id"]
        print(f"\nExecuting tool: {tool_name} with args: {tool_args}")
        result = await call_tool_fun(tool_name, tool_args)
        print(result)
        tool_messages.append(
            ToolMessage(
                tool_call_id=tool_id,
                content=json.dumps(result, default=str),
            )
        )

    # Second LLM call
    final_messages = [
        SystemMessage(content=SECOND_SYSTEM_PROMPT),
        *_history_messages(),
        HumanMessage(content=prompt_text),
        first_response,
        *tool_messages,
    ]

    final_llm = build_llm()
    final_response = await final_llm.ainvoke(final_messages)
    root_client = getattr(final_llm, "root_async_client", None)
    if root_client is not None:
        await root_client.close()
    _append_turn(user_prompt, final_response.content)
    return final_response.content


# --------------------------------------------------
# MAIN
# --------------------------------------------------

async def main():
    _print_header("MCP + Azure OpenAI Agent Test")

    if not MCP_SERVER_URL:
        print("\n❌ Error: STARGUIDE_MCP_SERVER_URL not set in .env")
        sys.exit(1)

    if not API_KEY:
        print("\n❌ Error: STARGUIDE_API_KEY not set in .env")
        sys.exit(1)

    if not AZURE_ENDPOINT or not AZURE_API_KEY or not AZURE_DEPLOYMENT_NAME:
        print("\n❌ Error: Missing Azure OpenAI credentials in .env")
        sys.exit(1)

    print("\nConfiguration loaded:")
    print(f"  MCP Server: {MCP_SERVER_URL}")
    print(f"  Azure Endpoint: {AZURE_ENDPOINT}")
    print(f"  Azure Deployment: {AZURE_DEPLOYMENT_NAME}")

    print("\nFetching MCP tools once...")
    await initialize_once()
    print("Available MCP tools:")
    print(_safe_json(ALL_TOOL_NAMES))

    # Hardcoded example values
    lat = 19.777
    lon = 72.888
    time = "2026-05-28T20:34:44+05:30"
    alti = 52

    # --------------------------------------------------
    # Startup MCP checks before chatbot
    # --------------------------------------------------
    print("\nRunning MCP startup checks...")

    health_result = await call_tool_fun("health_check", {})
    print("Health check:", _safe_json(health_result))

    visible_result = await call_tool_fun(
        "visible_objects",
        {
            "lat": lat,
            "lon": lon,
            "time": time,
            "alti": alti,
        },
    )

    objects = []
    if isinstance(visible_result, dict):
        objects = visible_result.get("objects", []) or []

    print("\n10 brightest Celestial objects above you:")
    if objects:
        for obj in objects[:10]:
            print(f"- {obj.get('name')} ({obj.get('type')})")
    else:
        print("- No visible objects found right now.")

    print("\nStarting LLM chatbot...")

    while True:
        user_prompt = input("\n\n\nEnter your astronomy query (or 'q' to quit): ")
        if user_prompt.lower() == "q":
            break
        print("\nSending prompt to LLM...")
        print(user_prompt,"\n\n")
        final_answer = await LLM_flow(user_prompt, lat, lon, time, alti)




if __name__ == "__main__":
    
    asyncio.run(main())
   
