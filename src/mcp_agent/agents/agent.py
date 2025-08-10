"""
Agent implementation using the clean BaseAgent adapter.

This provides a streamlined implementation that adheres to AgentProtocol
while delegating LLM operations to an attached AugmentedLLMProtocol instance.
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar

from mcp_agent.agents.base_agent import BaseAgent
from mcp_agent.core.agent_types import AgentConfig
from mcp_agent.human_input.types import HumanInputCallback
from mcp_agent.logging.logger import get_logger
from mcp_agent.mcp.interfaces import AugmentedLLMProtocol

if TYPE_CHECKING:
    from mcp_agent.context import Context

logger = get_logger(__name__)

# Define a TypeVar for AugmentedLLM and its subclasses
LLM = TypeVar("LLM", bound=AugmentedLLMProtocol)


class Agent(BaseAgent):
    """
    An Agent is an entity that has access to a set of MCP servers and can interact with them.
    Each agent should have a purpose defined by its instruction.

    This implementation provides a clean adapter that adheres to AgentProtocol
    while delegating LLM operations to an attached AugmentedLLMProtocol instance.
    """

    def __init__(
        self,
        config: AgentConfig,  # Can be AgentConfig or backward compatible str name
        functions: Optional[List[Callable]] = None,
        connection_persistence: bool = True,
        human_input_callback: Optional[HumanInputCallback] = None,
        context: Optional["Context"] = None,
        **kwargs: Dict[str, Any],
    ) -> None:
        # Initialize with BaseAgent constructor
        super().__init__(
            config=config,
            functions=functions,
            connection_persistence=connection_persistence,
            human_input_callback=human_input_callback,
            context=context,
            **kwargs,
        )
