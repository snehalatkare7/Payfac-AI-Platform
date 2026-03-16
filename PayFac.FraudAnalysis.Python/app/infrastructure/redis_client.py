"""Redis client for short-term memory and caching."""

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Async Redis client used for:
      - Short-term memory (session/conversation context)
      - Agent state caching
      - Rate limiting / velocity tracking
      - Pub/Sub for real-time agent notifications
    """

    def __init__(self, redis_url: Optional[str] = None):
        settings = get_settings()
        self._redis_url = redis_url or settings.redis_url
        self._password = settings.redis_password or None
        self._client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self._client is None:
            self._client = aioredis.from_url(
                self._redis_url,
                password=self._password,
                decode_responses=True,
                max_connections=20,
            )
            # Verify connection
            await self._client.ping()
            logger.info("Redis connection established")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        """Get the underlying Redis client."""
        if self._client is None:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    # ── Key-Value Operations ──────────────────────────────────────────

    async def set_json(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store a JSON-serializable value with optional TTL."""
        serialized = json.dumps(value, default=str)
        if ttl_seconds:
            await self.client.setex(key, ttl_seconds, serialized)
        else:
            await self.client.set(key, serialized)

    async def get_json(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize a JSON value."""
        raw = await self.client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def delete(self, key: str) -> None:
        """Delete a key."""
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return bool(await self.client.exists(key))

    # ── List Operations (for conversation history) ────────────────────

    async def append_to_list(self, key: str, value: Any, max_length: int = 100) -> None:
        """Append to a list with max length cap (FIFO eviction)."""
        serialized = json.dumps(value, default=str)
        pipe = self.client.pipeline()
        pipe.rpush(key, serialized)
        pipe.ltrim(key, -max_length, -1)
        await pipe.execute()

    async def get_list(self, key: str, start: int = 0, end: int = -1) -> list[Any]:
        """Retrieve list elements."""
        raw_items = await self.client.lrange(key, start, end)
        return [json.loads(item) for item in raw_items]

    # ── Hash Operations (for structured agent state) ──────────────────

    async def set_hash(self, key: str, mapping: dict[str, Any]) -> None:
        """Store a hash map."""
        serialized = {k: json.dumps(v, default=str) for k, v in mapping.items()}
        await self.client.hset(key, mapping=serialized)

    async def get_hash(self, key: str) -> dict[str, Any]:
        """Retrieve all fields from a hash."""
        raw = await self.client.hgetall(key)
        return {k: json.loads(v) for k, v in raw.items()}

    # ── Sorted Set (for velocity tracking) ────────────────────────────

    async def add_to_sorted_set(self, key: str, member: str, score: float) -> None:
        """Add member to sorted set with score (typically timestamp)."""
        await self.client.zadd(key, {member: score})

    async def count_in_window(self, key: str, min_score: float, max_score: float) -> int:
        """Count members in a score range (time window for velocity checks)."""
        return await self.client.zcount(key, min_score, max_score)

    async def get_sorted_set_range(
        self, key: str, start: int = 0, end: int = -1
    ) -> list[str]:
        """Get members from sorted set by rank."""
        return await self.client.zrange(key, start, end)

    # ── Pattern Operations ────────────────────────────────────────────

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Returns count deleted."""
        count = 0
        async for key in self.client.scan_iter(match=pattern):
            await self.client.delete(key)
            count += 1
        return count
