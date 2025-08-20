"""
Chat interface for communicating with LLM models.
"""

import requests
from typing import List, Dict, Any, Optional
from .runner_common import LLM_BASE, get_logger

logger = get_logger(__name__)


def chat(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    num_ctx: int = 2048
) -> str:
    """
    Send a chat request to the LLM.

    Args:
        model: Model name to use
        messages: List of message dictionaries with 'role' and 'content'
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        max_tokens: Maximum tokens to generate
        num_ctx: Context window size

    Returns:
        Generated response text

    Raises:
        requests.RequestException: If the request fails
    """
    if ":11434" in LLM_BASE or LLM_BASE.endswith(":11434"):
        return _chat_ollama(model, messages, temperature, max_tokens, num_ctx)
    else:
        return _chat_openai_style(model, messages, temperature, max_tokens)


def _chat_ollama(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    num_ctx: int
) -> str:
    """Send chat request to Ollama API."""
    url = f"{LLM_BASE}/api/chat"

    # Convert OpenAI-style messages to Ollama format
    prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            prompt += f"System: {msg['content']}\n\n"
        elif msg["role"] == "user":
            prompt += f"User: {msg['content']}\n\n"
        elif msg["role"] == "assistant":
            prompt += f"Assistant: {msg['content']}\n\n"

    prompt += "Assistant: "

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": num_ctx
        }
    }

    logger.debug(f"Sending request to Ollama: {url}")
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()

    result = response.json()
    return result.get("message", {}).get("content", "").strip()


def _chat_openai_style(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int
) -> str:
    """Send chat request to OpenAI-style API."""
    url = f"{LLM_BASE}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }

    logger.debug(f"Sending request to OpenAI-style API: {url}")
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()

    result = response.json()
    return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()


def get_default_params(model_type: str) -> Dict[str, Any]:
    """
    Get default parameters for different model types.

    Args:
        model_type: Either 'planner' or 'patcher'

    Returns:
        Dictionary with default parameters
    """
    if model_type == "planner":
        return {
            "temperature": 0.2,
            "num_ctx": 4096,
            "max_tokens": 600
        }
    elif model_type == "patcher":
        return {
            "temperature": 0.1,
            "num_ctx": 2048,
            "max_tokens": 500
        }
    else:
        raise ValueError(f"Unknown model type: {model_type}")
