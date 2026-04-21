"""
Test Script for StarGuide MCP Client - WITH STREAMING

Tests two functions with updated streaming configuration:
1. initial_stargazing_session() - Initial message with storytelling (1 LLM call - STREAMING)
2. chat_with_starguide() - Chat with tool decision and response (1st: NO STREAMING, 2nd: STREAMING)

Run: uv run python test3.py
"""

import asyncio
from mcp_client import initial_stargazing_session, chat_with_starguide

# Example parameters
LATITUDE = 19.274        # Mumbai
LONGITUDE = 72.881       # Mumbai
ALTITUDE = -0.052        # ~52 meters
TIME = "2026-04-20T20:30:00+05:30"  # IST


async def test_function_1_initial_message():
    """Test Function 1: Initial stargazing session with STREAMING (JSON format)."""
    print("\n" + "="*80)
    print("TEST 1: Initial Stargazing Session (STREAMING JSON Format)")
    print("="*80)
    
    result = await initial_stargazing_session(
        latitude=LATITUDE,
        longitude=LONGITUDE,
        altitude=ALTITUDE,
        observation_time=TIME,
    )
    
    print("\n[RESULT]:")
    print(f"Success: {result['success']}")
    
    if result['success']:
        print(f"\n[RESPONSE - JSON Format (Above Shows STREAMING):]")
        response_data = result.get('data', {})
        print(f"\nIntro: {response_data.get('intro', 'N/A')}")
        print(f"\nObjects:")
        for obj in response_data.get('objects', []):
            print(f"\n  * {obj.get('name', 'Unknown')}")
            print(f"     Magnitude: {obj.get('magnitude', 'N/A')}")
            print(f"     Position: Alt {obj.get('altitude', 'N/A')}°, Az {obj.get('azimuth', 'N/A')}°")
            print(f"     Info: {obj.get('info', 'N/A')}")
        
        print(f"\n[INFO]:")
        print(f"  - Total objects available: {result['total_objects_available']}")
        print(f"  - Objects returned: {result['objects_returned']}")
        print(f"  - Location: {result['location']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    return result


async def test_function_2_complex_chat():
    """Test Function 2: Chat with complex query (Tool Decision - NO STREAMING + Multi-Info Request)."""
    print("\n" + "="*80)
    print("TEST 2: Complex Chat Query (Tool Decision + Multi-Info Request)")
    print("       → First LLM call (NO STREAMING - internal tool decision only)")
    print("       → Second LLM call STREAMING (final response with tool results)")
    print("="*80)
    
    complex_query = """I want to know:
1. What are the 10 brightest visible objects tonight?
2. Tell me detailed information about Sirius - its mythology, distance, and characteristics
3. Where exactly is Sirius in the sky? Give me the altitude and azimuth.

Please combine all this information in a comprehensive answer."""
    
    result = await chat_with_starguide(
        query=complex_query,
        latitude=LATITUDE,
        longitude=LONGITUDE,
        altitude=ALTITUDE,
        observation_time=TIME,
        chat_history=None,  # No chat history for initial query
    )
    
    print("\n[RESULT]:")
    print(f"Success: {result['success']}")
    
    if result['success']:
        print(f"\n[RESPONSE (Above Shows STREAMING):]")
        # Truncate long responses for display
        response_text = result['response']
        if len(response_text) > 500:
            print(f"{response_text[:500]}...")
            print(f"\n[... Response truncated, total length: {len(response_text)} chars ...]")
        else:
            try:
                print(f"{response_text}")
            except UnicodeEncodeError:
                print(f"{response_text.encode('utf-8', 'ignore').decode('utf-8')}")
        print(f"\n[INFO]:")
        print(f"  - Query: {result['query'][:100]}...")
        print(f"  - Tools called: {result['tools_called']}")
        print(f"  - Location: {result['location']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    return result


async def test_function_2_with_history():
    """Test Function 3: Chat with history (follow-up question - NO STREAMING on decision + STREAMING on answer)."""
    print("\n" + "="*80)
    print("TEST 3: Chat with History (Follow-up Question)")
    print("="*80)
    
    # Simulated chat history
    chat_history = [
        {
            "role": "user",
            "content": "What planets are visible tonight?"
        },
        {
            "role": "assistant",
            "content": "Venus is visible in the western sky at magnitude -4.0, and Mars appears in the southern region."
        }
    ]
    
    follow_up_query = "How far are these planets from Earth?"
    
    result = await chat_with_starguide(
        query=follow_up_query,
        latitude=LATITUDE,
        longitude=LONGITUDE,
        altitude=ALTITUDE,
        observation_time=TIME,
        chat_history=chat_history,
    )
    
    print("\n[RESULT]:")
    print(f"Success: {result['success']}")
    
    if result['success']:
        print(f"\n[RESPONSE (Above Shows STREAMING):]")
        # Truncate long responses for display
        response_text = result['response']
        if len(response_text) > 500:
            print(f"{response_text[:500]}...")
            print(f"\n[... Response truncated, total length: {len(response_text)} chars ...]")
        else:
            try:
                print(f"{response_text}")
            except UnicodeEncodeError:
                print(f"{response_text.encode('utf-8', 'ignore').decode('utf-8')}")
        print(f"\n[INFO]:")
        print(f"  - Query: {result['query']}")
        print(f"  - Tools called: {result['tools_called']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    return result


async def run_all_tests():
    """Run all tests with streaming."""
    print("\n" + "="*80)
    print("StarGuide MCP Client - Test Suite WITH STREAMING")
    print("="*80)
    print(f"Parameters:")
    print(f"  Latitude: {LATITUDE}")
    print(f"  Longitude: {LONGITUDE}")
    print(f"  Altitude: {ALTITUDE} km")
    print(f"  Time: {TIME}")
    print(f"\nStreaming Configuration:")
    print(f"  ✓ Test 1: Initial message (1 LLM call - STREAMING)")
    print(f"  ✓ Test 2: Complex chat (1st LLM call - NO STREAM, 2nd LLM call - STREAMING)")
    print(f"  ✓ Test 3: Chat with history (1st LLM call - NO STREAM, 2nd LLM call - STREAMING)")
    
    results = []
    
    # Test 1: Initial message
    print("\n[Starting Test 1...]")
    result1 = await test_function_1_initial_message()
    results.append(("Initial Message", result1))
    
    await asyncio.sleep(2)
    
    # Test 2: Complex chat
    print("\n[Starting Test 2...]")
    result2 = await test_function_2_complex_chat()
    results.append(("Complex Chat", result2))
    
    await asyncio.sleep(2)
    
    # Test 3: Chat with history
    print("\n[Starting Test 3...]")
    result3 = await test_function_2_with_history()
    results.append(("Chat with History", result3))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, r in results if r.get('success'))
    failed = sum(1 for _, r in results if not r.get('success'))
    
    for name, result in results:
        status = "[OK] PASSED" if result.get('success') else "[FAIL] FAILED"
        print(f"{status}: {name}")
        if not result.get('success'):
            print(f"  Error: {result.get('error', 'Unknown')}")
    
    print(f"\nTotal: {passed} passed, {failed} failed out of {len(results)} tests")
    print("="*80)
    print("\n✓ STREAMING SUMMARY:")
    print("  ✓ Test 1: Initial message JSON - STREAMED in real-time")
    print("  ✓ Test 2: Tool decision analysis - NO STREAMING (internal only)")
    print("  ✓ Test 2: Final response generation - STREAMED in real-time")
    print("  ✓ Test 3: Tool analysis - NO STREAMING (internal only)")
    print("  ✓ Test 3: Final response with history - STREAMED in real-time")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
