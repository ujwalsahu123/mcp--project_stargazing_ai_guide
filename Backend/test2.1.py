"""
Test script to verify Azure OpenAI LLM API is working with STREAMING
Uses LangChain to connect to Azure OpenAI
run -> uv run python test2.py
"""

import os
import sys
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.callbacks import StreamingStdOutCallbackHandler

# Load environment variables
load_dotenv()

# Get Azure OpenAI credentials from .env
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Fix endpoint format for Azure OpenAI (remove /openai/v1 if present)
if endpoint and "/openai/v1" in endpoint:
    endpoint = endpoint.replace("/openai/v1", "")

print("\n" + "="*60)
print("  Azure OpenAI LLM API Test")
print("="*60)

# Check if credentials are loaded
if not endpoint or not api_key or not deployment_name:
    print("\nERROR: Missing Azure OpenAI credentials in .env")
    print(f"  Endpoint: {endpoint}")
    print(f"  API Key: {'***' if api_key else 'MISSING'}")
    print(f"  Deployment: {deployment_name}")
    sys.exit(1)

print("\nConfiguration loaded:")
print(f"  Endpoint: {endpoint}")
print(f"  Deployment: {deployment_name}")
print(f"  API Key: {'***' + api_key[-10:] if api_key else 'MISSING'}")

# Initialize LangChain Azure Chat OpenAI with Streaming
print("\nInitializing LangChain AzureChatOpenAI with Streaming...")
try:
    llm = AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment_name,
        api_version="2024-08-01-preview",
        streaming=True,
        callbacks=[StreamingStdOutCallbackHandler()],
    )
    print("  Status: SUCCESS")
except Exception as e:
    print(f"  Status: FAILED - {e}")
    sys.exit(1)

# Test the connection with a comprehensive astronomical query
test_query = """
Explain the life cycle of a star in detail, covering the following aspects:
1. Formation and birth from a molecular cloud
2. Main sequence phase and how long it lasts for different star types
3. Red giant phase and what happens to its outer layers
4. End states: white dwarf, neutron star, or black hole formation
5. How can we observe these different stages in the night sky?

Provide specific examples of well-known stars in each stage and how this life cycle relates to stellar classification systems like the Hertzsprung-Russell diagram.
"""

print(f"\nSending comprehensive test query about stellar life cycles...")
print("=" * 60)
try:
    print("\nStreaming Response:")
    print("-" * 60)
    response = llm.invoke(test_query)
    print("\n" + "-" * 60)
    print(f"\nStatus: SUCCESS")
except Exception as e:
    print(f"  Status: FAILED - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("All tests passed!")
print("="*60 + "\n")
