"""
Simple MCP Server Check - Test StarGuide MCP Server connection and tools
"""

from langchain_mcp_adapters.client import MultiServerMCPClient
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


async def check_mcp_server():
    """Check if MCP Server is working and list all tools."""
    
    print("\n" + "="*70)
    print("  MCP Server Status Check")
    print("="*70)
    print(f"Server URL: {MCP_SERVER_URL}")
    print(f"API Key: {API_KEY[:20]}..." if API_KEY else "❌ NO API KEY")
    
    if not API_KEY:
        print("\n❌ Error: STARGUIDE_API_KEY not set in .env")
        return
    
    # Initialize MCP client
    mcp_client = MultiServerMCPClient()
    
    try:
        print("\n🔗 Connecting to StarGuide MCP Server...")
        await mcp_client.add_server(
            name="starguide",
            url=MCP_SERVER_URL,
            auth_token=API_KEY
        )
        print("✓ Connected!\n")
        
        # Get available tools
        tools = await mcp_client.get_tools()
        print(f"📦 Available Tools: {len(tools)}")
        for tool in tools:
            print(f"   - {tool.name}")
        
        # Test Tool 1: visible_objects
        print("\n" + "="*70)
        print("TEST 1: Visible Objects")
        print("="*70)
        print(f"Location: {EXAMPLE_LAT}°N, {EXAMPLE_LON}°E")
        print(f"Time: {EXAMPLE_TIME}")
        print(f"Altitude: {EXAMPLE_ALTI}m\n")
        
        tool_1 = next((t for t in tools if t.name == "visible_objects"), None)
        if tool_1:
            result = await tool_1.run({
                "lat": EXAMPLE_LAT,
                "lon": EXAMPLE_LON,
                "time": EXAMPLE_TIME,
                "alti": EXAMPLE_ALTI
            })
            print(f"Result:\n{json.dumps(result, indent=2)}\n")
        
        # Test Tool 2: object_position
        print("="*70)
        print("TEST 2: Object Position (Mars)")
        print("="*70)
        print(f"Object: Mars")
        print(f"Location: {EXAMPLE_LAT}°N, {EXAMPLE_LON}°E")
        print(f"Time: {EXAMPLE_TIME}\n")
        
        tool_2 = next((t for t in tools if t.name == "object_position"), None)
        if tool_2:
            result = await tool_2.run({
                "object_name": "Mars",
                "lat": EXAMPLE_LAT,
                "lon": EXAMPLE_LON,
                "time": EXAMPLE_TIME,
                "alti": EXAMPLE_ALTI
            })
            print(f"Result:\n{json.dumps(result, indent=2)}\n")
        
        # Test Tool 3: object_detail
        print("="*70)
        print("TEST 3: Object Details")
        print("="*70)
        print(f"Object: {EXAMPLE_STAR}\n")
        
        tool_3 = next((t for t in tools if t.name == "object_detail"), None)
        if tool_3:
            result = await tool_3.run({
                "object_name": EXAMPLE_STAR
            })
            print(f"Result:\n{json.dumps(result, indent=2)}\n")
        
        print("="*70)
        print("✓ All tests completed successfully!")
        print("="*70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await mcp_client.close()


if __name__ == "__main__":
    asyncio.run(check_mcp_server())
