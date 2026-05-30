# Run Local :-
# `.venv/scripts/activate`
# `uv run python main.py`
# or 
# `uv run fastmcp dev inspector main.py`   # -> to test the tools using inspector


# then Deploy on Remote Server using fastMCP cloud
# Use Inspector on fastMCP cloud website to test the tools on the server

# Server URL after deploying :-
# https://MCP-Project-Stargazing.fastmcp.app/mcp

from fastmcp import FastMCP
from tools import (
    _load_ephemeris,
    initialize_ephemeris,
    get_visible_objects,
    get_object_position,
    get_object_detail,
    health_check as run_health_check,
    get_weather_forecast
)


load, planets = _load_ephemeris()
initialize_ephemeris(load, planets)

# Create MCP server
mcp = FastMCP("stargazing-mcp-server")


# -------------------------
# TOOL 1: get_visible_objects
# -------------------------
@mcp.tool()
def visible_objects(lat: float, lon: float, time: str = None, alti: float = 0):
    """
    Get top visible celestial objects above the horizon.
    """

    try:
        result = get_visible_objects(lat=lat, lon=lon, time=time, alti=alti)

        return result

    except Exception as e:
        return {
            "error": f"Failed to fetch visible objects: {str(e)}"
        }


# -------------------------
# TOOL 2: get_object_position
# -------------------------
@mcp.tool()
def object_position(object_name: str, lat: float, lon: float, time: str = None, alti: float = 0):
    """
    Get position (alt, az) of a celestial object.
    """

    try:
        result = get_object_position(
            object_name=object_name,
            lat=lat,
            lon=lon,
            time=time,
            alti=alti
        )

        return result

    except Exception as e:
        return {
            "error": f"Failed to fetch object position: {str(e)}"
        }


# -------------------------
# TOOL 3: get_object_detail
# -------------------------
@mcp.tool()
def object_detail(object_name: str):
    """
    Get details of a celestial object.
    """

    try:
        result = get_object_detail(object_name=object_name)

        return result

    except Exception as e:
        return {
            "error": f"Failed to fetch object details: {str(e)}"
        }


# -------------------------
# TOOL 4: health_check
# -------------------------
@mcp.tool()
def health_check():
    """
    Simple no-input health check.
    """

    try:
        return run_health_check()

    except Exception as e:
        return {
            "error": f"Failed health check: {str(e)}"
        }


# -------------------------
# TOOL 5: get_weather_forecast
# -------------------------
@mcp.tool()
def weather_forecast(lat: float, lon: float):
    """
    Get current weather and forecast for a location.

    """

    try:
        result = get_weather_forecast(lat=lat, lon=lon)
        return result

    except Exception as e:
        return {
            "error": f"Failed to fetch weather forecast: {str(e)}"
        }


# -------------------------
# RUN SERVER
# -------------------------

# LOCAL
# if __name__ == "__main__":
#     mcp.run()

# REMOTE
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
    # mcp.run()