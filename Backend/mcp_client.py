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
from typing import Optional, AsyncIterator
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.callbacks import StreamingStdOutCallbackHandler

# Load environment variables
load_dotenv()

# MCP Server config
MCP_SERVER_URL = "https://MCP-Project-Stargazing.fastmcp.app/mcp"
API_KEY = os.getenv("STARGUIDE_API_KEY")


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
        callbacks=[StreamingStdOutCallbackHandler()],
    )


def load_object_names() -> dict:
    """Load celestial object names from JSON."""
    try:
        with open("object_names.json", "r") as f:
            return json.load(f)
    except:
        print("[WARN] Could not load object_names.json")
        return {}


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
        visible_data = await call_mcp_tool(
            "visible_objects",
            lat=latitude,
            lon=longitude,
            time=observation_time,
            alti=altitude,
        )
        
        # Parse response using the new extraction function
        # visible_data should have a 'result' key from the MCP response
        if isinstance(visible_data, dict) and "result" in visible_data:
            objects = extract_visible_objects(visible_data["result"])
        else:
            objects = extract_visible_objects(visible_data)
        
        # Ensure objects is a list
        if isinstance(objects, dict):
            objects = list(objects.values()) if objects else []
        elif not isinstance(objects, list):
            objects = [objects] if objects else []
        
        total_objects = len(objects)
        print(f"[OK] Got {total_objects} total visible objects (actually retrieved from MCP)")
        
        # For initial message: use top 10 if available, otherwise all
        objects_to_send = objects[:10] if total_objects >= 10 else objects
        print(f"[OK] Sending {len(objects_to_send)} objects to LLM (top 10 or all if less than 10)")
        
        # Step 2: Single LLM call to extract object details
        print("\n[2/2] Extracting object information with STREAMING...")
        
        llm = get_streaming_llm()
        
        system_prompt = """You are a poetic stargazing storyteller. Your task is to create engaging narratives about visible celestial objects.

For the intro (1-2 sentences): Paint a vivid picture of tonight's sky that draws the reader in.

For each object (EXACTLY 2-3 sentences ONLY): 
- Be concise and impactful
- Include one key fact (mythology, distance, or significance)
- Make it poetic but brief
- NO lengthy descriptions

Return ONLY valid JSON:
{
    "intro": "2 sentence vivid opening about tonight's sky",
    "objects": [
        {
            "name": "Object Name",
            "magnitude": "value",
            "altitude": "degrees",
            "azimuth": "degrees",
            "info": "5-7 sentence storytelling narrative about this object"
        }
    ]
}"""

        objects_text = json.dumps(objects_to_send, indent=2)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""Extract information about these {len(objects_to_send)} visible objects at {latitude}°, {longitude}° on {observation_time}:

{objects_text}

Return ONLY valid JSON, no other text. Generate info for ALL {len(objects_to_send)} objects.""")
        ]
        
        print("\n" + "-"*70)
        response = llm.invoke(messages)
        print("\n" + "-"*70)
        
        response_text = response.content
        try:
            # Clean response - remove markdown code blocks if present
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            
            response_json = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            response_json = {
                "intro": f"Tonight at {latitude}°, {longitude}°, {len(objects)} celestial objects are visible.",
                "objects": []
            }
        
        print("[OK] Object information extracted")
        
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
        
        first_system_prompt = """You are an expert stargazing assistant. Your task is to ALWAYS use MCP tools to get fresh, location-specific data.

CRITICAL RULES:
1. NEVER reuse or mention data from the initial "top visible objects" introduction
2. ALWAYS call tools for ANY query about tonight's sky, object positions, or celestial information
3. ALWAYS provide fresh data - do NOT use general/training data

Available Tools (USE THEM!):
1. **visible_objects**: Use for "what can I see", "what's visible tonight", "brightest objects", "anything interesting"
2. **object_position**: Use for "where is [object]", "find [object]", "show me [object]", location/direction queries
3. **object_detail**: Use for "tell me about [object]", "info on [object]", "facts about [object]"

MANDATORY Tool Usage Rules:
- "What can I see?" / "What's visible?" / "What's up tonight?" → MUST call visible_objects
- "Where is [object]?" / "Show me [object]" / "Can I see [object]?" → MUST call object_position
- "Tell me about [object]" / "What is [object]?" / "Info about [object]?" → MUST call object_detail
- User mentions a specific object → MUST call relevant tool, NEVER use general knowledge
- User asks about tonight's sky → MUST call visible_objects, NEVER reuse intro data
- ANY question about positions/visibility/details → MUST call tools

If user asks multiple questions → Call ALL relevant tools

