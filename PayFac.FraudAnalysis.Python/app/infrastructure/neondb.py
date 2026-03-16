"""NeonDB (PostgreSQL + pgvector) connection and operations."""

import json
import logging
from typing import Any, Optional

import asyncpg
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


class NeonDbClient:
    """
    Manages connections and vector operations against NeonDB (PostgreSQL + pgvector).

    NeonDB is serverless PostgreSQL with native pgvector support.
    We use it for:
      - Long-term memory (merchant profiles, learned fraud patterns)
      - Episodic memory (investigation episodes with vector embeddings)
      - Vector search across synthetic transactions and compliance docs
    """

    def __init__(self, connection_string: Optional[str] = None):
        self._connection_string = connection_string or get_settings().neondb_connection_string
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Initialize the connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._connection_string,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            # Ensure pgvector extension is available
            async with self._pool.acquire() as conn:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info("NeonDB connection pool initialized")

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def vector_search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        min_score: float = 0.75,
        metadata_filter: Optional[dict[str, str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Perform cosine similarity search against a vector collection.

        Args:
            collection: Table name containing vectors.
            query_embedding: The query vector.
            top_k: Maximum results to return.
            min_score: Minimum cosine similarity threshold (0.0-1.0).
            metadata_filter: Optional key-value filters on metadata JSONB column.

        Returns:
            List of matching records with id, content, metadata, and similarity score.
        """
        if not self._pool:
            await self.connect()

        # Build metadata filter clauses
        filter_clauses = []
        filter_params = []
        param_idx = 3  # $1=embedding, $2=min_score, $3=top_k

        if metadata_filter:
            for key, value in metadata_filter.items():
                param_idx += 1
                filter_clauses.append(f"metadata->>'{key}' = ${param_idx}")
                filter_params.append(value)

        where_clause = " AND ".join(filter_clauses) if filter_clauses else "TRUE"

        query = f"""
            SELECT
                id,
                content,
                metadata,
                1 - (embedding <=> $1::vector) AS score
            FROM {collection}
            WHERE {where_clause}
              AND 1 - (embedding <=> $1::vector) >= $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                embedding_str,
                min_score,
                top_k,
                *filter_params,
            )

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"],
                "score": float(row["score"]),
            })

        logger.debug(
            "Vector search on '%s': query_len=%d, results=%d",
            collection, len(query_embedding), len(results),
        )
        return results

    async def upsert_vector(
        self,
        collection: str,
        record_id: str,
        embedding: list[float],
        content: str,
        metadata: dict[str, Any],
    ) -> None:
        """
        Insert or update a vector record.

        Args:
            collection: Target table name.
            record_id: Unique record identifier.
            embedding: Vector embedding.
            content: Text content associated with the vector.
            metadata: JSONB metadata.
        """
        if not self._pool:
            await self.connect()

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        metadata_json = json.dumps(metadata)

        query = f"""
            INSERT INTO {collection} (id, embedding, content, metadata)
            VALUES ($1, $2::vector, $3, $4::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                content = EXCLUDED.content,
                metadata = EXCLUDED.metadata
        """

        async with self._pool.acquire() as conn:
            await conn.execute(query, record_id, embedding_str, content, metadata_json)

        logger.debug("Upserted vector record '%s' in '%s'", record_id, collection)

    async def execute_query(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a raw SQL query and return results."""
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute_command(self, query: str, *args: Any) -> str:
        """Execute a raw SQL command (INSERT/UPDATE/DELETE)."""
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)
