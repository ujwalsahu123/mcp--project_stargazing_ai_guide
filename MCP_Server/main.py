# main.py

from fastmcp import FastMCP
from tools import (
    get_visible_objects,
    get_object_position,
    get_object_detail
)

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

        if not result:
            return {
                "error": "No visible objects found for this location and time."
            }

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
# RUN SERVER
# -------------------------

# LOCAL
# if __name__ == "__main__":
#     mcp.run()

# REMOTE
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
    # mcp.run()