"""Unified Memory Manager — facade for the 3-tier memory system.

The MemoryManager provides a single entry point to all memory tiers:
  - Short-Term (Redis): Session context, chat history, velocity tracking
  - Long-Term (NeonDB): Merchant profiles, learned fraud patterns
  - Episodic (NeonDB + vectors): Investigation episode recall

Agents use the MemoryManager to read and write memories without
needing to know which tier stores what.
"""

import logging
from typing import Any, Optional

from app.infrastructure.neondb import NeonDbClient
from app.infrastructure.redis_client import RedisClient
from app.infrastructure.llm_client import LLMClient
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.memory.episodic import EpisodicMemory
from app.models import (
    FraudType,
    InvestigationEpisode,
    InvestigationOutcome,
    MerchantRiskProfile,
)
from app.config import get_settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Unified facade for the 3-tier memory system.

    Usage:
        memory = MemoryManager(neondb, redis, llm)
        await memory.initialize()

        # Short-term
        await memory.short_term.store_session_context(session, "key", value)

        # Long-term
        profile = await memory.long_term.get_merchant_profile("M123")

        # Episodic
        episodes = await memory.episodic.recall_similar_episodes("card testing pattern")

        # Convenience methods
        context = await memory.build_agent_context(session_id, merchant_id)
    """

    def __init__(
        self,
        neondb_client: NeonDbClient,
        redis_client: RedisClient,
        llm_client: LLMClient,
    ):
        settings = get_settings()
        self.short_term = ShortTermMemory(redis_client, settings.short_term_memory_ttl)
        self.long_term = LongTermMemory(neondb_client)
        self.episodic = EpisodicMemory(neondb_client, llm_client)

    async def initialize(self) -> None:
        """Initialize all memory tier storage."""
        await self.long_term.initialize_tables()
        await self.episodic.initialize_table()
        logger.info("All memory tiers initialized")

    # ── Convenience Methods ───────────────────────────────────────────

    async def build_agent_context(
        self,
        session_id: str,
        merchant_id: Optional[str] = None,
        situation_description: Optional[str] = None,
        exclude_exact_transaction_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Build a comprehensive context object for an agent by pulling
        from all three memory tiers.

        This is the primary method agents use to gather context before
        making decisions.

        Args:
            session_id: Current session identifier.
            merchant_id: Merchant being analyzed (if known).
            situation_description: Current situation for episodic recall.

        Returns:
            Dictionary with context from all memory tiers.
        """
        context: dict[str, Any] = {
            "session_id": session_id,
            "short_term": {},
            "long_term": {},
            "episodic": [],
        }

        # Short-term: chat history and any prior agent results
        context["short_term"]["chat_history"] = (
            await self.short_term.get_chat_history(session_id, last_n=10)
        )
        context["short_term"]["agent_results"] = (
            await self.short_term.get_all_agent_results(session_id)
        )

        # Long-term: merchant profile if we have a merchant
        if merchant_id:
            profile = await self.long_term.get_merchant_profile(merchant_id)
            if profile:
                context["long_term"]["merchant_profile"] = profile.model_dump()

        # Episodic: recall similar past investigations
        if situation_description:
            episodes = await self.episodic.recall_similar_episodes(
                situation_description, top_k=3
            )
            if exclude_exact_transaction_id:
                txid = exclude_exact_transaction_id.lower()
                episodes = [
                    ep for ep in episodes
                    if txid not in (ep.get("content", "") or "").lower()
                ]
            context["episodic"] = episodes

        return context

    async def record_investigation_complete(
        self,
        session_id: str,
        episode: InvestigationEpisode,
        merchant_profile_update: Optional[MerchantRiskProfile] = None,
        risk_score: int = 0,
    ) -> None:
        """
        Record the completion of an investigation across all memory tiers.

        This is called at the end of an analysis cycle to persist
        learnings across all tiers.
        """
        # Episodic: record the full episode
        await self.episodic.record_episode(episode)

        # Long-term: update merchant profile if provided
        if merchant_profile_update:
            await self.long_term.store_merchant_profile(merchant_profile_update)

        # Long-term: record the decision for feedback loop
        await self.long_term.record_decision(
            decision_id=episode.episode_id,
            merchant_id=episode.merchant_id,
            transaction_ids=episode.transaction_ids,
            fraud_type=episode.fraud_type,
            risk_score=risk_score,
            decision=episode.outcome.value,
        )

        # Short-term: clear the session to free Redis memory
        await self.short_term.clear_session(session_id)

        logger.info(
            "Investigation complete: episode=%s, merchant=%s",
            episode.episode_id, episode.merchant_id,
        )
