"""
StarGuide Backend API

REST API for stargazing guidance using MCP tools and LLM.

Three main endpoints:
1. /health - Health check
2. /initial - Get initial stargazing session with top 10 visible objects
3. /chat - Chat with StarGuide about astronomy
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
import json

from mcp_client import initial_stargazing_session, chat_with_starguide_stream

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="StarGuide API",
    description="Personalized stargazing guidance powered by MCP and AI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class LocationRequest(BaseModel):
    """Base model for location-based requests."""
    latitude: float = Field(..., description="Observer latitude in degrees (-90 to 90)")
    longitude: float = Field(..., description="Observer longitude in degrees (-180 to 180)")
    time: str = Field(..., description="ISO 8601 format time (e.g., 2026-04-20T20:30:00+05:30)")
    altitude: Optional[float] = Field(0, description="Observer altitude in km (default: 0)")


class InitialSessionRequest(LocationRequest):
    """Request for initial stargazing session."""
    pass


class ChatMessage(BaseModel):
    """Single message in chat history."""
    role: str = Field(..., description="Either 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(LocationRequest):
    """Request for chatbot endpoint."""
    query: str = Field(..., description="User's astronomy question")
    chat_history: Optional[List[ChatMessage]] = Field(
        None,
        description="Previous conversation history for context"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(description="API status")
    version: str = Field(description="API version")
    message: str = Field(description="Status message")


class CelestialObject(BaseModel):
    """Information about a celestial object."""
    name: str = Field(description="Object name")
    magnitude: float = Field(description="Brightness magnitude")
    altitude: float = Field(description="Altitude in degrees")
    azimuth: float = Field(description="Azimuth in degrees")
    info: str = Field(description="Narrative information about the object")


class InitialSessionResponse(BaseModel):
    """Response from initial session endpoint."""
    success: bool = Field(description="Whether the request was successful")
    format: str = Field(description="Response format (json)")
    intro: str = Field(description="Introduction to tonight's sky")
    objects: List[CelestialObject] = Field(description="List of visible objects")
    total_objects_available: int = Field(description="Total visible objects from MCP")
    objects_returned: int = Field(description="Number of objects returned")
    location: dict = Field(description="Observer location")
    observation_time: str = Field(description="Observation time")


class ChatResponse(BaseModel):
    """Response from chatbot endpoint."""
    success: bool = Field(description="Whether the request was successful")
    query: str = Field(description="The user's question")
    response: str = Field(description="Assistant's response")
    tools_called: int = Field(description="Number of MCP tools called")
    location: dict = Field(description="Observer location")
    observation_time: str = Field(description="Observation time")


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        HealthResponse: API status and version information
    """
    logger.info("Health check called")
    return {
        "status": "healthy",
        "version": "1.0.0",
        "message": "StarGuide API is running"
    }


@app.post("/initial", tags=["Stargazing"])
async def get_initial_session(request: InitialSessionRequest):
    """
    Get initial stargazing session with streaming response.
    
    Streams intro first, then objects as they're processed.
    Allows frontend to display content as it arrives instead of waiting.
    """
    try:
        logger.info(f"Initial session requested: lat={request.latitude}, lon={request.longitude}, time={request.time}")
        
        result = await initial_stargazing_session(
            latitude=request.latitude,
            longitude=request.longitude,
            altitude=request.altitude,
            observation_time=request.time,
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get initial session: {result.get('error', 'Unknown error')}"
            )
        
        # Extract data from result
        data = result.get("data", {})
        
        async def stream_response():
            # Stream intro first
            intro_chunk = {
                "type": "intro",
                "content": data.get("intro", "")
            }
            yield json.dumps(intro_chunk) + "\n"
            
            # Then stream each object
            for obj in data.get("objects", []):
                obj_chunk = {
                    "type": "object",
                    "data": obj
                }
                yield json.dumps(obj_chunk) + "\n"
            
            # Finally stream metadata
            metadata_chunk = {
                "type": "complete",
                "total_objects_available": result.get("total_objects_available", 0),
                "objects_returned": result.get("objects_returned", 0),
                "location": result.get("location", {}),
                "observation_time": result.get("observation_time", "")
            }
            yield json.dumps(metadata_chunk) + "\n"
        
        return StreamingResponse(
            stream_response(),
            media_type="application/x-ndjson"
        )
        
    except Exception as e:
        logger.error(f"Error in initial session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/chat", tags=["Stargazing"])
async def chat_with_guide(request: ChatRequest):
    """
    Chat with StarGuide about astronomy with STREAMING response.
    
    Ask any astronomy question and get an intelligent response. The system will
    decide which MCP tools to use (visible objects, positions, details) to provide
    the most accurate and helpful answer. Supports conversation history for context.
    
    Two-step process:
    1. First LLM call (internal): Decides which tools to call - NO STREAMING
    2. Tools execution: Calls necessary MCP tools with results
    3. Second LLM call (user-facing): Generates final answer - STREAMED in real-time
    
    Args:
        request: User query, location, time, and optional chat history
    
    Returns:
        StreamingResponse: NDJSON format with streamed response chunks
        
    Raises:
        HTTPException: If the request fails
    """
    try:
        logger.info(f"Chat requested: query='{request.query[:50]}...', lat={request.latitude}, lon={request.longitude}")
        
        # Convert chat_history to list of dicts if provided
        chat_history = None
        if request.chat_history:
            chat_history = [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in request.chat_history
            ]
        
        async def stream_response():
            async for chunk in chat_with_starguide_stream(
                query=request.query,
                latitude=request.latitude,
                longitude=request.longitude,
                altitude=request.altitude,
                observation_time=request.time,
                chat_history=chat_history,
            ):
                yield json.dumps(chunk) + "\n"
        
        return StreamingResponse(
            stream_response(),
            media_type="application/x-ndjson"
        )
        
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API documentation link."""
    return {
        "message": "Welcome to StarGuide API",
        "documentation": "http://localhost:8000/docs",
        "endpoints": {
            "health": "/health",
            "initial_session": "/initial",
            "chat": "/chat",
            "demo": "/demo",
            "demo_initial": "/demo-initial",
            "demo_chat": "/demo-chat"
        }
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    logger.error(f"HTTP Exception: {exc.detail}")
    return {
        "error": True,
        "status_code": exc.status_code,
        "detail": exc.detail
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled Exception: {str(exc)}", exc_info=True)
    return {
        "error": True,
        "status_code": 500,
        "detail": "Internal server error"
    }


# ============================================================================
# STARTUP/SHUTDOWN EVENTS
# ============================================================================

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async context manager for app lifecycle events."""
    # Startup
    logger.info("StarGuide API starting up...")
    yield
    # Shutdown
    logger.info("StarGuide API shutting down...")

app.router.lifespan_context = lifespan


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting StarGuide Backend API...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )