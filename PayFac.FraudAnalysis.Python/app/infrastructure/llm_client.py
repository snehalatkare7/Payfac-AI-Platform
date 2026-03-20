"""LLM and embedding client using SentenceTransformer (all-MiniLM-L6-v2).

This client provides:
  - Chat completion model for agent reasoning (OpenAI)
  - Local embedding model for vector operations (SentenceTransformer)
"""

import logging
from typing import Optional

from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global model instance (cached)
_EMBEDDING_MODEL: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model (singleton pattern)."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        logger.info("Loading all-MiniLM-L6-v2 embedding model...")
        _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("✅ Embedding model loaded: all-MiniLM-L6-v2 (384 dimensions)")
    return _EMBEDDING_MODEL


class LLMClient:
    """
    Factory for OpenAI LLM and SentenceTransformer embedding models.

    Provides:
      - Chat completion model for agent reasoning (OpenAI)
      - Embedding model for vector operations (SentenceTransformer: all-MiniLM-L6-v2)
    """

    def __init__(self):
        self._settings = get_settings()
        self._chat_model: Optional[ChatOpenAI] = None

    @property
    def chat_model(self) -> ChatOpenAI:
        """Get the chat completion model (lazy initialization)."""
        if self._chat_model is None:
            self._chat_model = ChatOpenAI(
                model=self._settings.openai_model,
                api_key=self._settings.openai_api_key,
                base_url=self._settings.openai_base_url,
                temperature=0.1,  # Low temperature for consistent fraud analysis
                max_tokens=4096,
            )
            logger.info("Chat model initialized: %s", self._settings.openai_model)
        return self._chat_model

    @property
    def embedding_model(self) -> SentenceTransformer:
        """Get the embedding model (lazy initialization)."""
        return get_embedding_model()

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a vector embedding for the given text (384 dimensions).
        
        Uses all-MiniLM-L6-v2 which produces normalized embeddings.
        """
        model = self.embedding_model
        # SentenceTransformer.encode returns numpy array
        embedding = model.encode(
            text,
            convert_to_tensor=False,
            normalize_embeddings=True  # L2 normalization for cosine similarity
        )
        return embedding.tolist()

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for multiple texts (384 dimensions each).
        
        Uses all-MiniLM-L6-v2 which produces normalized embeddings.
        """
        model = self.embedding_model
        embeddings = model.encode(
            texts,
            convert_to_tensor=False,
            normalize_embeddings=True,  # L2 normalization for cosine similarity
            batch_size=32,  # Process in batches for efficiency
        )
        return embeddings.tolist()