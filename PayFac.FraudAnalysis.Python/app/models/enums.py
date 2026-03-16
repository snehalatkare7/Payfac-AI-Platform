"""Domain enumerations for the fraud analysis platform."""

from enum import Enum


class FraudType(str, Enum):
    """Identifies the category of fraud detected or suspected."""

    CARD_TESTING = "card_testing"
    TRANSACTION_LAUNDERING = "transaction_laundering"
    EXCESSIVE_CHARGEBACKS = "excessive_chargebacks"
    SYNTHETIC_IDENTITY = "synthetic_identity"
    ACCOUNT_TAKEOVER = "account_takeover"
    FRIENDLY_FRAUD = "friendly_fraud"
    VELOCITY_ABUSE = "velocity_abuse"
    CROSS_MERCHANT_COLLUSION = "cross_merchant_collusion"
    BIN_ATTACK = "bin_attack"


class RiskLevel(str, Enum):
    """Risk classification for merchants and transactions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    SEVERE = "severe"

    @property
    def numeric_value(self) -> int:
        return {
            "low": 0,
            "medium": 25,
            "high": 50,
            "critical": 75,
            "severe": 100,
        }[self.value]


class AgentRole(str, Enum):
    """Agent roles in the multi-agent system."""

    ORCHESTRATOR = "orchestrator"
    FRAUD_DETECTION = "fraud_detection"
    COMPLIANCE = "compliance"
    RISK_SCORING = "risk_scoring"
    INVESTIGATION = "investigation"


class CardBrand(str, Enum):
    """Supported card brands for compliance checks."""

    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"
    ALL = "all"


class InvestigationOutcome(str, Enum):
    """Outcome of a fraud investigation episode."""

    CONFIRMED_FRAUD = "confirmed_fraud"
    FALSE_POSITIVE = "false_positive"
    ESCALATED = "escalated"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
