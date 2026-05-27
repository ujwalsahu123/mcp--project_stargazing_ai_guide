"""
check if the tools of the tools.py are working or not. 

run -> 
cd MCP_Server
.venv/scripts/activate # Activate virtual environment
uv run python test.py
"""

import json
import sys
from tools import (
    get_visible_objects,
    get_object_position,
    get_object_detail,
    get_weather_forecast,
)

# Fix encoding for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Test parameters
TEST_LAT = 19.274
TEST_LON = 72.881
TEST_TIME = "2026-05-26T13:30:00+05:30"
TEST_ALTI = -52

print("\n" + "="*60)
print("  StarGuide MCP - Tool Tests")
print("="*60)

# ============================================================
# TOOL 1: get_visible_objects
# ============================================================
print("\n[TOOL 1] get_visible_objects()")
print("-"*60)
try:
    result = get_visible_objects(
        lat=TEST_LAT,
        lon=TEST_LON,
        time=TEST_TIME,
        alti=TEST_ALTI
    )
    print(f"Status: SUCCESS")
    print(f"Found {len(result)} visible objects")
    print(f"Sample: {result} ")
    # print(f"Sample: {result[1]} ")
    # print(f"Sample: {result[2]} ")

    
except Exception as e:
    print(f"Status: FAILED - {e}")

# ============================================================
# TOOL 2: get_object_position
# ============================================================
print("\n[TOOL 2] get_object_position()")
print("-"*60)
try:
    result = get_object_position(
        object_name="Mars",
        lat=TEST_LAT,
        lon=TEST_LON,
        time=TEST_TIME,
        alti=TEST_ALTI
    )
    if "error" in result:
        print(f"Status: FAILED - {result['error']}")
    else:
        print(f"Status: SUCCESS")
        print(f"Object: Mars")
        print(f"Altitude: {result['alt']:.2f}°")
        print(f"Azimuth: {result['az']:.2f}°")
except Exception as e:
    print(f"Status: FAILED - {e}")

# ============================================================
# TOOL 3: get_object_detail
# ============================================================
print("\n[TOOL 3] get_object_detail()")
print("-"*60)
try:
    result = get_object_detail("Mars")
    if "error" in result:
        print(f"Status: FAILED - {result['error']}")
    else:
        print(f"Status: SUCCESS")
        print(f"Object: Mars")
        print(f"{result}")
except Exception as e:
    print(f"Status: FAILED - {e}")

# ============================================================
# TOOL 4: get_weather_forecast
# ============================================================
print("\n[TOOL 4] get_weather_forecast()")
print("-"*60)
try:
    result = get_weather_forecast(
        lat=28.6139,
        lon=77.2090,
        time="2026-05-27T15:00:00Z",
    )
    if "error" in result:
        print(f"Status: FAILED - {result['error']}")
        if "hint" in result:
            print(f"Hint: {result['hint']}")
    else:
        print("Status: SUCCESS")
        print(result)
        
except Exception as e:
    print(f"Status: FAILED - {e}")

print("\n" + "="*60 + "\n")
