"""
MCP Server Check - Test MCP Server connection and tools working or not

- Directly Calling the tools without using LLM decision making to call the tools

- using way 1) using langchain_mcp_adapters.client
- Execution Time: 45.1584 seconds

run ->
cd Backend
.venv/scripts/activate    # Activate virtual environment
uv run python test1.py
"""


import asyncio
import json
import os

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




# --------------------------------------------------
# Load Tools & Store Tool globally so that we can call them in any function
# --------------------------------------------------

TOOLS = {}

async def load_tools():

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

    global TOOLS

    TOOLS = {
        tool.name: tool
        for tool in tools
    }


    print("Available Tools:")
    print(json.dumps(list(TOOLS.keys()), indent=2))
    print("=" * 70, "\n")




# --------------------------------------------------
# Call Tool - Parse Response - Return Output
# --------------------------------------------------

async def call_tool_fun(tool_name, params):

    # call the tool using the tool_name and pass the params as arguments to the tool
    response = await tool_name.ainvoke(params)

    if not response:
        return None
    
    # # Response Format When using LangChain MCP Adapters Client to call the tool :-
    # [
    #   {
    #       '#type': 'text', 
    #       'text': '{"status":"success"}', 
    #       'id': 'lc_07acb411-866d-4cf6-b8a3-c7880f84d5bb'
    #   }
    # ]
    # so we need to extract the text from the response > text 



    # Extract text from first content block
    text = response[0].get("text", "")

    # Convert JSON string -> Python Dict
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        return {"text": text}


# -----------------------------------
# Test Tools - Directly just like any API endpoint from any function using LangChain MCP Adapters Client
# -----------------------------------

async def test_tools():

    # we will be calling tools manually, and not relying on agent to call tools
    # thus we need to store tool handles 
    # and using it we can call tools directly
    # in case of agent calling tools, we can skip this step and let agent decide which tool to call based 
    health_check_tool = TOOLS.get("health_check")
    visible_objects_tool = TOOLS.get("visible_objects")
    object_position_tool = TOOLS.get("object_position")
    object_detail_tool = TOOLS.get("object_detail")
    weather_forecast_tool = TOOLS.get("weather_forecast")

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
        # Pass the Tool & arguments to call_tool function which will call the tool and return the output
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
        output = await call_tool_fun(tool,params)
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

# So that when the backend starts then main function will automatically run in the start , and then it will load the tools and store them in the global variable TOOLS and then we can call those tools from any function in the backend using the TOOLS variable.

async def main():

    await load_tools() # to load tools and store them in global variable TOOLS so that we can call them from any function in the backend

    await test_tools() # to test the tools by calling them directly using the global variable TOOLS without relying on agent to call the tools

# for FastAPI there is no main function but we can call the load_tools() function in the startup event of the FastAPI so that when the FastAPI server starts then it will automatically load the tools and store them in the global variable TOOLS and then we can call those tools from any endpoint in the FastAPI using the TOOLS variable.

# @app.on_event("startup")
# async def startup():
#     await load_tools()



if __name__ == "__main__":

    # time counter start
    import time
    start = time.perf_counter()

    # run the main function
    asyncio.run(main())

    # time counter end
    end = time.perf_counter()
    print(f"Time Taken: {end - start:.4f} sec")
 
