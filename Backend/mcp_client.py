"""
StarGuide MCP Client - Clean Architecture with Streaming

Two functions:
1. initial_stargazing_session() - Initial message with storytelling (1 LLM call)
2. chat_with_starguide() - Chat endpoint with tool decision (2 LLM calls)

Uses HTTP directly to call MCP tools (like test1.py)
Implements streaming for real-time response output
"""

import os
import json
import asyncio
import httpx
import logging
from typing import Optional, AsyncIterator
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool

# Load environment variables
load_dotenv()

# MCP Server config
MCP_SERVER_URL = "https://MCP-Project-Stargazing.fastmcp.app/mcp"
API_KEY = os.getenv("STARGUIDE_API_KEY")
BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


FIRST_SYSTEM_PROMPT = """You are StarGuide, an astronomy assistant.

IMPORTANT BEHAVIOR RULES:

- The CURRENT user query is the primary source of intent.
- Always decide tool usage based ONLY on the current query.
- Chat history is secondary context and should be ignored unless the current query clearly depends on it.

- If the current query is a greeting or unrelated (e.g., "hi", "hello"), DO NOT call any tools.
- Do NOT continue previous tool-related tasks unless the current query explicitly asks for continuation.

- Treat each query as independent unless it clearly references previous context (e.g., "and what about Jupiter?").

Your job is to decide whether the user's question requires live, location-based data.

Use tools ONLY when necessary.

Tool usage rules:
- Use a tool if the question depends on the user's current location or time (e.g., visibility, position, direction).
- Use a tool if the user asks about where something is in the sky right now.
- Use a tool if the user asks what is visible tonight.

Do NOT use tools when:
- The question is general knowledge (e.g., "What is Mars?")
- The answer does not depend on current sky conditions.

Available tools:
- visible_objects -> for what is visible tonight
- object_position -> for where an object is right now
- object_detail -> for factual information about an object

Rules:
- Call only the minimum necessary tool(s).
- Do not call multiple tools unless the question clearly requires it.
- If no tool is needed, answer directly.

Examples:

User: "altitude of Mars"
-> Call object_position

User: "hi"
-> Do NOT call any tool

User: "what about Jupiter?"
-> Use previous context and possibly call tool

User: "thanks"
-> Do NOT call any tool

Keep your reasoning internal and do not explain tool decisions.
"""


SECOND_SYSTEM_PROMPT = """You are StarGuide, a helpful stargazing assistant.

Answer the user's question clearly and directly.

Rules:
1. If tool results are provided, use them as the primary source of truth.
2. If no tool results are provided, answer from general astronomy knowledge.
3. Keep the answer short and focused (2-5 sentences).
4. Do not add unnecessary information.
5. Do not mention tools, internal reasoning, or steps.
6. If the user asks for a position, give the position first.

Style:
- Simple, natural, and conversational
- Clear and direct
- No formatting or lists unless necessary
"""


@tool
def visible_objects() -> str:
    """Use to get what celestial objects are visible tonight from the user's location/time."""
    return "visible_objects"


@tool
def object_position(object_name: str) -> str:
    """Use to get where a named object is in the sky right now from the user's location/time."""
    return object_name


@tool
def object_detail(object_name: str) -> str:
    """Use to get factual astronomy information about a named object."""
    return object_name


def parse_sse_response(text: str) -> dict:
    """Extract JSON from SSE response."""
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except:
                pass
    raise ValueError("No valid JSON in response")


def extract_visible_objects(result_data):
    """Extract visible objects from MCP response structure."""
    # Result can have multiple formats - check for common patterns
    
    # Pattern 1: Direct list/dict with objects
    if isinstance(result_data, list):
        # Check if it's a list of objects with 'name' field
        if result_data and isinstance(result_data[0], dict) and 'name' in result_data[0]:
            return result_data
        # Check if it's a list with text response containing JSON string
        if result_data and isinstance(result_data[0], dict) and 'type' in result_data[0] and 'text' in result_data[0]:
            try:
                json_text = result_data[0]['text']
                return json.loads(json_text)
            except:
                pass
    
    # Pattern 2: Dict with 'value' or 'content' key
    if isinstance(result_data, dict):
        if 'value' in result_data:
            return extract_visible_objects(result_data['value'])
        if 'content' in result_data:
            return extract_visible_objects(result_data['content'])
        # Check for text response with embedded JSON
        for key in result_data:
            if isinstance(result_data[key], dict) and 'text' in result_data[key]:
                try:
                    json_text = result_data[key]['text']
                    return json.loads(json_text)
                except:
                    pass
    
    # Fallback: return as-is
    return result_data


