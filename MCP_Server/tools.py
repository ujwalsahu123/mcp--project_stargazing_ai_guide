# tools.py

from skyfield.api import Loader, Topos
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy import units as u
from astroquery.vizier import Vizier
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


# -------------------------
# LOAD DATA ONCE
# -------------------------

BASE_DIR = Path(__file__).resolve().parent
SKYFIELD_DATA_DIR = Path(os.getenv("STARGUIDE_SKYFIELD_DATA_DIR", BASE_DIR / "skyfield-data"))
DEBUG_MODE = os.getenv("STARGUIDE_DEBUG", "0") == "1"


def _debug_log(message):
    if DEBUG_MODE:
        print(f"[tools.py] {message}")


# 
def _load_ephemeris():
    candidate_dirs = [SKYFIELD_DATA_DIR, BASE_DIR.parent.parent / "skyfield-data"]
    last_error = None

    for data_dir in candidate_dirs:
        try:
            loader = Loader(str(data_dir))
            ephemeris = loader("de440s.bsp")
            # Health check: some truncated files can load but fail on the first planet computation.
            test_time = loader.timescale().now()
            earth_test = ephemeris["earth"]
            mars_test = ephemeris[4]
            earth_test.at(test_time).observe(mars_test)
            _debug_log(f"Loaded de440s.bsp from {data_dir}")
            return loader, ephemeris
        except Exception as exc:
            last_error = exc
            _debug_log(f"Failed to load de440s.bsp from {data_dir}: {exc}")

    raise RuntimeError("Unable to load de440s.bsp from any configured data directory") from last_error


load, planets = _load_ephemeris()

earth = planets["earth"]
ts = load.timescale()


# -------------------------
# OBJECT LISTS
# -------------------------

SOLAR_SYSTEM_MAP = {
    "sun": 10,
    "moon": 301,
    "mercury": 199,
    "venus": 299,
    "mars": 4,
    "jupiter": 5,
    "saturn": 6,
    "uranus": 7,
    "neptune": 8,
    "pluto": 9,
}

STARS = [
    "Sirius", "Canopus", "Alpha Centauri", "Arcturus", "Vega",
    "Capella", "Rigel", "Procyon", "Achernar", "Betelgeuse",
    "Hadar", "Altair", "Acrux", "Aldebaran", "Antares",
    "Spica", "Pollux", "Fomalhaut", "Deneb", "Mimosa",
    "Regulus", "Adhara", "Shaula", "Castor", "Gacrux",
    "Bellatrix", "Elnath", "Miaplacidus", "Alnilam", "Alnair",
    "Alnitak", "Regor", "Kaus Australis", "Avior", "Sargas",
    "Menkalinan", "Atria", "Alhena", "Peacock", "Mirzam",
    "Polaris"
]


# -------------------------
# MAGNITUDE/BRIGHTNESS CALCULATIONS
# -------------------------

# Cache for star magnitudes (name -> magnitude)
_STAR_MAGNITUDE_CACHE = {}

def get_planet_magnitude(name, skyfield_time):
    """
    Calculate apparent magnitude of a planet.
    Lower values = brighter.
    """
    try:
        sun = planets[10]
        obj = planets[SOLAR_SYSTEM_MAP[name.lower()]]
        
        location = earth
        
        astrometric = location.at(skyfield_time).observe(obj)
        
        # Get elongation (angle from sun) for magnitude calculation
        geocentric = location.at(skyfield_time).observe(obj)
        sun_geocentric = location.at(skyfield_time).observe(sun)
        
        # Simple magnitude estimation based on object
        # These are approximate values for average conditions
        magnitude_map = {
            "sun": -26.74,
            "moon": -2.5,
            "mercury": 1.0,
            "venus": -4.0,
            "mars": 1.5,
            "jupiter": -2.0,
            "saturn": 0.5,
            "uranus": 5.5,
            "neptune": 7.5,
            "pluto": 14.0,
        }
        
        mag = magnitude_map.get(name.lower(), 5.0)
        return mag
    except Exception as exc:
        _debug_log(f"get_planet_magnitude failed for {name}: {exc}")
        return 5.0  # default fallback


