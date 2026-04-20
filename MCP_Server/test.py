"""
Local test suite for StarGuide MCP tools
Tests all functions in tools.py without needing FastMCP
"""

import json
import sys
from tools import (
    get_visible_objects,
    get_object_position,
    get_object_detail,
    get_planet_magnitude,
    get_star_magnitude,
    _resolve_observation_times,
)

# Fix encoding for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Test parameters (Mumbai, India)
TEST_LAT = 19.274
TEST_LON = 72.881
TEST_TIME = "2026-04-20T20:30:00+05:30"
TEST_ALTI = -52

print("\n" + "="*70)
print("  StarGuide MCP - Local Tool Tests")
print("="*70)
print(f"Location: {TEST_LAT}°N, {TEST_LON}°E")
print(f"Time: {TEST_TIME}")
print(f"Altitude: {TEST_ALTI}m\n")

# ============================================================
# TEST 1: Planet Magnitudes
# ============================================================
print("="*70)
print("TEST 1: Planet Magnitudes")
print("="*70)

planets_to_test = ["sun", "moon", "venus", "mars", "jupiter", "saturn"]
skyfield_time, _ = _resolve_observation_times(TEST_TIME)

print("\nPlanet magnitudes (lower = brighter):")
for planet in planets_to_test:
    try:
        mag = get_planet_magnitude(planet, skyfield_time)
        print(f"  {planet.capitalize():10} > Magnitude: {mag:6.2f}")
    except Exception as e:
        print(f"  {planet.capitalize():10} > Error: {e}")

# ============================================================
# TEST 2: Star Magnitudes
# ============================================================
print("\n" + "="*70)
print("TEST 2: Star Magnitudes (from Vizier)")
print("="*70)

stars_to_test = ["Sirius", "Vega", "Arcturus", "Pollux", "Capella"]
print("\nStar magnitudes (lower = brighter):")
for star in stars_to_test:
    try:
        mag = get_star_magnitude(star)
        print(f"  {star:15} > Magnitude: {mag:6.2f}")
    except Exception as e:
        print(f"  {star:15} > Error: {e}")

# ============================================================
# TEST 3: Visible Objects
# ============================================================
print("\n" + "="*70)
print("TEST 3: Visible Objects (sorted by brightness)")
print("="*70)

try:
    print("\n🔍 Finding visible objects...")
    objects = get_visible_objects(
        lat=TEST_LAT,
        lon=TEST_LON,
        time=TEST_TIME,
        alti=TEST_ALTI
    )
    
    print(f"\n✓ Found {len(objects)} visible objects:\n")
    print(f"{'#':3} {'Name':20} {'Type':10} {'Alt (°)':10} {'Az (°)':10} {'Mag':8}")
    print("-" * 70)
    
    for i, obj in enumerate(objects[:15], 1):  # Show top 15
        print(f"{i:3} {obj['name']:20} {obj['type']:10} {obj['alt']:10.2f} {obj['az']:10.2f} {obj['magnitude']:8.2f}")
    
    if len(objects) > 15:
        print(f"... and {len(objects) - 15} more")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# TEST 4: Object Position
# ============================================================
print("\n" + "="*70)
print("TEST 4: Object Position")
print("="*70)

objects_to_test = ["Mars", "Jupiter", "Sirius", "Vega"]

for obj_name in objects_to_test:
    try:
        print(f"\n{obj_name}:")
        result = get_object_position(
            object_name=obj_name,
            lat=TEST_LAT,
            lon=TEST_LON,
            time=TEST_TIME,
            alti=TEST_ALTI
        )
        
        if "error" in result:
            print(f"  ❌ {result['error']}")
        else:
            print(f"  ✓ Altitude: {result['alt']:8.2f}°")
            print(f"    Azimuth:  {result['az']:8.2f}°")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")

# ============================================================
# TEST 5: Object Details
# ============================================================
print("\n" + "="*70)
print("TEST 5: Object Details")
print("="*70)

objects_to_detail = ["Sirius", "Venus", "Mars", "Jupiter"]

for obj_name in objects_to_detail:
    try:
        print(f"\n{obj_name}:")
        result = get_object_detail(obj_name)
        
        if "error" in result:
            print(f"  ❌ {result['error']}")
        else:
            print(f"  ✓ Type: {result.get('type', 'N/A')}")
            print(f"    Distance: {result.get('distance', 'N/A')}")
            print(f"    Constellation: {result.get('constellation', 'N/A')}")
            if 'description' in result:
                print(f"    Description: {result['description'][:60]}...")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "="*70)
print("✓ All tests completed!")
print("="*70 + "\n")
