"""Standard RAG retriever for augmenting agent prompts.

This module implements the classic RAG pattern:
  1. Receive a query
  2. Retrieve relevant context from vector stores
  3. Augment the LLM prompt with retrieved context
  4. Generate a response

Used as the baseline retrieval strategy. For adaptive/autonomous
retrieval, see agentic_rag.py.
"""

import logging
from typing import Any, Optional

from app.rag.vector_store import VectorStore
from app.memory.manager import MemoryManager

logger = logging.getLogger(__name__)


class FraudAnalysisRetriever:
    """
    Standard RAG retriever that gathers context from multiple sources
    and builds an augmented prompt for fraud analysis.

    Retrieval flow:
      1. Search similar transactions in vector DB
      2. Search relevant compliance documents
      3. Search known fraud patterns
      4. Pull merchant history from long-term memory
      5. Recall similar past episodes from episodic memory
      6. Combine into a structured context block
    """

    def __init__(self, vector_store: VectorStore, memory: MemoryManager):
        self._vector_store = vector_store
        self._memory = memory

    async def retrieve_context(
        self,
        query: str,
        session_id: str,
        merchant_id: Optional[str] = None,
        card_brand: Optional[str] = None,
        fraud_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Retrieve comprehensive context for fraud analysis.

        This is the standard RAG retrieval — gather everything potentially
        relevant and let the LLM decide what matters.

        Args:
            query: The analysis query or transaction description.
            session_id: Current session for short-term memory access.
            merchant_id: Merchant being analyzed.
            card_brand: Card brand for compliance doc filtering.
            fraud_type: Suspected fraud type for pattern filtering.

        Returns:
            Structured context dictionary with all retrieved information.
        """
        context: dict[str, Any] = {
            "similar_transactions": [],
            "compliance_docs": [],
            "fraud_patterns": [],
            "merchant_profile": None,
            "past_episodes": [],
            "chat_history": [],
        }

        # 1. Similar transactions from vector DB
        context["similar_transactions"] = (
            await self._vector_store.search_similar_transactions(
                query=query,
                top_k=10,
                merchant_id=merchant_id,
                card_brand=card_brand,
            )
        )

        # 2. Compliance documents
        if card_brand:
            context["compliance_docs"] = (
                await self._vector_store.search_compliance_docs(
                    query=query,
                    card_brand=card_brand,
                )
            )

        # 3. Known fraud patterns
        context["fraud_patterns"] = (
            await self._vector_store.search_fraud_patterns(
                pattern_description=query,
                fraud_type=fraud_type,
            )
        )

        # 4. Merchant profile from long-term memory
        if merchant_id:
            profile = await self._memory.long_term.get_merchant_profile(merchant_id)
            if profile:
                context["merchant_profile"] = profile.model_dump()

        # 5. Episodic memory — similar past investigations
        past_episodes = await self._memory.episodic.recall_similar_episodes(
            description=query, top_k=3
        )
        context["past_episodes"] = past_episodes

        # 6. Chat history from short-term memory
        context["chat_history"] = (
            await self._memory.short_term.get_chat_history(session_id, last_n=5)
        )

        logger.info(
            "RAG retrieval complete: txns=%d, docs=%d, patterns=%d, episodes=%d",
            len(context["similar_transactions"]),
            len(context["compliance_docs"]),
            len(context["fraud_patterns"]),
            len(context["past_episodes"]),
        )

        return context

    def format_context_for_prompt(self, context: dict[str, Any]) -> str:
        """
        Format retrieved context into a structured text block
        suitable for LLM prompt augmentation.
        """
        sections = []

        # Similar transactions
        if context["similar_transactions"]:
            txn_texts = []
            for i, txn in enumerate(context["similar_transactions"][:5], 1):
                txn_texts.append(
                    f"  {i}. [Score: {txn.get('score', 0):.2f}] {txn.get('content', '')}"
                )
            sections.append(
                "SIMILAR HISTORICAL TRANSACTIONS:\n" + "\n".join(txn_texts)
            )

        # Compliance docs
        if context["compliance_docs"]:
            doc_texts = []
            for i, doc in enumerate(context["compliance_docs"][:3], 1):
                doc_texts.append(
                    f"  {i}. [Score: {doc.get('score', 0):.2f}] {doc.get('content', '')}"
                )
            sections.append(
                "RELEVANT COMPLIANCE RULES:\n" + "\n".join(doc_texts)
            )

        # Fraud patterns
        if context["fraud_patterns"]:
            pattern_texts = []
            for i, pat in enumerate(context["fraud_patterns"][:3], 1):
                pattern_texts.append(
                    f"  {i}. [Score: {pat.get('score', 0):.2f}] {pat.get('content', '')}"
                )
            sections.append(
                "KNOWN FRAUD PATTERNS:\n" + "\n".join(pattern_texts)
            )

        # Merchant profile
        if context.get("merchant_profile"):
            mp = context["merchant_profile"]
            sections.append(
                f"MERCHANT PROFILE:\n"
                f"  Merchant: {mp.get('merchant_name', 'Unknown')} (ID: {mp.get('merchant_id', '')})\n"
                f"  MCC: {mp.get('mcc', 'N/A')}\n"
                f"  Historical fraud count: {mp.get('historical_fraud_count', 0)}\n"
                f"  Chargeback ratio: {mp.get('chargeback_ratio', 0):.4f}\n"
                f"  Average risk score: {mp.get('average_risk_score', 0):.1f}\n"
                f"  High risk: {mp.get('is_high_risk', False)}"
            )

        # Past episodes
        if context["past_episodes"]:
            ep_texts = []
            for i, ep in enumerate(context["past_episodes"][:3], 1):
                ep_texts.append(
                    f"  {i}. [Score: {ep.get('score', 0):.2f}] {ep.get('content', '')}"
                )
            sections.append(
                "SIMILAR PAST INVESTIGATIONS:\n" + "\n".join(ep_texts)
            )

        if not sections:
            return "No relevant context found in knowledge base."

        return "\n\n".join(sections)
