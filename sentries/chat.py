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

    # Import observability here to avoid circular imports
    try:
        from packages.metrics_core.observability import analyze_text_for_pii, log_llm_interaction

        observability_available = True
    except ImportError:
        observability_available = False

    # Determine which mode we're using
    mode = "simulation" if is_simulation_mode() else "api" if has_api_key() else "local"

    # Extract prompt for observability
    user_messages = [msg for msg in messages if msg.get("role") == "user"]
    prompt = "\n".join([msg["content"] for msg in user_messages])

    logger.info(f"🤖 Using {mode} mode with model: {model}")
    if observability_available:
        logger.info("📊 Observability enabled - logging LLM interaction")

    # Make the actual LLM call based on mode
    if mode == "simulation":
        from .chat_simulation import chat_simulation

        response = chat_simulation(model, messages, temperature, max_tokens, **kwargs)
    elif mode == "api":
        response = chat_with_api(model, messages, temperature, max_tokens, **kwargs)
    else:  # local mode
        response = chat_with_ollama(model, messages, temperature, max_tokens, **kwargs)

    # Log the interaction for observability
    if observability_available:
        try:
            system_messages = [msg for msg in messages if msg.get("role") == "system"]

            log_llm_interaction(
                prompt=prompt,
                response=response,
                service="testsentry",
                release="dev",
                metadata={
                    "model": model,
                    "mode": mode,  # Track which mode was used
                    "system_messages": len(system_messages),
                    "user_messages": len(user_messages),
                    "total_messages": len(messages),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )

            # Analyze response for PII
            pii_analysis = analyze_text_for_pii(response)
            if pii_analysis.get("pii_spans"):
                logger.warning(
                    f"⚠️  PII detected in LLM response: {len(pii_analysis['pii_spans'])} spans"
                )
            else:
                logger.info("✅ No PII detected in LLM response")

        except Exception as e:
            logger.warning(f"⚠️  Observability logging failed: {e}")
            # Continue execution - don't let observability errors break chat

    return response


def chat_with_api(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    **kwargs: Any,
) -> str:
    """Chat using API keys (OpenAI, Anthropic, or Groq) with fallback."""

    # Try Groq first (free tier available)
    if os.getenv("GROQ_API_KEY"):
        try:
            return chat_with_groq(model, messages, temperature, max_tokens, **kwargs)
        except Exception as e:
            logger.warning(f"Groq API failed: {e}, trying fallback...")

    # Try OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            return chat_with_openai(model, messages, temperature, max_tokens, **kwargs)
        except Exception as e:
            logger.warning(f"OpenAI API failed: {e}, trying fallback...")

    # Try Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return chat_with_anthropic(model, messages, temperature, max_tokens, **kwargs)
        except Exception as e:
            logger.warning(f"Anthropic API failed: {e}, no more fallbacks available")
            raise

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