async def call_mcp_tool(tool_name: str, **kwargs) -> dict:
    """Call MCP tool via HTTP with extended timeout."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": kwargs
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    try:
        # Increased timeout to 180 seconds for slow responses
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(MCP_SERVER_URL, json=payload, headers=headers)
            response.raise_for_status()
            return parse_sse_response(response.text)
    except Exception as e:
        print(f"[FAIL] Tool call error: {e}")
        raise


def get_llm():
    """Initialize Azure OpenAI LLM."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    
    if endpoint and "/openai/v1" in endpoint:
        endpoint = endpoint.replace("/openai/v1", "")
    
    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version="2024-08-01-preview",
        temperature=0.7,
    )


def get_streaming_llm():
    """Initialize Azure OpenAI LLM with streaming enabled."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    
    if endpoint and "/openai/v1" in endpoint:
        endpoint = endpoint.replace("/openai/v1", "")
    
    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version="2024-08-01-preview",
        temperature=0.7,
        streaming=True,
    )


def load_object_names() -> dict:
    """Load celestial object names from JSON."""
    try:
        with open(BASE_DIR / "object_names.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        print("[WARN] Could not load object_names.json")
        return {}


def _format_metric(value, unit: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return f"{value:.1f}{unit}"
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized or normalized.lower() == "unknown":
            return None
        return normalized
    return None


def build_object_info(obj: dict) -> str:
    """Create a concise info line using MCP metrics and any extra text."""
    altitude = _format_metric(obj.get("altitude"), "°")
    azimuth = _format_metric(obj.get("azimuth"), "°")
    magnitude = _format_metric(obj.get("magnitude"), "")

    parts = []
    if altitude:
        parts.append(f"Altitude {altitude}")
    if azimuth:
        parts.append(f"Azimuth {azimuth}")
    if magnitude:
        parts.append(f"Magnitude {magnitude}")

    metrics_sentence = ", ".join(parts) + "." if parts else ""
    extra = obj.get("info") or obj.get("description") or obj.get("summary")

    if extra and metrics_sentence:
        return f"{metrics_sentence} {extra}"
    if extra:
        return extra
    if metrics_sentence:
        return metrics_sentence
    return "Visible tonight from your location."


def normalize_object_record(obj: dict) -> dict:
    """Normalize MCP object data for the frontend."""
    if not isinstance(obj, dict):
        return {
            "name": str(obj),
            "magnitude": "Unknown",
            "altitude": "Unknown",
            "azimuth": "Unknown",
            "info": "Visible tonight from your location.",
        }

    info_text = build_object_info(obj)

    return {
        "name": obj.get("name", "Unknown Object"),
        "magnitude": str(obj.get("magnitude", "Unknown")),
        "altitude": str(obj.get("altitude", "Unknown")),
        "azimuth": str(obj.get("azimuth", "Unknown")),
        "info": info_text,
    }


async def fetch_visible_objects(
    latitude: float,
    longitude: float,
    altitude: float,
    observation_time: str,
) -> tuple[list, int]:
    """Fetch and normalize visible objects from the MCP tool."""
    visible_data = await call_mcp_tool(
        "visible_objects",
        lat=latitude,
        lon=longitude,
        time=observation_time,
        alti=altitude,
    )

    if isinstance(visible_data, dict) and "result" in visible_data:
        objects = extract_visible_objects(visible_data["result"])
    else:
        objects = extract_visible_objects(visible_data)

    if isinstance(objects, dict):
        objects = list(objects.values()) if objects else []
    elif not isinstance(objects, list):
        objects = [objects] if objects else []

    normalized_objects = [normalize_object_record(obj) for obj in objects]
    return normalized_objects, len(normalized_objects)


# ============================================================================
# FUNCTION 1: Initial Stargazing Session (1 LLM Call - Storytelling)
# ============================================================================

async def initial_stargazing_session(
    latitude: float,
    longitude: float,
    altitude: float,
    observation_time: str,
) -> dict:
    """
    Initial stargazing session endpoint.
    
    Gets visible objects and returns JSON format with intro + object details.
    Frontend can parse this to bold object names and show info.
    
    Args:
        latitude: Observation latitude (degrees)
        longitude: Observation longitude (degrees)
        altitude: Observation altitude (km)
        observation_time: ISO format time
    
    Returns:
        dict with JSON-formatted response
    """
    
    print("\n" + "="*70)
    print("FUNCTION 1: Initial Stargazing Session")
    print("="*70)
    print(f"Location: {latitude}°, {longitude}°")
    print(f"Time: {observation_time}\n")
    
    try:
        # Step 1: Get visible objects
        print("[1/2] Fetching visible objects...")
        objects, total_objects = await fetch_visible_objects(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            observation_time=observation_time,
        )
        
        print(f"[OK] Got {total_objects} total visible objects (actually retrieved from MCP)")
        
        # For initial message: use top 10 if available, otherwise all
        objects_to_send = objects[:10] if total_objects >= 10 else objects
        print(f"[OK] Using {len(objects_to_send)} objects")

        # Step 2: Generate intro only (non-streaming)
        print("\n[2/2] Generating intro with LLM...")
        llm = get_llm()

        intro_prompt = """You are a poetic stargazing storyteller. Write a vivid 2-sentence opening about tonight's sky that draws the reader in. Be poetic but brief.

