"""
MCP Server Check - Test MCP Server connection and tools working or not.

run ->
cd Backend
.venv/scripts/activate    # Activate virtual environment
uv run python test1.py
"""

import asyncio
import json
import os
import uuid

import httpx
from dotenv import load_dotenv


# Load environment variables
load_dotenv()


# Example values
EXAMPLE_LAT = 19.274      # Mumbai
EXAMPLE_LON = 72.881
EXAMPLE_ALTI = -52        # meters
EXAMPLE_TIME = "2026-05-27T20:34:44+05:30"
EXAMPLE_STAR = "Sirius"


# MCP Server URL & API key
MCP_SERVER_URL = os.getenv("STARGUIDE_MCP_SERVER_URL")
API_KEY = os.getenv("STARGUIDE_API_KEY")


# --------------------------------------------------
# RESPONSE PARSER
# --------------------------------------------------

def parse_response(response):
    result = response.get("result", {}) if isinstance(response, dict) else {}

    if not result and isinstance(response, list):
        content_text = ""

        for item in response:
            if item.get("type") == "text":
                content_text += item.get("text", "")

        if content_text:
            try:
                return json.dumps(json.loads(content_text), indent=2)
            except json.JSONDecodeError:
                return content_text

    is_error = result.get("isError")
    if is_error:
        return "error"

    structured_content = result.get("structuredContent")
    if structured_content:
        return json.dumps(structured_content, indent=2)

    content = result.get("content", [])
    if content and isinstance(content, list):
        content_text = ""

        for item in content:
            if item.get("type") == "text":
                content_text += item.get("text", "")

        return content_text or "No content returned"

    return "No content returned"


def print_response(response):
    output = parse_response(response)
    print(output)


async def call_mcp_tool(client: httpx.AsyncClient, tool_name: str, **kwargs):
    """Call a tool on the MCP server using direct JSON-RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": kwargs,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {API_KEY}",
    }

    response = await client.post(MCP_SERVER_URL, json=payload, headers=headers)
    response.raise_for_status()

    for line in response.text.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue

    raise ValueError("No valid JSON in response")












# async def call_tool_fun(tool_name, params):

#     # call the tool using the tool_name and pass the params as arguments to the tool
#     response = await tool_name.ainvoke(params)
#     if not response:
#         return "No response from tool"
    

#     # parse the result from the response
#     result = response.get("result", response)
#     if not result:
#         return "No result in response"

#     # check if error
#     is_error = result.get("isError")
#     if is_error:
#         return "error"

#     # return the structured content if available
#     structured_content = result.get("structuredContent")
#     if structured_content:
#         return json.dumps(structured_content, indent=2)

#     # if structured content is not available, try to extract content > text
#     content = result.get("content", [])
#     if content:
#         text = content[0].get("text")        
#         return text

#     # if tool called successfully but no content returned
#     return "No content in tool response"








# --------------------------------------------------
# Visible Objects
# --------------------------------------------------

async def test_visible_objects(client: httpx.AsyncClient):
    print("\n" + "=" * 70)
    print("TEST 1: Visible Objects")
    print("=" * 70)
    print(f"Location: {EXAMPLE_LAT}°N, {EXAMPLE_LON}°E")
    print(f"Time: {EXAMPLE_TIME}")
    print(f"Altitude: {EXAMPLE_ALTI}m\n")

    try:
        response = await call_mcp_tool(
            client,
            "visible_objects",
            lat=EXAMPLE_LAT,
            lon=EXAMPLE_LON,
            time=EXAMPLE_TIME,
            alti=EXAMPLE_ALTI,
        )
        print("✓ Success!")
        print_response(response)
    except Exception as e:
        print(f"❌ Error: {e}")


# --------------------------------------------------
# Object Position
# --------------------------------------------------

async def test_object_position(client: httpx.AsyncClient):
    print("=" * 70)
    print("TEST 2: Object Position (Mars)")
    print("=" * 70)
    print("Object: Mars")
    print(f"Location: {EXAMPLE_LAT}°N, {EXAMPLE_LON}°E")
    print(f"Time: {EXAMPLE_TIME}\n")

    try:
        response = await call_mcp_tool(
            client,
            "object_position",
            object_name="Mars",
            lat=EXAMPLE_LAT,
            lon=EXAMPLE_LON,
            time=EXAMPLE_TIME,
            alti=EXAMPLE_ALTI,
        )
        print("✓ Success!")
        print_response(response)
    except Exception as e:
        print(f"❌ Error: {e}")


# --------------------------------------------------
# Object Detail
# --------------------------------------------------

async def test_object_detail(client: httpx.AsyncClient):
    print("=" * 70)
    print("TEST 3: Object Details")
    print("=" * 70)
    print(f"Object: {EXAMPLE_STAR}\n")

    try:
        response = await call_mcp_tool(
            client,
            "object_detail",
            object_name=EXAMPLE_STAR,
        )
        print("✓ Success!")
        print_response(response)
    except Exception as e:
        print(f"❌ Error: {e}")


# --------------------------------------------------
# Health Check
# --------------------------------------------------

async def test_health_check(client: httpx.AsyncClient):
    print("=" * 70)
    print("TEST 4: Health Check")
    print("=" * 70)

    try:
        response = await call_mcp_tool(client, "health_check")
        print("✓ Success!")
        print_response(response)
    except Exception as e:
        print(f"❌ Error: {e}")


# --------------------------------------------------
# Weather Forecast
# --------------------------------------------------

async def test_weather_forecast(client: httpx.AsyncClient):
    print("=" * 70)
    print("TEST 5: Weather Forecast")
    print("=" * 70)
    print(f"Location: {EXAMPLE_LAT}°N, {EXAMPLE_LON}°E")

    try:
        response = await call_mcp_tool(
            client,
            "weather_forecast",
            lat=EXAMPLE_LAT,
            lon=EXAMPLE_LON,
        )
        print("✓ Success! (tool: weather_forecast)")
        print_response(response)
    except Exception as e:
        print(f"❌ Error: {e}")


async def check_mcp_server():
    """Check if MCP Server is working and print tool outputs."""

    print("\n" + "=" * 70)
    print("  MCP Server Status Check")
    print("=" * 70)
    print(f"Server URL: {MCP_SERVER_URL}")
    print(f"API Key: {API_KEY[:20]}..." if API_KEY else "❌ NO API KEY")

    if not MCP_SERVER_URL:
        print("\n❌ Error: STARGUIDE_MCP_SERVER_URL not set in .env")
        return

    if not API_KEY:
        print("\n❌ Error: STARGUIDE_API_KEY not set in .env")
        return

    try:
        print("\n🔗 Connecting to StarGuide MCP Server...")
        timeout = httpx.Timeout(120.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            await test_visible_objects(client)
            await test_object_position(client)
            await test_object_detail(client)
            await test_health_check(client)
            await test_weather_forecast(client)

        print("=" * 70)
        print("✓ All tests completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await check_mcp_server()


if __name__ == "__main__":
    asyncio.run(main())
