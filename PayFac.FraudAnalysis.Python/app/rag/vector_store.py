"""NeonDB vector store integration for RAG.

Provides typed search methods across the three vector collections:
  - synthetic_transactions: Historical transaction data for pattern matching
  - compliance_documents: Card brand rules and compliance documentation
  - fraud_patterns: Known fraud pattern signatures
"""

import logging
from typing import Any, Optional

from app.infrastructure.neondb import NeonDbClient
from app.infrastructure.llm_client import LLMClient

logger = logging.getLogger(__name__)


class VectorStore:
    """
    High-level vector store operations over NeonDB collections.

    Wraps the raw NeonDbClient with collection-aware methods and
    automatic embedding generation.
    """

    # Collection names (tables in NeonDB)
    TRANSACTIONS = "synthetic_transactions"
    COMPLIANCE = "compliance_documents"
    FRAUD_PATTERNS = "fraud_patterns"

    def __init__(self, neondb_client: NeonDbClient, llm_client: LLMClient):
        self._db = neondb_client
        self._llm = llm_client

    async def initialize_collections(self) -> None:
        """Create vector tables if they don't exist."""
        for collection in [self.TRANSACTIONS, self.COMPLIANCE, self.FRAUD_PATTERNS]:
            await self._db.execute_command(f"""
                CREATE TABLE IF NOT EXISTS {collection} (
                    id TEXT PRIMARY KEY,
                    embedding vector(1536),
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}'
                )
            """)
            await self._db.execute_command(f"""
                CREATE INDEX IF NOT EXISTS idx_{collection}_embedding
                ON {collection}
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
        logger.info("Vector store collections initialized")

    # ── Transaction Search ────────────────────────────────────────────

    async def search_similar_transactions(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.75,
        merchant_id: Optional[str] = None,
        card_brand: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Search for historically similar transactions.

        Used by the Fraud Detection Agent to find past transactions
        that match a suspected fraud pattern.

        Args:
            query: Natural language description of the pattern to search.
            top_k: Maximum results.
            min_score: Minimum cosine similarity.
            merchant_id: Optional filter by merchant.
            card_brand: Optional filter by card brand.
        """
        embedding = await self._llm.generate_embedding(query)

        metadata_filter = {}
        if merchant_id:
            metadata_filter["merchant_id"] = merchant_id
        if card_brand:
            metadata_filter["card_brand"] = card_brand

        results = await self._db.vector_search(
            collection=self.TRANSACTIONS,
            query_embedding=embedding,
            top_k=top_k,
            min_score=min_score,
            metadata_filter=metadata_filter or None,
        )

        logger.info(
            "Transaction search: query='%s...', results=%d",
            query[:60], len(results),
        )
        return results

    # ── Compliance Document Search ────────────────────────────────────

    async def search_compliance_docs(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.7,
        card_brand: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Search card brand compliance documents.

        Used by the Compliance Agent to retrieve relevant rules
        for Visa VDMP, Mastercard ECM, etc.

        Args:
            query: Compliance topic to search (e.g., "Visa chargeback thresholds").
            top_k: Maximum document chunks to return.
            min_score: Minimum similarity.
            card_brand: Filter by card brand ('visa', 'mastercard', 'amex').
        """
        embedding = await self._llm.generate_embedding(query)

        metadata_filter = None
        if card_brand and card_brand.lower() != "all":
            metadata_filter = {"card_brand": card_brand.lower()}

        results = await self._db.vector_search(
            collection=self.COMPLIANCE,
            query_embedding=embedding,
            top_k=top_k,
            min_score=min_score,
            metadata_filter=metadata_filter,
        )

        logger.info(
            "Compliance search: query='%s...', brand=%s, results=%d",
            query[:60], card_brand or "all", len(results),
        )
        return results

    # ── Fraud Pattern Search ──────────────────────────────────────────

    async def search_fraud_patterns(
        self,
        pattern_description: str,
        top_k: int = 5,
        min_score: float = 0.7,
        fraud_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Search known fraud pattern signatures.

        Used by agents to verify suspected fraud against known patterns.

        Args:
            pattern_description: Description of the suspected pattern.
            top_k: Maximum patterns to return.
            min_score: Minimum similarity.
            fraud_type: Filter by specific fraud type.
        """
        embedding = await self._llm.generate_embedding(pattern_description)

        metadata_filter = None
        if fraud_type and fraud_type != "any":
            metadata_filter = {"fraud_type": fraud_type}

        results = await self._db.vector_search(
            collection=self.FRAUD_PATTERNS,
            query_embedding=embedding,
            top_k=top_k,
            min_score=min_score,
            metadata_filter=metadata_filter,
        )

        logger.info(
            "Fraud pattern search: desc='%s...', type=%s, results=%d",
            pattern_description[:60], fraud_type or "any", len(results),
        )
        return results

    # ── Ingest Methods (for loading data) ─────────────────────────────

    async def ingest_transaction(
        self,
        transaction_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        """Ingest a transaction record into the vector store."""
        embedding = await self._llm.generate_embedding(text)
        await self._db.upsert_vector(
            self.TRANSACTIONS, transaction_id, embedding, text, metadata,
        )

    async def ingest_compliance_doc(
        self,
        chunk_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        """Ingest a compliance document chunk into the vector store."""
        embedding = await self._llm.generate_embedding(text)
        await self._db.upsert_vector(
            self.COMPLIANCE, chunk_id, embedding, text, metadata,
        )

    async def ingest_fraud_pattern(
        self,
        pattern_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        """Ingest a fraud pattern into the vector store."""
        embedding = await self._llm.generate_embedding(text)
        await self._db.upsert_vector(
            self.FRAUD_PATTERNS, pattern_id, embedding, text, metadata,
        )
