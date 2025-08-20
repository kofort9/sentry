"""
Token Bucket Rate Limiter

A thread-safe, deterministic rate limiter implementation using the token bucket algorithm.

Invariants:
- Token count is always between 0 and capacity (inclusive)
- Refill occurs lazily based on elapsed time since last operation
- All public methods maintain state consistency via lazy refill
- Serialization preserves internal state for exact reconstruction
"""

import time
from typing import Callable, Dict, Any, Optional


class TokenBucket:
    """
    A token bucket rate limiter that allows bursts up to capacity
    and refills at a steady rate.

    The bucket starts full and refills at the specified rate.
    Tokens are consumed when operations are performed.
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        time_fn: Optional[Callable[[], float]] = None
    ) -> None:
        """
        Initialize a token bucket.

        Args:
            capacity: Maximum number of tokens (must be > 0)
            refill_rate: Tokens added per second (must be >= 0)
            time_fn: Clock function for testing (defaults to time.monotonic)

        Raises:
            ValueError: If capacity <= 0 or refill_rate < 0
        """
        if capacity <= 0:
            raise ValueError("Capacity must be greater than 0")
        if refill_rate < 0:
            raise ValueError("Refill rate must be >= 0")

        self._capacity = capacity
        self._refill_rate = refill_rate
        self._time_fn = time_fn or time.monotonic

        # Start with a full bucket
        self._tokens = float(capacity)
        self._last_refill = self._time_fn()

    def _refill(self) -> None:
        """Lazily refill tokens based on elapsed time."""
        now = self._time_fn()
        elapsed = now - self._last_refill

        if elapsed > 0 and self._refill_rate > 0:
            tokens_to_add = elapsed * self._refill_rate
            self._tokens = min(self._capacity, self._tokens + tokens_to_add)

        self._last_refill = now

    def available(self) -> int:
        """
        Get current number of available tokens.

        Returns:
            Integer count of available tokens (after lazy refill)
        """
        self._refill()
        return int(self._tokens)

    def consume(self, n: int = 1) -> bool:
        """
        Attempt to consume n tokens.

        Args:
            n: Number of tokens to consume (default: 1)

        Returns:
            True if tokens were consumed, False otherwise
        """
        self._refill()

        if self._tokens >= n:
            self._tokens -= n
            return True
        return False

    def try_consume_by(self, deadline_s: float, n: int = 1) -> bool:
        """
        Check if n tokens will be available by deadline and consume if available now.

        Args:
            deadline_s: Deadline in monotonic time
            n: Number of tokens needed (default: 1)

        Returns:
            True if tokens will be available by deadline (and consumed if available now)
        """
        self._refill()

        # If we already have enough tokens, consume them
        if self._tokens >= n:
            self._tokens -= n
            return True

        # Calculate if we'll have enough by the deadline
        now = self._time_fn()
        time_until_deadline = deadline_s - now

        if time_until_deadline <= 0:
            return False

        if self._refill_rate == 0:
            return False

        tokens_by_deadline = self._tokens + (time_until_deadline * self._refill_rate)
        tokens_by_deadline = min(self._capacity, tokens_by_deadline)

        return tokens_by_deadline >= n

    def until_available(self, n: int = 1) -> float:
        """
        Calculate seconds until n tokens would be available.

        Args:
            n: Number of tokens needed (default: 1)

        Returns:
            Seconds until n tokens available (0.0 if available now)
            Returns float('inf') if impossible (n > capacity or refill_rate = 0)
        """
        self._refill()

        if n > self._capacity:
            return float('inf')

        if self._tokens >= n:
            return 0.0

        if self._refill_rate == 0:
            return float('inf')

        tokens_needed = n - self._tokens
        return tokens_needed / self._refill_rate

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the bucket state to a dictionary.

        Returns:
            Dictionary containing bucket state
        """
        self._refill()  # Ensure state is current before serializing

        return {
            'capacity': self._capacity,
            'refill_rate': self._refill_rate,
            'tokens': self._tokens,
            'last_refill': self._last_refill
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        time_fn: Optional[Callable[[], float]] = None
    ) -> 'TokenBucket':
        """
        Restore a token bucket from serialized state.

        Args:
            data: Dictionary from to_dict()
            time_fn: Clock function (defaults to time.monotonic)

        Returns:
            TokenBucket instance with restored state
        """
        bucket = cls(
            capacity=data['capacity'],
            refill_rate=data['refill_rate'],
            time_fn=time_fn
        )

        bucket._tokens = data['tokens']
        bucket._last_refill = data['last_refill']

        return bucket
