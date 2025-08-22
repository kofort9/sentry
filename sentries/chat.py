"""
Chat interface for communicating with LLM models.
"""

import requests
import json
import time
from typing import List, Dict, Any
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

    # Choose between streaming and non-streaming based on context size
    use_streaming = len(prompt) > 3000  # Use streaming for very large contexts

    if use_streaming:
        logger.info(f"Using streaming mode for large context ({len(prompt)} chars)")
        return _chat_ollama_streaming(model, prompt, temperature, max_tokens, num_ctx)
    else:
        return _chat_ollama_standard(model, prompt, temperature, max_tokens, num_ctx)


def _chat_ollama_standard(
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    num_ctx: int
) -> str:
    """Standard non-streaming chat request."""
    url = f"{LLM_BASE}/api/generate"

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

    logger.debug(f"Sending standard request to Ollama: {url}")

    # Smart timeout calculation based on context complexity
    base_timeout = 30  # Base time for simple requests
    char_timeout = 0.02  # 20ms per character (empirical estimate)
    buffer_timeout = 30  # Safety buffer

    estimated_timeout = base_timeout + (len(prompt) * char_timeout) + buffer_timeout
    # Cap at reasonable maximum (5 minutes)
    timeout_seconds = min(estimated_timeout, 300)

    logger.info(
        f"Smart timeout calculation: {len(prompt)} chars → "
        f"{timeout_seconds:.1f}s (estimated: {estimated_timeout:.1f}s)")

    try:
        response = requests.post(url, json=payload, timeout=timeout_seconds)
        response.raise_for_status()

        result = response.json()
    except requests.exceptions.Timeout:
        logger.warning(f"Request timed out after {timeout_seconds}s for {len(prompt)} chars")
        logger.warning("Consider reducing context size or using streaming for large requests")
        raise
    except Exception as e:
        logger.error(f"Error communicating with Ollama: {e}")
        if 'response' in locals():
            logger.error(f"Response status: {getattr(response, 'status_code', 'N/A')}")
            logger.error(f"Response text: {getattr(response, 'text', 'N/A')}")
        raise

    # Debug: Log the full Ollama response
    logger.debug(f"Ollama response: {result}")

    # Use the generate API response format
    content = result.get("response", "")

    logger.debug(f"Extracted content: '{content}' (length: {len(content)})")
    return content.strip()


def _chat_ollama_streaming(
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    num_ctx: int
) -> str:
    """Streaming chat request for large contexts with progress monitoring."""
    url = f"{LLM_BASE}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": num_ctx
        }
    }

    logger.info(f"Starting streaming request for {len(prompt)} chars")

    try:
        response = requests.post(url, json=payload, stream=True, timeout=300)
        response.raise_for_status()

        content = ""
        start_time = time.time()
        last_progress = start_time

        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    if 'response' in data:
                        chunk = data['response']
                        content += chunk

                        # Log progress every 5 seconds
                        current_time = time.time()
                        if current_time - last_progress >= 5:
                            elapsed = current_time - start_time
                            logger.info(
                                f"Streaming progress: {len(content)} chars received "
                                f"in {elapsed:.1f}s")
                            last_progress = current_time

                        # Check if done
                        if data.get('done', False):
                            break

                except json.JSONDecodeError:
                    continue

        elapsed = time.time() - start_time
        logger.info(f"Streaming completed: {len(content)} chars in {elapsed:.1f}s")

        return content.strip()

    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        raise


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


def compress_test_context(context: str, max_chars: int = 2000) -> str:
    """
    Intelligently compress test context to reduce processing time.

    Args:
        context: Full test failure context
        max_chars: Maximum characters to allow

    Returns:
        Compressed context focusing on essential information
    """
    if len(context) <= max_chars:
        return context

    logger.info(f"Compressing context from {len(context)} to ~{max_chars} chars")

    # Extract key failure information
    lines = context.split('\n')
    compressed_lines = []

    # Always include header
    for line in lines[:5]:  # First 5 lines usually contain summary
        if line.strip():
            compressed_lines.append(line)

    # Find and include test failure details
    failure_section = False
    for line in lines:
        if 'FAILED' in line or 'ERROR' in line:
            failure_section = True
            compressed_lines.append(line)
        elif failure_section and line.strip() and len(compressed_lines) < 20:
            # Include a few lines after each failure
            compressed_lines.append(line)
        elif failure_section and line.strip() == '':
            # Stop at first empty line after failures
            break

    # Add compression note
    compressed_lines.append(
        f"\n[Context compressed from {len(context)} to "
        f"{sum(len(l) for l in compressed_lines)} chars]")

    compressed = '\n'.join(compressed_lines)
    logger.info(f"Context compressed: {len(context)} → {len(compressed)} chars")

    return compressed


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