DO NOT:
✗ Reuse "tonight's top visible objects" from the intro
✗ Use training data instead of tool results
✗ Avoid tool calls - ALWAYS call them
✗ Mix old intro data with fresh tool results"""

        first_messages = [
            SystemMessage(content=first_system_prompt),
            *messages,
            HumanMessage(content=f"{query}\n\n{location_context}")
        ]
        
        # NO STREAMING for first call
        # Reason: First LLM call can do TWO things:
        #   1. Direct answer (should be shown to user) - but we don't know if this happens
        #   2. Tool call instructions (internal only, shouldn't be shown to user)
        # Since we can't differentiate, we don't stream. Second LLM call will stream the final answer.
        llm = get_llm()
        first_response = llm.invoke(first_messages)
        
        # ====================================================================
        # TOOL EXECUTION
        # ====================================================================
        tool_results = ""
        tools_called = 0
        
        # Parse tool calls from LLM response if any
        # For now, we'll check the text response for tool suggestions
        response_text = first_response.content
        
        # Look for tool mentions in response
        tool_keywords = {
            "visible_objects": "visible",
            "object_position": "position|altitude|azimuth",
            "object_detail": "detail|information|about"
        }
        
        tools_to_call = []
        query_lower = query.lower()
        
        # Comprehensive keyword detection for visible_objects
        visible_keywords = ["visible", "see tonight", "what can i see", "what's visible", "what's up", 
                           "look at tonight", "tonight", "can i see", "anything to see", "objects tonight",
                           "what's out tonight", "any objects", "brightest", "observable", "tonight's sky"]
        
        if any(keyword in query_lower for keyword in visible_keywords):
            tools_to_call.append("visible_objects")
        
        # Comprehensive keyword detection for object_position
        position_keywords = ["position", "altitude", "azimuth", "where", "locate", "show me", 
                            "find", "can i see", "direction", "pointing", "how high", "northeast"]
        
        if any(keyword in query_lower for keyword in position_keywords):
            # Extract object name from query
            for obj_name in object_names.keys():
                if obj_name.lower() in query_lower:
                    tools_to_call.append(("object_position", obj_name))
                    break
        
        # Comprehensive keyword detection for object_detail
        detail_keywords = ["tell me about", "info", "detail", "facts", "information", "explain",
                          "describe", "what is", "about", "distance", "size", "composition",
                          "brightness", "magnitude", "star", "planet", "constellation"]
        
        if any(keyword in query_lower for keyword in detail_keywords):
            for obj_name in object_names.keys():
                if obj_name.lower() in query_lower:
                    tools_to_call.append(("object_detail", obj_name))
                    break
        
        # If still no tools detected but user asked a question about the sky → call visible_objects
        if not tools_to_call and ("?" in query or "can" in query_lower or "show" in query_lower):
            tools_to_call.append("visible_objects")
        
        if tools_to_call:
            print(f"\n[3/4] Executing {len(tools_to_call)} tool(s)...")
            
            for tool_call in tools_to_call:
                if isinstance(tool_call, tuple):
                    tool_name, obj_name = tool_call
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
                    print(f"  -> Calling: {tool_call}")
                    
                    try:
                        result = await call_mcp_tool(
                            tool_call,
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
                        
                        tool_results += f"\n{tool_call}:\n{json.dumps(items_to_include, indent=2)}\n"
                        print(f"    [OK] Success")
                        tools_called += 1
                    except Exception as e:
                        print(f"    [FAIL] {e}")
                        tool_results += f"\n{tool_call} Error: {str(e)}\n"
        else:
            print("\n[3/4] No tools needed - LLM will provide direct answer")
        
        # ====================================================================
        # SECOND LLM CALL: Generate final response
        # ====================================================================
        print("\n[4/4] Second LLM call - Generating final response...")
        
        second_system_prompt = """You are an expert stargazing guide having a natural conversation with someone interested in the night sky.

CRITICAL RULES:
1. ALWAYS use the tool results provided - they contain the latest, location-specific data
2. NEVER reuse or reference the "top visible objects" from the initial intro
3. Base your answer ONLY on the tool results, NOT on general knowledge
4. If tool results exist, weave them naturally - do NOT ignore them
5. Present data as fresh observations for tonight, not generic information

Response Style:
✓ Conversational and warm, like talking to a friend
✓ Accurate with the tool data provided (this is the authoritative source)
✓ Concise but complete (2-4 paragraphs maximum)
✓ Natural flow without unnecessary formatting
✓ Use specific numbers/positions from tool data
✓ Grounded in tonight's actual sky, not general astronomy

