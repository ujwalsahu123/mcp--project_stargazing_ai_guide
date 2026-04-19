# tools.py

from skyfield.api import Loader, Topos
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy import units as u
from astroquery.vizier import Vizier
import json
import os
from datetime import datetime, timezone
from pathlib import Path


# -------------------------
# LOAD DATA ONCE
# -------------------------

BASE_DIR = Path(__file__).resolve().parent
SKYFIELD_DATA_DIR = Path(os.getenv("STARGUIDE_SKYFIELD_DATA_DIR", BASE_DIR / "skyfield-data"))
DEBUG_MODE = os.getenv("STARGUIDE_DEBUG", "0") == "1"


def _debug_log(message):
    if DEBUG_MODE:
        print(f"[tools.py] {message}")


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
# HELPER FUNCTIONS
# -------------------------


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
# We are not going through each and every star and then filtering by altitude, and then sorting by brightness, and then returning the top 50. 
# Instead, we are only going through a predefined list of bright stars and planets, which is much more efficient.

 
def get_visible_objects(lat, lon, time=None, alti=0):
    """
    Returns list of visible objects (alt > 0) sorted by brightness (approx).
    """

    visible = []

    # Solar system objects
    for name in SOLAR_SYSTEM_MAP.keys():
        alt, az = calculate_solar_system_alt_az(name, lat, lon, alti, time_input=time)
        if alt is not None and alt > 0:
            visible.append({
                "name": name.capitalize(),
                "type": "planet",
                "alt": alt,
                "az": az,
                "brightness": -1  # approx
            })

    # Stars
    for star in STARS:
        ra, dec = get_ra_dec(star)
        if ra is None:
            continue

        alt, az = calculate_star_alt_az(ra, dec, lat, lon, alti, time_input=time)
        if alt is not None and alt > 0:
            visible.append({
                "name": star,
                "type": "star",
                "alt": alt,
                "az": az,
                "brightness": 1  # rough placeholder
            })

    # Sort by brightness (lower = brighter)
    visible.sort(key=lambda x: x["brightness"])

    return visible[:50]  # return top 50


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

    return {"error": "Object not found or not visible"}


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

        return {"error": "No data found for this object"}

    except Exception as exc:
        _debug_log(f"get_object_detail failed: {exc}")
        return {"error": "Failed to load star data"}