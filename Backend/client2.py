import asyncio
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
from dotenv import load_dotenv


load_dotenv()

MCP_SERVER_URL = os.getenv("STARGUIDE_MCP_SERVER_URL")
API_KEY = os.getenv("STARGUIDE_API_KEY")

BOOTSTRAP_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def current_iso_time():
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


async def fetch_tools_info():
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
		short_description = " ".join(str(description).split())
		if len(short_description) > 64:
			short_description = short_description[:61].rstrip() + "..."
		output.append(
			{
				"name": name,
				"description": description,
				"short_description": short_description or "No description",
			}
		)

	return output


def auto_fetch_location():
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

	errors = []
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


async def health_check():
	return await call_tool("health_check", {})


async def bootstrap_connection_state():
	"""Run health_check without blocking the main UI thread."""
	return await health_check()


def start_health_check_bootstrap():
	return BOOTSTRAP_EXECUTOR.submit(asyncio.run, bootstrap_connection_state())