If tools provided data → Use ONLY that data in your response
If no tools were called → This shouldn't happen - tools are mandatory!"""

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
            SystemMessage(content=second_system_prompt),
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

        first_system_prompt = """You are an expert stargazing assistant. Your task is to ALWAYS use MCP tools to get fresh, location-specific data.

CRITICAL RULES:
1. NEVER reuse or mention data from the initial "top visible objects" introduction
2. ALWAYS call tools for ANY query about tonight's sky, object positions, or celestial information
3. ALWAYS provide fresh data - do NOT use general/training data

Available Tools (USE THEM!):
1. **visible_objects**: Use for "what can I see", "what's visible tonight", "brightest objects", "anything interesting"
2. **object_position**: Use for "where is [object]", "find [object]", "show me [object]", location/direction queries
3. **object_detail**: Use for "tell me about [object]", "info on [object]", "facts about [object]"

MANDATORY Tool Usage Rules:
- "What can I see?" / "What's visible?" / "What's up tonight?" -> MUST call visible_objects
- "Where is [object]?" / "Show me [object]" / "Can I see [object]?" -> MUST call object_position
- "Tell me about [object]" / "What is [object]?" / "Info about [object]?" -> MUST call object_detail
- User mentions a specific object -> MUST call relevant tool, NEVER use general knowledge
- User asks about tonight's sky -> MUST call visible_objects, NEVER reuse intro data
- ANY question about positions/visibility/details -> MUST call tools

If user asks multiple questions -> Call ALL relevant tools

DO NOT:
✗ Reuse "tonight's top visible objects" from the intro
✗ Use training data instead of tool results
✗ Avoid tool calls - ALWAYS call them
✗ Mix old intro data with fresh tool results"""

        first_messages = [
            SystemMessage(content=first_system_prompt),
            *messages,
            HumanMessage(content=f"{query}\n\n{location_context}"),
        ]

        first_llm = get_llm()
        first_response = first_llm.invoke(first_messages)

        tool_results = ""
        tools_called = 0
        tools_to_call = []
        query_lower = query.lower()

        visible_keywords = [
            "visible", "see tonight", "what can i see", "what's visible", "what's up",
            "look at tonight", "tonight", "can i see", "anything to see", "objects tonight",
            "what's out tonight", "any objects", "brightest", "observable", "tonight's sky",
        ]
        if any(keyword in query_lower for keyword in visible_keywords):
            tools_to_call.append("visible_objects")

        position_keywords = [
            "position", "altitude", "azimuth", "where", "locate", "show me",
            "find", "can i see", "direction", "pointing", "how high", "northeast",
        ]
        if any(keyword in query_lower for keyword in position_keywords):
            for obj_name in object_names.keys():
                if obj_name.lower() in query_lower:
                    tools_to_call.append(("object_position", obj_name))
                    break

        detail_keywords = [
            "tell me about", "info", "detail", "facts", "information", "explain",
            "describe", "what is", "about", "distance", "size", "composition",
            "brightness", "magnitude", "star", "planet", "constellation",
        ]
        if any(keyword in query_lower for keyword in detail_keywords):
            for obj_name in object_names.keys():
                if obj_name.lower() in query_lower:
                    tools_to_call.append(("object_detail", obj_name))
                    break

        if not tools_to_call and ("?" in query or "can" in query_lower or "show" in query_lower):
            tools_to_call.append("visible_objects")

        metadata_chunk = {
            "type": "metadata",
            "query": query,
            "tools_called": 0,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            },
            "observation_time": observation_time,
        }

        # If no tool required, treat first call answer as direct non-stream output.
        if not tools_to_call:
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
            if isinstance(tool_call, tuple):
                tool_name, obj_name = tool_call
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
                except Exception as e:
                    tool_results += f"\n{tool_name} Error: {str(e)}\n"
            else:
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
                except Exception as e:
                    tool_results += f"\nvisible_objects Error: {str(e)}\n"

        metadata_chunk["tools_called"] = tools_called
        metadata_chunk["mode"] = "stream"
        yield metadata_chunk

        second_system_prompt = """You are an expert stargazing guide having a natural conversation with someone interested in the night sky.

CRITICAL RULES:
1. ALWAYS use the tool results provided - they contain the latest, location-specific data
2. NEVER reuse or reference the "top visible objects" from the initial intro
3. Base your answer ONLY on the tool results, NOT on general knowledge
4. If tool results exist, weave them naturally - do NOT ignore them
5. Present data as fresh observations for tonight, not generic information

Response Style:
✓ Conversational and warm, like talking to a friend
✓ Accurate with the tool data provided (this is the authoritative source)
✓ Concise but complete (2-4 paragraphs maximum)
✓ Natural flow without unnecessary formatting
✓ Use specific numbers/positions from tool data
✓ Grounded in tonight's actual sky, not general astronomy"""

        final_prompt = f"""User's Question: {query}

Location: {latitude}°, {longitude}° | Time: {observation_time}

Tool Results:
{tool_results}

Please answer their question naturally, using the tool results above."""

        second_messages = [
            SystemMessage(content=second_system_prompt),
            *messages,
            HumanMessage(content=final_prompt),
        ]

        streaming_llm_final = get_streaming_llm()
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

    except Exception as e:
        yield {
            "type": "error",
            "success": False,
            "error": str(e),
        }
