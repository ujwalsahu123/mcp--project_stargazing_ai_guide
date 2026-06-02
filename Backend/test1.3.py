"""
MCP Server Check - Test MCP Server connection and tools working or not.

- Directly Calling the tools without using LLM decision making to call the tools

- using way 2) direct HTTP request 
- same as test1.2.py but here instead of initalizing & closing the client - in each tool call, we are creating a global client which will be initialized once in the start and then we can use that global client to call the tools from any function without creating new client every time.
- Execution Time: 7.3325 seconds

- This way is Recommended , since its better than test1.2.py

- Warning comes when we run this code ... telling to close the client after using it - await CLIENT.aclose()
- but since a backend server it runs continuously - it will not show warning to close the client.
- it is a bit faster since we are not creating new client every time we call the tool

- need to run the initialize_client() function at startup to initialize the global client

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


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

MCP_SERVER_URL = os.getenv("STARGUIDE_MCP_SERVER_URL")
API_KEY = os.getenv("STARGUIDE_API_KEY")



# --------------------------------------------------
# Make global Client - so that we can call the tools from any function without creating new client every time
# --------------------------------------------------

CLIENT = None

async def initialize_client():

    print("\n" + "=" * 70)
    print("  MCP Server Status Check")

    if not MCP_SERVER_URL:
        print("\n❌ Error: STARGUIDE_MCP_SERVER_URL not set in .env")

    if not API_KEY:
        print("\n❌ Error: STARGUIDE_API_KEY not set in .env")


    global CLIENT

    CLIENT = httpx.AsyncClient(
        timeout=120.0,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
    )

    print("✓ MCP Client Initialized")






# --------------------------------------------------
# Call Tool - Parse Response - Return Output
# --------------------------------------------------

async def call_tool_fun(tool_name, params):

    # making the mcp request by ourself without using any client library
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),  # so that every request has unique id
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params,
        },
    }

    response = await CLIENT.post(
        MCP_SERVER_URL,
        json=payload,
    )

    response.raise_for_status()
    
    # # Response Format When using https to call the tool :-
    # {
    #   "result": 
    #    {
    #        "content": 
    #         [
    #           {
    #               "type": "text",
    #               "text": "The Weather of Mumbai is pleasant"
    #           }
    #         ],
    #       
    #        "structuredContent": 
    #         {
    #             "temp": 31,
    #             "condition": "Cloudy"
    #         },
    #
    #         "isError": false    # if error then true, else false
    #     }
    # }
    
    # The content is always returned , but the structuredContent is only returned when the output is in a structured format like Dictionary, JSON ... and structuredContent is same as content.text just in a structured JSON format.
    # so we need to extract the text from the response > result > structured content > or if structured content is not available then extract context > text 
  

    # parse the result from the response    
    for line in response.text.splitlines():
        if line.startswith("data:"):
            data = json.loads(
                line.replace("data:", "").strip()
            )
            result = data.get("result", {})
            break
    else:
        return "No result in response"
     

    # check if result available    
    if not result:
        return None

    # check if error
    is_error = result.get("isError")
    if is_error:
        return None

    # return the structured content if available
    structured_content = result.get("structuredContent")
    if structured_content:
        return structured_content

    # if structured content is not available, try to extract content > text
    content = result.get("content", [])
    if content:
        text = content[0].get("text")        
        return text

    # if tool called successfully but no content returned
    return None






# -----------------------------------
# Test Tools - Directly just like any API endpoint from any function using https
# -----------------------------------

async def test_tools():

    # we need to pass the tool name and the arguments to the call_tool_fun function which will call the tool and return the output
    # for example if we want to call the visible_objects tool then we need to pass the tool name as "visible_objects" and the arguments as a dictionary like this :-
    # tool_name = "visible_objects"
    # so not like in way 1) where we were making tool objects, here we just need to pass the tool name as string
    # and we already need to know the tool names. 

    health_check_tool = "health_check"
    visible_objects_tool = "visible_objects"
    object_position_tool = "object_position"
    object_detail_tool = "object_detail"
    weather_forecast_tool = "weather_forecast"

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
# In Main function - call the initialize_client() function 
# -----------------------------------

# So that when the backend starts then main function will automatically run in the start , and then it will load the client and store them in the global variable CLIENT and then we can use it from any function in the backend.

async def main():

    await initialize_client() # to initialize the global client which we can use to call the tools from any function without creating new client every time

    await test_tools() # to test the tools by calling them directly using the global variable TOOLS without relying on agent to call the tools
  





if __name__ == "__main__":

    # time counter start
    import time
    start = time.perf_counter()

    # run the main function
    asyncio.run(main())
    
    # time counter end
    end = time.perf_counter()
    print(f"Time Taken: {end - start:.4f} sec")
 