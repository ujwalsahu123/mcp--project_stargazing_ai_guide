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
from urllib import response
from urllib import response
from xmlrpc import client

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient


# Load environment variables
load_dotenv()


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

MCP_SERVER_URL = os.getenv("STARGUIDE_MCP_SERVER_URL")
API_KEY = os.getenv("STARGUIDE_API_KEY")

SERVERS = {
    "starguide": {
        "transport": "streamable_http",
        "url": MCP_SERVER_URL,
        "headers": {
            "Authorization": f"Bearer {API_KEY}",
        },
    }
}

health_check_tool = None
visible_objects_tool = None
object_position_tool = None
object_detail_tool = None
weather_forecast_tool = None



# --------------------------------------------------
# Call Tool - Parse Response - Return Output
# --------------------------------------------------

async def call_tool_fun(tool_name, params):

    # call the tool using the tool_name and pass the params as arguments to the tool
    response = await tool_name.ainvoke(params)
    
    if not response:
        return None
    

    # Extract text from first content block
    text = response[0].get("text", "")

    # Convert JSON string -> Python Dict
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        return {"text": text}







async def main():

    """Check if MCP Server is working and print tool outputs."""

    print("\n" + "=" * 70)
    print("  MCP Server Status Check")

    if not MCP_SERVER_URL:
        print("\n❌ Error: STARGUIDE_MCP_SERVER_URL not set in .env")

    if not API_KEY:
        print("\n❌ Error: STARGUIDE_API_KEY not set in .env")


    print("\n🔗 Connecting to StarGuide MCP Server...")
    client = MultiServerMCPClient(SERVERS)
    tools = await client.get_tools()
    named_tools = {tool.name: tool for tool in tools}

    print("Available Tools:")
    print(named_tools.keys())
    
    print("=" * 70, "\n")


    # Store tools by name, as we already know the tools.
    # we will be calling tools manually, and not relying on agent to call tools
    # thus we need to store tool handles to call them directly in test functions
    # in case of agent calling tools, we can skip this step and let agent decide which tool to call based 
    health_check_tool = named_tools.get("health_check")
    visible_objects_tool = named_tools.get("visible_objects")
    object_position_tool = named_tools.get("object_position")
    object_detail_tool = named_tools.get("object_detail")
    weather_forecast_tool = named_tools.get("weather_forecast")


    # Example values - for testing 
    # later use the users provided values 
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
        print(output)
    
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
        # Pass the Tool & arguments to call_tool function which will call the tool and return the output
        output = await call_tool_fun(tool, params)
        print(output)

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
        "object_name": "Mars",
        "lat": EXAMPLE_LAT,
        "lon": EXAMPLE_LON,
        "time": EXAMPLE_TIME,
        "alti": EXAMPLE_ALTI,
    }
    
    try:
        output = await call_tool_fun(tool,params)
        print(output)

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
        "object_name": "Mars",
    }

    try:
        output = await call_tool_fun(tool, params)
        print(output)
    
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
        print(output)

    except Exception as e:
        print(f"❌ Error: {e}")

    print("=" * 70, "\n")


    print("✓ All tests completed successfully!")




if __name__ == "__main__":
    asyncio.run(main())
