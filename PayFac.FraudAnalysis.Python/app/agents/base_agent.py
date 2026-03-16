"""Base agent class with shared capabilities.

All specialized agents inherit from BaseAgent, which provides:
  - LLM access (chat and embeddings)
  - Memory tier access (short-term, long-term, episodic)
  - Kafka event publishing
  - Tool registration
  - Common prompt building utilities
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from app.infrastructure.llm_client import LLMClient
from app.memory.manager import MemoryManager
from app.kafka_bus.producer import KafkaProducer
from app.kafka_bus.events import AgentEvent

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all fraud analysis agents.

    Provides shared infrastructure:
      - LLM model access
      - Memory manager for all 3 tiers
      - Kafka producer for event publishing
      - Common methods for prompt construction and result storage
    """

    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        memory: MemoryManager,
        kafka_producer: KafkaProducer,
    ):
        self.name = name
        self._llm = llm_client
        self._memory = memory
        self._kafka = kafka_producer
        self._tools: list = []
        self._system_prompt: str = ""

    @property
    def chat_model(self) -> ChatOpenAI:
        """Get the LLM chat model."""
        return self._llm.chat_model

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the agent's system prompt defining its role and capabilities."""
        ...

    @abstractmethod
    def get_tools(self) -> list:
        """Return the list of tools available to this agent."""
        ...

    async def invoke(
        self,
        query: str,
        session_id: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Invoke the agent with a query and optional context.

        Flow:
          1. Build messages (system prompt + context + query)
          2. Bind tools to the LLM
          3. Execute with tool calling loop
          4. Store result in short-term memory
          5. Publish result event to Kafka

        Args:
            query: The analysis query.
            session_id: Session for memory context.
            context: Pre-built context (from MemoryManager.build_agent_context).

        Returns:
            Agent result dictionary with analysis and metadata.
        """
        logger.info("Agent '%s' invoked: session=%s", self.name, session_id)

        # Build the message chain
        messages = [SystemMessage(content=self.get_system_prompt())]

        # Add context if provided
        if context:
            context_text = self._format_context(context)
            messages.append(
                HumanMessage(content=f"CONTEXT FROM MEMORY:\n{context_text}")
            )

        # Add the main query
        messages.append(HumanMessage(content=query))

        # Get tools and bind to model
        tools = self.get_tools()
        if tools:
            model_with_tools = self.chat_model.bind_tools(tools)
        else:
            model_with_tools = self.chat_model

        # Execute with tool calling loop (Agentic RAG)
        result = await self._execute_with_tools(model_with_tools, messages, tools)

        # Store result in short-term memory for other agents
        await self._memory.short_term.store_agent_result(
            session_id, self.name, result
        )

        # Record in chat history
        await self._memory.short_term.add_chat_message(
            session_id, "agent", result.get("analysis", ""), agent_name=self.name
        )

        logger.info("Agent '%s' completed: session=%s", self.name, session_id)
        return result

    async def _execute_with_tools(
        self,
        model: Any,
        messages: list,
        tools: list,
        max_iterations: int = 10,
    ) -> dict[str, Any]:
        """
        Execute the LLM with iterative tool calling.

        This is the core Agentic RAG loop — the model can call tools
        multiple times, evaluate results, and decide when it has enough
        context to produce a final answer.
        """
        from langchain_core.messages import ToolMessage

        current_messages = list(messages)
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            response = await model.ainvoke(current_messages)
            current_messages.append(response)

            # Check if model wants to call tools
            if not response.tool_calls:
                # No tool calls — model has produced final answer
                return {
                    "agent": self.name,
                    "analysis": response.content,
                    "iterations": iteration,
                    "tool_calls_made": iteration - 1,
                }

            # Execute each tool call
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                logger.debug(
                    "Agent '%s' calling tool: %s(%s)",
                    self.name, tool_name, tool_args,
                )

                # Find and execute the tool
                tool_result = await self._execute_tool(tool_name, tool_args, tools)

                current_messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call["id"],
                    )
                )

        # Max iterations reached
        last_content = current_messages[-1].content if current_messages else ""
        return {
            "agent": self.name,
            "analysis": f"Analysis completed after {max_iterations} iterations. {last_content}",
            "iterations": max_iterations,
            "max_iterations_reached": True,
        }

    async def _execute_tool(
        self, tool_name: str, tool_args: dict, tools: list
    ) -> str:
        """Execute a tool by name with given arguments."""
        for tool in tools:
            if tool.name == tool_name:
                try:
                    result = await tool.ainvoke(tool_args)
                    return str(result)
                except Exception as e:
                    logger.error("Tool '%s' failed: %s", tool_name, e)
                    return f"Tool '{tool_name}' failed: {str(e)}"

        return f"Tool '{tool_name}' not found."

    def publish_event(self, event: AgentEvent) -> None:
        """Publish an event to the Kafka event bus."""
        self._kafka.publish(event)

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format a context dictionary into readable text for the LLM."""
        sections = []

        # Short-term context
        st = context.get("short_term", {})
        if st.get("agent_results"):
            for agent_name, result in st["agent_results"].items():
                sections.append(
                    f"[{agent_name.upper()} AGENT FINDINGS]:\n{result.get('analysis', 'No findings')}"
                )

        # Long-term context
        lt = context.get("long_term", {})
        if lt.get("merchant_profile"):
            mp = lt["merchant_profile"]
            sections.append(
                f"[MERCHANT PROFILE]:\n"
                f"  ID: {mp.get('merchant_id')}, Name: {mp.get('merchant_name')}\n"
                f"  MCC: {mp.get('mcc')}, High Risk: {mp.get('is_high_risk')}\n"
                f"  Fraud Count: {mp.get('historical_fraud_count')}, "
                f"Chargeback Ratio: {mp.get('chargeback_ratio')}"
            )

        # Episodic context
        episodes = context.get("episodic", [])
        if episodes:
            ep_texts = []
            for ep in episodes[:3]:
                ep_texts.append(f"  - {ep.get('content', '')[:200]}")
            sections.append(
                "[SIMILAR PAST INVESTIGATIONS]:\n" + "\n".join(ep_texts)
            )

        return "\n\n".join(sections) if sections else "No prior context available."
