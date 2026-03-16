"""Tests for the 3-tier memory system."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.memory.short_term import ShortTermMemory
from app.infrastructure.redis_client import RedisClient


class TestShortTermMemorySessionContext:
    """Tests for short-term memory session context operations."""

    @pytest.fixture
    def mock_redis(self):
        redis = MagicMock(spec=RedisClient)
        redis.set_json = AsyncMock()
        redis.get_json = AsyncMock()
        redis.delete_pattern = AsyncMock(return_value=0)
        redis.append_to_list = AsyncMock()
        redis.get_list = AsyncMock(return_value=[])
        redis.add_to_sorted_set = AsyncMock()
        redis.count_in_window = AsyncMock(return_value=0)
        return redis

    @pytest.fixture
    def memory(self, mock_redis):
        return ShortTermMemory(mock_redis, default_ttl=3600)

    @pytest.mark.asyncio
    async def test_store_session_context_uses_correct_key(self, memory, mock_redis):
        await memory.store_session_context("session-1", "merchant", "M001")
        mock_redis.set_json.assert_called_once_with(
            "stm:session:session-1:merchant", "M001", 3600
        )

    @pytest.mark.asyncio
    async def test_store_session_context_custom_ttl(self, memory, mock_redis):
        await memory.store_session_context("session-1", "key", "val", ttl=120)
        mock_redis.set_json.assert_called_once_with(
            "stm:session:session-1:key", "val", 120
        )

    @pytest.mark.asyncio
    async def test_get_session_context(self, memory, mock_redis):
        mock_redis.get_json.return_value = {"risk": "high"}
        result = await memory.get_session_context("session-1", "analysis")
        mock_redis.get_json.assert_called_once_with("stm:session:session-1:analysis")
        assert result == {"risk": "high"}

    @pytest.mark.asyncio
    async def test_get_session_context_missing_returns_none(self, memory, mock_redis):
        mock_redis.get_json.return_value = None
        result = await memory.get_session_context("session-1", "missing")
        assert result is None


class TestShortTermMemoryChatHistory:
    """Tests for chat history operations."""

    @pytest.fixture
    def mock_redis(self):
        redis = MagicMock(spec=RedisClient)
        redis.append_to_list = AsyncMock()
        redis.get_list = AsyncMock(return_value=[])
        return redis

    @pytest.fixture
    def memory(self, mock_redis):
        return ShortTermMemory(mock_redis)

    @pytest.mark.asyncio
    async def test_add_chat_message(self, memory, mock_redis):
        await memory.add_chat_message("s1", "user", "analyze this transaction")
        mock_redis.append_to_list.assert_called_once()
        call_args = mock_redis.append_to_list.call_args
        assert call_args[0][0] == "stm:chat:s1:history"
        message = call_args[0][1]
        assert message["role"] == "user"
        assert message["content"] == "analyze this transaction"

    @pytest.mark.asyncio
    async def test_add_chat_message_with_agent(self, memory, mock_redis):
        await memory.add_chat_message("s1", "agent", "fraud detected", "fraud_detection")
        call_args = mock_redis.append_to_list.call_args
        message = call_args[0][1]
        assert message["agent_name"] == "fraud_detection"

    @pytest.mark.asyncio
    async def test_get_chat_history_last_n(self, memory, mock_redis):
        mock_redis.get_list.return_value = [{"role": "user", "content": "test"}]
        result = await memory.get_chat_history("s1", last_n=5)
        mock_redis.get_list.assert_called_once_with("stm:chat:s1:history", -5, -1)


class TestShortTermMemoryVelocity:
    """Tests for velocity tracking operations."""

    @pytest.fixture
    def mock_redis(self):
        redis = MagicMock(spec=RedisClient)
        redis.add_to_sorted_set = AsyncMock()
        redis.count_in_window = AsyncMock(return_value=42)
        return redis

    @pytest.fixture
    def memory(self, mock_redis):
        return ShortTermMemory(mock_redis)

    @pytest.mark.asyncio
    async def test_record_transaction_event(self, memory, mock_redis):
        await memory.record_transaction_event("M001", "TXN001", timestamp=1000.0)
        mock_redis.add_to_sorted_set.assert_called_once_with(
            "stm:velocity:merchant:M001", "TXN001", 1000.0
        )

    @pytest.mark.asyncio
    async def test_get_velocity_count(self, memory, mock_redis):
        count = await memory.get_velocity_count("M001", window_seconds=300)
        assert count == 42
        mock_redis.count_in_window.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_card_bin_event(self, memory, mock_redis):
        await memory.record_card_event("411111", "TXN002", timestamp=2000.0)
        mock_redis.add_to_sorted_set.assert_called_once_with(
            "stm:velocity:bin:411111", "TXN002", 2000.0
        )
