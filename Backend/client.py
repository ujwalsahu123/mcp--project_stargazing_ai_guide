import json
import os
import uuid
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

import httpx
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import AzureChatOpenAI


load_dotenv()

MCP_SERVER_URL = os.getenv("STARGUIDE_MCP_SERVER_URL")
API_KEY = os.getenv("STARGUIDE_API_KEY")

AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

if AZURE_ENDPOINT and "/openai/v1" in AZURE_ENDPOINT:
	AZURE_ENDPOINT = AZURE_ENDPOINT.replace("/openai/v1", "")

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


BOOTSTRAP_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def current_iso_time():
	"""Return current local time in ISO format with timezone offset."""
	return datetime.now().astimezone().isoformat(timespec="seconds")


def extract_mcp_result(response_text):
	for line in response_text.splitlines():
		if line.startswith("data:"):
			data = json.loads(line.replace("data:", "").strip())
			return data.get("result", {})
	return {}


async def post_mcp(payload):
	if not MCP_SERVER_URL:
		raise RuntimeError("STARGUIDE_MCP_SERVER_URL is not set.")
	if not API_KEY:
		raise RuntimeError("STARGUIDE_API_KEY is not set.")

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


async def fetch_tool_names():
	payload = {
		"jsonrpc": "2.0",
		"id": str(uuid.uuid4()),
		"method": "tools/list",
		"params": {},
	}
	response = await post_mcp(payload)
	result = extract_mcp_result(response.text)
	tools = result.get("tools", []) or []
	return [tool["name"] for tool in tools]


def _short_description(text, max_len=64):
	if not text:
		return "No description"

	clean = " ".join(str(text).split())
	if len(clean) <= max_len:
		return clean

	return clean[: max_len - 3].rstrip() + "..."


async def fetch_tools_info():
	"""Return list of tools with short display descriptions."""
	payload = {
		"jsonrpc": "2.0",
		"id": str(uuid.uuid4()),
		"method": "tools/list",
		"params": {},
	}

	response = await post_mcp(payload)
	result = extract_mcp_result(response.text)
	tools = result.get("tools", []) or []

	output = []
	for tool in tools:
		name = tool.get("name", "unknown_tool")
		description = tool.get("description", "")
		output.append(
			{
				"name": name,
				"description": description,
				"short_description": _short_description(description),
			}
		)

	return output


async def fetch_tools_raw():
	"""Return full raw MCP tool metadata from tools/list."""
	payload = {
		"jsonrpc": "2.0",
		"id": str(uuid.uuid4()),
		"method": "tools/list",
		"params": {},
	}

	response = await post_mcp(payload)
	result = extract_mcp_result(response.text)
	return result.get("tools", []) or []


async def call_tool(tool_name, params):
	payload = {
		"jsonrpc": "2.0",
		"id": str(uuid.uuid4()),
		"method": "tools/call",
		"params": {
			"name": tool_name,
			"arguments": params,
		},
	}

	response = await post_mcp(payload)
	result = extract_mcp_result(response.text)

	if not result:
		return {"error": "Empty MCP result"}
	if result.get("isError"):
		return {"error": f"Tool call failed for {tool_name}", "raw": result}

	structured = result.get("structuredContent")
	if structured is not None:
		return structured

	content = result.get("content", [])
	if content:
		text = content[0].get("text")
		if text is not None:
			try:
				return json.loads(text)
			except json.JSONDecodeError:
				return {"text": text}

	return {"status": "ok", "raw": result}


def _build_llm(streaming=False):
	if not AZURE_ENDPOINT or not AZURE_API_KEY or not AZURE_DEPLOYMENT_NAME:
		raise RuntimeError("Missing Azure OpenAI credentials in environment variables.")

	return AzureChatOpenAI(
		azure_endpoint=AZURE_ENDPOINT,
		api_key=AZURE_API_KEY,
		deployment_name=AZURE_DEPLOYMENT_NAME,
		api_version="2024-08-01-preview",
		temperature=0,
		streaming=streaming,
	)


def _build_openai_tools(mcp_tools):
	openai_tools = []
	for tool in mcp_tools:
		openai_tools.append(
			convert_to_openai_tool(
				{
					"name": tool.get("name", "unknown_tool"),
					"description": tool.get("description", ""),
					"parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
				}
			)
		)
	return openai_tools