Output ONLY the 2 sentences. NO markdown, NO formatting, NO JSON."""

        messages = [
            SystemMessage(content=intro_prompt),
            HumanMessage(content=f"Location: {latitude}°, {longitude}° | Time: {observation_time}\n\nWrite a poetic intro for tonight's stargazing session with {len(objects_to_send)} visible objects."),
        ]

        intro = ""
        try:
            intro_response = llm.invoke(messages)
            intro = intro_response.content if hasattr(intro_response, "content") else ""
        except Exception as e:
            print(f"[WARN] Intro generation failed: {e}")

        if not intro.strip():
            intro = f"Tonight at {latitude}°, {longitude}°, the celestial stage awaits your gaze."

        response_json = {
            "intro": intro.strip(),
            "objects": objects_to_send,
        }

        print("[OK] Initial session prepared")

        return {
            "success": True,
            "format": "json",
            "data": response_json,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "observation_time": observation_time,
            "total_objects_available": total_objects,
            "objects_returned": len(objects_to_send),
        }
    
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "error": str(e),
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "observation_time": observation_time,
        }


async def initial_stargazing_session_stream(
    latitude: float,
    longitude: float,
    altitude: float,
    observation_time: str,
) -> AsyncIterator[dict]:
    """
    Stream initial stargazing session with real-time LLM streaming.
    
    Yields chunks as they're generated:
    - paragraph chunks as LLM generates (TRUE STREAMING, not buffered)
    - complete marker when done
    """
    try:
        # Step 1: Get visible objects (non-blocking, we need these anyway)
        print("[1/3] Fetching visible objects...")
        objects, total_objects = await fetch_visible_objects(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            observation_time=observation_time,
        )
        
        print(f"[OK] Got {total_objects} total visible objects")
        
        objects_to_send = objects[:10] if total_objects >= 10 else objects
        print(f"[OK] Using {len(objects_to_send)} objects")

        # Step 2: Stream intro + object descriptions from LLM in real-time (NO buffering)
        print("\n[2/2] Streaming intro + objects from LLM...")
        
        llm = get_streaming_llm()
        
        intro_prompt = """You are StarGuide, a stargazing assistant.

    Your task is to describe tonight's sky in a natural, flowing paragraph.

    Instructions:
    1. Start with a short, vivid 2-sentence introduction about the night sky at the given location and time.
    2. Then describe each visible object one by one, using numbering like "1)" "2)" in the same paragraph.
    3. For each object, write 1-2 short sentences in simple, natural language.
    4. Focus on what the object is and why it is interesting to observe.
    5. Do NOT include technical data like altitude, azimuth, magnitude, coordinates, or numbers.
    6. Do NOT use bullet points, headings, or new sections. Numbering is required and must stay inline in the paragraph.
    7. Do NOT output JSON or structured format.
    8. Everything must be in a single continuous paragraph.

    Style:
    - Warm, engaging, and conversational
    - Simple and easy to understand
    - Not too poetic, not too technical
    - Keep everything concise

    Important:
    - Use ONLY the provided object names.
    - Do not invent objects.
    - Do not skip objects.

    Output:
    - A single paragraph only.
    - No line breaks, no formatting, no lists (except inline numbering like "1)" "2)").
    """

        object_names = [obj.get("name", "Unknown Object") for obj in objects_to_send]
        messages = [
            SystemMessage(content=intro_prompt),
            HumanMessage(content=f"""Location: {latitude}°, {longitude}°
