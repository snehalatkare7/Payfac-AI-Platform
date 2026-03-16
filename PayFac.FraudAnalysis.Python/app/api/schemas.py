"""API request/response schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AnalyzeTransactionRequest(BaseModel):
    """Request to analyze a transaction for fraud."""

    transaction_id: str = Field(..., description="Unique transaction identifier")
    merchant_id: str = Field(..., description="Merchant identifier")
    merchant_name: str = Field(default="", description="Merchant display name")
    merchant_category_code: str = Field(default="", description="MCC code")
    amount_cents: int = Field(..., description="Amount in cents")
    currency: str = Field(default="USD")
    card_brand: str = Field(default="")
    card_last_four: str = Field(default="")
    card_bin: str = Field(default="")
    is_card_present: bool = Field(default=False)
    entry_mode: str = Field(default="")
    ip_address: Optional[str] = None
    billing_country: str = Field(default="")
    shipping_country: Optional[str] = None
    customer_id: Optional[str] = None
    is_recurring: bool = Field(default=False)


class FraudAlertResponse(BaseModel):
    """Fraud analysis result response."""

    alert_id: str
    merchant_id: str
    transaction_id: str
    fraud_type: str
    risk_level: str
    risk_score: int
    summary: str
    evidence: list[str]
    recommendations: list[str]
    confidence: float
    analyzed_by_agents: list[str]
    analyzed_at: datetime


class BatchAnalyzeRequest(BaseModel):
    """Request to analyze multiple transactions."""

    transactions: list[AnalyzeTransactionRequest]


class BatchAnalyzeResponse(BaseModel):
    """Batch analysis results."""

    total: int
    alerts: list[FraudAlertResponse]
    high_risk_count: int
    processing_time_ms: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    neondb_connected: bool
    redis_connected: bool
    kafka_connected: bool


class MerchantRiskProfileResponse(BaseModel):
    """Merchant risk profile response."""

    merchant_id: str
    merchant_name: str
    mcc: str
    historical_fraud_count: int
    chargeback_ratio: float
    average_risk_score: float
    known_fraud_types: list[str]
    is_high_risk: bool
    last_review_date: Optional[datetime] = None


class FeedbackRequest(BaseModel):
    """Feedback on a previous analysis decision."""

    decision_id: str = Field(..., description="The alert_id / episode_id to provide feedback for")
    was_correct: bool = Field(..., description="Whether the fraud determination was correct")
    feedback_notes: str = Field(default="", description="Optional notes about the feedback")
