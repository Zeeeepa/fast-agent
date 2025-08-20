"""
Base Decorator class that implements simple delegation to an AugmentedLLMProtocol.

This class provides a pure delegation wrapper around AugmentedLLMProtocol instances,
focusing only on core delegation functionality without LLM interaction behaviors.
"""

from typing import (
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from mcp import Tool
from mcp.types import (
    GetPromptResult,
    PromptMessage,
)
from opentelemetry import trace
from pydantic import BaseModel

from fast_agent.context import Context
from mcp_agent.core.agent_types import AgentConfig, AgentType
from mcp_agent.core.request_params import RequestParams
from mcp_agent.llm.provider_types import Provider
from mcp_agent.llm.usage_tracking import UsageAccumulator
from mcp_agent.logging.logger import get_logger
from mcp_agent.mcp.helpers.content_helpers import normalize_to_multipart_list
from mcp_agent.mcp.interfaces import AugmentedLLMProtocol, LlmAgentProtocol, LLMFactoryProtocol
from mcp_agent.mcp.prompt_message_multipart import PromptMessageMultipart

# Define a TypeVar for models
ModelT = TypeVar("ModelT", bound=BaseModel)

# Define a TypeVar for AugmentedLLM and its subclasses
LLM = TypeVar("LLM", bound=AugmentedLLMProtocol)


class LlmDecorator(LlmAgentProtocol):
    """
    A pure delegation wrapper around AugmentedLLMProtocol instances.

    This class provides simple delegation to an attached LLM without adding
    any LLM interaction behaviors. Subclasses can add specialized logic
    for stop reason handling, UI display, tool execution, etc.
    """

    def __init__(
        self,
        config: AgentConfig,
        context: Context | None = None,
    ) -> None:
        self.config = config

        self._context = context
        self._name = self.config.name
        self._tracer = trace.get_tracer(__name__)
        self.instruction = self.config.instruction
        self.logger = get_logger(f"{__name__}.{self._name}")

        # Store the default request params from config
        self._default_request_params = self.config.default_request_params

        # Initialize the LLM to None (will be set by attach_llm)
        self._llm: Optional[AugmentedLLMProtocol] = None

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    @property
    def agent_type(self) -> AgentType:
        """
        Return the type of this agent.
        """
        return AgentType.LLM

    @property
    def name(self) -> str:
        """
        Return the name of this agent.
        """
        return self._name

    async def attach_llm(
        self,
        llm_factory: LLMFactoryProtocol,
        model: str | None = None,
        request_params: RequestParams | None = None,
        **additional_kwargs,
    ) -> AugmentedLLMProtocol:
        """
        Create and attach an LLM instance to this agent.

        Parameters have the following precedence (highest to lowest):
        1. Explicitly passed parameters to this method
        2. Agent's default_request_params
        3. LLM's default values

        Args:
            llm_factory: A factory function that constructs an AugmentedLLM
            model: Optional model name override
            request_params: Optional request parameters override
            **additional_kwargs: Additional parameters passed to the LLM constructor

        Returns:
            The created LLM instance
        """
        # Merge parameters with proper precedence
        effective_params = self._merge_request_params(
            self._default_request_params, request_params, model
        )

        # Create the LLM instance
        self._llm = llm_factory(
            agent=self, request_params=effective_params, context=self._context, **additional_kwargs
        )

        return self._llm

    async def __call__(
        self,
        message: Union[str, PromptMessage, PromptMessageMultipart],
    ) -> str:
        """
        Make the agent callable to send messages.

        Args:
            message: Optional message to send to the agent

        Returns:
            The agent's response as a string
        """
        return await self.send(message)

    async def send(self, message: Union[str, PromptMessage, PromptMessageMultipart]) -> str:
        """
        Convenience method to generate and return a string directly
        """
        response = await self.generate(message)
        return response.last_text()

    async def generate(
        self,
        messages: Union[
            str,
            PromptMessage,
            PromptMessageMultipart,
            List[Union[str, PromptMessage, PromptMessageMultipart]],
        ],
        request_params: RequestParams | None = None,
        tools: List[Tool] | None = None,
    ) -> PromptMessageMultipart:
        """
        Create a completion with the LLM using the provided messages.

        This method provides the friendly agent interface by normalizing inputs
        and delegating to the LLM's internal interface.

        Args:
            messages: Message(s) in various formats:
                - String: Converted to a user PromptMessageMultipart
                - PromptMessage: Converted to PromptMessageMultipart
                - PromptMessageMultipart: Used directly
                - List of any combination of the above
            request_params: Optional parameters to configure the request

        Returns:
            The LLM's response as a PromptMessageMultipart
        """

        assert self._llm
        # Normalize all input types to a list of PromptMessageMultipart
        multipart_messages = normalize_to_multipart_list(messages)

        with self._tracer.start_as_current_span(f"Agent: '{self._name}' generate"):
            return await self._llm.generate(multipart_messages, request_params, tools)

    async def apply_prompt_template(self, prompt_result: GetPromptResult, prompt_name: str) -> str:
        """
        Apply a prompt template as persistent context that will be included in all future conversations.
        Delegates to the attached LLM.

        Args:
            prompt_result: The GetPromptResult containing prompt messages
            prompt_name: The name of the prompt being applied

        Returns:
            String representation of the assistant's response if generated
        """
        assert self._llm
        return await self._llm.apply_prompt_template(prompt_result, prompt_name)

    async def structured(
        self,
        messages: Union[
            str,
            PromptMessage,
            PromptMessageMultipart,
            List[Union[str, PromptMessage, PromptMessageMultipart]],
        ],
        model: Type[ModelT],
        request_params: RequestParams | None = None,
    ) -> Tuple[ModelT | None, PromptMessageMultipart]:
        """
        Apply the prompt and return the result as a Pydantic model.

        This method provides the friendly agent interface by normalizing inputs
        and delegating to the LLM's internal interface.

        Args:
            messages: Message(s) in various formats:
                - String: Converted to a user PromptMessageMultipart
                - PromptMessage: Converted to PromptMessageMultipart
                - PromptMessageMultipart: Used directly
                - List of any combination of the above
            model: The Pydantic model class to parse the result into
            request_params: Optional parameters to configure the LLM request

        Returns:
            An instance of the specified model, or None if coercion fails
        """
        assert self._llm
        # Normalize all input types to a list of PromptMessageMultipart
        multipart_messages = normalize_to_multipart_list(messages)

        with self._tracer.start_as_current_span(f"Agent: '{self._name}' structured"):
            return await self._llm.structured(multipart_messages, model, request_params)

    @property
    def message_history(self) -> List[PromptMessageMultipart]:
        """
        Return the agent's message history as PromptMessageMultipart objects.

        This history can be used to transfer state between agents or for
        analysis and debugging purposes.

        Returns:
            List of PromptMessageMultipart objects representing the conversation history
        """
        if self._llm:
            return self._llm.message_history
        return []

    @property
    def usage_accumulator(self) -> UsageAccumulator | None:
        """
        Return the usage accumulator for tracking token usage across turns.

        Returns:
            UsageAccumulator object if LLM is attached, None otherwise
        """
        if self._llm:
            return self._llm.usage_accumulator
        return None

    @property
    def llm(self) -> AugmentedLLMProtocol:
        assert self._llm, "LLM is not attached"
        return self._llm

    @property
    def provider(self) -> Provider:
        return self.llm.provider

    def _merge_request_params(
        self,
        base_params: Optional[RequestParams],
        override_params: Optional[RequestParams],
        model_override: Optional[str] = None,
    ) -> Optional[RequestParams]:
        """
        Merge request parameters with proper precedence.

        Args:
            base_params: Base parameters (lower precedence)
            override_params: Override parameters (higher precedence)
            model_override: Optional model name to override

        Returns:
            Merged RequestParams or None if both inputs are None
        """
        if not base_params and not override_params:
            return None

        if not base_params:
            result = override_params.model_copy() if override_params else None
        else:
            result = base_params.model_copy()
            if override_params:
                # Merge only the explicitly set values from override_params
                for k, v in override_params.model_dump(exclude_unset=True).items():
                    if v is not None:
                        setattr(result, k, v)

        # Apply model override if specified
        if model_override and result:
            result.model = model_override

        return result