Time: {observation_time}

Visible objects:
{object_names}

Describe tonight's sky and these objects."""),
        ]
        
        print("-"*70)
        
        # Stream paragraph chunks directly - yield immediately as they arrive
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else ""
            if content:
                print(content, end="", flush=True)
                # Yield chunk immediately (TRUE STREAMING)
                yield {
                    "type": "intro",
                    "content": content,
                }
        
        print("\n" + "-"*70)
        
        # Completion marker
        yield {
            "type": "complete",
            "total_objects_available": total_objects,
            "objects_returned": len(objects_to_send),
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "observation_time": observation_time,
        }
        
        print(f"[OK] Stream complete - {len(objects_to_send)} objects described")
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        
        yield {
            "type": "error",
            "error": str(e),
        }


# ============================================================================
# FUNCTION 2: Chat with Starguide (2 LLM Calls - Tool Decision)
# ============================================================================

async def chat_with_starguide(
    query: str,
    latitude: float,
    longitude: float,
    altitude: float,
    observation_time: str,
    chat_history: Optional[list] = None,
) -> dict:
    """
    Chat endpoint with intelligent tool decision.
    
    Two LLM calls:
    1. First: Analyze query and decide if tools are needed
    2. Second: Generate final response using tool results
    
    Args:
        query: User's question
        latitude: Observation latitude
        longitude: Observation longitude
        altitude: Observation altitude (km)
        observation_time: ISO format time
        chat_history: Previous messages
    
    Returns:
        dict with response and metadata
    """
    
    print("\n" + "="*70)
    print("FUNCTION 2: Chat with StarGuide")
    print("="*70)
    print(f"Query: {query}")
    print(f"Location: {latitude}°, {longitude}°")
    print(f"Time: {observation_time}\n")
    
    try:
        llm = get_llm()
        object_names = load_object_names()
        
        # Build message history
        print("[1/4] Building message history...")
        messages = []
        
        if chat_history:
            for msg in chat_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))
            print(f"[OK] Added {len(chat_history)} previous messages")
        
        # Location context
        location_context = f"""Location: {latitude}°, {longitude}°, {altitude}m
Time: {observation_time}

Valid celestial object names (use these for tool calls):
{json.dumps(object_names, indent=2)}"""
        
        # ====================================================================
        # FIRST LLM CALL: Analyze and decide tools (internal only - NO STREAMING)
        # ====================================================================
        print("\n[2/4] First LLM call - Analyzing query and selecting tools (internal, no streaming)...")
        
        first_messages = [
            SystemMessage(content=FIRST_SYSTEM_PROMPT),
            *messages,
            HumanMessage(content=f"{query}\n\n{location_context}"),
        ]
        
        # NO STREAMING for first call
        # Reason: First LLM call can do TWO things:
        #   1. Direct answer (should be shown to user) - but we don't know if this happens
        #   2. Tool call instructions (internal only, shouldn't be shown to user)
        # Since we can't differentiate, we don't stream. Second LLM call will stream the final answer.
        planner_llm = get_llm().bind_tools([visible_objects, object_position, object_detail], tool_choice="auto")
        first_response = planner_llm.invoke(first_messages)
        
        # ====================================================================
        # TOOL EXECUTION
        # ====================================================================
        tool_results = ""
        tools_called = 0
        
        tools_to_call = first_response.tool_calls or []
        
        if tools_to_call:
            print(f"\n[3/4] Executing {len(tools_to_call)} tool(s)...")
            
            for tool_call in tools_to_call:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else {}
                obj_name = (tool_args or {}).get("object_name")

                if tool_name in ("object_position", "object_detail"):
                    if not obj_name:
                        print(f"  -> Skipping {tool_name}: missing object_name")
                        continue

                    print(f"  -> Calling: {tool_name}({obj_name})")
                    
                    try:
                        if tool_name == "object_position":
                            result = await call_mcp_tool(
                                tool_name,
                                object_name=obj_name,
                                lat=latitude,
                                lon=longitude,
                                time=observation_time,
                                alti=altitude,
                            )
                        elif tool_name == "object_detail":
                            result = await call_mcp_tool(
                                tool_name,
                                object_name=obj_name,
                            )
                        
                        tool_results += f"\n{tool_name} ({obj_name}):\n{json.dumps(result, indent=2)}\n"
                        print(f"    [OK] Success")
                        tools_called += 1
                    except Exception as e:
                        print(f"    [FAIL] {e}")
                        tool_results += f"\n{tool_name} Error: {str(e)}\n"
                
                else:
                    # visible_objects
                    if tool_name != "visible_objects":
                        print(f"  -> Skipping unknown tool: {tool_name}")
                        continue

                    print(f"  -> Calling: {tool_name}")
                    
                    try:
                        result = await call_mcp_tool(
                            tool_name,
                            lat=latitude,
                            lon=longitude,
                            time=observation_time,
                            alti=altitude,
                        )
                        
                        # Handle response using extraction function
                        if isinstance(result, dict) and "result" in result:
                            result_list = extract_visible_objects(result["result"])
                        else:
                            result_list = extract_visible_objects(result)
                        
                        # Ensure result_list is a list
                        if isinstance(result_list, dict):
                            result_list = list(result_list.values())
                        elif not isinstance(result_list, list):
                            result_list = [result_list] if result_list else []
                        
                        # IMPORTANT: For user queries, ALWAYS send ALL retrieved objects to 2nd LLM call
                        # (Only for initial message do we limit to top 10)
                        # This gives the LLM complete information about what's visible tonight
                        items_to_include = result_list
                        print(f"    [INFO] Sending ALL {len(result_list)} visible objects to 2nd LLM call for complete context")
                        
                        tool_results += f"\n{tool_name}:\n{json.dumps(items_to_include, indent=2)}\n"
                        print(f"    [OK] Success")
                        tools_called += 1
                    except Exception as e:
                        print(f"    [FAIL] {e}")
                        tool_results += f"\n{tool_name} Error: {str(e)}\n"
        else:
            print("\n[3/4] No tools needed - LLM will provide direct answer")
        
        # ====================================================================
        # SECOND LLM CALL: Generate final response
        # ====================================================================
        print("\n[4/4] Second LLM call - Generating final response...")
        
        if tool_results:
            final_prompt = f"""User's Question: {query}

Location: {latitude}°, {longitude}° | Time: {observation_time}

Tool Results:
{tool_results}

Please answer their question naturally, using the tool results above."""
        else:
            final_prompt = f"""User's Question: {query}

Location: {latitude}°, {longitude}° | Time: {observation_time}

Please share your expertise on this astronomical topic."""

        second_messages = [
            SystemMessage(content=SECOND_SYSTEM_PROMPT),
            *messages,
            HumanMessage(content=final_prompt),
        ]
        
        # Use streaming LLM for second call to stream the final response
        streaming_llm_final = get_streaming_llm()
        print("\n" + "="*70)
        print("FINAL RESPONSE (STREAMING):")
        print("="*70)
        final_response = streaming_llm_final.invoke(second_messages)
        print("\n" + "="*70)
        response_text = final_response.content
        
        print("\n" + "="*70)
        print("[OK] Chat processed successfully")
        print("="*70)
        
        return {
            "success": True,
            "query": query,
            "response": response_text,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "observation_time": observation_time,
            "tools_called": tools_called,
        }
    
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "query": query,
            "error": str(e),
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "observation_time": observation_time,
        }


