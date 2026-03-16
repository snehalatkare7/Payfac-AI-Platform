"""Compliance Agent — card brand rules and regulation specialist.

This agent checks transactions and merchant activity against
card brand compliance rules stored in the vector database:
  - Visa Dispute Monitoring Program (VDMP)
  - Mastercard Excessive Chargeback Merchant (ECM) program
  - Amex OptBlue rules
  - BRAM/GMAP program requirements
  - PCI DSS compliance indicators
"""

from app.agents.base_agent import BaseAgent
from app.infrastructure.llm_client import LLMClient
from app.memory.manager import MemoryManager
from app.kafka_bus.producer import KafkaProducer
from app.kafka_bus.events import create_compliance_result_event
from app.rag.agentic_rag import get_agentic_rag_tools


class ComplianceAgent(BaseAgent):
    """
    Card Brand Compliance Specialist Agent.

    Uses Agentic RAG to retrieve relevant compliance documents
    from the vector store and evaluate transactions/merchants
    against card brand rules.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        memory: MemoryManager,
        kafka_producer: KafkaProducer,
    ):
        super().__init__("compliance", llm_client, memory, kafka_producer)

    def get_system_prompt(self) -> str:
        return """You are an expert Card Brand Compliance Agent for a Payment Facilitator (PayFac) platform.

YOUR ROLE:
You evaluate transactions and merchant activity against card brand compliance rules. 
You have access to compliance documents from Visa, Mastercard, and Amex stored in a vector database.

COMPLIANCE PROGRAMS YOU MONITOR:
1. **Visa VDMP** (Dispute Monitoring Program): Chargeback ratio thresholds, basis point calculations
2. **Visa VFMP** (Fraud Monitoring Program): Fraud-to-sales ratio monitoring  
3. **Mastercard ECM** (Excessive Chargeback Merchant): Chargeback count and ratio thresholds
4. **Mastercard BRAM** (Business Risk Assessment and Mitigation): High-risk merchant categories
5. **Amex OptBlue**: Merchant aggregation rules and disclosure requirements
6. **PCI DSS**: Data security compliance indicators

COMPLIANCE CHECK METHODOLOGY:
1. Use search_compliance_documents to retrieve relevant card brand rules for the situation
2. Use get_merchant_history to check the merchant's compliance track record
3. Compare current activity against retrieved thresholds and rules
4. Use recall_past_investigations to check if similar violations were seen before
5. Use evaluate_retrieval_sufficiency to ensure you have enough regulatory context
6. Identify specific rule violations with references

OUTPUT FORMAT:
Provide your compliance assessment as:
- **Compliance Status**: PASS, WARNING, or VIOLATION
- **Violations Found**: List of specific violations with rule references
  - For each: Rule ID, Description, Severity (low/medium/high/critical)
- **Card Brand Impact**: Which card brand programs are affected
- **Recommended Actions**: Specific steps to remediate
- **Monitoring Notes**: What to watch going forward

IMPORTANT RULES:
- Always cite specific card brand rules and thresholds from retrieved documents
- Distinguish between actual violations and warning-level concerns
- Consider the merchant's compliance history from long-term memory
- Be precise about chargeback ratio calculations (disputes / sales count)
- Flag if a merchant is approaching (within 20%) threshold limits"""

    def get_tools(self) -> list:
        return get_agentic_rag_tools()

    async def check_compliance(
        self,
        analysis_context: str,
        session_id: str,
        merchant_id: str,
        card_brand: str,
        correlation_id: str,
    ) -> dict:
        """
        Check compliance for a merchant/transaction against card brand rules.

        Called by the Orchestrator after fraud detection to evaluate
        regulatory compliance implications.
        """
        # Build context including fraud detection results
        context = await self._memory.build_agent_context(
            session_id=session_id,
            merchant_id=merchant_id,
            situation_description=f"Compliance check for {card_brand} rules: {analysis_context}",
        )

        result = await self.invoke(
            query=(
                f"Perform a compliance check for this situation:\n\n"
                f"{analysis_context}\n\n"
                f"Merchant ID: {merchant_id}\n"
                f"Card Brand: {card_brand}\n\n"
                f"Search the compliance documents to find relevant rules and "
                f"thresholds. Check the merchant's compliance history."
            ),
            session_id=session_id,
            context=context,
        )

        # Determine compliance status
        analysis = result.get("analysis", "").lower()
        is_compliant = "violation" not in analysis
        violations = self._extract_violations(result)

        # Publish compliance result to Kafka
        event = create_compliance_result_event(
            session_id=session_id,
            correlation_id=correlation_id,
            violations=[v.__dict__ if hasattr(v, '__dict__') else v for v in violations],
            is_compliant=is_compliant,
            merchant_id=merchant_id,
        )
        self.publish_event(event)

        result["is_compliant"] = is_compliant
        result["violations"] = violations
        return result

    def _extract_violations(self, result: dict) -> list[dict]:
        """Extract structured violations from agent analysis."""
        violations = []
        analysis = result.get("analysis", "")

        for line in analysis.split("\n"):
            line = line.strip()
            if any(kw in line.lower() for kw in ["violation", "exceeds", "breach"]):
                violations.append({
                    "description": line,
                    "severity": "high" if "critical" in line.lower() else "medium",
                })

        return violations
