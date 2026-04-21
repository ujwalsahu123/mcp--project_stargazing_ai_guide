# StarGuide Backend - LLM-Powered Stargazing API

Intelligent stargazing assistant REST API combining Azure OpenAI GPT-4o, remote MCP astronomical tools, and FastAPI.

---

## 🚀 Quick Start (2 minutes)

### 1. Install Dependencies
```bash
cd Backend
uv sync
```

### 2. Configure Credentials
Create/edit `.env`:
```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
STARGUIDE_API_KEY=your-starguide-key
```

### 3. Start Server
```bash
uv run python main.py
```

Server runs at: **http://localhost:8000**

### 4. Test API
- **API Docs:** http://localhost:8000/docs (Swagger UI)
- **Health Check:** `curl http://localhost:8000/health`

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [API Endpoints](#api-endpoints)
3. [Installation & Setup](#installation--setup)
4. [How It Works](#how-it-works)
5. [Architecture](#architecture)
6. [Request/Response Examples](#requestresponse-examples)
7. [Configuration](#configuration)
8. [MCP Tools](#mcp-tools)
9. [Running the Server](#running-the-server)
10. [Debugging & Troubleshooting](#debugging--troubleshooting)
11. [Frontend Integration](#frontend-integration)

---

## Overview

This backend provides a production-ready REST API for stargazing queries powered by:

- **Azure OpenAI (GPT-4o)** - Natural language understanding and response generation
- **Remote FastMCP Server** - 3 astronomical tools for real-time data
- **FastAPI** - Modern REST framework with automatic documentation
- **Async Processing** - Non-blocking request handling for better performance
- **Chat History Support** - Multi-turn conversations with full context

### Key Features

✅ Two main endpoints: `/initial` (fresh queries) and `/chat` (contextual)  
✅ Real-time astronomical data (visible objects, positions, details)  
✅ Multi-turn conversation support with chat history  
✅ Comprehensive error handling and logging  
✅ Type-safe request/response models (Pydantic)  
✅ Automatic API documentation (Swagger + ReDoc)  
✅ Async/await for optimal performance  

---

## API Endpoints

### 1. GET `/health` - Health Check

**Purpose:** Verify API is running

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "message": "StarGuide API is running"
}
```

---

### 2. POST `/initial` - Initial Stargazing Session

**Purpose:** Get initial stargazing experience with top 10 visible objects and poetic narratives

**Use when:** User opens app and asks "What can I see tonight?"

**Request:**
```bash
curl -X POST http://localhost:8000/initial \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 19.274,
    "longitude": 72.881,
    "altitude": -0.052,
    "time": "2026-04-20T20:30:00+05:30"
  }'
```

**Request Model:**
```python
{
  "latitude": float,        # Observer latitude (-90 to 90)
  "longitude": float,       # Observer longitude (-180 to 180)
  "altitude": float,        # Observer altitude in km (default: 0)
  "time": str              # ISO 8601 format (e.g., 2026-04-20T20:30:00+05:30)
}
```

**Response:**
```json
{
  "success": true,
  "format": "json",
  "intro": "Tonight's sky unfurls a tapestry of luminous treasures...",
  "objects": [
    {
      "name": "Venus",
      "magnitude": "-4.0",
      "altitude": "3.37°",
      "azimuth": "289.59°",
      "info": "Venus, the radiant evening star, glimmers low on the horizon..."
    },
    ...
  ],
  "total_objects_available": 31,
  "objects_returned": 10,
  "location": {
    "latitude": 19.274,
    "longitude": 72.881,
    "altitude": -0.052
  },
  "observation_time": "2026-04-20T20:30:00+05:30"
}
```

---

### 3. POST `/chat` - Chat with StarGuide

**Purpose:** Answer astronomy questions with smart tool selection and conversation history support

**Use when:** User asks follow-up questions or detailed queries

**Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Is Jupiter visible tonight? Where is it exactly?",
    "latitude": 19.274,
    "longitude": 72.881,
    "altitude": -0.052,
    "time": "2026-04-20T20:30:00+05:30",
    "chat_history": [
      {
        "role": "user",
        "content": "What can I see tonight?"
      },
      {
        "role": "assistant",
        "content": "Tonight you can see Venus, Jupiter, the Moon..."
      }
    ]
  }'
```

**Request Model:**
```python
{
  "query": str,                      # Your astronomy question
  "latitude": float,
  "longitude": float,
  "altitude": float,
  "time": str,
  "chat_history": Optional[List[{
    "role": str,                     # "user" or "assistant"
    "content": str                   # Message content
  }]]
}
```

**Response:**
```json
{
  "success": true,
  "query": "Is Jupiter visible tonight? Where is it exactly?",
  "response": "Yes, Jupiter is absolutely visible tonight at an altitude of 54.9° in the west-southwest (azimuth 282°). Through a telescope you'll see...",
  "tools_called": 2,
  "location": {
    "latitude": 19.274,
    "longitude": 72.881,
    "altitude": -0.052
  },
  "observation_time": "2026-04-20T20:30:00+05:30"
}
```

---

## Architecture

### System Diagram

```
Frontend Application
    ↓
REST Request (POST /initial or /chat)
    ↓
FastAPI Server (main.py)
├─ Request validation (Pydantic)
├─ CORS middleware (allows all origins)
└─ Route handler
    ↓
MCP Client (mcp_client.py)
├─ Call 1: Initial LLM call (analyze query)
├─ Execute MCP Tools
│   ├─ get_visible_objects
│   ├─ get_object_position
│   └─ get_object_detail
└─ Call 2: Final LLM call (generate response)
    ↓
Azure OpenAI API (GPT-4o)
    ↓
Response JSON
    ↓
Frontend Display
```

### File Structure

```
Backend/
├── main.py                  ← FastAPI REST API + endpoints
├── mcp_client.py            ← LLM-MCP orchestration (2 functions)
├── test.py                  ← Quick Azure OpenAI connection test
├── test1.py                 ← MCP HTTP tool calling test
├── test2.py                 ← Azure OpenAI chat test
├── test3.py                 ← Full integration test suite
├── .env                     ← Your credentials (KEEP SECRET!)
├── .env.example             ← Configuration template
├── pyproject.toml           ← Dependencies and Python config
├── object_names.json        ← Celestial object database
├── star_info.json           ← Star information reference
└── README.md                ← This file
```

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- `uv` package manager
- Azure OpenAI account with GPT-4o deployment
- Internet connection (for FastMCP server)

### Step 1: Install Dependencies

```bash
cd Backend
uv sync
```

This installs:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `langchain` - LLM orchestration
- `langchain-openai` - Azure OpenAI integration
- `langchain-mcp-adapters` - MCP tool support
- `python-dotenv` - Environment variable management
- Other dependencies

### Step 2: Get Azure OpenAI Credentials

1. Go to Azure Portal: https://portal.azure.com
2. Find your OpenAI instance
3. Copy:
   - **Endpoint:** (WITHOUT `/openai/v1` suffix) - e.g., `https://ujwalopenaiinstance.openai.azure.com`
   - **API Key:** From Access Keys section
   - **Deployment Name:** Usually `gpt-4o`

### Step 3: Configure Environment

Create `.env` file:
```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_API_KEY=your-actual-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
STARGUIDE_API_KEY=any-key-you-want
```

### Step 4: Verify Setup

```bash
# Test LLM connection
uv run python test.py

# Should output:
# ✓ Setup complete and working
```

---

## How It Works

### Function 1: `initial_stargazing_session()`

**Purpose:** Generate introduction to tonight's sky with storytelling

**Flow:**
1. Fetch all visible objects from MCP tool (typically 20-40 objects)
2. Send top 10 to LLM with storytelling system prompt
3. LLM generates 2-sentence intro + 5-7 sentence narrative per object
4. Return JSON with intro + 10 objects

**Characteristics:**
- ✅ Single LLM call
- ✅ Poetic, narrative-focused responses
- ✅ 10 brightest/most interesting objects
- ✅ Fast response time (3-8 seconds)

### Function 2: `chat_with_starguide()`

**Purpose:** Answer specific astronomy questions using smart tool selection

**Flow:**
1. Build message history with previous context
2. **First LLM call:** Analyze query and decide which tools to use
3. Execute selected tools (get_visible_objects, get_object_position, get_object_detail)
4. **Second LLM call:** Generate final answer using tool results
5. Return response

**Characteristics:**
- ✅ Two LLM calls (better decisions + natural responses)
- ✅ Supports chat history for context
- ✅ Smart tool selection (calls 0-3 tools as needed)
- ✅ Conversational, informative tone
- ✅ Medium response time (4-10 seconds)

### Example: "Is Jupiter visible and where is it?"

```
Query: "Is Jupiter visible and where is it exactly?"

[1] First LLM Call
    LLM: "User wants visibility + position info. I'll use:
          - get_visible_objects (to check if visible)
          - get_object_position (for exact coordinates)"

[2] Tool Execution
    get_visible_objects → Returns 31 objects including Jupiter
    get_object_position(Jupiter) → Returns alt: 54.92°, az: 282.26°

[3] Second LLM Call
    LLM: "Craft friendly response about Jupiter with real data..."
    
Response: "Yes, Jupiter is absolutely visible tonight at an altitude 
           of 54.9° in the west-southwest (azimuth 282°)..."
```

---

## Request/Response Examples

### Example 1: Initial Session (Simple)

**Request:**
```bash
curl -X POST http://localhost:8000/initial \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 19.274,
    "longitude": 72.881,
    "altitude": 0,
    "time": "2026-04-20T20:30:00+05:30"
  }'
```

**Response (shortened):**
```json
{
  "success": true,
  "intro": "Tonight's sky unfurls a tapestry of luminous treasures...",
  "objects": [
    {
      "name": "Venus",
      "magnitude": "-4.0",
      "altitude": "3.37°",
      "azimuth": "289.59°",
      "info": "Venus, the radiant evening star, glimmers low on the horizon like a jewel spilled from the heavens..."
    }
  ],
  "total_objects_available": 31,
  "objects_returned": 10
}
```

### Example 2: Chat with History

**Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How far is Jupiter from Earth right now?",
    "latitude": 19.274,
    "longitude": 72.881,
    "altitude": 0,
    "time": "2026-04-20T20:30:00+05:30",
    "chat_history": [
      {
        "role": "user",
        "content": "What planets are visible?"
      },
      {
        "role": "assistant",
        "content": "Venus, Jupiter, and Mars are all visible tonight from your location."
      }
    ]
  }'
```

**Response:**
```json
{
  "success": true,
  "query": "How far is Jupiter from Earth right now?",
  "response": "Jupiter is currently approximately 715 million kilometers away from Earth...",
  "tools_called": 0,
  "observation_time": "2026-04-20T20:30:00+05:30"
}
```

---

## Configuration

### Environment Variables

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `AZURE_OPENAI_ENDPOINT` | Yes | API endpoint | `https://ujwalopenaiinstance.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | Yes | Authentication | `FBedPoRqC4Ln...` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Yes | Model deployment | `gpt-4o` |
| `STARGUIDE_API_KEY` | No | API key for frontend | Any string |

**Important:** Endpoint must NOT include `/openai/v1` suffix

### Location Format

All endpoints expect ISO 8601 format time strings:
```
2026-04-20T20:30:00+05:30  ✅ Correct
2026-04-20 20:30:00        ❌ Wrong (no timezone)
20/04/2026 8:30 PM         ❌ Wrong (not ISO)
```

---

## Running the Server

### Development Mode

```bash
uv run python main.py
```

- Server: http://localhost:8000
- Logs: Printed to console
- Auto-reload: Disabled
- Workers: 1

### Production Mode

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

- Accessible from all network interfaces
- Multiple worker processes
- Production-ready logging

### Access API Documentation

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

Both auto-generated from code with full descriptions and Try-It-Out feature.

---

## MCP Tools

Three tools available via remote FastMCP server:

### 1. `get_visible_objects`

Get all celestial objects visible from location/time

**Parameters:**
- `lat` (float) - Latitude in degrees
- `lon` (float) - Longitude in degrees
- `alti` (float) - Altitude in km
- `time` (str) - ISO format time

**Returns:** Array of visible objects with magnitude, position, type

### 2. `get_object_position`

Get precise altitude/azimuth for specific object

**Parameters:**
- `object_name` (str) - Object name (e.g., "Mars", "Sirius")
- `lat`, `lon`, `alti`, `time` - Location/time

**Returns:** Altitude and azimuth in degrees

### 3. `get_object_detail`

Get comprehensive object information

**Parameters:**
- `object_name` (str) - Object name

**Returns:** Type, distance, constellation, description, mythology

---

## Debugging & Troubleshooting

### Check Server Status

```bash
curl http://localhost:8000/health
```

Should return: `{"status": "healthy", "version": "1.0.0", ...}`

### View Logs

Watch the terminal where `python main.py` is running. You'll see:
- Request timestamps and methods
- Function execution steps
- Tool calls and results
- Errors with full tracebacks

### Test Individual Components

```bash
# Test LLM only
uv run python test2.py

# Test MCP tools only  
uv run python test1.py

# Full integration test
uv run python test3.py
```

### Common Issues

#### "ModuleNotFoundError: No module named 'fastapi'"

```bash
uv sync
```

#### "Error: Could not initialize LLM"

Check `.env` file:
- ✓ Endpoint without `/openai/v1` suffix
- ✓ API key is valid and not expired
- ✓ Deployment name matches your Azure setup

```bash
# Verify manually
uv run python test.py
```

#### "MCP Client initialization failed"

- Internet connection working?
- FastMCP server reachable?
  ```bash
  curl https://mcp-project-stargazing.fastmcp.app/mcp
  ```

#### "Request times out"

Normal timing:
- First LLM call: 1-3 seconds
- Tool execution: 0.5-2 seconds  
- Second LLM call: 1-2 seconds
- **Total: 3-8 seconds**

If slower, check:
- Network latency
- Azure OpenAI API performance
- FastMCP server status

#### 404 Not Found

- Server running? Check terminal
- Correct URL? Use `http://localhost:8000`
- Correct method? POST for `/initial` and `/chat`

---

## Frontend Integration

### React Example

```javascript
async function askStarGuide(query, lat, lon, time) {
  const response = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      latitude: lat,
      longitude: lon,
      altitude: 0,
      time,
      chat_history: []  // Add previous messages here
    })
  });
  
  const data = await response.json();
  return data.response;
}
```

### JavaScript with Fetch

```javascript
// Initial stargazing session
fetch('http://localhost:8000/initial', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    latitude: 19.274,
    longitude: 72.881,
    altitude: 0,
    time: new Date().toISOString()
  })
})
.then(r => r.json())
.then(data => console.log(data.objects));
```

### Vue.js Example

```vue
<template>
  <div>
    <button @click="getStargazing">Tonight's Sky</button>
    <div v-for="obj in objects" :key="obj.name">
      <h3>{{ obj.name }}</h3>
      <p>{{ obj.info }}</p>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return { objects: [] };
  },
  methods: {
    async getStargazing() {
      const res = await fetch('http://localhost:8000/initial', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          latitude: 19.274,
          longitude: 72.881,
          altitude: 0,
          time: new Date().toISOString()
        })
      });
      const data = await res.json();
      this.objects = data.objects;
    }
  }
};
</script>
```

---

## Support

For issues or questions:
1. Check `.env` configuration
2. Run test suite: `uv run python test3.py`
3. Check server logs in terminal
4. Visit API docs: http://localhost:8000/docs

---

**Last Updated:** April 20, 2026
**Version:** 1.0.0
**Status:** Production Ready ✅
