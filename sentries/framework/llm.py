"""
Abstract base classes for LLM integration in the reusable framework.
"""

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class LLMProvider(Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OLLAMA = "ollama"
    HUGGING_FACE = "hugging_face"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """Configuration for LLM integration."""

    provider: LLMProvider
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 1000
    timeout_seconds: float = 60.0
    retry_attempts: int = 3
    streaming: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMResponse:
    """Standardized response from LLM interactions."""

    def __init__(
        self,
        content: str,
        model: str,
        usage: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ):
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.metadata = metadata or {}
        self.timestamp = datetime.datetime.now()

    def get_token_count(self) -> Dict[str, int]:
        """Get token usage information."""
        return {
            "input_tokens": self.usage.get("prompt_tokens", 0),
            "output_tokens": self.usage.get("completion_tokens", 0),
            "total_tokens": self.usage.get("total_tokens", 0),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "content": self.content,
            "model": self.model,
            "usage": self.usage,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseLLMWrapper(ABC):
    """
    Abstract base class for LLM integrations.

    Provides standardized interface for different LLM providers
    with consistent error handling, retries, and observability.
    """

    def __init__(self, config: LLMConfig, observer: Optional[Callable] = None):
        self.config = config
        self.observer = observer
        self.request_history: List[Dict[str, Any]] = []

    @abstractmethod
    def _make_request(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        Make the actual LLM request (provider-specific implementation).

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse object
        """
        pass

    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate response from LLM with error handling and retries.

        Args:
            messages: List of message dictionaries
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        # Merge config with kwargs
        request_params = {
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout_seconds,
            **kwargs,
        }

        start_time = datetime.datetime.now()
        last_exception = None

        for attempt in range(self.config.retry_attempts):
            try:
                # Log request if observer available
                if self.observer:
                    self._log_request(messages, request_params, attempt + 1)

                response = self._make_request(messages, **request_params)

                # Log successful response
                if self.observer:
                    self._log_response(response, attempt + 1, start_time)

                # Record in history
                self._record_request(messages, response, request_params, success=True)

                return response.content

            except Exception as e:
                last_exception = e

                # Log failed attempt
                if self.observer:
                    self._log_error(e, attempt + 1, start_time)

                # If not last attempt, wait and retry
                if attempt < self.config.retry_attempts - 1:
                    import time

                    time.sleep(2**attempt)  # Exponential backoff
                    continue

        # Record failed request
        self._record_request(messages, None, request_params, success=False, error=last_exception)

        # All attempts failed
        raise RuntimeError(
            f"LLM request failed after {self.config.retry_attempts} attempts: {last_exception}"
        )

    def generate_structured(
        self, messages: List[Dict[str, str]], schema: Dict[str, Any] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response from LLM.

        Args:
            messages: List of message dictionaries
            schema: JSON schema for validation (optional)
            **kwargs: Additional parameters

        Returns:
            Parsed JSON response
        """
        # Add JSON instruction to the last user message
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += "\n\nPlease respond with valid JSON only."
        else:
            messages.append({"role": "user", "content": "Please respond with valid JSON only."})

        response_text = self.generate(messages, **kwargs)

        # Parse JSON response
        import json
        import re

        try:
            # Try direct parsing first
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            # Try extracting JSON from code blocks
            json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
            match = re.search(json_pattern, response_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))

            # Try finding JSON-like patterns
            json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
            match = re.search(json_pattern, response_text, re.DOTALL)
            if match:
                return json.loads(match.group())

            raise ValueError(f"Could not parse JSON from LLM response: {response_text[:200]}...")

    def _log_request(self, messages: List[Dict[str, str]], params: Dict[str, Any], attempt: int):
        """Log LLM request."""
        if self.observer:
            self.observer(
                "llm_request",
                {
                    "provider": self.config.provider.value,
                    "model": self.config.model_name,
                    "messages": messages,
                    "params": params,
                    "attempt": attempt,
                    "timestamp": datetime.datetime.now().isoformat(),
                },
            )

    def _log_response(self, response: LLMResponse, attempt: int, start_time: datetime.datetime):
        """Log successful LLM response."""
        if self.observer:
            duration = (datetime.datetime.now() - start_time).total_seconds()
            self.observer(
                "llm_response",
                {
                    "provider": self.config.provider.value,
                    "model": response.model,
                    "content_length": len(response.content),
                    "usage": response.usage,
                    "duration_seconds": duration,
                    "attempt": attempt,
                    "success": True,
                    "timestamp": datetime.datetime.now().isoformat(),
                },
            )

    def _log_error(self, error: Exception, attempt: int, start_time: datetime.datetime):
        """Log LLM error."""
        if self.observer:
            duration = (datetime.datetime.now() - start_time).total_seconds()
            self.observer(
                "llm_error",
                {
                    "provider": self.config.provider.value,
                    "model": self.config.model_name,
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "duration_seconds": duration,
                    "attempt": attempt,
                    "success": False,
                    "timestamp": datetime.datetime.now().isoformat(),
                },
            )

    def _record_request(
        self,
        messages: List[Dict[str, str]],
        response: Optional[LLMResponse],
        params: Dict[str, Any],
        success: bool,
        error: Exception = None,
    ):
        """Record request in history."""
        record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "messages": messages,
            "params": params,
            "response": response.to_dict() if response else None,
            "success": success,
            "error": str(error) if error else None,
        }

        self.request_history.append(record)

        # Trim history to last 100 requests
        if len(self.request_history) > 100:
            self.request_history = self.request_history[-100:]

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for this LLM instance."""
        total_requests = len(self.request_history)
        successful_requests = sum(1 for r in self.request_history if r["success"])

        total_tokens = 0
        total_input_tokens = 0
        total_output_tokens = 0

        for record in self.request_history:
            if record["response"] and record["response"]["usage"]:
                usage = record["response"]["usage"]
                total_tokens += usage.get("total_tokens", 0)
                total_input_tokens += usage.get("prompt_tokens", 0)
                total_output_tokens += usage.get("completion_tokens", 0)

        return {
            "provider": self.config.provider.value,
            "model": self.config.model_name,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
            "total_tokens": total_tokens,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "average_tokens_per_request": (
                total_tokens / successful_requests if successful_requests > 0 else 0
            ),
        }

    def clear_history(self):
        """Clear request history."""
        self.request_history = []


class MockLLMWrapper(BaseLLMWrapper):
    """Mock LLM wrapper for testing and simulation."""

    def __init__(self, responses: List[str] = None, **kwargs):
        config = LLMConfig(provider=LLMProvider.CUSTOM, model_name="mock")
        super().__init__(config, **kwargs)
        self.responses = responses or ["Mock response"]
        self.call_count = 0

    def _make_request(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Return mock response."""
        response_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1

        return LLMResponse(
            content=response_text,
            model="mock",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )


class LLMPool:
    """
    Pool of LLM wrappers for load balancing and redundancy.

    Automatically routes requests to available LLMs and handles failover.
    """

    def __init__(self):
        self.llms: List[BaseLLMWrapper] = []
        self.current_index = 0

    def add_llm(self, llm: BaseLLMWrapper):
        """Add an LLM to the pool."""
        self.llms.append(llm)

    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate response using available LLM from pool."""
        if not self.llms:
            raise ValueError("No LLMs available in pool")

        last_exception = None

        # Try each LLM in the pool
        for _ in range(len(self.llms)):
            llm = self.llms[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.llms)

            try:
                return llm.generate(messages, **kwargs)
            except Exception as e:
                last_exception = e
                continue

        # All LLMs failed
        raise RuntimeError(f"All LLMs in pool failed. Last error: {last_exception}")

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics for all LLMs in the pool."""
        return {
            "total_llms": len(self.llms),
            "llm_stats": [llm.get_usage_stats() for llm in self.llms],
        }