def get_star_magnitude(star_name):
    """
    Get visual magnitude (V mag) of a star from Vizier catalog.
    Lower values = brighter.
    Caches results to avoid repeated queries.
    """
    if star_name in _STAR_MAGNITUDE_CACHE:
        return _STAR_MAGNITUDE_CACHE[star_name]
    
    try:
        vizier = Vizier(columns=["Vmag", "RA_ICRS", "DE_ICRS"])
        vizier.ROW_LIMIT = 1
        
        # Try Gaia first (has V mag)
        result = vizier.query_object(star_name, catalog="I/345/gaia2")
        if result and len(result) > 0 and "Vmag" in result[0].colnames:
            mag = float(result[0]["Vmag"][0])
            _STAR_MAGNITUDE_CACHE[star_name] = mag
            return mag
        
        # Try Hipparcos (has Vmag)
        result = vizier.query_object(star_name, catalog="I/239/hip_main")
        if result and len(result) > 0 and "Vmag" in result[0].colnames:
            mag = float(result[0]["Vmag"][0])
            _STAR_MAGNITUDE_CACHE[star_name] = mag
            return mag
        
        # Default fallback (dim star)
        _STAR_MAGNITUDE_CACHE[star_name] = 6.0
        return 6.0
        
    except Exception as exc:
        _debug_log(f"get_star_magnitude failed for {star_name}: {exc}")
        _STAR_MAGNITUDE_CACHE[star_name] = 6.0
        return 6.0





def _resolve_observation_times(time_input=None):
    """
    Returns both Skyfield Time and Astropy Time for a given input.

    Supported inputs:
    - None -> current time (computed by tools.py)
    - ISO datetime string
    - datetime.datetime
    - astropy.time.Time
    - skyfield Time-like object (must expose utc_iso)
    """
    if time_input is None:
        skyfield_time = ts.now()
        return skyfield_time, Time(skyfield_time.utc_iso())

    if isinstance(time_input, Time):
        return ts.from_astropy(time_input), time_input

    if isinstance(time_input, datetime):
        astropy_time = Time(time_input)
        return ts.from_astropy(astropy_time), astropy_time

    if isinstance(time_input, str):
        try:
            astropy_time = Time(time_input)
        except ValueError:
            try:
                dt_value = datetime.fromisoformat(time_input.replace("Z", "+00:00"))
                if dt_value.tzinfo is not None:
                    dt_value = dt_value.astimezone(timezone.utc).replace(tzinfo=None)
                astropy_time = Time(dt_value)
            except Exception as exc:
                raise ValueError(f"Unsupported time string format: {time_input}") from exc
        return ts.from_astropy(astropy_time), astropy_time

    # Fallback: treat as a Skyfield Time-like object
    if hasattr(time_input, "utc_iso"):
        return time_input, Time(time_input.utc_iso())

    raise ValueError("Unsupported time format")

# Returns the alt-az of a solar system object.
def calculate_solar_system_alt_az(name, lat, lon, alti, time_input=None):
    try:
        obj = planets[SOLAR_SYSTEM_MAP[name.lower()]]
        skyfield_time, _ = _resolve_observation_times(time_input)

        location = Topos(
            latitude_degrees=lat,
            longitude_degrees=lon,
            elevation_m=alti
        )

        astrometric = (earth + location).at(skyfield_time).observe(obj)
        alt, az, _ = astrometric.apparent().altaz()

        return float(alt.degrees), float(az.degrees)

    except Exception as exc:
        _debug_log(f"calculate_solar_system_alt_az failed for {name}: {exc}")
        return None, None


# Returns the RA/Dec of a Star by its name.
def get_ra_dec(name):
    try:
        vizier = Vizier(columns=["RA_ICRS", "DE_ICRS"])
        vizier.ROW_LIMIT = 1

        result = vizier.query_object(name, catalog="I/345/gaia2")
        if result:
            return result[0]["RA_ICRS"][0], result[0]["DE_ICRS"][0]

        result = vizier.query_object(name, catalog="I/239/hip_main")
        if result:
            return result[0]["RA_ICRS"][0], result[0]["DE_ICRS"][0]

    except Exception as exc:
        _debug_log(f"get_ra_dec failed for {name}: {exc}")

    return None, None

