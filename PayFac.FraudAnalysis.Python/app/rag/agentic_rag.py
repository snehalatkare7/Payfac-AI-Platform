"""Agentic RAG — Agent-driven adaptive retrieval strategy.

Unlike standard RAG which retrieves everything upfront, Agentic RAG
lets the agent autonomously decide:
  - WHAT to retrieve (which collections, what queries)
  - WHEN to retrieve (based on confidence in current context)
  - WHETHER to iterate (retrieve more if results are insufficient)

This is implemented as LangChain tools that agents can invoke
during their reasoning process. The agent's chain-of-thought
drives the retrieval strategy.

Flow:
  1. Agent receives a task
  2. Agent decides it needs transaction data → calls search_transactions tool
  3. Agent evaluates results → decides it needs compliance docs too
  4. Agent calls search_compliance tool
  5. Agent evaluates sufficiency → confident enough to proceed
  6. Agent generates analysis with retrieved context
"""

import logging
from typing import Optional

from langchain_core.tools import tool

from app.rag.vector_store import VectorStore
from app.memory.manager import MemoryManager

logger = logging.getLogger(__name__)

# Module-level references set during initialization
_vector_store: Optional[VectorStore] = None
_memory: Optional[MemoryManager] = None


def init_agentic_rag(vector_store: VectorStore, memory: MemoryManager) -> None:
    """Initialize the agentic RAG module with dependencies."""
    global _vector_store, _memory
    _vector_store = vector_store
    _memory = memory


@tool
async def search_similar_transactions(
    query: str,
    min_score: float = 0.75,
    top_k: int = 10,
    merchant_id: str = "",
    card_brand: str = "",
) -> str:
    """Search for historically similar transactions that may indicate fraud patterns.

    Use this tool when you need to compare a current transaction against
    known fraud cases in the historical database. Provide a natural language
    description of the transaction pattern you're looking for.

    Args:
        query: Natural language description of the transaction pattern to search for.
        min_score: Minimum similarity threshold (0.0-1.0). Use 0.7 for broad, 0.9 for precise.
        top_k: Maximum number of results to return.
        merchant_id: Optional merchant ID to filter results.
        card_brand: Optional card brand filter (visa, mastercard, amex).
    """
    if not _vector_store:
        return "ERROR: Vector store not initialized."

    results = await _vector_store.search_similar_transactions(
        query=query,
        top_k=top_k,
        min_score=min_score,
        merchant_id=merchant_id or None,
        card_brand=card_brand or None,
    )

    if not results:
        return f"No similar transactions found for: '{query}' (min_score={min_score}). Consider lowering the similarity threshold or broadening the search query."

    formatted = [f"Found {len(results)} similar transactions:\n"]
    for i, r in enumerate(results, 1):
        formatted.append(
            f"{i}. [Similarity: {r['score']:.3f}] {r['content']}"
        )
    return "\n".join(formatted)


@tool
async def search_compliance_documents(
    query: str,
    card_brand: str = "all",
    top_k: int = 5,
) -> str:
    """Search card brand compliance documents (Visa, Mastercard, Amex rules).

    Use this tool when checking if a transaction or merchant pattern violates
    card brand rules. Search for specific programs like Visa VDMP, Mastercard
    ECM, chargeback thresholds, or merchant monitoring requirements.

    Args:
        query: The compliance topic to search for.
        card_brand: Filter by card brand: 'visa', 'mastercard', 'amex', or 'all'.
        top_k: Maximum number of document chunks to return.
    """
    if not _vector_store:
        return "ERROR: Vector store not initialized."

    results = await _vector_store.search_compliance_docs(
        query=query,
        card_brand=card_brand if card_brand != "all" else None,
        top_k=top_k,
    )

    if not results:
        return f"No compliance documents found for: '{query}' (brand={card_brand}). Try a broader search term."

    formatted = [f"Found {len(results)} compliance document chunks:\n"]
    for i, r in enumerate(results, 1):
        brand = r.get("metadata", {}).get("card_brand", "unknown")
        formatted.append(
            f"{i}. [{brand.upper()} | Score: {r['score']:.3f}] {r['content']}"
        )
    return "\n".join(formatted)


@tool
async def search_fraud_patterns(
    pattern_description: str,
    fraud_type: str = "any",
    top_k: int = 5,
) -> str:
    """Search known fraud pattern database for matching patterns.

    Use this tool when you suspect a specific fraud type and need to verify
    against known fraud signatures. Describe the pattern you're seeing.

    Args:
        pattern_description: Description of the suspected fraud pattern.
        fraud_type: Specific fraud type filter, or 'any' for all types.
        top_k: Maximum patterns to return.
    """
    if not _vector_store:
        return "ERROR: Vector store not initialized."

    results = await _vector_store.search_fraud_patterns(
        pattern_description=pattern_description,
        fraud_type=fraud_type if fraud_type != "any" else None,
        top_k=top_k,
    )

    if not results:
        return f"No matching fraud patterns found for: '{pattern_description}'. This could be a novel pattern."

    formatted = [f"Found {len(results)} matching fraud patterns:\n"]
    for i, r in enumerate(results, 1):
        ftype = r.get("metadata", {}).get("fraud_type", "unknown")
        formatted.append(
            f"{i}. [Type: {ftype} | Score: {r['score']:.3f}] {r['content']}"
        )
    return "\n".join(formatted)


