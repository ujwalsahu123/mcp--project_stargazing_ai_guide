"""
MCP Server Check - Test MCP Server connection and tools working or not

- Directly calling the tools without using LLM decision making to call the tools

- using FastMCP Client directly (from fastmcp import Client, FastMCP)
- Execution Time: 19.430 seconds


run ->
cd Backend
.venv/scripts/activate  # Activate virtual environment
uv run python test1.4.py
"""


import asyncio
import json
import os

from dotenv import load_dotenv
from fastmcp import Client, FastMCP


# Load environment variables
load_dotenv()


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

MCP_SERVER_URL = os.getenv("STARGUIDE_MCP_SERVER_URL", "https://MCP-Project-Stargazing.fastmcp.app/mcp")
API_KEY = os.getenv("STARGUIDE_API_KEY")

SERVER_CONFIG = {
	"mcpServers": {
		"starguide": {
			"url": MCP_SERVER_URL,
			"transport": "http",
			"headers": {
				"Authorization": f"Bearer {API_KEY}",
			},
		}
	}
}


# --------------------------------------------------
# FastMCP Client
# --------------------------------------------------

client = Client(SERVER_CONFIG)


# --------------------------------------------------
# Load Tools & Store Tool Names Globally
# --------------------------------------------------

TOOLS = {}


def _jsonable(value):
	"""Convert FastMCP objects into plain Python data for printing."""

	if hasattr(value, "model_dump"):
		return value.model_dump()
	if hasattr(value, "dict"):
		try:
			return value.dict()
		except Exception:
			pass
	if isinstance(value, list):
		return [_jsonable(item) for item in value]
	if isinstance(value, dict):
		return {key: _jsonable(item) for key, item in value.items()}
	return value


async def load_tools():
	"""Check if MCP Server is working and print tool outputs."""

	print("\n" + "=" * 70)
	print("  MCP Server Status Check")

	if not MCP_SERVER_URL:
		print("\n❌ Error: STARGUIDE_MCP_SERVER_URL not set in .env")

	if not API_KEY:
		print("\n❌ Error: STARGUIDE_API_KEY not set in .env")

	print("\n🔗 Connecting to StarGuide MCP Server...")

	await client.ping()

	tools = await client.list_tools()
	resources = await client.list_resources()
	prompts = await client.list_prompts()

	global TOOLS
	TOOLS = {
		tool.name: tool.name
		for tool in tools
	}

	print("Available Tools:")
	print(json.dumps(list(TOOLS.keys()), indent=2))

	print("Available Resources:")
	print(json.dumps(_jsonable(resources), indent=2, default=str))

	print("Available Prompts:")
	print(json.dumps(_jsonable(prompts), indent=2, default=str))

	print("=" * 70, "\n")


def _extract_text_from_result(response):
	"""Handle the common FastMCP tool result shapes."""

	if response is None:
		return None

	content = response
	if hasattr(response, "content"):
		content = response.content

	if isinstance(content, dict):
		if "text" in content:
			return content["text"]
		return json.dumps(content, default=str)

	if isinstance(content, list) and content:
		first_item = content[0]
		if isinstance(first_item, dict):
			return first_item.get("text", json.dumps(first_item, default=str))
		if hasattr(first_item, "text"):
			return first_item.text
		return str(first_item)

	if hasattr(content, "text"):
		return content.text

	return str(content)


# --------------------------------------------------
# Call Tool - Parse Response - Return Output
# --------------------------------------------------

async def call_tool_fun(tool_name, params):
	response = await client.call_tool(tool_name, params)

	text = _extract_text_from_result(response)
	if not text:
		return None

	try:
		return json.loads(text)
	except json.JSONDecodeError:
		return {"text": text}


# -----------------------------------
# Test Tools - Directly just like any API endpoint from any function using FastMCP Client
# -----------------------------------

async def test_tools():

	# We store tool names globally, then call them directly by name.
	health_check_tool = TOOLS.get("health_check")
	visible_objects_tool = TOOLS.get("visible_objects")
	object_position_tool = TOOLS.get("object_position")
	object_detail_tool = TOOLS.get("object_detail")
	weather_forecast_tool = TOOLS.get("weather_forecast")

	# Example values - for testing
	EXAMPLE_LAT = 19.274      # Mumbai
	EXAMPLE_LON = 72.881
	EXAMPLE_ALTI = -52        # meters
	EXAMPLE_TIME = "2026-05-27T20:34:44+05:30"
	EXAMPLE_STAR = "Sirius"

	# --------------------------------------------------
	# Health Check
	# --------------------------------------------------

	print("=" * 70)
	print("TEST Health Check")

	tool = health_check_tool
	params = {}

	try:
		output = await call_tool_fun(tool, params)
		print(json.dumps(output, indent=2))
	except Exception as e:
		print(f"❌ Error: {e}")

	print("=" * 70, "\n")

	# --------------------------------------------------
	# Visible Objects
	# --------------------------------------------------

	print("=" * 70)
	print("TEST Visible Objects")

	tool = visible_objects_tool
	params = {
		"lat": EXAMPLE_LAT,
		"lon": EXAMPLE_LON,
		"time": EXAMPLE_TIME,
		"alti": EXAMPLE_ALTI,
	}

	try:
		output = await call_tool_fun(tool, params)
		print(json.dumps(output, indent=2))
	except Exception as e:
		print(f"❌ Error: {e}")

	print("=" * 70, "\n")

	# --------------------------------------------------
	# Object Position
	# --------------------------------------------------

	print("=" * 70)
	print("TEST Object Position")

	tool = object_position_tool
	params = {
		"object_name": EXAMPLE_STAR,
		"lat": EXAMPLE_LAT,
		"lon": EXAMPLE_LON,
		"time": EXAMPLE_TIME,
		"alti": EXAMPLE_ALTI,
	}

	try:
		output = await call_tool_fun(tool, params)
		print(json.dumps(output, indent=2))
	except Exception as e:
		print(f"❌ Error: {e}")

	print("=" * 70, "\n")

	# --------------------------------------------------
	# Object Detail
	# --------------------------------------------------

	print("=" * 70)
	print("TEST Object Detail")

	tool = object_detail_tool
	params = {
		"object_name": EXAMPLE_STAR,
	}

	try:
		output = await call_tool_fun(tool, params)
		print(json.dumps(output, indent=2))
	except Exception as e:
		print(f"❌ Error: {e}")

	print("=" * 70, "\n")

	# --------------------------------------------------
	# Weather Forecast
	# --------------------------------------------------

	print("=" * 70)
	print("TEST Weather Forecast")

	tool = weather_forecast_tool
	params = {
		"lat": EXAMPLE_LAT,
		"lon": EXAMPLE_LON,
	}

	try:
		output = await call_tool_fun(tool, params)
		print(json.dumps(output, indent=2))
	except Exception as e:
		print(f"❌ Error: {e}")

	print("=" * 70, "\n")

	print("✓ All tests completed successfully!")


# -----------------------------------
# In Main function - call the load_tools() function
# -----------------------------------

async def main():
	async with client:
		await load_tools()
		await test_tools()


if __name__ == "__main__":

	# time counter start
	import time

	start = time.perf_counter()

	# run the main function
	asyncio.run(main())

	# time counter end
	end = time.perf_counter()
	print(f"Time Taken: {end - start:.4f} sec")
