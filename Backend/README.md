# StarGuide Backend

StarGuide Backend is a FastAPI service for location-aware stargazing guidance.
It combines Azure OpenAI with remote MCP astronomy tools and streams responses to the frontend using NDJSON.

## Live Deployment

This backend is deployed on Render.

- Live API base URL: https://mcp-project-stargazing-ai-guide.onrender.com
- Swagger UI: https://mcp-project-stargazing-ai-guide.onrender.com/docs
- ReDoc: https://mcp-project-stargazing-ai-guide.onrender.com/redoc
- Health endpoint: https://mcp-project-stargazing-ai-guide.onrender.com/health

Use the base URL in frontend API config, not the docs URL.

## Table of Contents

1. Overview
2. Current Architecture
3. Full Request Flow
4. API Endpoints
5. Streaming Format (NDJSON)
6. Local Setup and Starter Guide
7. Environment Variables
8. Testing
9. Deployment Notes (Render)
10. Troubleshooting

## Overview

This backend is designed for two user experiences:

- Initial sky session: a warm, streamed introduction for the current sky.
- Interactive chat: short, accurate answers with optional live tool calls when needed.

Core goals:

- Use live location/time astronomy data only when required.
- Keep responses concise and user-focused.
- Stream responses so UI feels real-time and responsive.

## Current Architecture

High-level components:

- FastAPI app in main.py
- LLM and MCP orchestration in mcp_client.py
- Azure OpenAI via langchain-openai
- Remote MCP tool server for astronomy data

MCP endpoint used by backend:

- https://MCP-Project-Stargazing.fastmcp.app/mcp

Available MCP tools:

- visible_objects
- object_position
- object_detail
- health_check
- weather_forecast (lat, lon)



## Full Request Flow

### 1) Initial Session Flow (POST /initial)

Current behavior is streaming-first.

1. Frontend sends latitude, longitude, altitude, and time.
2. Backend calls visible_objects from MCP.
3. Backend normalizes object records.
4. Backend selects top objects for initial experience.
5. LLM generates a single paragraph (intro plus object descriptions) in streaming mode.
6. Backend streams text chunks as they arrive.
7. Backend emits a final complete chunk with metadata.

Important:

- This endpoint returns streaming NDJSON.
- Frontend should read chunks incrementally.

### 2) Chat Flow (POST /chat)

Chat uses a two-stage LLM design:

1. First LLM call is a planner.
   - Input includes current query, location/time context, and optional history.
   - Uses tool binding with tool_choice auto.
   - Decides whether to call tools and which minimal set is needed.

2. Tool execution stage.
   - Backend runs only requested MCP tools.
   - Collects tool results in text/json form for response synthesis.

3. Second LLM call is response generation.
   - Uses tool results as primary truth when present.
   - Streams user-facing answer chunks to frontend.

Behavioral guardrails in planner prompt:

- Current user query is primary intent source.
- Chat history is secondary unless current query clearly depends on it.
- Greetings or unrelated messages should not trigger tool calls.
- Query should not continue old tool tasks unless user explicitly asks.

## API Endpoints

### GET /health

Purpose:

- Service liveness and version check.

Typical response:

{
  "status": "healthy",
  "version": "1.0.0",
  "message": "StarGuide API is running"
}

### POST /initial

Purpose:

- Start stargazing session with streamed paragraph output.

Request body:

{
  "latitude": 19.274,
  "longitude": 72.881,
  "altitude": 0,
  "time": "2026-04-21T20:30:00+05:30"
}

Response type:

- StreamingResponse
- content-type: application/x-ndjson

### POST /chat

Purpose:

- Conversational Q and A with smart tool usage.

Request body:

{
  "query": "Where is Jupiter right now?",
  "latitude": 19.274,
  "longitude": 72.881,
  "altitude": 0,
  "time": "2026-04-21T20:30:00+05:30",
  "chat_history": [
    { "role": "user", "content": "Can I see Mars tonight?" },
    { "role": "assistant", "content": "Yes, Mars is visible from your location." }
  ]
}

Response type:

- StreamingResponse
- content-type: application/x-ndjson

## Streaming Format (NDJSON)

Each line is one JSON object.

### /initial chunk types

- intro
  - content: streamed text piece
- complete
  - totals and request metadata
- error
  - error message

Example lines:

{"type":"intro","content":"Tonight the sky opens with..."}
{"type":"intro","content":"1) Moon appears bright..."}
{"type":"complete","objects_returned":10,"total_objects_available":31}

### /chat chunk types

- metadata
  - query, requested tools, location, mode
- direct_response
  - used when planner selects no tools
- response
  - streamed answer piece from second LLM call
- complete
  - success and mode
- error
  - error details

Mode behavior:

- direct mode: no tool calls; first-call answer is returned.
- stream mode: tools used and second-call answer streamed.

## Local Setup and Starter Guide

### Prerequisites

- Python 3.10+
- uv package manager
- Azure OpenAI deployment (example: gpt-4o)
- Network access to remote MCP server

### Step 1: Install dependencies

cd Backend
uv sync

### Step 2: Configure environment file

Create Backend/.env with:

AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
STARGUIDE_API_KEY=your-mcp-key

### Step 3: Start backend

uv run python main.py

Default local URLs:

- http://localhost:8000
- http://localhost:8000/docs
- http://localhost:8000/health

## Environment Variables

Required:

- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_API_KEY
- AZURE_OPENAI_DEPLOYMENT_NAME
- STARGUIDE_API_KEY

Notes:

- Endpoint cleanup is handled in code if accidental /openai/v1 suffix exists.
- Keep secrets in environment variables, never commit .env.

## Testing

From Backend folder:

- uv run python test.py
- uv run python test1.py
- uv run python test2.py
- uv run python test3.py

Suggested order:

1. test.py for basic model connectivity
2. test1.py for MCP tool connectivity
3. test2.py for streaming model behavior
4. test3.py for end-to-end integration checks

## Deployment Notes (Render)

The backend is live on Render at:

- https://mcp-project-stargazing-ai-guide.onrender.com

Recommended Render configuration:

- Runtime: Python
- Start command: uv run python main.py or uv run uvicorn main:app --host 0.0.0.0 --port 10000
- Environment variables: same as local .env keys
- Health check path: /health

For production hardening, consider:

- Restricting CORS origins
- Structured logging
- Request rate limiting
- Timeout and retry tuning for MCP calls

## Troubleshooting

### 1) Authentication failures

Symptoms:

- 401 from Azure or MCP calls

Checks:

- Verify AZURE_OPENAI_API_KEY
- Verify AZURE_OPENAI_DEPLOYMENT_NAME
- Verify STARGUIDE_API_KEY

### 2) Slow responses

Checks:

- Azure model latency
- MCP endpoint latency
- Network path between hosting region and MCP server

### 3) No chunks in frontend

Checks:

- Confirm frontend reads NDJSON streaming body
- Confirm response content-type is application/x-ndjson
- Confirm reverse proxy does not buffer streaming responses

### 4) Wrong tool calls on simple greetings

Checks:

- Confirm current planner prompt includes query-first intent rules
- Confirm current query is sent distinctly from history

## Frontend Integration Note

If frontend is in this project root, configure API endpoint as:

https://mcp-project-stargazing-ai-guide.onrender.com

Then call:

- /initial
- /chat

Do not point frontend requests to /docs.

## Version

- Service: StarGuide Backend
- Version: 1.0.0
- Last updated: 2026-04-21
