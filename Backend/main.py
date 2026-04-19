"""
Simple StarGuide MCP Client - Test the live server
"""

import json
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
API_KEY = os.getenv("STARGUIDE_API_KEY")

if not API_KEY:
    print("❌ Error: STARGUIDE_API_KEY not found in .env file")
    print("Create a .env file with: STARGUIDE_API_KEY=your-key-here")
    exit(1)

MCP_SERVER_URL = "https://MCP-Project-Stargazing.fastmcp.app/mcp"


def parse_sse_response(text: str) -> dict:
    """Extract JSON from SSE (Server-Sent Events) response."""
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except:
                pass
    raise ValueError("No valid JSON in response")


def call_tool(tool_name: str, **kwargs) -> dict:
    """Call a tool on the MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": kwargs}
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    print(f"\n📡 {tool_name}")
    print(f"   Args: {json.dumps(kwargs)}")
    
    try:
        with httpx.Client(timeout=120) as client:
            response = client.post(MCP_SERVER_URL, json=payload, headers=headers)
            response.raise_for_status()
            
            result = parse_sse_response(response.text)
            print(f"   ✓ Success!")
            return result
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return {"error": str(e)}


def main():
    """Test the three MCP tools."""
    print("\n" + "="*60)
    print("  StarGuide MCP - Live Server Test")
    print("="*60)
    
    # Test 1: Visible objects
    print("\n[1] Get Visible Objects")
    result1 = call_tool(
        "visible_objects",
        lat=19.274,
        lon=72.881,
        time="2026-04-19T20:30:00+05:30",
        alti=-52
    )
    
    # Test 2: Object position
    print("\n[2] Get Mars Position")
    result2 = call_tool(
        "object_position",
        object_name="Mars",
        lat=19.274,
        lon=72.881,
        time="2026-04-19T20:30:00+05:30",
        alti=-52
    )
    
    # Test 3: Object details
    print("\n[3] Get Sirius Details")
    result3 = call_tool(
        "object_detail",
        object_name="Sirius"
    )
    
    print("\n" + "="*60)
    print("✓ All tests completed!")
    print("="*60)


if __name__ == "__main__":
    main()
