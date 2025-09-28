"""
Free simulation mode for TestSentry LLM operations.
Uses deterministic mock responses for testing without API costs.
"""

import hashlib
import json
import os
from typing import Any, Dict, List

from .runner_common import get_logger

logger = get_logger(__name__)


def is_simulation_mode() -> bool:
    """Check if we're in simulation mode."""
    return (
        os.getenv("SENTRIES_SIMULATION_MODE", "false").lower() == "true"
        or os.getenv("CI", "false").lower() == "true"  # Auto-enable in CI
    )


def generate_mock_response(messages: List[Dict[str, str]], model: str) -> str:
    """Generate a deterministic mock response based on the input."""
    # Handle malformed messages gracefully
    try:
        message_text = " ".join([msg.get("content", "") for msg in messages if msg.get("content")])
        if not message_text:
            return "I understand you need help, but I didn't receive a clear message. Please provide more details."
        
        # Hash is used for potential future deterministic variations
        hashlib.md5(message_text.encode()).hexdigest()
    except Exception:
        return "I encountered an issue processing your request. Please check your message format."

    # Extract the user's request
    user_messages = [msg for msg in messages if msg.get("role") == "user"]
    user_content = user_messages[-1]["content"] if user_messages else ""

    # Determine response type based on content
    if "fix" in user_content.lower() and "test" in user_content.lower():
        if "assert 1 == 2" in user_content:
            return (
                "I can see the issue. The assertion `assert 1 == 2` will always fail "
                "because 1 is not equal to 2.\n\n"
                "Here's the fix:\n\n"
                "```python\n"
                "def test_example():\n"
                "    assert 1 == 1  # Fixed: changed 2 to 1\n"
                "```\n\n"
                "The test now asserts that 1 equals 1, which will pass."
            )
        else:
            return """I can help fix this test. Based on the error, here's a suggested fix:

```python
def test_function():
    # Original failing assertion
    # assert condition_that_fails

    # Fixed assertion
    assert condition_that_passes
```

This should resolve the test failure while preserving the test's purpose."""

    elif "plan" in user_content.lower():
        return """## Analysis and Plan

**Issue Identified**: Test failure in assertion logic
**Root Cause**: The assertion condition is incorrect
**Proposed Fix**: Update the assertion to use the correct expected value
**Files to Modify**: Test file containing the failing assertion
**Risk Assessment**: Low - Simple assertion fix with minimal impact"""

    elif "json" in user_content.lower():
        return json.dumps(
            {
                "operations": [
                    {
                        "file": "test_file.py",
                        "changes": [{"find": "assert 1 == 2", "replace": "assert 1 == 1"}],
                    }
                ]
            },
            indent=2,
        )

    else:
        return (
            "I understand you need help with this issue. Based on the context, "
            "here's what I can suggest:\n\n"
            "1. **Identify the problem**: Look for the specific error or failure\n"
            "2. **Analyze the cause**: Determine why the issue is occurring\n"
            "3. **Propose a solution**: Provide a fix that addresses the root cause\n"
            "4. **Verify the fix**: Ensure the solution works and doesn't break other functionality"
        )


def chat_simulation(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 500,
    **kwargs: Any,
) -> str:
    """Simulate a chat request without making actual API calls."""
    logger.info(f"🎭 Simulation mode: Mocking LLM response for model {model}")

    response = generate_mock_response(messages, model)

    # Truncate if too long (simulate max_tokens)
    if len(response.split()) > max_tokens:
        words = response.split()[:max_tokens]
        response = " ".join(words) + "..."

    return response
