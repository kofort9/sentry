#!/usr/bin/env python3
"""
Minimal example demonstrating TokenBucket usage.

This example shows basic rate limiting operations without tests or documentation.
"""

import sys
import time
from pathlib import Path

# Add the parent directory to sys.path to import sentry_examples
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentry_examples.rate_limiter import TokenBucket  # noqa: E402


def main():
    """Demonstrate basic TokenBucket functionality."""
    print("TokenBucket Rate Limiter Example")
    print("=" * 35)

    # Create a bucket with 5 tokens, refilling at 2 tokens/second
    bucket = TokenBucket(capacity=5, refill_rate=2.0)

    print(f"Initial tokens: {bucket.available()}")

    # Consume some tokens
    print(f"Consume 3 tokens: {bucket.consume(3)}")
    print(f"Remaining tokens: {bucket.available()}")

    # Try to consume more than available
    print(f"Try to consume 5 tokens: {bucket.consume(5)}")
    print(f"Remaining tokens: {bucket.available()}")

    # Check when tokens will be available
    print(f"Seconds until 3 tokens available: {bucket.until_available(3):.2f}")

    # Demonstrate serialization
    state = bucket.to_dict()
    print(f"Serialized state: {state}")

    # Restore from state
    restored_bucket = TokenBucket.from_dict(state)
    print(f"Restored bucket tokens: {restored_bucket.available()}")

    # Demonstrate deadline-based consumption
    deadline = time.monotonic() + 1.0  # 1 second from now
    will_have_tokens = bucket.try_consume_by(deadline, 3)
    print(f"Will have 3 tokens within 1 second: {will_have_tokens}")

    print("\nExample completed!")


if __name__ == "__main__":
    main()
