"""LLM wrapper utilities for CAMEL agents."""

from typing import Dict, List

from ..chat import chat, get_default_params
from ..runner_common import get_logger

logger = get_logger(__name__)


class SentryLLMWrapper:
    """
    Lightweight wrapper to integrate existing Sentry chat backend with CAMEL agents.

    This preserves our multi-backend support (Ollama, OpenAI, simulation, etc.)
    while providing a simple interface for agent interactions.
    """

    def __init__(self, model_name: str, model_type: str = "planner"):
        self.model_name = model_name
        self.model_type = model_type
        logger.info(f"🔧 Created SentryLLMWrapper for {model_name} ({model_type})")

    def generate(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate response using our existing chat backend.

        Args:
            messages: List of message dictionaries

        Returns:
            Generated response
        """
        params = get_default_params(self.model_type)
        response = chat(
            model=self.model_name,
            messages=messages,
            temperature=params.get("temperature", 0.1),
            max_tokens=int(params.get("max_tokens", 500)),
        )

        return response
