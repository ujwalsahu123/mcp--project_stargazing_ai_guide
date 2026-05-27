# StarGuide MCP Server

MCP server for stargazing + weather.

It exposes 5 tools:
1. `visible_objects` - visible celestial objects sorted by brightness
2. `object_position` - altitude/azimuth for a specific object
3. `object_detail` - static object details from `star_info.json`
4. `health_check` - simple no-input status check
5. `weather_forecast` - current weather + forecast

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
  "name": "mars",
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

### `health_check`

No input.

Output (example):

```json
{
  "status": "success"
}
```

### `weather_forecast`

Input shape:

```json
{
  "lat": 28.6139,
  "lon": 77.2090,
}
```

Weather Output Shape

The `weather_forecast` tool returns a flat mapping of time strings to a short summary string in the format "MAIN, description".

- The first entry is the current weather time (formatted as `YYYY-MM-DD HH:MM:SS`, UTC).
- Following entries are the starting 6 forecast items (use OpenWeather `dt_txt` when available, format `YYYY-MM-DD HH:MM:SS`).

Example return value (Python dict / JSON object):

```json
{
  "2026-05-27 17:07:39": "Clear, clear sky",
  "2026-05-27 18:00:00": "Clear, clear sky",
  "2026-05-27 21:00:00": "Clear, clear sky",
  "2026-05-28 00:00:00": "Clouds, few clouds",
  "2026-05-28 03:00:00": "Clouds, overcast clouds",
  "2026-05-28 06:00:00": "Clouds, broken clouds",
  "2026-05-28 09:00:00": "Clouds, scattered clouds"
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


