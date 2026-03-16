"""Short-term memory backed by Redis.

Short-term memory is session-scoped and ephemeral. It stores:
  - Current conversation context and chat history
  - Active investigation state within a session
  - Intermediate agent results during multi-agent orchestration
  - Velocity tracking data for real-time checks

All entries have a TTL and are automatically evicted by Redis.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from app.infrastructure.redis_client import RedisClient

logger = logging.getLogger(__name__)

# Redis key prefixes for organization
_PREFIX_SESSION = "stm:session"
_PREFIX_CHAT = "stm:chat"
_PREFIX_AGENT_STATE = "stm:agent"
_PREFIX_VELOCITY = "stm:velocity"


class ShortTermMemory:
    """
    Redis-backed short-term memory for active session context.

    Design:
      - All keys are namespaced with prefixes for isolation
      - TTL ensures automatic cleanup of stale data
      - Sorted sets enable time-windowed velocity checks
      - Lists maintain ordered conversation history
    """

    def __init__(self, redis_client: RedisClient, default_ttl: int = 3600):
        self._redis = redis_client
        self._default_ttl = default_ttl

    # ── Session Context ───────────────────────────────────────────────

    async def store_session_context(
        self,
        session_id: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Store a value in the session context.

        Args:
            session_id: Unique session identifier.
            key: Context key (e.g., 'current_merchant', 'analysis_stage').
            value: Any JSON-serializable value.
            ttl: Time-to-live in seconds (defaults to 1 hour).
        """
        redis_key = f"{_PREFIX_SESSION}:{session_id}:{key}"
        await self._redis.set_json(redis_key, value, ttl or self._default_ttl)
        logger.debug("Stored session context: %s/%s", session_id, key)

    async def get_session_context(self, session_id: str, key: str) -> Optional[Any]:
        """Retrieve a value from session context."""
        redis_key = f"{_PREFIX_SESSION}:{session_id}:{key}"
        return await self._redis.get_json(redis_key)

    async def clear_session(self, session_id: str) -> int:
        """Clear all data for a session. Returns count of keys deleted."""
        count = await self._redis.delete_pattern(f"{_PREFIX_SESSION}:{session_id}:*")
        count += await self._redis.delete_pattern(f"{_PREFIX_CHAT}:{session_id}:*")
        count += await self._redis.delete_pattern(f"{_PREFIX_AGENT_STATE}:{session_id}:*")
        logger.info("Cleared session '%s': %d keys deleted", session_id, count)
        return count

    # ── Chat History ──────────────────────────────────────────────────

    async def add_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_name: Optional[str] = None,
    ) -> None:
        """
        Append a message to the conversation history.

        Args:
            session_id: Session identifier.
            role: Message role ('user', 'assistant', 'system', 'agent').
            content: Message content.
            agent_name: Name of the agent (if role is 'agent').
        """
        message = {
            "role": role,
            "content": content,
            "agent_name": agent_name,
            "timestamp": datetime.utcnow().isoformat(),
        }
        redis_key = f"{_PREFIX_CHAT}:{session_id}:history"
        await self._redis.append_to_list(redis_key, message, max_length=50)

    async def get_chat_history(
        self, session_id: str, last_n: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve conversation history.

        Args:
            session_id: Session identifier.
            last_n: If provided, return only the last N messages.
        """
        redis_key = f"{_PREFIX_CHAT}:{session_id}:history"
        if last_n:
            return await self._redis.get_list(redis_key, -last_n, -1)
        return await self._redis.get_list(redis_key)

    # ── Agent State (inter-agent communication within a session) ──────

    async def store_agent_result(
        self,
        session_id: str,
        agent_name: str,
        result: dict[str, Any],
    ) -> None:
        """
        Store an agent's intermediate result for other agents to consume.

        This enables agent-to-agent data sharing within a single
        orchestration cycle without going through Kafka.
        """
        redis_key = f"{_PREFIX_AGENT_STATE}:{session_id}:{agent_name}"
        await self._redis.set_json(redis_key, result, self._default_ttl)
        logger.debug(
            "Stored agent result: session=%s, agent=%s", session_id, agent_name
        )

    async def get_agent_result(
        self, session_id: str, agent_name: str
    ) -> Optional[dict[str, Any]]:
        """Retrieve another agent's result from the current session."""
        redis_key = f"{_PREFIX_AGENT_STATE}:{session_id}:{agent_name}"
        return await self._redis.get_json(redis_key)

    async def get_all_agent_results(self, session_id: str) -> dict[str, Any]:
        """Retrieve all agent results for the current session."""
        results = {}
        # Check for each known agent type
        for agent in ["fraud_detection", "compliance", "risk_scoring", "investigation"]:
            result = await self.get_agent_result(session_id, agent)
            if result:
                results[agent] = result
        return results

    # ── Velocity Tracking ─────────────────────────────────────────────

    async def record_transaction_event(
        self,
        merchant_id: str,
        transaction_id: str,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Record a transaction event for velocity checking.

        Uses Redis sorted sets with timestamp as score for efficient
        time-window counting.
        """
        ts = timestamp or datetime.utcnow().timestamp()
        redis_key = f"{_PREFIX_VELOCITY}:merchant:{merchant_id}"
        await self._redis.add_to_sorted_set(redis_key, transaction_id, ts)

    async def get_velocity_count(
        self,
        merchant_id: str,
        window_seconds: int = 3600,
    ) -> int:
        """
        Count transactions for a merchant within a time window.

        Args:
            merchant_id: Merchant to check.
            window_seconds: Lookback window in seconds (default 1 hour).

        Returns:
            Number of transactions in the window.
        """
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds
        redis_key = f"{_PREFIX_VELOCITY}:merchant:{merchant_id}"
        return await self._redis.count_in_window(redis_key, window_start, now)

    async def record_card_event(
        self,
        card_bin: str,
        transaction_id: str,
        timestamp: Optional[float] = None,
    ) -> None:
        """Record a card BIN event for BIN attack detection."""
        ts = timestamp or datetime.utcnow().timestamp()
        redis_key = f"{_PREFIX_VELOCITY}:bin:{card_bin}"
        await self._redis.add_to_sorted_set(redis_key, transaction_id, ts)

    async def get_bin_velocity(self, card_bin: str, window_seconds: int = 300) -> int:
        """Count transactions for a BIN within a time window (default 5 min)."""
        now = datetime.utcnow().timestamp()
        redis_key = f"{_PREFIX_VELOCITY}:bin:{card_bin}"
        return await self._redis.count_in_window(redis_key, now - window_seconds, now)
