"""
LangChain + MCP Agent - Connect to multiple MCP servers with LLM intelligence
"""

from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import os
import json

# Load environment variables
load_dotenv()

# MCP Servers configuration
SERVERS = {
    "starguide": {
        "url": "https://MCP-Project-Stargazing.fastmcp.app/mcp",
        "token": os.getenv("STARGUIDE_API_KEY"),
        "description": "StarGuide MCP - Astronomy observation tools"
    }
}

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY")
)


async def setup_agent():
    """Setup the MCP agent with LLM."""
    
    # Initialize MCP client
    mcp_client = MultiServerMCPClient()
    
    # Connect to all servers
    for server_name, config in SERVERS.items():
        print(f"🔗 Connecting to {server_name}...")
        try:
            await mcp_client.add_server(
                name=server_name,
                url=config["url"],
                auth_token=config["token"]
            )
            print(f"   ✓ Connected!")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    # Get all tools from MCP servers
    tools = await mcp_client.get_tools()
    print(f"\n📦 Loaded {len(tools)} tools from MCP servers")
    for tool in tools:
        print(f"   - {tool.name}: {tool.description}")
    
    # Create agent prompt
    system_prompt = """You are an astronomy expert assistant powered by the StarGuide MCP system.
You have access to tools that can:
- Get visible celestial objects from a location
- Calculate positions of objects (alt/az)
- Get detailed information about celestial objects

Help users explore the night sky and understand celestial mechanics.
Use the available tools to answer questions and provide insights."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Create agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    return executor, mcp_client


async def main():
    """Main entry point."""
    print("\n" + "="*60)
    print("  StarGuide LangChain + MCP Agent")
    print("="*60)
    
    # Setup agent
    executor, mcp_client = await setup_agent()
    
    # Example queries
    queries = [
        "What celestial objects are visible from Mumbai (19.274°N, 72.881°E) on 2026-04-19 at 20:30 IST?",
        "Where is Mars in the sky right now from that location?",
        "Tell me about Sirius"
    ]
    
    for query in queries:
        print(f"\n{'='*60}")
        print(f"👤 Query: {query}")
        print(f"{'='*60}")
        
        try:
            result = await executor.ainvoke({
                "input": query,
                "chat_history": []
            })
            print(f"\n✓ Response: {result['output']}")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    await mcp_client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