# Returns the alt-az of a star 
def calculate_star_alt_az(ra, dec, lat, lon, alti, time_input=None):
    try:
        _, astropy_time = _resolve_observation_times(time_input)

        location = EarthLocation(
            lat=lat * u.deg,
            lon=lon * u.deg,
            height=alti * u.m
        )

        coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
        altaz = coord.transform_to(AltAz(obstime=astropy_time, location=location))

        return float(altaz.alt.deg), float(altaz.az.deg)

    except Exception as exc:
        _debug_log(f"calculate_star_alt_az failed: {exc}")
        return None, None


# -------------------------
# TOOL 1: GET VISIBLE OBJECTS
# -------------------------

# Returns list of visible objects (alt > 0) sorted by brightness
# We are not going through each and every star (millions) and then filtering by altitude, and then sorting by brightness, and then returning the top 50. 
# Instead, we are only going through a predefined list of bright stars and planets (50 brightest once), which is much more efficient.
# later instead of top 50 brightest objects , we can search from a larger list of objects and then return top 50 brightest objects. 
# but for now we are simply calculating the alt-az and brightness of a predefined list of bright objects (top 50) and then sorting them by brightness 
# and then returning all the objects which are visible (alt > 0) sorted by brightness.

# so later :-
# Large list of object -> calc the alt az & brightness -> filter by alt > 0 -> sort by brightness -> Now we have a big list of visible objects sorted by brightness -> return top N from that list.
 
def get_visible_objects(lat, lon, time=None, alti=0):
    """
    Returns list of visible objects (alt > 0) sorted by brightness.
    Lower magnitude means higher brightness.
    """

    visible = []
    skyfield_time, _ = _resolve_observation_times(time)

    def _brightness_from_magnitude(magnitude):
        try:
            return math.pow(10, -0.4 * float(magnitude))
        except Exception:
            return 0.0

    # Solar system objects
    for name in SOLAR_SYSTEM_MAP.keys():
        alt, az = calculate_solar_system_alt_az(name, lat, lon, alti, time_input=time)
        if alt is not None and alt > 0:
            magnitude = get_planet_magnitude(name, skyfield_time)
            object_type = "star" if name.lower() == "sun" else "planet"
            visible.append({
                "name": name.capitalize(),
                "type": object_type,
                "alt": round(float(alt), 4),
                "az": round(float(az), 4),
                "magnitude": round(float(magnitude), 4),
                "brightness": round(_brightness_from_magnitude(magnitude), 4),
            })

    # Stars
    for star in STARS:
        ra, dec = get_ra_dec(star)
        if ra is None:
            continue

        alt, az = calculate_star_alt_az(ra, dec, lat, lon, alti, time_input=time)
        if alt is not None and alt > 0:
            magnitude = get_star_magnitude(star)
            visible.append({
                "name": star,
                "type": "star",
                "alt": round(float(alt), 4),
                "az": round(float(az), 4),
                "magnitude": round(float(magnitude), 4),
                "brightness": round(_brightness_from_magnitude(magnitude), 6),  # keeping it 6 since some objects have very low brightness and we want to differentiate them in the sorting
            })

    # Sort by brightness (higher brightness first)
    visible.sort(key=lambda x: x["brightness"], reverse=True)

    if visible:
        return visible # return all the visible objects sorted by brightness (we started with 50 but it may not always return 50 since some objects may not be visible alt<0)
    else:
        return {"error": "No visible objects found for this location and time."}

# -------------------------
# TOOL 2: GET OBJECT POSITION
# -------------------------

