"""
Quick client to test StarGuide MCP server on FastMCP Cloud
"""

import json
import os
import httpx

MCP_SERVER_URL = "https://MCP-Project-Stargazing.fastmcp.app/mcp"

# Get API key from environment variable or use placeholder
# Get your API key from FastMCP dashboard: https://console.fastmcp.ai/
API_KEY = os.getenv("STARGUIDE_API_KEY", "your-api-key-here")

# Test location: Mumbai, India
TEST_LAT = 19.274
TEST_LON = 72.881
TEST_ALTI = -52
TEST_TIME = "2026-04-19T20:30:00+05:30"


def _parse_sse_json(event_stream_text: str) -> dict:
    """Extract the last JSON payload from an SSE response."""
    data_payloads = []
    for line in event_stream_text.splitlines():
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload:
                data_payloads.append(payload)

    for payload in reversed(data_payloads):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            continue

    raise ValueError("No JSON payload found in SSE response")


def call_mcp_tool(tool_name: str, **kwargs) -> dict:
    """Call a tool on the live MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": kwargs
        }
    }
    
    print(f"\n{'='*60}")
    print(f"📡 Calling: {tool_name}")
    print(f"{'='*60}")
    print(f"Arguments: {json.dumps(kwargs, indent=2)}")
    
    if API_KEY == "your-api-key-here":
        print("✗ Error: API_KEY not set!")
        print("\nTo get your API key:")
        print("1. Visit: https://console.fastmcp.ai/")
        print("2. Find 'MCP-Project-Stargazing' deployment")
        print("3. Copy the API key")
        print("4. Set environment variable: STARGUIDE_API_KEY=<your-key>")
        return {"error": "API_KEY not configured"}
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "StarGuide-Client/1.0"
        }
        
        timeout = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(MCP_SERVER_URL, json=payload, headers=headers)
            
            # Log response details
            print(f"Status: {response.status_code}")
            if response.status_code != 200:
                print(f"Response Text: {response.text[:500]}")
            
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            response_text = response.text

            if "text/event-stream" in content_type:
                result = _parse_sse_json(response_text)
            elif not response_text.strip():
                raise ValueError("Empty response body from server")
            else:
                result = json.loads(response_text)

            print(f"✓ Success!")
            print(f"Response:\n{json.dumps(result, indent=2)}")
            return result
    except httpx.HTTPStatusError as e:
        print(f"✗ HTTP Error {e.response.status_code}: {e.response.text[:200]}")
        return {"error": str(e)}
    except Exception as e:
        print(f"✗ Error: {e}")
        return {"error": str(e)}


def main():
    """Test all three tools."""
    print("\n" + "█"*60)
    print("  StarGuide MCP - Live Server Test")
    print("█"*60)
    print(f"Server: {MCP_SERVER_URL}")
    print(f"Location: {TEST_LAT}°N, {TEST_LON}°E | Time: {TEST_TIME}")
    
    # Test 1: visible_objects
    print(f"\n\n{'#'*60}")
    print("TEST 1: Get Visible Objects")
    print(f"{'#'*60}")
    result1 = call_mcp_tool(
        "visible_objects",
        lat=TEST_LAT,
        lon=TEST_LON,
        time=TEST_TIME,
        alti=TEST_ALTI
    )
    
    # Test 2: object_position (Mars)
    print(f"\n\n{'#'*60}")
    print("TEST 2: Get Mars Position")
    print(f"{'#'*60}")
    result2 = call_mcp_tool(
        "object_position",
        object_name="Mars",
        lat=TEST_LAT,
        lon=TEST_LON,
        time=TEST_TIME,
        alti=TEST_ALTI
    )
    
    # Test 3: object_detail (Sirius)
    print(f"\n\n{'#'*60}")
    print("TEST 3: Get Sirius Details")
    print(f"{'#'*60}")
    result3 = call_mcp_tool(
        "object_detail",
        object_name="Sirius"
    )
    
    print("\n\n" + "█"*60)
    print("✓ All tests completed!")
    print("█"*60)


if __name__ == "__main__":
    main()
