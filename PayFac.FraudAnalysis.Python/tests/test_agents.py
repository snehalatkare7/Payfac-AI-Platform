"""Tests for the multi-agent system."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Transaction, FraudType, RiskLevel
from app.models.fraud_alert import FraudAlert


class TestTransaction:
    """Tests for the Transaction domain model."""

    def test_amount_dollars_conversion(self):
        txn = Transaction(
            transaction_id="TXN001",
            merchant_id="M001",
            amount_cents=1500,
        )
        assert txn.amount_dollars == 15.00

    def test_amount_dollars_zero(self):
        txn = Transaction(
            transaction_id="TXN002",
            merchant_id="M001",
            amount_cents=0,
        )
        assert txn.amount_dollars == 0.0

    def test_to_analysis_text_contains_key_info(self):
        txn = Transaction(
            transaction_id="TXN003",
            merchant_id="M001",
            merchant_name="Test Shop",
            amount_cents=9999,
            card_brand="visa",
            card_last_four="1234",
            is_card_present=False,
        )
        text = txn.to_analysis_text()
        assert "TXN003" in text
        assert "Test Shop" in text
        assert "$99.99" in text
        assert "visa" in text
        assert "1234" in text
        assert "Card-not-present" in text


class TestFraudAlert:
    """Tests for the FraudAlert model."""

    def test_default_values(self):
        alert = FraudAlert()
        assert alert.risk_score == 0
        assert alert.risk_level == RiskLevel.LOW
        assert alert.fraud_type == FraudType.CARD_TESTING
        assert alert.evidence == []
        assert alert.confidence == 0.0

    def test_alert_with_values(self):
        alert = FraudAlert(
            merchant_id="M001",
            fraud_type=FraudType.TRANSACTION_LAUNDERING,
            risk_level=RiskLevel.CRITICAL,
            risk_score=85,
            summary="High risk transaction laundering detected",
            evidence=["MCC mismatch", "No refund activity"],
            confidence=0.92,
        )
        assert alert.merchant_id == "M001"
        assert alert.risk_score == 85
        assert len(alert.evidence) == 2
        assert alert.confidence == 0.92


class TestEnums:
    """Tests for domain enumerations."""

    def test_risk_level_numeric_values(self):
        assert RiskLevel.LOW.numeric_value == 0
        assert RiskLevel.MEDIUM.numeric_value == 25
        assert RiskLevel.HIGH.numeric_value == 50
        assert RiskLevel.CRITICAL.numeric_value == 75
        assert RiskLevel.SEVERE.numeric_value == 100

    def test_fraud_type_values(self):
        assert FraudType.CARD_TESTING.value == "card_testing"
        assert FraudType.TRANSACTION_LAUNDERING.value == "transaction_laundering"
        assert FraudType.BIN_ATTACK.value == "bin_attack"
