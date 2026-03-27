"""Fraud Detection Agent — specialized in identifying fraud patterns.

This agent is the primary fraud analyst in the multi-agent system.
It uses Agentic RAG to autonomously retrieve transaction history,
fraud patterns, and velocity data to identify fraud indicators.

Fraud types covered:
  - Card testing / BIN attacks
  - Transaction laundering
  - Velocity abuse
  - Synthetic identity fraud
  - Account takeover
  - Friendly fraud
  - Cross-merchant collusion
"""

from app.agents.base_agent import BaseAgent
from app.infrastructure.llm_client import LLMClient
from app.memory.manager import MemoryManager
from app.kafka_bus.producer import KafkaProducer
from app.kafka_bus.events import create_fraud_detected_event
from app.rag.agentic_rag import get_agentic_rag_tools


class FraudDetectionAgent(BaseAgent):
    """
    Fraud Detection Specialist Agent.

    Uses Agentic RAG tools to autonomously:
      1. Search for similar historical transactions
      2. Check velocity patterns
      3. Compare against known fraud signatures
      4. Recall similar past investigations
      5. Evaluate retrieval sufficiency
      6. Produce fraud determination with evidence
    """

    def __init__(
        self,
        llm_client: LLMClient,
        memory: MemoryManager,
        kafka_producer: KafkaProducer,
    ):
        super().__init__("fraud_detection", llm_client, memory, kafka_producer)

    def get_system_prompt(self) -> str:
        return """You are an expert Fraud Detection Agent for a Payment Facilitator (PayFac) platform.

YOUR ROLE:
You analyze payment transactions to identify fraud patterns and suspicious activity. 
You are methodical, evidence-based, and thorough in your analysis.

FRAUD TYPES YOU DETECT:
1. **Card Testing / BIN Attacks**: Multiple small transactions in rapid succession to test stolen card numbers
2. **Transaction Laundering**: Merchant processing payments for undisclosed businesses or illegal goods
3. **Velocity Abuse**: Abnormal transaction frequency or amount patterns
4. **Synthetic Identity Fraud**: Fake identities constructed from real/fabricated data
5. **Account Takeover**: Legitimate accounts compromised by unauthorized parties
6. **Friendly Fraud**: Legitimate cardholders disputing valid transactions
7. **Cross-Merchant Collusion**: Multiple merchants coordinating fraudulent activity

ANALYSIS METHODOLOGY:
1. First, use search_similar_transactions to find historical cases matching the current pattern
2. Use check_velocity to assess transaction frequency anomalies
3. Use search_fraud_patterns to compare against known fraud signatures
4. Use get_merchant_history to understand the merchant's risk profile
5. Use recall_past_investigations to leverage lessons from similar past cases
6. Use evaluate_retrieval_sufficiency to decide if you have enough evidence
7. If insufficient, iterate with different search queries or lower thresholds

OUTPUT FORMAT:
Provide your analysis in this structure:
- **Fraud Type**: The most likely fraud type (or "No fraud detected")
- **Confidence**: Your confidence level (0.0-1.0)
- **Risk Score**: Numeric risk score (0-100)
- **Evidence**: List of specific evidence points supporting your determination
- **Indicators**: Red flags identified in the transaction data
- **Recommendations**: Suggested actions (monitor, block, investigate, escalate)

IMPORTANT RULES:
- Always retrieve evidence before making determinations — never guess
- Consider false positive impact — legitimate transactions should not be blocked
- Use episodic memory to avoid repeating past mistakes
- If confidence is below 0.6, recommend monitoring instead of blocking
- Always explain your reasoning with specific data points"""

    def get_tools(self) -> list:
        return get_agentic_rag_tools()

    async def analyze_transaction(
        self,
        transaction_text: str,
        session_id: str,
        merchant_id: str,
        correlation_id: str,
    ) -> dict:
        """
        Analyze a single transaction for fraud.

        This is the primary entry point called by the Orchestrator.
        The agent will autonomously use Agentic RAG tools to gather
        evidence and produce a fraud determination.
        """
        # Build context from all memory tiers
        context = await self._memory.build_agent_context(
            session_id=session_id,
            merchant_id=merchant_id,
            situation_description=transaction_text,
        )

        # Invoke the agent (triggers Agentic RAG loop)
        result = await self.invoke(
            query=(
                f"Analyze this transaction for potential fraud:\n\n"
                f"{transaction_text}\n\n"
                f"Merchant ID: {merchant_id}\n"
                f"Use your tools to search for evidence before making a determination."
            ),
            session_id=session_id,
            context=context,
        )

        # Publish fraud detection event to Kafka for downstream agents
        if "no fraud" not in result.get("analysis", "").lower():
            event = create_fraud_detected_event(
                session_id=session_id,
                correlation_id=correlation_id,
                fraud_type=self._extract_fraud_type(result),
                confidence=self._extract_confidence(result),
                evidence=self._extract_evidence(result),
                transaction_id="",  # Extracted from transaction_text
                merchant_id=merchant_id,
            )
            self.publish_event(event)

        return result

    def _extract_fraud_type(self, result: dict) -> str:
        """Extract fraud type from agent analysis text."""
        analysis = result.get("analysis", "").lower()
        # Check for explicit no-fraud determination first to prevent keyword false-positives
        # (e.g. the word 'velocity' appearing in tool-call output for a clean transaction)
        no_fraud_phrases = ["no fraud detected", "no fraud", "not fraud", "fraud not detected"]
        if any(phrase in analysis for phrase in no_fraud_phrases):
            return "unknown"
        type_map = {
            "card testing": "card_testing",
            "bin attack": "bin_attack",
            "transaction laundering": "transaction_laundering",
            "velocity abuse": "velocity_abuse",   # require 'abuse'; 'velocity' alone is too broad
            "synthetic identity": "synthetic_identity",
            "account takeover": "account_takeover",
            "friendly fraud": "friendly_fraud",
            "collusion": "cross_merchant_collusion",
        }
        for keyword, fraud_type in type_map.items():
            if keyword in analysis:
                return fraud_type
        return "unknown"

    def _extract_confidence(self, result: dict) -> float:
        """Extract confidence score from agent analysis."""
        import re
        analysis = result.get("analysis", "")
        match = re.search(r"[Cc]onfidence[:\s]*(\d+\.?\d*)", analysis)
        if match:
            val = float(match.group(1))
            return val if val <= 1.0 else val / 100.0
        return 0.5

    def _extract_evidence(self, result: dict) -> list[str]:
        """Extract evidence points from agent analysis.

        Skips structural section headers (Fraud Type, Confidence, Risk Score,
        Evidence, Indicators, Recommendations) that the LLM emits as bullet
        points but are NOT individual evidence items.
        """
        analysis = result.get("analysis", "")
        evidence = []
        # Section header prefixes to skip — these are output structure labels
        skip_prefixes = (
            "fraud type:", "confidence:", "risk score:", "evidence:",
            "indicators:", "recommendations:", "red flags:", "summary:",
            "overall risk score:", "risk level:",
        )
        for line in analysis.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip leading list markers to test the actual content
            content = line.lstrip("- *•0123456789. )")
            if not content or content.lower().startswith(skip_prefixes):
                continue
            # Only include lines that were bullet/numbered list items
            if line.startswith(("- ", "* ", "• ")) or (
                len(line) > 2 and line[0].isdigit() and line[1] in ". )"
            ):
                if len(content) > 10:  # ignore near-empty stubs
                    evidence.append(content)
        return evidence[:10]