def _summarize_tools(mcp_tools):
	tools = []
	for tool in mcp_tools:
		tools.append(
			{
				"name": tool.get("name", "unknown_tool"),
				"description": tool.get("description", ""),
				"short_description": _short_description(tool.get("description", "")),
			}
		)
	return tools


def _history_to_langchain_messages(chat_messages):
	messages = []
	for msg in chat_messages:
		if msg.get("role") == "user":
			messages.append(HumanMessage(content=msg.get("content", "")))
		elif msg.get("role") == "assistant":
			messages.append(AIMessage(content=msg.get("content", "")))
	return messages


def _format_visible_intro(visible_result):
	objects = []
	if isinstance(visible_result, dict):
		objects = visible_result.get("objects", []) or []

	if not objects:
		return "I could not find visible objects right now. How can I help you?"

	lines = ["10 brightest celestial objects above you right now:"]
	for obj in objects[:10]:
		name = obj.get("name", "Unknown")
		obj_type = obj.get("type", "object")
		lines.append(f"- {name} ({obj_type})")
	lines.append("\nHow can I help you?")
	return "\n".join(lines)


async def initialize_chatbot_runtime(lat, lon, alti):
	"""Run startup checks and return a tool-bound first-pass LLM plus intro message."""
	health = await call_tool("health_check", {})
	if isinstance(health, dict) and health.get("error"):
		return {"error": f"Health check failed: {health['error']}"}

	raw_tools = await fetch_tools_raw()
	llm_with_tools = _build_llm(streaming=False).bind_tools(_build_openai_tools(raw_tools))

	visible_result = await call_tool(
		"visible_objects",
		{
			"lat": float(lat),
			"lon": float(lon),
			"time": current_iso_time(),
			"alti": float(alti or 0.0),
		},
	)

	return {
		"llm_with_tools": llm_with_tools,
		"intro_message": _format_visible_intro(visible_result),
	}


async def bootstrap_chatbot_runtime(lat, lon, alti):
	"""Fetch startup data concurrently so the UI can render immediately."""
	health_task = call_tool("health_check", {})
	raw_tools_task = fetch_tools_raw()
	visible_task = call_tool(
		"visible_objects",
		{
			"lat": float(lat),
			"lon": float(lon),
			"time": current_iso_time(),
			"alti": float(alti or 0.0),
		},
	)

	health_result, raw_tools, visible_result = await asyncio.gather(health_task, raw_tools_task, visible_task)
	if isinstance(health_result, dict) and health_result.get("error"):
		return {"error": f"Health check failed: {health_result['error']}"}

	llm_with_tools = _build_llm(streaming=False).bind_tools(_build_openai_tools(raw_tools))
	return {
		"llm_with_tools": llm_with_tools,
		"intro_message": _format_visible_intro(visible_result),
		"tools_info": _summarize_tools(raw_tools),
	}


def start_chatbot_bootstrap(lat, lon, alti):
	"""Start bootstrap work in a background thread and return a future."""
	return BOOTSTRAP_EXECUTOR.submit(asyncio.run, bootstrap_chatbot_runtime(lat, lon, alti))


async def run_llm_chat_turn(user_prompt, lat, lon, alti, chat_messages, llm_with_tools):
	"""Two-pass LLM tool flow for one user turn."""
	if llm_with_tools is None:
		raise RuntimeError("LLM is not initialized. Run initialize_chatbot_runtime first.")

	latest_time = current_iso_time()
	prompt_text = (
		f"User prompt: {user_prompt}\n"
		f"latitude: {float(lat)}\n"
		f"longitude: {float(lon)}\n"
		f"time: {latest_time}\n"
		f"altitude: {float(alti or 0.0)}"
	)

	history = _history_to_langchain_messages(chat_messages)
	first_messages = [
		SystemMessage(content=FIRST_SYSTEM_PROMPT),
		*history,
		HumanMessage(content=prompt_text),
	]

	first_response = await llm_with_tools.ainvoke(first_messages)

	if not getattr(first_response, "tool_calls", None):
		return first_response.content or ""

	tool_messages = []
	for tool_call in first_response.tool_calls:
		tool_name = tool_call.get("name")
		tool_args = tool_call.get("args", {})
		tool_id = tool_call.get("id", str(uuid.uuid4()))
		result = await call_tool(tool_name, tool_args)
		tool_messages.append(
			ToolMessage(
				tool_call_id=tool_id,
				content=json.dumps(result, default=str),
			)
		)

	second_messages = [
		SystemMessage(content=SECOND_SYSTEM_PROMPT),
		*history,
		HumanMessage(content=prompt_text),
		first_response,
		*tool_messages,
	]

	final_llm = _build_llm(streaming=False)
	final_response = await final_llm.ainvoke(second_messages)
	root_client = getattr(final_llm, "root_async_client", None)
	if root_client is not None:
		await root_client.close()

	return final_response.content or ""


