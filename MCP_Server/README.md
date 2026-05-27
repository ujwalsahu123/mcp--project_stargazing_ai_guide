# StarGuide MCP Server

MCP server for stargazing + weather.

It exposes 4 tools:
1. `visible_objects` - visible celestial objects sorted by brightness
2. `object_position` - altitude/azimuth for a specific object
3. `object_detail` - static object details from `star_info.json`
4. `weather_forecast` - current weather + next 6 hours forecast

Deployed endpoint:
`https://MCP-Project-Stargazing.fastmcp.app/mcp`

## Quick Start

```bash
cd MCP_Server
uv sync
uv run python main.py
```

For local tool inspection:

```bash
uv run fastmcp dev inspector main.py
```

Run local tests:

```bash
uv run python test.py
```

## Tools :-

### `visible_objects`

Input shape:

```json
{
  "lat": 19.274,
  "lon": 72.881,
  "time": "2026-05-27T15:00:00Z",
  "alti": 0
}
```

Output shape (example):

```json
[
  {
    "name": "Sun",
    "type": "star",
    "alt": 77.0819,
    "az": 280.6664,
    "magnitude": -26.74,
    "brightness": 49659232145.0336
  },
  {
    "name": "Venus",
    "type": "planet",
    "alt": 68.1661,
    "az": 70.7921,
    "magnitude": -4.0,
    "brightness": 39.8107
  }
]
```

### `object_position`

Input shape:

```json
{
  "object_name": "Mars",
  "lat": 19.274,
  "lon": 72.881,
  "time": "2026-05-27T15:00:00Z",
  "alti": 0
}
```

Output shape (example):

```json
{
  "alt": 47.9604,
  "az": 267.7496
}
```

### `object_detail`

Input shape:

```json
{
  "object_name": "Mars"
}
```

Output (example):

```json
{
  "display_name": "Mars",
  "type": "Planet",
  "distance": "1.52 AU",
  "constellation": "Varies",
  "description": "The red planet, known for its iron-rich dusty surface.",
  "mythology": "Named after the Roman god of war."
}
```

### `weather_forecast`

Input shape:

```json
{
  "lat": 28.6139,
  "lon": 77.2090,
  "time": "2026-05-27T15:00:00Z"
}
```

Weather Output Shape


```json
{
  "target_time": "2026-05-27T15:00:00Z",
  "location": {
    "name": "Parliament House, Delhi",
    "country": "IN",
    "lat": 28.6139,
    "lon": 77.209
  },
  "current_weather": {
    "time": "2026-05-27 10:34 UTC",
    "temperature_c": 44.07,
    "feels_like_c": 41.13,
    "conditions": "clear sky",
    "humidity_pct": 10,
    "wind_speed_mps": 5.14
  },
  "next_6h_forecast": [
    {
      "time": "2026-05-27 15:00 UTC",
      "temperature_c": 43.78,
      "conditions": "clear sky"
    }
  ]
}
```

## Environment Variables

- `STARGUIDE_OPENWEATHER_API_KEY`: OpenWeather API key for weather tool
- `STARGUIDE_SKYFIELD_DATA_DIR`: custom path for ephemeris data (optional)
- `STARGUIDE_DEBUG=1`: enable debug logs

## Files

- `main.py`: MCP tool wrappers + server startup
- `tools.py`: astronomy and weather logic
- `test.py`: local test runner
- `weather.py`: standalone weather script
- `star_info.json`: object detail database

## Notes

- Time should be ISO format (example: `2026-05-27T15:00:00Z`).
- If weather returns auth error, check your OpenWeather key in `STARGUIDE_OPENWEATHER_API_KEY`.
