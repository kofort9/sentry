"""
Simple chat interface for communicating with Ollama.
"""

from typing import Dict, List

import requests

from .runner_common import LLM_BASE, get_logger

logger = get_logger(__name__)


def chat(
    model: str, messages: List[Dict[str, str]], temperature: float = 0.1, max_tokens: int = 500
) -> str:
    """
    Send a chat request to Ollama.

    Args:
        model: Model name to use
        messages: List of message dictionaries with 'role' and 'content'
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate

    Returns:
        Generated response text
    """
    # Convert OpenAI-style messages to Ollama prompt format
    prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            prompt += f"System: {msg['content']}\n\n"
        elif msg["role"] == "user":
            prompt += f"User: {msg['content']}\n\n"
        elif msg["role"] == "assistant":
            prompt += f"Assistant: {msg['content']}\n\n"

    prompt += "Assistant: "

    url = f"{LLM_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    logger.debug(f"Sending request to Ollama: {url}")

    try:
        response = requests.post(url, json=payload, timeout=300)  # 5 minute timeout
        response.raise_for_status()
        result = response.json()
        content = result.get("response", "")
        return content.strip()
    except Exception as e:
        logger.error(f"Error communicating with Ollama: {e}")
        raise


def get_default_params(model_type: str) -> Dict[str, float]:
    """Get default parameters for different model types."""
    if model_type == "planner":
        return {"temperature": 0.2, "max_tokens": 600}
    elif model_type == "patcher":
        return {"temperature": 0.1, "max_tokens": 500}
    else:
        return {"temperature": 0.1, "max_tokens": 500}
