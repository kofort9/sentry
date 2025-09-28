"""
Chat functionality for TestSentry with support for multiple LLM backends.
"""

import os
from typing import Any, Dict, List

import requests

from .runner_common import LLM_BASE, get_logger

logger = get_logger(__name__)


def is_simulation_mode() -> bool:
    """Check if we're in simulation mode."""
    return (
        os.getenv("SENTRIES_SIMULATION_MODE", "false").lower() == "true"
        or os.getenv("CI", "false").lower() == "true"  # Auto-enable in CI
    )


def has_api_key() -> bool:
    """Check if we have any API keys available."""
    return bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("GROQ_API_KEY")  # Add Groq as a free option
    )


def chat(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    **kwargs: Any,
) -> str:
    """Chat with an LLM using the specified model and messages."""

    # Check for simulation mode first
    if is_simulation_mode():
        from .chat_simulation import chat_simulation

        return chat_simulation(model, messages, temperature, max_tokens, **kwargs)

    # Check for API key mode
    if has_api_key():
        logger.info(f"🔑 Using API key mode with model: {model}")
        return chat_with_api(model, messages, temperature, max_tokens, **kwargs)

    # Default to local LLM mode
    logger.info(f"🤖 Using local LLM mode with model: {model}")
    return chat_with_ollama(model, messages, temperature, max_tokens, **kwargs)


def chat_with_api(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    **kwargs: Any,
) -> str:
    """Chat using API keys (OpenAI, Anthropic, or Groq)."""

    # Try Groq first (free tier available)
    if os.getenv("GROQ_API_KEY"):
        return chat_with_groq(model, messages, temperature, max_tokens, **kwargs)

    # Try OpenAI
    if os.getenv("OPENAI_API_KEY"):
        return chat_with_openai(model, messages, temperature, max_tokens, **kwargs)

    # Try Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        return chat_with_anthropic(model, messages, temperature, max_tokens, **kwargs)

    raise ValueError("No valid API key found")


def chat_with_groq(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    **kwargs: Any,
) -> str:
    """Chat using Groq API (free tier available)."""
    try:
        import groq

        client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        return response.choices[0].message.content
    except ImportError:
        logger.error("Groq library not installed. Install with: pip install groq")
        raise
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise


def chat_with_openai(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    **kwargs: Any,
) -> str:
    """Chat using OpenAI API."""
    try:
        import openai

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        return response.choices[0].message.content
    except ImportError:
        logger.error("OpenAI library not installed. Install with: pip install openai")
        raise
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise


def chat_with_anthropic(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    **kwargs: Any,
) -> str:
    """Chat using Anthropic API."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        return response.content[0].text
    except ImportError:
        logger.error("Anthropic library not installed. Install with: pip install anthropic")
        raise
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        raise


def chat_with_ollama(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    **kwargs: Any,
) -> str:
    """Chat using local Ollama (existing implementation)."""
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
        if isinstance(content, str):
            return content.strip()
        else:
            return str(content).strip()
    except Exception as e:
        logger.error(f"Error communicating with Ollama: {e}")
        raise


def get_default_params(model_type: str) -> Dict[str, float | int]:
    """Get default parameters for different model types."""
    if model_type == "planner":
        return {"temperature": 0.2, "max_tokens": 600}
    elif model_type == "patcher":
        return {"temperature": 0.1, "max_tokens": 500}
    else:
        return {"temperature": 0.1, "max_tokens": 500}
