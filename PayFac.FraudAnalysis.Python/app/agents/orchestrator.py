"""Orchestrator Agent — multi-agent workflow coordinator using LangGraph.

The Orchestrator manages the entire fraud analysis pipeline:
  1. Receives analysis requests
  2. Routes to Fraud Detection Agent (Agentic RAG)
  3. Routes to Compliance Agent (Agentic RAG)
  4. Routes to Risk Scoring Agent (aggregation)
  5. Conditionally routes to Investigation Agent (if high risk)
  6. Aggregates all results into a FraudAlert
  7. Records the episode in memory
  8. Publishes events to Kafka

Uses LangGraph for stateful, conditional workflow orchestration.

┌──────────────┐
│  START        │
│  (Receive Txn)│
└──────┬───────┘
       ▼
┌──────────────┐
│ Fraud        │  ← Agentic RAG (autonomous tool calling)
│ Detection    │
└──────┬───────┘
       ▼
┌──────────────┐
│ Compliance   │  ← Agentic RAG (compliance doc retrieval)
│ Check        │
└──────┬───────┘
       ▼
┌──────────────┐
│ Risk         │  ← Reads fraud + compliance results
│ Scoring      │
└──────┬───────┘
       ▼
┌──────────────┐     ┌──────────────┐
│ Score > 60?  │─YES─▶ Investigation │
│ (Conditional)│     │ Deep Dive    │
└──────┬───────┘     └──────┬───────┘
       │NO                   │
       ▼                     ▼
┌──────────────────────────────────┐
│  Aggregate Results → FraudAlert  │
│  Record Episode → Memory         │
│  Publish Events → Kafka          │
└──────────────────────────────────┘
"""

import logging
from datetime import datetime
from typing import Any, TypedDict, Annotated
from uuid import uuid4

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.agents.fraud_detection_agent import FraudDetectionAgent
from app.agents.compliance_agent import ComplianceAgent
from app.agents.risk_scoring_agent import RiskScoringAgent
from app.agents.investigation_agent import InvestigationAgent
from app.infrastructure.llm_client import LLMClient
from app.memory.manager import MemoryManager
from app.kafka_bus.producer import KafkaProducer
from app.kafka_bus.events import AgentEvent, EventType
from app.models import (
    FraudAlert,
    FraudType,
    RiskLevel,
    InvestigationEpisode,
    InvestigationOutcome,
    Transaction,
)

logger = logging.getLogger(__name__)


# ── LangGraph State Definition ────────────────────────────────────────

class AnalysisState(TypedDict):
    """State that flows through the LangGraph workflow."""

    # Input
    session_id: str
    correlation_id: str
    transaction: dict
    merchant_id: str

    # Agent results (populated as workflow progresses)
    fraud_result: dict
    compliance_result: dict
    risk_result: dict
    investigation_result: dict

    # Final output
    fraud_alert: dict
    needs_investigation: bool
    workflow_complete: bool


# ── Orchestrator ──────────────────────────────────────────────────────

