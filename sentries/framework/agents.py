"""
Abstract base classes for agents in the reusable framework.
"""

import datetime
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class AgentRole(Enum):
    """Standard agent roles in multi-agent workflows."""

    ANALYZER = "analyzer"  # Analyzes input and extracts insights
    PLANNER = "planner"  # Creates structured plans from analysis
    EXECUTOR = "executor"  # Executes plans into concrete actions
    VALIDATOR = "validator"  # Validates outputs and provides feedback
    COORDINATOR = "coordinator"  # Orchestrates other agents
    OBSERVER = "observer"  # Monitors and logs workflow progress


@dataclass
class AgentConfig:
    """Configuration for agent initialization."""

    name: str
    role: AgentRole
    model_name: str
    system_message: str
    max_history_length: int = 10
    tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the framework.

    Provides standard structure for LLM-based agents with tools,
    conversation history, and observability hooks.
    """

    def __init__(self, config: AgentConfig, llm_wrapper=None, tool_registry=None, observer=None):
        self.config = config
        self.llm = llm_wrapper
        self.tool_registry = tool_registry
        self.observer = observer

        self.conversation_history: List[Dict[str, Any]] = []
        self.execution_history: List[Dict[str, Any]] = []

        # Initialize tools if registry provided
        self.tools = {}
        if tool_registry and config.tools:
            for tool_name in config.tools:
                self.tools[tool_name] = tool_registry.get_tool(tool_name)

    @abstractmethod
    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main processing method that each agent must implement.

        Args:
            input_data: The primary input for the agent to process
            context: Additional context from the workflow

        Returns:
            Dictionary with processing results and metadata
        """
        pass

    def _log_interaction(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Log an LLM interaction for observability."""
        if self.observer:
            self.observer.log_llm_interaction(
                agent_name=self.config.name,
                agent_role=self.config.role.value,
                llm_role=role,
                content=content,
                model=self.config.model_name,
                metadata=metadata or {},
            )

    def _record_execution(self, input_data: Any, output_data: Any, duration: float, success: bool):
        """Record execution for history and observability."""
        execution_record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "input_summary": (
                str(input_data)[:200] + "..." if len(str(input_data)) > 200 else str(input_data)
            ),
            "output_summary": (
                str(output_data)[:200] + "..." if len(str(output_data)) > 200 else str(output_data)
            ),
            "duration_seconds": duration,
            "success": success,
        }

        self.execution_history.append(execution_record)

        # Trim history to max length
        if len(self.execution_history) > self.config.max_history_length:
            self.execution_history = self.execution_history[-self.config.max_history_length :]

    def _add_to_conversation_history(
        self, role: str, content: str, metadata: Dict[str, Any] = None
    ):
        """Add an entry to conversation history."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }

        self.conversation_history.append(entry)

        # Trim history to max length
        if len(self.conversation_history) > self.config.max_history_length:
            self.conversation_history = self.conversation_history[-self.config.max_history_length :]

    def get_tool(self, tool_name: str):
        """Get a tool by name if available."""
        return self.tools.get(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        """Check if agent has access to a specific tool."""
        return tool_name in self.tools

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status for monitoring."""
        return {
            "name": self.config.name,
            "role": self.config.role.value,
            "model": self.config.model_name,
            "tools_available": list(self.tools.keys()),
            "conversation_entries": len(self.conversation_history),
            "executions_completed": len(self.execution_history),
            "last_execution": self.execution_history[-1] if self.execution_history else None,
        }


class LLMAgent(BaseAgent):
    """
    Base class for agents that primarily use LLM interactions.

    Provides standard patterns for system messages, user prompts,
    and structured output parsing.
    """

    def __init__(self, config: AgentConfig, llm_wrapper=None, tool_registry=None, observer=None):
        super().__init__(config, llm_wrapper, tool_registry, observer)

        if not llm_wrapper:
            raise ValueError("LLMAgent requires an LLM wrapper")

    def _generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate LLM response with logging."""
        # Log system message
        system_msg = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
        if system_msg:
            self._log_interaction("system", system_msg, {"context": "agent_process"})

        # Log user message
        user_msg = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
        if user_msg:
            self._log_interaction("user", user_msg, {"context": "agent_process"})

        # Generate response
        response = self.llm.generate(messages, **kwargs)

        # Log assistant response
        self._log_interaction("assistant", response, {"context": "agent_process"})

        return response

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response with error handling."""
        try:
            # Try direct JSON parsing first
            return json.loads(response.strip())
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code blocks
            import re

            json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
            match = re.search(json_pattern, response, re.DOTALL)
            if match:
                return json.loads(match.group(1))

            # Try finding JSON-like patterns
            json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
            match = re.search(json_pattern, response, re.DOTALL)
            if match:
                return json.loads(match.group())

            raise ValueError(f"Could not parse JSON from response: {response[:100]}...")


class ToolAgent(BaseAgent):
    """
    Base class for agents that primarily use tools rather than LLMs.

    Useful for validation, execution, and data processing agents.
    """

    def __init__(self, config: AgentConfig, tool_registry=None, observer=None):
        super().__init__(config, llm_wrapper=None, tool_registry=tool_registry, observer=observer)

        if not self.tools:
            raise ValueError("ToolAgent requires at least one tool")

    def _execute_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """Execute a tool with error handling and logging."""
        if not self.has_tool(tool_name):
            raise ValueError(f"Tool '{tool_name}' not available to agent '{self.config.name}'")

        tool = self.get_tool(tool_name)

        try:
            start_time = datetime.datetime.now()
            result = tool.execute(*args, **kwargs)
            duration = (datetime.datetime.now() - start_time).total_seconds()

            if self.observer:
                self.observer.log_tool_execution(
                    agent_name=self.config.name,
                    tool_name=tool_name,
                    duration=duration,
                    success=True,
                    result_summary=(
                        str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                    ),
                )

            return result

        except Exception as e:
            duration = (datetime.datetime.now() - start_time).total_seconds()

            if self.observer:
                self.observer.log_tool_execution(
                    agent_name=self.config.name,
                    tool_name=tool_name,
                    duration=duration,
                    success=False,
                    error=str(e),
                )

            raise