async def stream_llm_chat_turn(user_prompt, lat, lon, alti, chat_messages, llm_with_tools, on_delta):
	"""Run one chat turn and stream the final answer text through on_delta."""
	if llm_with_tools is None:
		raise RuntimeError("LLM is not initialized. Run initialize_chatbot_runtime first.")

	latest_time = current_iso_time()
	prompt_text = (
		f"User prompt: {user_prompt}\n"
		f"latitude: {float(lat)}\n"
		f"longitude: {float(lon)}\n"
		f"time: {latest_time}\n"
		f"altitude: {float(alti or 0.0)}"
	)

	history = _history_to_langchain_messages(chat_messages)
	first_messages = [
		SystemMessage(content=FIRST_SYSTEM_PROMPT),
		*history,
		HumanMessage(content=prompt_text),
	]

	first_response = await llm_with_tools.ainvoke(first_messages)
	if not getattr(first_response, "tool_calls", None):
		text = first_response.content or ""
		on_delta(text)
		return text

	tool_messages = []
	for tool_call in first_response.tool_calls:
		tool_name = tool_call.get("name")
		tool_args = tool_call.get("args", {})
		tool_id = tool_call.get("id", str(uuid.uuid4()))
		result = await call_tool(tool_name, tool_args)
		tool_messages.append(
			ToolMessage(
				tool_call_id=tool_id,
				content=json.dumps(result, default=str),
			)
		)

	second_messages = [
		SystemMessage(content=SECOND_SYSTEM_PROMPT),
		*history,
		HumanMessage(content=prompt_text),
		first_response,
		*tool_messages,
	]

	final_llm = _build_llm(streaming=True)
	text_parts = []
	async for chunk in final_llm.astream(second_messages):
		chunk_text = getattr(chunk, "content", None) or ""
		if chunk_text:
			text_parts.append(chunk_text)
			on_delta("".join(text_parts))

	root_client = getattr(final_llm, "root_async_client", None)
	if root_client is not None:
		await root_client.close()

	return "".join(text_parts).strip()


def auto_fetch_location():
	"""Best-effort location from public IP geolocation service."""
	errors = []

	providers = [
		(
			"ipapi",
			"https://ipapi.co/json/",
			lambda data: {
				"latitude": data.get("latitude"),
				"longitude": data.get("longitude"),
				"city": data.get("city"),
				"country": data.get("country_name"),
			},
		),
		(
			"ipwho",
			"https://ipwho.is/",
			lambda data: {
				"latitude": data.get("latitude"),
				"longitude": data.get("longitude"),
				"city": data.get("city"),
				"country": data.get("country"),
			},
		),
	]

	for provider_name, url, parser in providers:
		try:
			r = httpx.get(url, timeout=10.0)
			if r.status_code == 429:
				errors.append(f"{provider_name}: rate limited")
				continue
			r.raise_for_status()
			data = r.json()

			if provider_name == "ipwho" and data.get("success") is False:
				errors.append(f"{provider_name}: {data.get('message', 'request failed')}")
				continue

			geo = parser(data)
			if geo.get("latitude") is None or geo.get("longitude") is None:
				errors.append(f"{provider_name}: missing coordinates")
				continue

			return geo
		except Exception as exc:
			errors.append(f"{provider_name}: {exc}")

	return {"error": "; ".join(errors) if errors else "Unable to fetch location."}