# Returns alt-az position of an object
def get_object_position(object_name, lat, lon, time=None, alti=0):
    """
    Returns alt-az position of object
    """

    name = object_name.lower()

    # Solar system
    if name in SOLAR_SYSTEM_MAP:
        alt, az = calculate_solar_system_alt_az(name, lat, lon, alti, time_input=time)
        if alt is not None:
            return {"alt": alt, "az": az}

    # Star
    ra, dec = get_ra_dec(object_name)
    if ra is not None:
        alt, az = calculate_star_alt_az(ra, dec, lat, lon, alti, time_input=time)
        if alt is not None:
            return {"alt": alt, "az": az}

    return {"error": f"Object '{object_name}' not found or not visible"}


# -------------------------
# TOOL 3: GET OBJECT DETAILS
# -------------------------

# Returns details from star_info.json
def get_object_detail(object_name):
    """
    Returns details from star_info.json
    """

    try:
        star_info_path = BASE_DIR / "star_info.json"
        _debug_log(f"Loading star info from: {star_info_path}")
        
        with open(star_info_path) as f:
            data = json.load(f)

        result = data.get(object_name)

        if result:
            return result
        else:
            return {"error": f"No data found for object '{object_name}'"}

    except Exception as exc:
        _debug_log(f"get_object_detail failed: {exc}")
        return {"error": "Failed to load star data"}


# -------------------------
# TOOL 4: GET WEATHER FORECAST
# -------------------------

OPENWEATHER_API_KEY = os.getenv("STARGUIDE_OPENWEATHER_API_KEY", "[REDACTED]")


def _parse_iso_time(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    raise ValueError("Unsupported time format")


def _format_dt_from_unix(timestamp):
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fetch_json(url):
    try:
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"OpenWeather request failed with HTTP {exc.code}: {error_body or exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenWeather request failed: {exc.reason}") from exc


def get_weather_forecast(lat, lon, time=None, api_key=None):
    """
    Returns current weather and the next 6 hours forecast from OpenWeather.
    """

    api_key = api_key or OPENWEATHER_API_KEY
    target_time = _parse_iso_time(time)

    query = urlencode(
        {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
        }
    )

    current_url = f"https://api.openweathermap.org/data/2.5/weather?{query}"
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?{query}"

    try:
        current_data = _fetch_json(current_url)
        forecast_data = _fetch_json(forecast_url)
    except RuntimeError as exc:
        return {
            "target_time": target_time.isoformat().replace("+00:00", "Z"),
            "coordinates": {"lat": lat, "lon": lon},
            "error": str(exc),
            "hint": "Check that the OpenWeather API key is valid and activated, or set STARGUIDE_OPENWEATHER_API_KEY in your environment.",
        }

    if current_data.get("cod") not in (200, "200"):
        raise RuntimeError(f"Current weather request failed: {current_data}")
    if forecast_data.get("cod") not in (200, "200"):
        raise RuntimeError(f"Forecast request failed: {forecast_data}")

    current_weather = {
        "time": _format_dt_from_unix(current_data.get("dt", 0)),
        "temperature_c": round(float(current_data["main"]["temp"]), 3),
        "feels_like_c": round(float(current_data["main"]["feels_like"]), 3),
        "conditions": current_data["weather"][0]["description"],
        "humidity_pct": int(current_data["main"]["humidity"]),
        "wind_speed_mps": round(float(current_data.get("wind", {}).get("speed", 0.0)), 3),
    }

    forecast_items = []
    for item in forecast_data.get("list", []):
        item_dt = datetime.fromtimestamp(int(item["dt"]), tz=timezone.utc)
        delta_hours = (item_dt - target_time).total_seconds() / 3600.0
        if 0 <= delta_hours <= 6:
            forecast_items.append(
                {
                    "time": _format_dt_from_unix(item["dt"]),
                    "temperature_c": round(float(item["main"]["temp"]), 3),
                    "conditions": item["weather"][0]["description"],
                }
            )

    return {
        "target_time": target_time.isoformat().replace("+00:00", "Z"),
        "location": {
            "name": current_data.get("name"),
            "country": current_data.get("sys", {}).get("country"),
            "lat": round(float(lat), 4),
            "lon": round(float(lon), 4),
        },
        "current_weather": current_weather,
        "next_6h_forecast": forecast_items,
    }