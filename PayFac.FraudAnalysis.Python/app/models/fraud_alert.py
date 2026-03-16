"""Fraud alert and analysis result models."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import uuid4

from app.models.enums import FraudType, RiskLevel, InvestigationOutcome


class ComplianceViolation(BaseModel):
    """A specific card brand compliance violation."""

    card_brand: str
    rule_id: str
    rule_description: str
    severity: str
    recommended_action: str


class FraudAlert(BaseModel):
    """Represents a fraud analysis finding from the multi-agent system."""

    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    merchant_id: str = ""
    transaction_id: str = ""
    fraud_type: FraudType = FraudType.CARD_TESTING
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: int = Field(default=0, ge=0, le=100)
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    compliance_violations: list[ComplianceViolation] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    analyzed_by_agents: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RiskScore(BaseModel):
    """Composite risk score from the risk scoring agent."""

    merchant_id: str
    overall_score: int = Field(ge=0, le=100)
    fraud_score: int = Field(ge=0, le=100)
    compliance_score: int = Field(ge=0, le=100)
    velocity_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    factors: list[str] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class MerchantRiskProfile(BaseModel):
    """Long-term risk profile for a merchant."""

    merchant_id: str
    merchant_name: str = ""
    mcc: str = ""
    historical_fraud_count: int = 0
    chargeback_ratio: float = 0.0
    average_risk_score: float = 0.0
    known_fraud_types: list[FraudType] = Field(default_factory=list)
    last_review_date: Optional[datetime] = None
    is_high_risk: bool = False
    notes: list[str] = Field(default_factory=list)


class InvestigationEpisode(BaseModel):
    """Records a specific fraud investigation episode for episodic memory."""

    episode_id: str = Field(default_factory=lambda: str(uuid4()))
    merchant_id: str
    transaction_ids: list[str] = Field(default_factory=list)
    fraud_type: FraudType
    outcome: InvestigationOutcome = InvestigationOutcome.MONITORING
    narrative: str = ""
    evidence_collected: list[str] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)
    agents_involved: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    resolution_notes: str = ""

    def to_narrative(self) -> str:
        """Convert episode to natural language for embedding."""
        return (
            f"Investigation episode for merchant {self.merchant_id}: "
            f"Suspected {self.fraud_type.value} fraud. "
            f"Transactions involved: {', '.join(self.transaction_ids)}. "
            f"{self.narrative} "
            f"Evidence: {'; '.join(self.evidence_collected)}. "
            f"Actions: {'; '.join(self.actions_taken)}. "
            f"Outcome: {self.outcome.value}. "
            f"Notes: {self.resolution_notes}"
        )
