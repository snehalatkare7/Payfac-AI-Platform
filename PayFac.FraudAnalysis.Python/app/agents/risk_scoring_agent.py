"""Risk Scoring Agent — computes composite risk scores.

This agent aggregates findings from the Fraud Detection and
Compliance agents to compute a composite risk score (0-100)
with weighted factors and risk level classification.
"""

from app.agents.base_agent import BaseAgent
from app.infrastructure.llm_client import LLMClient
from app.memory.manager import MemoryManager
from app.kafka_bus.producer import KafkaProducer
from app.kafka_bus.events import create_risk_score_event
from app.rag.agentic_rag import get_agentic_rag_tools


class RiskScoringAgent(BaseAgent):
    """
    Risk Scoring Analyst Agent.

    Computes composite risk scores by aggregating fraud detection
    and compliance findings, weighted by severity and confidence.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        memory: MemoryManager,
        kafka_producer: KafkaProducer,
    ):
        super().__init__("risk_scoring", llm_client, memory, kafka_producer)

    def get_system_prompt(self) -> str:
        return """You are a Risk Scoring Analyst Agent for a Payment Facilitator (PayFac) platform.

YOUR ROLE:
You compute composite risk scores by aggregating findings from the Fraud Detection 
Agent and Compliance Agent. Your scores drive automated actions and human review queues.

SCORING METHODOLOGY:
You compute a composite score (0-100) using these weighted factors:

1. **Fraud Score (40% weight)**:
   - Based on fraud detection agent's confidence and fraud type severity
   - Card testing: base 30, Transaction laundering: base 70, Velocity abuse: base 50
   - Adjust by detection confidence

2. **Compliance Score (30% weight)**:
   - Based on number and severity of compliance violations
   - Critical violation: +25, High: +15, Medium: +10, Low: +5
   - Cap at 100

3. **Velocity Score (15% weight)**:
   - Based on transaction velocity relative to merchant baseline
   - >200% of baseline: 75+, >150%: 50+, >100%: 25+

4. **Historical Score (15% weight)**:
   - Based on merchant's long-term risk profile
   - Previous fraud incidents, chargeback ratio, risk trend

RISK LEVELS:
- 0-20: LOW — Normal monitoring
- 21-40: MEDIUM — Enhanced monitoring, flag for review
- 41-60: HIGH — Immediate review required, temporary hold
- 61-80: CRITICAL — Auto-block new transactions, urgent investigation
- 81-100: SEVERE — Suspend merchant, escalate to risk committee

OUTPUT FORMAT:
Provide your risk assessment as:
- **Overall Risk Score**: 0-100
- **Risk Level**: LOW / MEDIUM / HIGH / CRITICAL / SEVERE
- **Component Scores**:
  - Fraud Score: X/100 (weight: 40%)
  - Compliance Score: X/100 (weight: 30%)
  - Velocity Score: X/100 (weight: 15%)
  - Historical Score: X/100 (weight: 15%)
- **Key Risk Factors**: Top factors driving the score
- **Recommended Actions**: Based on risk level
- **Score Justification**: Brief explanation of score rationale

IMPORTANT:
- Use findings from other agents (available in context) — do NOT re-analyze transactions
- Be precise with the scoring formula
- Consider the merchant's trajectory (improving or worsening)
- Recommend specific, actionable next steps based on risk level"""

    def get_tools(self) -> list:
        return get_agentic_rag_tools()

    async def calculate_risk(
        self,
        session_id: str,
        merchant_id: str,
        correlation_id: str,
    ) -> dict:
        """
        Calculate composite risk score using findings from other agents.

        This agent reads fraud detection and compliance results from
        short-term memory (stored by those agents) and computes
        a weighted risk score.
        """
        # Build context — includes fraud + compliance agent results
        context = await self._memory.build_agent_context(
            session_id=session_id,
            merchant_id=merchant_id,
            situation_description=f"Risk scoring for merchant {merchant_id}",
        )

        # Get other agents' results from short-term memory
        fraud_result = await self._memory.short_term.get_agent_result(
            session_id, "fraud_detection"
        )
        compliance_result = await self._memory.short_term.get_agent_result(
            session_id, "compliance"
        )

        query_parts = [
            "Calculate a composite risk score for this merchant based on the following findings:\n"
        ]
        if fraud_result:
            query_parts.append(
                f"FRAUD DETECTION FINDINGS:\n{fraud_result.get('analysis', 'No findings')}\n"
            )
        if compliance_result:
            query_parts.append(
                f"COMPLIANCE FINDINGS:\n{compliance_result.get('analysis', 'No findings')}\n"
            )

        query_parts.append(
            f"\nMerchant ID: {merchant_id}\n"
            f"Use the merchant history and velocity tools to supplement your scoring."
        )

        result = await self.invoke(
            query="\n".join(query_parts),
            session_id=session_id,
            context=context,
        )

        # Extract and publish risk score
        overall_score = self._extract_risk_score(result)
        risk_level = self._determine_risk_level(overall_score)

        event = create_risk_score_event(
            session_id=session_id,
            correlation_id=correlation_id,
            merchant_id=merchant_id,
            overall_score=overall_score,
            risk_level=risk_level,
            factors=self._extract_factors(result),
        )
        self.publish_event(event)

        result["risk_score"] = overall_score
        result["risk_level"] = risk_level
        return result

    def _extract_risk_score(self, result: dict) -> int:
        """Extract numeric risk score from agent analysis."""
        import re
        analysis = result.get("analysis", "")
        # Strip markdown bold markers so patterns like "**Overall Risk Score**: 65" become plain text
        clean = analysis.replace("**", "")
        match = re.search(r"[Oo]verall\s*[Rr]isk\s*[Ss]core[:\s]*(\d+)", clean)
        if match:
            return min(int(match.group(1)), 100)

        match = re.search(r"(\d+)\s*/\s*100", clean)
        if match:
            return min(int(match.group(1)), 100)

        # Try looser pattern: "Risk Score" followed by a number
        match = re.search(r"[Rr]isk\s*[Ss]core[:\s]*(\d+)", clean)
        if match:
            return min(int(match.group(1)), 100)

        return 50  # Default if extraction fails

    def _determine_risk_level(self, score: int) -> str:
        """Map numeric score to risk level."""
        if score <= 20:
            return "low"
        elif score <= 40:
            return "medium"
        elif score <= 60:
            return "high"
        elif score <= 80:
            return "critical"
        return "severe"

    def _extract_factors(self, result: dict) -> list[str]:
        """Extract key risk factors and recommended actions from analysis."""
        analysis = result.get("analysis", "").replace("**", "")
        factors = []
        capture = False
        for line in analysis.split("\n"):
            stripped = line.strip()
            low = stripped.lower()
            # Start capturing after factor/recommendation headings
            if any(kw in low for kw in ("key risk factor", "recommended action", "risk factor")):
                capture = True
                continue
            # Stop capturing on next major section heading (non-bullet line with colon)
            if capture and stripped and not stripped.startswith(("-", "*", "•")) and ":" in stripped and len(stripped.split()) <= 6:
                capture = False
            if capture and (stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("• ")):
                content = stripped.lstrip("- *•").strip()
                if content and len(content) > 10:
                    factors.append(content)
        return factors[:10]
