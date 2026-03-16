"""Investigation Agent — deep-dive analysis with episodic memory.

This agent handles complex or escalated fraud cases that require
deeper analysis. It heavily leverages episodic memory to recall
similar past investigations and their outcomes.
"""

from app.agents.base_agent import BaseAgent
from app.infrastructure.llm_client import LLMClient
from app.memory.manager import MemoryManager
from app.kafka_bus.producer import KafkaProducer
from app.rag.agentic_rag import get_agentic_rag_tools


class InvestigationAgent(BaseAgent):
    """
    Deep Investigation Agent.

    Activated for complex cases that require multi-step investigation.
    Uses episodic memory extensively to learn from past cases.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        memory: MemoryManager,
        kafka_producer: KafkaProducer,
    ):
        super().__init__("investigation", llm_client, memory, kafka_producer)

    def get_system_prompt(self) -> str:
        return """You are a Deep Investigation Agent for a Payment Facilitator (PayFac) platform.

YOUR ROLE:
You handle complex fraud cases that require thorough, multi-step investigation.
You are activated when the risk score exceeds 60 or when other agents flag 
ambiguous situations that need deeper analysis.

INVESTIGATION APPROACH:
1. Review all findings from the Fraud Detection, Compliance, and Risk Scoring agents
2. Use recall_past_investigations extensively to find similar historical cases
3. Search for additional evidence using broader search queries
4. Cross-reference multiple data sources (transactions, compliance docs, patterns)
5. Build a comprehensive case narrative
6. Provide a definitive recommendation with full justification

YOU EXCEL AT:
- Connecting disparate signals across multiple transactions
- Identifying sophisticated fraud schemes that evade simple pattern matching
- Leveraging institutional knowledge from past investigation episodes
- Producing detailed case reports for human reviewers
- Recommending escalation paths when human judgment is needed

OUTPUT FORMAT:
Structure your investigation report as:

1. **Case Summary**: One-paragraph overview of the situation
2. **Investigation Steps Taken**: What you searched for and found
3. **Evidence Analysis**:
   - Supporting evidence for fraud
   - Mitigating evidence (why this might be legitimate)
4. **Historical Precedents**: Similar past cases and their outcomes
5. **Determination**: Your final assessment with confidence level
6. **Recommended Actions**:
   - Immediate actions (block, hold, monitor)
   - Short-term (7-day) actions
   - Long-term actions (policy changes, enhanced monitoring)
7. **Escalation Notes**: If human review is needed, explain why

IMPORTANT:
- Always search for BOTH fraud evidence AND evidence of legitimacy
- Use episodic memory — similar past cases are invaluable
- Your report may be read by compliance officers and risk managers
- Be thorough but concise — focus on actionable findings
- If the case is ambiguous, say so and explain what additional information would help"""

    def get_tools(self) -> list:
        return get_agentic_rag_tools()

    async def investigate(
        self,
        session_id: str,
        merchant_id: str,
        escalation_reason: str,
        correlation_id: str,
    ) -> dict:
        """
        Conduct a deep investigation for an escalated case.

        Pulls all prior agent results and conducts additional analysis.
        """
        context = await self._memory.build_agent_context(
            session_id=session_id,
            merchant_id=merchant_id,
            situation_description=escalation_reason,
        )

        # Gather all agent results
        all_results = await self._memory.short_term.get_all_agent_results(session_id)

        query = (
            f"Conduct a deep investigation for merchant {merchant_id}.\n\n"
            f"ESCALATION REASON: {escalation_reason}\n\n"
        )

        for agent_name, agent_result in all_results.items():
            query += (
                f"\n{agent_name.upper()} AGENT FINDINGS:\n"
                f"{agent_result.get('analysis', 'No findings')}\n"
            )

        query += (
            "\nPerform additional searches, recall past investigations, "
            "and produce a comprehensive investigation report."
        )

        result = await self.invoke(
            query=query,
            session_id=session_id,
            context=context,
        )

        return result
