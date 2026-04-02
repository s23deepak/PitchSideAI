"""
Concurrency management and rate limiting.
"""
import asyncio
import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    burst_size: int = 10
    timeout_seconds: int = 10


class TokenBucket:
    """Token bucket algorithm for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in the bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        async with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary."""
        async with self.lock:
            while self.tokens < tokens:
                self._refill()
                if self.tokens < tokens:
                    # Calculate wait time
                    wait_time = (tokens - self.tokens) / self.refill_rate
                    await asyncio.sleep(min(wait_time, 0.1))

            self.tokens -= tokens

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_refill = now


class RateLimiter:
    """Rate limiter for API endpoints."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.buckets: Dict[str, TokenBucket] = {}
        self.request_history: Dict[str, list[float]] = {}

        # Calculate tokens per second
        rpm = config.requests_per_minute
        tokens_per_second = rpm / 60.0

        self.bucket = TokenBucket(config.burst_size, tokens_per_second)

    async def check_rate_limit(self, client_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if request is within rate limits.
        Returns (allowed, error_message)
        """
        if client_id not in self.buckets:
            self.buckets[client_id] = TokenBucket(
                self.config.burst_size,
                self.config.requests_per_minute / 60.0
            )

        bucket = self.buckets[client_id]

        if await bucket.consume(1):
            return True, None
        else:
            return False, f"Rate limit exceeded ({self.config.requests_per_minute} req/min)"

    async def acquire_token(self, client_id: str) -> None:
        """Acquire a token, waiting if necessary."""
        if client_id not in self.buckets:
            self.buckets[client_id] = TokenBucket(
                self.config.burst_size,
                self.config.requests_per_minute / 60.0
            )

        await self.buckets[client_id].acquire(1)

    def get_remaining_tokens(self, client_id: str) -> int:
        """Get remaining tokens for a client."""
        if client_id not in self.buckets:
            return self.config.burst_size

        bucket = self.buckets[client_id]
        bucket._refill()
        return int(bucket.tokens)


class ConnectionPool:
    """Manages connection pools for better resource management."""

    def __init__(self, max_connections: int = 100, max_retries: int = 3):
        self.max_connections = max_connections
        self.max_retries = max_retries
        self.active_connections = 0
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(max_connections)

    async def acquire(self) -> None:
        """Acquire a connection slot."""
        await self.semaphore.acquire()
        async with self.lock:
            self.active_connections += 1

    async def release(self) -> None:
        """Release a connection slot."""
        async with self.lock:
            self.active_connections = max(0, self.active_connections - 1)
        self.semaphore.release()

    async def execute_with_retry(self, coro, max_retries: Optional[int] = None) -> any:
        """Execute a coroutine with automatic retry on failure."""
        max_retries = max_retries or self.max_retries
        last_error = None

        for attempt in range(max_retries):
            try:
                await self.acquire()
                result = await coro
                return result

            except Exception as exc:
                last_error = exc
                wait_time = (2 ** attempt)  # Exponential backoff
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {exc}")
                await asyncio.sleep(wait_time)

            finally:
                await self.release()

        raise last_error


class CircuitBreaker:
    """Circuit breaker pattern for handling failing services."""

    class State:
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.state = self.State.CLOSED
        self.last_failure_time: Optional[datetime] = None

    async def call(self, coro) -> any:
        """Execute a coroutine through the circuit breaker."""
        if self.state == self.State.OPEN:
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if elapsed > self.recovery_timeout:
                self.state = self.State.HALF_OPEN
                self.failure_count = 0
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await coro
            self._on_success()
            return result

        except self.expected_exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful execution."""
        self.failure_count = 0
        self.state = self.State.CLOSED

    def _on_failure(self) -> None:
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = self.State.OPEN


# Global instances
_rate_limiter: Optional[RateLimiter] = None
_connection_pool: Optional[ConnectionPool] = None


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """Get or create global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(config or RateLimitConfig())
    return _rate_limiter


def get_connection_pool(max_connections: int = 100) -> ConnectionPool:
    """Get or create global connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool(max_connections=max_connections)
    return _connection_pool
