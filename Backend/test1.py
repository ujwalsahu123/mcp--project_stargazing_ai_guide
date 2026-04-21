"""
Simple MCP Server Check - Test MCP Server connection and tools working or not.
run -> uv run python main.py
"""

import httpx
from dotenv import load_dotenv
import os
import json
import asyncio

# Load environment variables
load_dotenv()

# Example values
EXAMPLE_LAT = 19.274      # Mumbai
EXAMPLE_LON = 72.881      # Mumbai
EXAMPLE_TIME = "2026-04-20T20:30:00+05:30"
EXAMPLE_ALTI = -52        # meters
EXAMPLE_STAR = "Sirius"

# MCP Server URL
MCP_SERVER_URL = "https://MCP-Project-Stargazing.fastmcp.app/mcp"
API_KEY = os.getenv("STARGUIDE_API_KEY")


def parse_sse_response(text: str) -> dict:
    """Extract JSON from SSE (Server-Sent Events) response."""
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except:
                pass
    raise ValueError("No valid JSON in response")


async def call_mcp_tool(tool_name: str, **kwargs) -> dict:
    """Call a tool on the MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": kwargs
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(MCP_SERVER_URL, json=payload, headers=headers)
        response.raise_for_status()
        return parse_sse_response(response.text)


async def check_mcp_server():
    """Check if MCP Server is working and print tool outputs."""
    
    print("\n" + "="*70)
    print("  MCP Server Status Check")
    print("="*70)
    print(f"Server URL: {MCP_SERVER_URL}")
    print(f"API Key: {API_KEY[:20]}..." if API_KEY else "❌ NO API KEY")
    
    if not API_KEY:
        print("\n❌ Error: STARGUIDE_API_KEY not set in .env")
        return
    
    try:
        print("\n🔗 Connecting to StarGuide MCP Server...")
        
        # Test Tool 1: visible_objects
        print("\n" + "="*70)
        print("TEST 1: Visible Objects")
        print("="*70)
        print(f"Location: {EXAMPLE_LAT}°N, {EXAMPLE_LON}°E")
        print(f"Time: {EXAMPLE_TIME}")
        print(f"Altitude: {EXAMPLE_ALTI}m\n")
        
        result1 = await call_mcp_tool(
            "visible_objects",
            lat=EXAMPLE_LAT,
            lon=EXAMPLE_LON,
            time=EXAMPLE_TIME,
            alti=EXAMPLE_ALTI
        )
        print("✓ Success!")
        print(f"Objects found:\n{json.dumps(result1, indent=2)}\n")
        
        # Test Tool 2: object_position
        print("="*70)
        print("TEST 2: Object Position (Mars)")
        print("="*70)
        print(f"Object: Mars")
        print(f"Location: {EXAMPLE_LAT}°N, {EXAMPLE_LON}°E")
        print(f"Time: {EXAMPLE_TIME}\n")
        
        result2 = await call_mcp_tool(
            "object_position",
            object_name="Mars",
            lat=EXAMPLE_LAT,
            lon=EXAMPLE_LON,
            time=EXAMPLE_TIME,
            alti=EXAMPLE_ALTI
        )
        print("✓ Success!")
        print(f"Position:\n{json.dumps(result2, indent=2)}\n")
        
        # Test Tool 3: object_detail
        print("="*70)
        print("TEST 3: Object Details")
        print("="*70)
        print(f"Object: {EXAMPLE_STAR}\n")
        
        result3 = await call_mcp_tool(
            "object_detail",
            object_name=EXAMPLE_STAR
        )
        print("✓ Success!")
        print(f"Details:\n{json.dumps(result3, indent=2)}\n")
        
        print("="*70)
        print("✓ All tests completed successfully!")
        print("="*70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_mcp_server())
