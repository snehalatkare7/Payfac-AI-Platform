"""Episodic memory backed by NeonDB vector embeddings.

Episodic memory stores specific investigation episodes as narratives
with vector embeddings, enabling semantic recall of similar past
investigations. This is modeled after human episodic memory — the
ability to remember specific events and their contexts.

Key capabilities:
  - Record investigation episodes with full context
  - Semantic recall: "find investigations similar to this situation"
  - Outcome-based recall: "what happened when we saw this pattern before?"
  - Time-aware recall: recent episodes weighted more heavily
"""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.infrastructure.neondb import NeonDbClient
from app.infrastructure.llm_client import LLMClient
from app.models import InvestigationEpisode, FraudType, InvestigationOutcome

logger = logging.getLogger(__name__)

_COLLECTION = "episodic_memory"


class EpisodicMemory:
    """
    Vector-backed episodic memory for investigation narratives.

    Each episode is stored as:
      - A vector embedding of the narrative (for semantic search)
      - Full structured data (for reconstruction)
      - Metadata for filtered retrieval

    This enables agents to "remember" past investigations and use
    those experiences to inform current analysis.
    """

    def __init__(self, neondb_client: NeonDbClient, llm_client: LLMClient):
        self._db = neondb_client
        self._llm = llm_client

    async def initialize_table(self) -> None:
        """Create the episodic memory vector table."""
        await self._db.execute_command(f"""
            CREATE TABLE IF NOT EXISTS {_COLLECTION} (
                id TEXT PRIMARY KEY,
                embedding vector(1536),
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{{}}'
            )
        """)
        # Create vector index for fast similarity search
        await self._db.execute_command(f"""
            CREATE INDEX IF NOT EXISTS idx_{_COLLECTION}_embedding
            ON {_COLLECTION}
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        logger.info("Episodic memory table initialized")

    # ── Record Episodes ───────────────────────────────────────────────

    async def record_episode(self, episode: InvestigationEpisode) -> str:
        """
        Record a new investigation episode in episodic memory.

        The episode narrative is embedded and stored alongside structured
        metadata for both semantic and filtered retrieval.

        Returns:
            The episode ID.
        """
        narrative = episode.to_narrative()
        embedding = await self._llm.generate_embedding(narrative)

        metadata = {
            "merchant_id": episode.merchant_id,
            "fraud_type": episode.fraud_type.value,
            "outcome": episode.outcome.value,
            "agents_involved": episode.agents_involved,
            "transaction_count": len(episode.transaction_ids),
            "timestamp": episode.timestamp.isoformat(),
        }

        await self._db.upsert_vector(
            collection=_COLLECTION,
            record_id=episode.episode_id,
            embedding=embedding,
            content=narrative,
            metadata=metadata,
        )

        logger.info(
            "Recorded episode %s: %s fraud for merchant %s (outcome: %s)",
            episode.episode_id,
            episode.fraud_type.value,
            episode.merchant_id,
            episode.outcome.value,
        )
        return episode.episode_id

    # ── Recall Episodes ───────────────────────────────────────────────

    async def recall_similar_episodes(
        self,
        description: str,
        top_k: int = 5,
        min_score: float = 0.7,
        fraud_type_filter: Optional[FraudType] = None,
    ) -> list[dict]:
        """
        Semantically recall episodes similar to the given description.

        This is the core episodic memory capability — given a current
        situation description, find past episodes that are most similar.

        Args:
            description: Natural language description of current situation.
            top_k: Maximum episodes to recall.
            min_score: Minimum similarity threshold.
            fraud_type_filter: Optionally filter by fraud type.

        Returns:
            List of episode records with similarity scores.
        """
        embedding = await self._llm.generate_embedding(description)

        metadata_filter = None
        if fraud_type_filter:
            metadata_filter = {"fraud_type": fraud_type_filter.value}

        results = await self._db.vector_search(
            collection=_COLLECTION,
            query_embedding=embedding,
            top_k=top_k,
            min_score=min_score,
            metadata_filter=metadata_filter,
        )

        logger.debug(
            "Recalled %d episodes for: '%s...'",
            len(results), description[:80],
        )
        return results

    async def recall_by_merchant(
        self, merchant_id: str, top_k: int = 10
    ) -> list[dict]:
        """Recall all episodes for a specific merchant."""
        return await self._db.vector_search(
            collection=_COLLECTION,
            query_embedding=await self._llm.generate_embedding(
                f"Investigation history for merchant {merchant_id}"
            ),
            top_k=top_k,
            min_score=0.5,
            metadata_filter={"merchant_id": merchant_id},
        )

    async def recall_by_outcome(
        self,
        outcome: InvestigationOutcome,
        fraud_type: Optional[FraudType] = None,
        top_k: int = 10,
    ) -> list[dict]:
        """
        Recall episodes with a specific outcome.

        Useful for learning from past confirmed frauds or false positives.
        """
        query = f"Investigations with outcome {outcome.value}"
        if fraud_type:
            query += f" involving {fraud_type.value} fraud"

        metadata_filter = {"outcome": outcome.value}
        if fraud_type:
            metadata_filter["fraud_type"] = fraud_type.value

        return await self._db.vector_search(
            collection=_COLLECTION,
            query_embedding=await self._llm.generate_embedding(query),
            top_k=top_k,
            min_score=0.3,
            metadata_filter=metadata_filter,
        )

    # ── Retrieval Logging ─────────────────────────────────────────────

    async def record_retrieval_event(
        self,
        session_id: str,
        query: str,
        result_count: int,
        agent_name: str,
    ) -> None:
        """
        Log a retrieval event as a mini-episode for meta-learning.

        Tracks what agents search for and how many results they find,
        helping improve retrieval strategies over time.
        """
        episode = InvestigationEpisode(
            episode_id=f"retrieval-{uuid4()}",
            merchant_id=f"session:{session_id}",
            fraud_type=FraudType.CARD_TESTING,  # placeholder
            outcome=InvestigationOutcome.MONITORING,
            narrative=(
                f"Agent '{agent_name}' searched for: '{query}'. "
                f"Found {result_count} results."
            ),
            agents_involved=[agent_name],
            timestamp=datetime.utcnow(),
        )
        await self.record_episode(episode)
