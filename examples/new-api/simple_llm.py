import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from fast_agent.agents.tool_agent_sync import ToolAgentSynchronous
from fast_agent.core import Core
from mcp_agent.core.agent_types import AgentConfig
from mcp_agent.llm.model_factory import ModelFactory

# Initialize FastMCP instance for decorator-based tools
# Set log_level to WARNING or ERROR to avoid httpx INFO logs
mcp = FastMCP("Weather Bot", log_level="WARNING")


# Option 1: Using @mcp.tool decorator
@mcp.tool()
async def check_weather(city: str) -> str:
    """Check the weather in a given city.

    Args:
        city: The city to check the weather for

    Returns:
        Weather information for the city
    """
    return f"The weather in {city} is sunny."


# Option 2: Simple function-based tool (without decorator)
async def check_weather_function(city: str) -> str:
    """Check the weather in a given city (function version).

    Args:
        city: The city to check the weather for

    Returns:
        Weather information for the city
    """
    return f"The weather in {city} is sunny."


# Alternative: Regular (non-async) function also works
def get_temperature(city: str) -> int:
    """Get the temperature in a city.

    Args:
        city: The city to get temperature for

    Returns:
        Temperature in degrees Celsius
    """
    # Mock implementation
    return 22


async def main():
    core: Core = Core()
    await core.initialize()

    # Create agent configuration
    config = AgentConfig(name="weather_bot", model="haiku")

    tool_agent = ToolAgentSynchronous(
        config,
        tools=[
            check_weather,  # Decorated with @mcp.tool()
            #            check_weather_function,  # Plain function (will be auto-converted)
            get_temperature,  # Regular sync function
        ],
        context=core.context,
    )

    # Attach the LLM
    await tool_agent.attach_llm(ModelFactory.create_factory("haiku"))

    # Test the agent
    await tool_agent.send("What's the weather like in San Francisco and what's the temperature?")


if __name__ == "__main__":
    asyncio.run(main())
