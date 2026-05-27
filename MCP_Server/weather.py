"""Standalone OpenWeather demo.

Run this file directly to fetch current weather and the next 6 hours forecast
for a hardcoded location/time.

The API key can come from STARGUIDE_OPENWEATHER_API_KEY or the fallback
constant below.

cd MCP_Server
.venv/scripts/activate # Activate virtual environment
uv run python weather.py

"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv


load_dotenv()


API_KEY = os.getenv("STARGUIDE_OPENWEATHER_API_KEY")
LATITUDE = 28.6139
LONGITUDE = 77.2090
OBSERVATION_TIME = "2026-05-27T15:00:00Z"


def _parse_iso_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_dt_from_unix(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fetch_json(url: str) -> dict:
    try:
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"OpenWeather request failed with HTTP {exc.code}: {error_body or exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenWeather request failed: {exc.reason}") from exc


def get_weather(lat: float, lon: float, time_iso: str, api_key: str) -> dict:
    """Return current weather plus the next 6 hours forecast summary."""
    target_time = _parse_iso_time(time_iso)

    current_query = urlencode(
        {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
        }
    )
    forecast_query = urlencode(
        {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
        }
    )

    current_url = f"https://api.openweathermap.org/data/2.5/weather?{current_query}"
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?{forecast_query}"

    try:
        current_data = _fetch_json(current_url)
        forecast_data = _fetch_json(forecast_url)
    except RuntimeError as exc:
        return {
            "target_time": time_iso,
            "coordinates": {"lat": lat, "lon": lon},
            "error": str(exc),
            "hint": "Check that the OpenWeather API key is valid and activated, or set STARGUIDE_OPENWEATHER_API_KEY in your environment.",
        }

    if current_data.get("cod") not in (200, "200"):
        raise RuntimeError(f"Current weather request failed: {current_data}")
    if forecast_data.get("cod") not in (200, "200"):
        raise RuntimeError(f"Forecast request failed: {forecast_data}")

    current_weather = {
        "time": _format_dt_from_unix(int(current_data.get("dt", 0))),
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
                    "time": _format_dt_from_unix(int(item["dt"])),
                    "temperature_c": round(float(item["main"]["temp"]), 3),
                    "conditions": item["weather"][0]["description"],
                }
            )

    return {
        "target_time": time_iso,
        "location": {
            "name": current_data.get("name"),
            "country": current_data.get("sys", {}).get("country"),
            "lat": round(float(lat), 4),
            "lon": round(float(lon), 4),
        },
        "current_weather": current_weather,
        "next_6h_forecast": forecast_items,
    }


if __name__ == "__main__":
    result = get_weather(LATITUDE, LONGITUDE, OBSERVATION_TIME, API_KEY)
    print(json.dumps(result, indent=2, ensure_ascii=False))