async def chat_with_starguide_stream(
    query: str,
    latitude: float,
    longitude: float,
    altitude: float,
    observation_time: str,
    chat_history: Optional[list] = None,
) -> AsyncIterator[dict]:
    """
    Stream chat response chunks for frontend consumption.

    Emits NDJSON-friendly dict chunks:
    - metadata
    - direct_response + complete (if first LLM responds directly)
    - response chunks + complete (if second LLM is used)
    - error (on failure)
    """
    try:
        object_names = load_object_names()

        messages = []
        if chat_history:
            for msg in chat_history:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                else:
                    messages.append(AIMessage(content=msg.get("content", "")))

        location_context = f"""Location: {latitude}°, {longitude}°, {altitude}m
Time: {observation_time}

Valid celestial object names (use these for tool calls):
{json.dumps(object_names, indent=2)}"""

        first_messages = [
            SystemMessage(content=FIRST_SYSTEM_PROMPT),
            *messages,
            HumanMessage(content=f"{query}\n\n{location_context}"),
        ]

        planner_llm = get_llm().bind_tools([visible_objects, object_position, object_detail], tool_choice="auto")
        first_response = planner_llm.invoke(first_messages)

        tool_results = ""
        tools_called = 0
        tools_to_call = first_response.tool_calls or []

        logger.info(
            "Chat tool planner: tools_requested=%s",
            [
                tool_call.get("name") if isinstance(tool_call, dict) else str(tool_call)
                for tool_call in tools_to_call
            ],
        )

        metadata_chunk = {
            "type": "metadata",
            "query": query,
            "tools_called": 0,
            "tools_requested": [
                tool_call.get("name") if isinstance(tool_call, dict) else str(tool_call)
                for tool_call in tools_to_call
            ],
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "observation_time": observation_time,
        }

        # If no tool required, treat first call answer as direct non-stream output.
        if not tools_to_call:
            logger.info("Chat tool planner: no tool calls selected, using direct first-LLM response")
            metadata_chunk["mode"] = "direct"
            yield metadata_chunk
            yield {
                "type": "direct_response",
                "content": first_response.content or "No response",
            }
            yield {
                "type": "complete",
                "success": True,
                "mode": "direct",
            }
            return

        for tool_call in tools_to_call:
            tool_name = tool_call.get("name") if isinstance(tool_call, dict) else None
            tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else {}
            obj_name = (tool_args or {}).get("object_name")

            if tool_name in ("object_position", "object_detail"):
                if not obj_name:
                    logger.warning("Skipping %s due to missing object_name", tool_name)
                    continue

                logger.info("Executing MCP tool: %s object=%s", tool_name, obj_name)
                try:
                    if tool_name == "object_position":
                        result = await call_mcp_tool(
                            tool_name,
                            object_name=obj_name,
                            lat=latitude,
                            lon=longitude,
                            time=observation_time,
                            alti=altitude,
                        )
                    else:
                        result = await call_mcp_tool(
                            "object_detail",
                            object_name=obj_name,
                        )
                    tool_results += f"\n{tool_name} ({obj_name}):\n{json.dumps(result, indent=2)}\n"
                    tools_called += 1
                    logger.info("MCP tool success: %s object=%s", tool_name, obj_name)
                except Exception as e:
                    tool_results += f"\n{tool_name} Error: {str(e)}\n"
                    logger.exception("MCP tool failed: %s object=%s", tool_name, obj_name)
            elif tool_name == "visible_objects":
                logger.info("Executing MCP tool: %s", tool_call)
                try:
                    result = await call_mcp_tool(
                        "visible_objects",
                        lat=latitude,
                        lon=longitude,
                        time=observation_time,
                        alti=altitude,
                    )
                    if isinstance(result, dict) and "result" in result:
                        result_list = extract_visible_objects(result["result"])
                    else:
                        result_list = extract_visible_objects(result)

                    if isinstance(result_list, dict):
                        result_list = list(result_list.values())
                    elif not isinstance(result_list, list):
                        result_list = [result_list] if result_list else []

                    tool_results += f"\nvisible_objects:\n{json.dumps(result_list, indent=2)}\n"
                    tools_called += 1
                    logger.info("MCP tool success: visible_objects count=%s", len(result_list))
                except Exception as e:
                    tool_results += f"\nvisible_objects Error: {str(e)}\n"
                    logger.exception("MCP tool failed: visible_objects")
            else:
                logger.warning("Skipping unknown planner tool: %s", tool_name)

        metadata_chunk["tools_called"] = tools_called
        metadata_chunk["mode"] = "stream"
        logger.info("Chat tool execution complete: tools_called=%s", tools_called)
        yield metadata_chunk

        final_prompt = f"""User's Question: {query}

Location: {latitude}°, {longitude}° | Time: {observation_time}

Tool Results:
{tool_results}

Please answer their question naturally, using the tool results above."""

        second_messages = [
            SystemMessage(content=SECOND_SYSTEM_PROMPT),
            *messages,
            HumanMessage(content=final_prompt),
        ]

        streaming_llm_final = get_streaming_llm()
        logger.info("Starting streamed final response generation")
        async for chunk in streaming_llm_final.astream(second_messages):
            content_piece = chunk.content if hasattr(chunk, "content") else ""
            if content_piece:
                yield {
                    "type": "response",
                    "content": content_piece,
                }

        yield {
            "type": "complete",
            "success": True,
            "mode": "stream",
        }
        logger.info("Completed streamed final response generation")

    except Exception as e:
        logger.exception("Chat streaming failed")
        yield {
            "type": "error",
            "success": False,
            "error": str(e),
        }