@tool
async def recall_past_investigations(
    description: str,
    fraud_type: str = "",
    top_k: int = 3,
) -> str:
    """Recall similar past fraud investigations from episodic memory.

    Use this tool to leverage institutional knowledge — find past
    investigations that had similar characteristics and learn from
    their outcomes.

    Args:
        description: Description of the current situation to find similar episodes.
        fraud_type: Optional fraud type filter.
        top_k: Maximum episodes to recall.
    """
    if not _memory:
        return "ERROR: Memory not initialized."

    from app.models.enums import FraudType

    fraud_type_enum = None
    if fraud_type:
        try:
            fraud_type_enum = FraudType(fraud_type)
        except ValueError:
            pass

    episodes = await _memory.episodic.recall_similar_episodes(
        description=description,
        top_k=top_k,
        fraud_type_filter=fraud_type_enum,
    )

    if not episodes:
        return "No similar past investigations found in episodic memory."

    formatted = [f"Found {len(episodes)} similar past investigations:\n"]
    for i, ep in enumerate(episodes, 1):
        outcome = ep.get("metadata", {}).get("outcome", "unknown")
        formatted.append(
            f"{i}. [Outcome: {outcome} | Score: {ep['score']:.3f}] {ep['content']}"
        )
    return "\n".join(formatted)


@tool
async def get_merchant_history(merchant_id: str) -> str:
    """Retrieve the historical risk profile for a merchant from long-term memory.

    Use this tool to understand a merchant's fraud history, chargeback
    ratios, and known risk factors before making a determination.

    Args:
        merchant_id: The merchant identifier to look up.
    """
    if not _memory:
        return "ERROR: Memory not initialized."

    profile = await _memory.long_term.get_merchant_profile(merchant_id)
    if not profile:
        return f"No historical profile found for merchant {merchant_id}. This may be a new merchant."

    return (
        f"Merchant Profile for {profile.merchant_id}:\n"
        f"  Name: {profile.merchant_name}\n"
        f"  MCC: {profile.mcc}\n"
        f"  Historical fraud incidents: {profile.historical_fraud_count}\n"
        f"  Chargeback ratio: {profile.chargeback_ratio:.4f}\n"
        f"  Average risk score: {profile.average_risk_score:.1f}\n"
        f"  High risk flag: {profile.is_high_risk}\n"
        f"  Known fraud types: {[ft.value for ft in profile.known_fraud_types]}\n"
        f"  Last reviewed: {profile.last_review_date}\n"
        f"  Notes: {profile.notes}"
    )


@tool
async def check_velocity(
    merchant_id: str,
    window_minutes: int = 60,
) -> str:
    """Check transaction velocity for a merchant within a time window.

    Use this tool to detect velocity anomalies — unusually high
    transaction counts that may indicate card testing or fraud.

    Args:
        merchant_id: The merchant to check.
        window_minutes: Time window in minutes (default 60).
    """
    if not _memory:
        return "ERROR: Memory not initialized."

    count = await _memory.short_term.get_velocity_count(
        merchant_id=merchant_id,
        window_seconds=window_minutes * 60,
    )

    return (
        f"Velocity check for merchant {merchant_id}:\n"
        f"  Transactions in last {window_minutes} minutes: {count}\n"
        f"  Status: {'⚠️ HIGH VELOCITY' if count > 50 else '✅ Normal'}"
    )


@tool
async def evaluate_retrieval_sufficiency(
    similar_txn_count: int,
    compliance_doc_count: int,
    fraud_pattern_count: int,
    confidence: float,
) -> str:
    """Evaluate whether enough context has been retrieved to make a confident determination.

    Call this after performing retrieval to decide if more searches are needed.
    This implements the 'adaptive' part of Agentic RAG.

    Args:
        similar_txn_count: Number of similar transactions found.
        compliance_doc_count: Number of compliance docs retrieved.
        fraud_pattern_count: Number of fraud patterns matched.
        confidence: Your current confidence level (0.0-1.0).
    """
    is_sufficient = (
        confidence >= 0.8
        and similar_txn_count >= 3
        and (compliance_doc_count >= 1 or fraud_pattern_count >= 1)
    )

    if is_sufficient:
        return (
            "✅ SUFFICIENT CONTEXT: You have enough information to proceed with analysis.\n"
            f"  Transactions: {similar_txn_count}, Docs: {compliance_doc_count}, "
            f"Patterns: {fraud_pattern_count}, Confidence: {confidence:.2f}"
        )

    recommendations = []
    if similar_txn_count < 3:
        recommendations.append(
            "- Search for more similar transactions with a lower similarity threshold (try 0.6)"
        )
    if compliance_doc_count < 1:
        recommendations.append(
            "- Retrieve compliance documents related to the suspected violation"
        )
    if fraud_pattern_count < 1:
        recommendations.append(
            "- Search fraud patterns with a broader description"
        )
    if confidence < 0.8:
        recommendations.append(
            "- Consider retrieving merchant history and past investigation episodes"
        )

    return (
        "⚠️ INSUFFICIENT CONTEXT: More retrieval needed.\n"
        f"  Current: txns={similar_txn_count}, docs={compliance_doc_count}, "
        f"patterns={fraud_pattern_count}, confidence={confidence:.2f}\n"
        "Recommendations:\n" + "\n".join(recommendations)
    )


def get_agentic_rag_tools() -> list:
    """Return all Agentic RAG tools for agent registration."""
    return [
        search_similar_transactions,
        search_compliance_documents,
        search_fraud_patterns,
        recall_past_investigations,
        get_merchant_history,
        check_velocity,
        evaluate_retrieval_sufficiency,
    ]
