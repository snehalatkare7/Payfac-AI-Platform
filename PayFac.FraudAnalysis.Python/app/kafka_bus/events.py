"""Kafka event schemas for agent-to-agent communication.

Defines the event types that flow between agents via Kafka topics.
Events are the primary mechanism for:
  - Asynchronous agent-to-agent communication
  - Audit trail of all agent decisions
  - Event-driven triggering of downstream agents
  - Investigation workflow state transitions
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class EventType(str, Enum):
    """Types of events that flow through the Kafka event bus."""

    # Agent lifecycle events
    ANALYSIS_REQUESTED = "analysis.requested"
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_COMPLETED = "analysis.completed"
    ANALYSIS_FAILED = "analysis.failed"

    # Fraud detection events
    FRAUD_DETECTED = "fraud.detected"
    FRAUD_CLEARED = "fraud.cleared"
    FRAUD_ESCALATED = "fraud.escalated"

    # Compliance events
    COMPLIANCE_CHECK_STARTED = "compliance.check.started"
    COMPLIANCE_VIOLATION_FOUND = "compliance.violation.found"
    COMPLIANCE_CHECK_PASSED = "compliance.check.passed"

    # Risk scoring events
    RISK_SCORE_CALCULATED = "risk.score.calculated"
    RISK_LEVEL_CHANGED = "risk.level.changed"

    # Investigation events
    INVESTIGATION_OPENED = "investigation.opened"
    INVESTIGATION_UPDATED = "investigation.updated"
    INVESTIGATION_CLOSED = "investigation.closed"

    # Agent coordination events
    AGENT_HANDOFF = "agent.handoff"
    AGENT_RESULT_PUBLISHED = "agent.result.published"
    CONTEXT_ENRICHMENT_NEEDED = "context.enrichment.needed"

    # Memory events
    PATTERN_LEARNED = "memory.pattern.learned"
    EPISODE_RECORDED = "memory.episode.recorded"


class AgentEvent(BaseModel):
    """
    Base event schema for all Kafka messages between agents.

    Every event has a consistent structure with:
      - Unique event ID and correlation ID for tracing
      - Source and target agent identification
      - Typed payload
      - Metadata for routing and filtering
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Groups related events in an analysis workflow",
    )
    session_id: str = ""
    source_agent: str = Field(..., description="Agent that produced this event")
    target_agent: Optional[str] = Field(
        default=None,
        description="Specific target agent, or None for broadcast",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


# ── Typed Event Factories ─────────────────────────────────────────────


def create_analysis_request(
    session_id: str,
    transaction_data: dict,
    correlation_id: Optional[str] = None,
) -> AgentEvent:
    """Create an analysis request event."""
    return AgentEvent(
        event_type=EventType.ANALYSIS_REQUESTED,
        correlation_id=correlation_id or str(uuid4()),
        session_id=session_id,
        source_agent="api_gateway",
        payload={"transaction": transaction_data},
    )


def create_fraud_detected_event(
    session_id: str,
    correlation_id: str,
    fraud_type: str,
    confidence: float,
    evidence: list[str],
    transaction_id: str,
    merchant_id: str,
) -> AgentEvent:
    """Create a fraud detection event for downstream agents."""
    return AgentEvent(
        event_type=EventType.FRAUD_DETECTED,
        correlation_id=correlation_id,
        session_id=session_id,
        source_agent="fraud_detection",
        target_agent="compliance",  # trigger compliance check
        payload={
            "fraud_type": fraud_type,
            "confidence": confidence,
            "evidence": evidence,
            "transaction_id": transaction_id,
            "merchant_id": merchant_id,
        },
    )


def create_compliance_result_event(
    session_id: str,
    correlation_id: str,
    violations: list[dict],
    is_compliant: bool,
    merchant_id: str,
) -> AgentEvent:
    """Create a compliance check result event."""
    return AgentEvent(
        event_type=(
            EventType.COMPLIANCE_CHECK_PASSED
            if is_compliant
            else EventType.COMPLIANCE_VIOLATION_FOUND
        ),
        correlation_id=correlation_id,
        session_id=session_id,
        source_agent="compliance",
        target_agent="risk_scoring",  # trigger risk calculation
        payload={
            "violations": violations,
            "is_compliant": is_compliant,
            "merchant_id": merchant_id,
        },
    )


def create_risk_score_event(
    session_id: str,
    correlation_id: str,
    merchant_id: str,
    overall_score: int,
    risk_level: str,
    factors: list[str],
) -> AgentEvent:
    """Create a risk score calculation event."""
    return AgentEvent(
        event_type=EventType.RISK_SCORE_CALCULATED,
        correlation_id=correlation_id,
        session_id=session_id,
        source_agent="risk_scoring",
        target_agent="orchestrator",
        payload={
            "merchant_id": merchant_id,
            "overall_score": overall_score,
            "risk_level": risk_level,
            "factors": factors,
        },
    )


def create_agent_handoff_event(
    session_id: str,
    correlation_id: str,
    source_agent: str,
    target_agent: str,
    reason: str,
    context: dict[str, Any],
) -> AgentEvent:
    """Create an agent-to-agent handoff event."""
    return AgentEvent(
        event_type=EventType.AGENT_HANDOFF,
        correlation_id=correlation_id,
        session_id=session_id,
        source_agent=source_agent,
        target_agent=target_agent,
        payload={"reason": reason, "context": context},
    )
