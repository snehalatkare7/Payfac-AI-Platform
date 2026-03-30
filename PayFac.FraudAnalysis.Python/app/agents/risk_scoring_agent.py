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
        transaction: dict | None = None,
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

        # Extract score from LLM output, then guard with deterministic scoring
        # so strong laundering signals cannot collapse to implausibly low values.
        llm_score = self._extract_risk_score(result)
        signal_score = self._compute_signal_based_score(fraud_result, compliance_result, transaction)
        overall_score = max(llm_score, signal_score)
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
        result["llm_risk_score"] = llm_score
        result["signal_risk_score"] = signal_score
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

        # Parse labeled component scores if present and compute weighted total.
        fraud_match = re.search(r"[Ff]raud\s*[Ss]core[:\s]*(\d+)", clean)
        compliance_match = re.search(r"[Cc]ompliance\s*[Ss]core[:\s]*(\d+)", clean)
        velocity_match = re.search(r"[Vv]elocity\s*[Ss]core[:\s]*(\d+)", clean)
        historical_match = re.search(r"[Hh]istorical\s*[Ss]core[:\s]*(\d+)", clean)
        if fraud_match or compliance_match or velocity_match or historical_match:
            fraud_score = int(fraud_match.group(1)) if fraud_match else 0
            compliance_score = int(compliance_match.group(1)) if compliance_match else 0
            velocity_score = int(velocity_match.group(1)) if velocity_match else 0
            historical_score = int(historical_match.group(1)) if historical_match else 0
            weighted = (
                fraud_score * 0.40
                + compliance_score * 0.30
                + velocity_score * 0.15
                + historical_score * 0.15
            )
            return min(max(int(round(weighted)), 0), 100)

        match = re.search(r"(\d+)\s*/\s*100", clean)
        if match:
            return min(int(match.group(1)), 100)

        # Try looser pattern: "Risk Score" followed by a number
        match = re.search(r"[Rr]isk\s*[Ss]core[:\s]*(\d+)", clean)
        if match:
            return min(int(match.group(1)), 100)

        return 50  # Default if extraction fails

    # MCC codes that represent inherently higher-risk merchant categories.
    HIGH_RISK_MCC = {
        "7995",  # Gambling / betting
        "7994",  # Arcade / amusement
        "5967",  # Direct marketing – inbound teleservices
        "5966",  # Direct marketing – outbound teleservices
        "5816",  # Digital goods
        "5912",  # Drug stores / pharmacies (online)
        "5962",  # Direct marketing – travel
        "5993",  # Cigar / tobacco stores
        "6051",  # Quasi-cash / money orders
        "6211",  # Securities / brokers
        "6012",  # Financial institutions – merch payments
        "4829",  # Money transfer
    }

    # Countries considered high-risk for cross-border fraud / sanctions.
    HIGH_RISK_COUNTRIES = {
        "RU", "NG", "KP", "IR", "SY", "CU", "VE", "MM", "BY", "SD",
        "SO", "YE", "LY", "AF", "IQ", "PK", "UA",
    }

    def _compute_signal_based_score(
        self,
        fraud_result: dict,
        compliance_result: dict,
        transaction: dict | None = None,
    ) -> int:
        """Compute deterministic score from fraud/compliance indicators.

        This acts as a safety floor when LLM formatting/extraction yields
        unrealistically low scores despite strong signals.
        """
        import re
        analysis = (fraud_result or {}).get("analysis", "")
        low = analysis.lower()
        txn = transaction or {}

        # Severity baseline by suspected fraud type wording in analysis.
        # Only match fraud types that appear in affirmative (non-negated) context.
        fraud_type_bases = [
            ("bin attack", 38),
            ("transaction laundering", 35),
            ("velocity abuse", 30),
            ("card testing", 24),
        ]
        score = 15  # default when no fraud type detected
        fraud_type_matched = False
        for keyword, base in fraud_type_bases:
            if self._has_affirmative_mention(low, keyword):
                score = base
                fraud_type_matched = True
                break

        # Confidence adjustment: only boost score when a fraud type was
        # positively identified.  When no fraud type is found, high
        # confidence in "no fraud" should *lower* the score, not raise it.
        confidence = self._extract_confidence_from_text(analysis)
        if fraud_type_matched:
            score += int(max(0.0, min(confidence, 1.0)) * 15)
        else:
            # Higher confidence in "no fraud" → lower floor
            score -= int(max(0.0, min(confidence, 1.0)) * 10)

        # --- Collect risk signals with weights ---
        # Signals are gathered from raw transaction fields (ground truth)
        # and supplemented by text-based indicators from the fraud analysis.
        # A compound multiplier is applied when multiple signals co-occur,
        # so ANY combination of stacking risks is naturally elevated.
        signals: list[tuple[str, int]] = []

        # -- Raw transaction field signals (authoritative) --

        entry_mode = str(txn.get("entry_mode", "") or "").lower()
        manual_keyed = "manual" in entry_mode or entry_mode == "manual_keyed"
        if manual_keyed:
            signals.append(("manual_keyed", 8))

        is_card_present = txn.get("is_card_present")
        cnp = is_card_present is False or str(is_card_present).lower() == "false"
        if cnp:
            signals.append(("cnp", 8))

        mcc = str(txn.get("merchant_category_code", txn.get("mcc", ""))).strip()
        if mcc in self.HIGH_RISK_MCC:
            signals.append(("high_risk_mcc", 12))

        try:
            amount_cents = int(txn.get("amount_cents", 0) or 0)
        except (TypeError, ValueError):
            amount_cents = 0
        if amount_cents >= 500_000:        # >= $5,000
            signals.append(("very_high_amount", 10))
        elif amount_cents >= 200_000:      # >= $2,000
            signals.append(("high_amount", 8))
        elif amount_cents >= 50_000:       # >= $500
            signals.append(("elevated_amount", 5))

        billing = str(txn.get("billing_country", "") or "").strip().upper()
        shipping_raw = txn.get("shipping_country")
        shipping = str(shipping_raw).strip().upper() if shipping_raw else ""
        cross_border = billing and shipping and billing != shipping
        if cross_border:
            if shipping in self.HIGH_RISK_COUNTRIES:
                signals.append(("cross_border_high_risk", 12))
            else:
                signals.append(("cross_border", 6))

        ip_country = str(txn.get("ip_country", "") or "").strip().upper()
        if ip_country and billing and ip_country != billing:
            signals.append(("ip_mismatch", 5))

        is_recurring = txn.get("is_recurring")
        if is_recurring is False or str(is_recurring).lower() == "false":
            signals.append(("non_recurring", 2))

        # -- Text-based signals (only when raw fields didn't already cover it) --

        if not manual_keyed and ("manual_keyed" in low or "manual keyed" in low):
            signals.append(("manual_keyed_text", 8))

        if not cross_border and "billing country" in low and "shipping country" in low and (
            "mismatch" in low or "cross-border" in low or "international shipping" in low
        ):
            signals.append(("cross_border_text", 8))

        # -- Aggregate signals with compound multiplier --
        signal_sum = sum(w for _, w in signals)
        n = len(signals)
        if n >= 5:
            signal_sum = int(signal_sum * 1.5)
        elif n >= 3:
            signal_sum = int(signal_sum * 1.3)

        score += signal_sum

        # --- Compliance escalation ---

        if compliance_result and not compliance_result.get("is_compliant", True):
            score += 8
            violations = compliance_result.get("violations", []) or []
            score += min(len(violations) * 3, 9)

        return max(0, min(score, 100))

    def _extract_confidence_from_text(self, analysis: str) -> float:
        """Extract confidence from free text analysis."""
        import re

        match = re.search(r"[Cc]onfidence[:\s]*(\d+\.?\d*)", analysis)
        if not match:
            return 0.5

        val = float(match.group(1))
        return val if val <= 1.0 else val / 100.0

    @staticmethod
    def _has_affirmative_mention(text_lower: str, keyword: str) -> bool:
        """Check if *keyword* appears in an affirmative (non-negated) context.

        Returns ``True`` when at least one occurrence of *keyword* in
        *text_lower* is **not** preceded by a negation word (no, not,
        without, nor, neither, lack, absence) within the same sentence.
        """
        import re
        idx = 0
        neg_re = re.compile(
            r"\b(no|not|without|nor|neither|lack\s+of|absence\s+of|no\s+abnormal)\b"
        )
        while True:
            pos = text_lower.find(keyword, idx)
            if pos == -1:
                return False
            # Determine sentence-level prefix: from last sentence boundary to keyword.
            sent_start = max(
                text_lower.rfind(".", 0, pos),
                text_lower.rfind("!", 0, pos),
                text_lower.rfind("\n", 0, pos),
            )
            prefix = text_lower[sent_start + 1 : pos]
            if not neg_re.search(prefix):
                return True            # this occurrence is affirmative
            idx = pos + len(keyword)    # check next occurrence

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
