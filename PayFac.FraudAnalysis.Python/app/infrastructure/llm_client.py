"""OpenAI (non-Azure) LLM and embedding client."""

import logging
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Factory for OpenAI LLM and embedding models.

    Provides:
      - Chat completion model for agent reasoning
      - Embedding model for vector operations
    """

    def __init__(self):
        self._settings = get_settings()
        self._chat_model: Optional[ChatOpenAI] = None
        self._embedding_model: Optional[OpenAIEmbeddings] = None

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
    def embedding_model(self) -> OpenAIEmbeddings:
        """Get the embedding model (lazy initialization)."""
        if self._embedding_model is None:
            self._embedding_model = OpenAIEmbeddings(
                model=self._settings.openai_embedding_model,
                api_key=self._settings.openai_api_key,
                base_url=self._settings.openai_base_url,
            )
            logger.info(
                "Embedding model initialized: %s",
                self._settings.openai_embedding_model,
            )
        return self._embedding_model

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a vector embedding for the given text."""
        embeddings = await self.embedding_model.aembed_documents([text])
        return embeddings[0]

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for multiple texts."""
        return await self.embedding_model.aembed_documents(texts)