class OrchestratorAgent:
    """
    Multi-agent workflow orchestrator using LangGraph.

    Coordinates the sequential execution of specialized agents,
    with conditional routing based on risk scores, and aggregates
    results into a final FraudAlert.

    Agent-to-Agent communication happens through:
      1. Short-term memory (Redis) — within the workflow
      2. Kafka events — for audit trail and async downstream processing
    """

    def __init__(
        self,
        llm_client: LLMClient,
        memory: MemoryManager,
        kafka_producer: KafkaProducer,
    ):
        self._llm = llm_client
        self._memory = memory
        self._kafka = kafka_producer

        # Initialize specialized agents
        self._fraud_agent = FraudDetectionAgent(llm_client, memory, kafka_producer)
        self._compliance_agent = ComplianceAgent(llm_client, memory, kafka_producer)
        self._risk_agent = RiskScoringAgent(llm_client, memory, kafka_producer)
        self._investigation_agent = InvestigationAgent(llm_client, memory, kafka_producer)

        # Build the LangGraph workflow
        self._graph = self._build_workflow()

    def _build_workflow(self) -> Any:
        """
        Build the LangGraph state machine for the analysis pipeline.

        Graph structure:
          start → fraud_detection → compliance_check → risk_scoring
                → should_investigate? → [investigation | aggregate]
                → END
        """
        workflow = StateGraph(AnalysisState)

        # Add nodes (each node is an async function)
        workflow.add_node("fraud_detection", self._run_fraud_detection)
        workflow.add_node("compliance_check", self._run_compliance_check)
        workflow.add_node("risk_scoring", self._run_risk_scoring)
        workflow.add_node("investigation", self._run_investigation)
        workflow.add_node("aggregate", self._aggregate_results)

        # Define edges (sequential flow)
        workflow.set_entry_point("fraud_detection")
        workflow.add_edge("fraud_detection", "compliance_check")
        workflow.add_edge("compliance_check", "risk_scoring")

        # Conditional edge: investigate if high risk
        workflow.add_conditional_edges(
            "risk_scoring",
            self._should_investigate,
            {
                "investigate": "investigation",
                "aggregate": "aggregate",
            },
        )

        workflow.add_edge("investigation", "aggregate")
        workflow.add_edge("aggregate", END)

        return workflow.compile()

    # ── Workflow Node Functions ────────────────────────────────────────

    async def _run_fraud_detection(self, state: AnalysisState) -> dict:
        """Node: Run the Fraud Detection Agent."""
        logger.info(
            "Orchestrator: Running fraud detection for session %s",
            state["session_id"],
        )

        transaction = state["transaction"]
        transaction_text = (
            transaction.get("analysis_text", "")
            or str(transaction)
        )

        result = await self._fraud_agent.analyze_transaction(
            transaction_text=transaction_text,
            session_id=state["session_id"],
            merchant_id=state["merchant_id"],
            correlation_id=state["correlation_id"],
        )

        return {"fraud_result": result}

    async def _run_compliance_check(self, state: AnalysisState) -> dict:
        """Node: Run the Compliance Agent."""
        logger.info(
            "Orchestrator: Running compliance check for session %s",
            state["session_id"],
        )

        fraud_analysis = state.get("fraud_result", {}).get("analysis", "")
        card_brand = state["transaction"].get("card_brand", "all")

        result = await self._compliance_agent.check_compliance(
            analysis_context=fraud_analysis,
            session_id=state["session_id"],
            merchant_id=state["merchant_id"],
            card_brand=card_brand,
            correlation_id=state["correlation_id"],
        )

        return {"compliance_result": result}

    async def _run_risk_scoring(self, state: AnalysisState) -> dict:
        """Node: Run the Risk Scoring Agent."""
        logger.info(
            "Orchestrator: Running risk scoring for session %s",
            state["session_id"],
        )

        result = await self._risk_agent.calculate_risk(
            session_id=state["session_id"],
            merchant_id=state["merchant_id"],
            correlation_id=state["correlation_id"],
        )

        needs_investigation = result.get("risk_score", 0) > 60

        return {
            "risk_result": result,
            "needs_investigation": needs_investigation,
        }

    def _should_investigate(self, state: AnalysisState) -> str:
        """Conditional edge: determine if investigation is needed."""
        if state.get("needs_investigation", False):
            logger.info(
                "Orchestrator: Risk score > 60, triggering investigation"
            )
            return "investigate"
        return "aggregate"

    async def _run_investigation(self, state: AnalysisState) -> dict:
        """Node: Run the Investigation Agent (conditional)."""
        logger.info(
            "Orchestrator: Running deep investigation for session %s",
            state["session_id"],
        )

        risk_score = state.get("risk_result", {}).get("risk_score", 0)
        result = await self._investigation_agent.investigate(
            session_id=state["session_id"],
            merchant_id=state["merchant_id"],
            escalation_reason=f"Risk score {risk_score} exceeds threshold (60)",
            correlation_id=state["correlation_id"],
        )

        return {"investigation_result": result}

    async def _aggregate_results(self, state: AnalysisState) -> dict:
        """
        Node: Aggregate all agent results into a final FraudAlert.

        Also records the investigation episode in episodic memory
        and updates the merchant's long-term risk profile.
        """
        logger.info(
            "Orchestrator: Aggregating results for session %s",
            state["session_id"],
        )

        fraud_result = state.get("fraud_result", {})
        compliance_result = state.get("compliance_result", {})
        risk_result = state.get("risk_result", {})
        investigation_result = state.get("investigation_result", {})

        risk_score = risk_result.get("risk_score", 50)
        risk_level_str = risk_result.get("risk_level", "medium")

        # Map to enums
        risk_level_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
            "severe": RiskLevel.SEVERE,
        }
        risk_level = risk_level_map.get(risk_level_str, RiskLevel.MEDIUM)

        # Determine fraud type from detection results.
        # Do not default unknown/no-fraud outcomes to a concrete fraud class.
        fraud_type_str = self._fraud_agent._extract_fraud_type(fraud_result)
        fraud_type_map = {ft.value: ft for ft in FraudType}
        fraud_type = fraud_type_map.get(fraud_type_str, FraudType.UNKNOWN)

        # Determine which agents participated
        agents_involved = ["fraud_detection", "compliance", "risk_scoring"]
        if investigation_result:
            agents_involved.append("investigation")

        # Build the FraudAlert
        alert = FraudAlert(
            merchant_id=state["merchant_id"],
            transaction_id=state["transaction"].get("transaction_id", ""),
            fraud_type=fraud_type,
            risk_level=risk_level,
            risk_score=risk_score,
            summary=self._build_summary(
                fraud_result, compliance_result, risk_result, investigation_result,
            ),
            evidence=self._fraud_agent._extract_evidence(fraud_result),
            recommendations=risk_result.get("factors", []),
            compliance_violations=[],
            analyzed_by_agents=agents_involved,
            confidence=self._fraud_agent._extract_confidence(fraud_result),
        )

        # Record episode in episodic memory
        outcome = (
            InvestigationOutcome.CONFIRMED_FRAUD
            if risk_score > 60
            else InvestigationOutcome.MONITORING
        )
        episode = InvestigationEpisode(
            merchant_id=state["merchant_id"],
            transaction_ids=[state["transaction"].get("transaction_id", "")],
            fraud_type=fraud_type,
            outcome=outcome,
            narrative=alert.summary,
            evidence_collected=alert.evidence,
            agents_involved=agents_involved,
        )

        await self._memory.record_investigation_complete(
            session_id=state["session_id"],
            episode=episode,
        )

        # Publish completion event
        completion_event = AgentEvent(
            event_type=EventType.ANALYSIS_COMPLETED,
            correlation_id=state["correlation_id"],
            session_id=state["session_id"],
            source_agent="orchestrator",
            payload=alert.model_dump(mode="json"),
        )
        self._kafka.publish(completion_event)

        return {
            "fraud_alert": alert.model_dump(mode="json"),
            "workflow_complete": True,
        }

    def _build_summary(
        self,
        fraud_result: dict,
        compliance_result: dict,
        risk_result: dict,
        investigation_result: dict,
    ) -> str:
        """Build a concise summary from all agent analyses."""
        parts = []

        fraud_analysis = fraud_result.get("analysis", "")
        if fraud_analysis:
            fa_lower = fraud_analysis.lower()
            if "no fraud detected" in fa_lower:
                parts.append("Fraud detection found no strong fraud indicators.")
            else:
                # Extract the first clean prose line; skip markdown bullet lines.
                clean_line = ""
                for line in fraud_analysis.split("\n"):
                    line = line.strip()
                    if line and not line.startswith(("-", "*", "#", "|", "•")) and len(line) > 20:
                        clean_line = line[:300]
                        break
                if not clean_line:
                    # Fallback: first non-empty flattened sentence without list markers
                    flat = fraud_analysis.replace("\n", " ").replace("- ", " ").replace("* ", " ")
                    clean_line = flat.split(".")[0].strip()[:300]
                if clean_line:
                    parts.append(clean_line + ".")

        risk_score = risk_result.get("risk_score", "N/A")
        risk_level = risk_result.get("risk_level", "N/A")
        parts.append(f"Risk Score: {risk_score}/100 ({risk_level}).")

        if not compliance_result.get("is_compliant", True):
            parts.append("Compliance violations detected.")

        if investigation_result:
            parts.append("Deep investigation was conducted due to elevated risk.")

        return " ".join(parts)

    # ── Public Interface ──────────────────────────────────────────────

    async def analyze(self, transaction: Transaction) -> FraudAlert:
        """
        Run the full multi-agent fraud analysis pipeline.

        This is the main entry point for the API layer.

        Args:
            transaction: The transaction to analyze.

        Returns:
            FraudAlert with complete analysis results.
        """
        session_id = str(uuid4())
        correlation_id = str(uuid4())

        logger.info(
            "Starting analysis: session=%s, merchant=%s, txn=%s",
            session_id, transaction.merchant_id, transaction.transaction_id,
        )

        # Publish analysis started event
        start_event = AgentEvent(
            event_type=EventType.ANALYSIS_STARTED,
            correlation_id=correlation_id,
            session_id=session_id,
            source_agent="orchestrator",
            payload=transaction.model_dump(mode="json"),
        )
        self._kafka.publish(start_event)

        # Store initial chat message
        await self._memory.short_term.add_chat_message(
            session_id, "system",
            f"Analysis started for transaction {transaction.transaction_id}",
        )

        # Record velocity event
        await self._memory.short_term.record_transaction_event(
            merchant_id=transaction.merchant_id,
            transaction_id=transaction.transaction_id,
        )

        # Build initial state
        initial_state: AnalysisState = {
            "session_id": session_id,
            "correlation_id": correlation_id,
            "transaction": {
                **transaction.model_dump(mode="json"),
                "analysis_text": transaction.to_analysis_text(),
            },
            "merchant_id": transaction.merchant_id,
            "fraud_result": {},
            "compliance_result": {},
            "risk_result": {},
            "investigation_result": {},
            "fraud_alert": {},
            "needs_investigation": False,
            "workflow_complete": False,
        }

        # Execute the LangGraph workflow
        final_state = await self._graph.ainvoke(initial_state)

        # Reconstruct FraudAlert from final state
        alert_data = final_state.get("fraud_alert", {})
        alert = FraudAlert(**alert_data) if alert_data else FraudAlert()

        logger.info(
            "Analysis complete: session=%s, risk=%d, level=%s",
            session_id, alert.risk_score, alert.risk_level.value,
        )

        return alert
