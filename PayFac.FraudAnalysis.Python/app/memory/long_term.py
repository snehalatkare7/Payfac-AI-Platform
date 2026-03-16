"""Long-term memory backed by NeonDB (PostgreSQL).

Long-term memory is persistent and survives across sessions. It stores:
  - Merchant risk profiles (learned over time)
  - Known fraud patterns discovered by agents
  - Historical analysis decisions and their accuracy
  - Agent performance metrics for self-improvement

This memory grows over time as the system processes more transactions
and investigations, enabling the agents to become more accurate.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from app.infrastructure.neondb import NeonDbClient
from app.models import FraudType, MerchantRiskProfile

logger = logging.getLogger(__name__)


class LongTermMemory:
    """
    NeonDB-backed persistent memory for learned patterns and profiles.

    Tables used:
      - merchant_risk_profiles: Accumulated risk data per merchant
      - learned_fraud_patterns: Patterns discovered through analysis
      - analysis_decisions: Historical decisions for feedback loops
    """

    def __init__(self, neondb_client: NeonDbClient):
        self._db = neondb_client

    async def initialize_tables(self) -> None:
        """Create long-term memory tables if they don't exist."""
        await self._db.execute_command("""
            CREATE TABLE IF NOT EXISTS merchant_risk_profiles (
                merchant_id TEXT PRIMARY KEY,
                merchant_name TEXT DEFAULT '',
                mcc TEXT DEFAULT '',
                historical_fraud_count INTEGER DEFAULT 0,
                chargeback_ratio REAL DEFAULT 0.0,
                average_risk_score REAL DEFAULT 0.0,
                known_fraud_types JSONB DEFAULT '[]',
                last_review_date TIMESTAMPTZ,
                is_high_risk BOOLEAN DEFAULT FALSE,
                notes JSONB DEFAULT '[]',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await self._db.execute_command("""
            CREATE TABLE IF NOT EXISTS learned_fraud_patterns (
                pattern_id TEXT PRIMARY KEY,
                fraud_type TEXT NOT NULL,
                pattern_description TEXT NOT NULL,
                indicators JSONB DEFAULT '[]',
                confidence REAL DEFAULT 0.0,
                times_seen INTEGER DEFAULT 1,
                merchant_categories JSONB DEFAULT '[]',
                first_seen TIMESTAMPTZ DEFAULT NOW(),
                last_seen TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await self._db.execute_command("""
            CREATE TABLE IF NOT EXISTS analysis_decisions (
                decision_id TEXT PRIMARY KEY,
                merchant_id TEXT NOT NULL,
                transaction_ids JSONB DEFAULT '[]',
                fraud_type TEXT,
                risk_score INTEGER,
                decision TEXT NOT NULL,
                was_correct BOOLEAN,
                feedback_notes TEXT DEFAULT '',
                decided_at TIMESTAMPTZ DEFAULT NOW(),
                feedback_at TIMESTAMPTZ
            )
        """)

        logger.info("Long-term memory tables initialized")

    # ── Merchant Risk Profiles ────────────────────────────────────────

    async def store_merchant_profile(self, profile: MerchantRiskProfile) -> None:
        """Store or update a merchant's risk profile."""
        await self._db.execute_command(
            """
            INSERT INTO merchant_risk_profiles
                (merchant_id, merchant_name, mcc, historical_fraud_count,
                 chargeback_ratio, average_risk_score, known_fraud_types,
                 last_review_date, is_high_risk, notes, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
            ON CONFLICT (merchant_id) DO UPDATE SET
                merchant_name = EXCLUDED.merchant_name,
                mcc = EXCLUDED.mcc,
                historical_fraud_count = EXCLUDED.historical_fraud_count,
                chargeback_ratio = EXCLUDED.chargeback_ratio,
                average_risk_score = EXCLUDED.average_risk_score,
                known_fraud_types = EXCLUDED.known_fraud_types,
                last_review_date = EXCLUDED.last_review_date,
                is_high_risk = EXCLUDED.is_high_risk,
                notes = EXCLUDED.notes,
                updated_at = NOW()
            """,
            profile.merchant_id,
            profile.merchant_name,
            profile.mcc,
            profile.historical_fraud_count,
            profile.chargeback_ratio,
            profile.average_risk_score,
            json.dumps([ft.value for ft in profile.known_fraud_types]),
            profile.last_review_date,
            profile.is_high_risk,
            json.dumps(profile.notes),
        )
        logger.debug("Stored merchant profile: %s", profile.merchant_id)

    async def get_merchant_profile(
        self, merchant_id: str
    ) -> Optional[MerchantRiskProfile]:
        """Retrieve a merchant's risk profile."""
        rows = await self._db.execute_query(
            "SELECT * FROM merchant_risk_profiles WHERE merchant_id = $1",
            merchant_id,
        )
        if not rows:
            return None

        row = rows[0]
        fraud_types_raw = row["known_fraud_types"]
        if isinstance(fraud_types_raw, str):
            fraud_types_raw = json.loads(fraud_types_raw)

        notes_raw = row["notes"]
        if isinstance(notes_raw, str):
            notes_raw = json.loads(notes_raw)

        return MerchantRiskProfile(
            merchant_id=row["merchant_id"],
            merchant_name=row["merchant_name"],
            mcc=row["mcc"],
            historical_fraud_count=row["historical_fraud_count"],
            chargeback_ratio=row["chargeback_ratio"],
            average_risk_score=row["average_risk_score"],
            known_fraud_types=[FraudType(ft) for ft in fraud_types_raw],
            last_review_date=row["last_review_date"],
            is_high_risk=row["is_high_risk"],
            notes=notes_raw,
        )

    async def get_high_risk_merchants(self) -> list[MerchantRiskProfile]:
        """Retrieve all merchants flagged as high risk."""
        rows = await self._db.execute_query(
            "SELECT * FROM merchant_risk_profiles WHERE is_high_risk = TRUE ORDER BY average_risk_score DESC"
        )
        profiles = []
        for row in rows:
            fraud_types_raw = row["known_fraud_types"]
            if isinstance(fraud_types_raw, str):
                fraud_types_raw = json.loads(fraud_types_raw)
            notes_raw = row["notes"]
            if isinstance(notes_raw, str):
                notes_raw = json.loads(notes_raw)

            profiles.append(MerchantRiskProfile(
                merchant_id=row["merchant_id"],
                merchant_name=row["merchant_name"],
                mcc=row["mcc"],
                historical_fraud_count=row["historical_fraud_count"],
                chargeback_ratio=row["chargeback_ratio"],
                average_risk_score=row["average_risk_score"],
                known_fraud_types=[FraudType(ft) for ft in fraud_types_raw],
                last_review_date=row["last_review_date"],
                is_high_risk=row["is_high_risk"],
                notes=notes_raw,
            ))
        return profiles

    # ── Learned Fraud Patterns ────────────────────────────────────────

    async def store_fraud_pattern(
        self,
        pattern_id: str,
        fraud_type: FraudType,
        description: str,
        indicators: list[str],
        confidence: float,
        merchant_categories: Optional[list[str]] = None,
    ) -> None:
        """Store a newly discovered fraud pattern."""
        await self._db.execute_command(
            """
            INSERT INTO learned_fraud_patterns
                (pattern_id, fraud_type, pattern_description, indicators,
                 confidence, merchant_categories, last_seen)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (pattern_id) DO UPDATE SET
                confidence = GREATEST(learned_fraud_patterns.confidence, EXCLUDED.confidence),
                times_seen = learned_fraud_patterns.times_seen + 1,
                indicators = EXCLUDED.indicators,
                last_seen = NOW()
            """,
            pattern_id,
            fraud_type.value,
            description,
            json.dumps(indicators),
            confidence,
            json.dumps(merchant_categories or []),
        )
        logger.info(
            "Stored fraud pattern: %s (type=%s, confidence=%.2f)",
            pattern_id, fraud_type.value, confidence,
        )

    async def get_patterns_for_category(self, mcc: str) -> list[dict]:
        """Retrieve fraud patterns relevant to a merchant category."""
        rows = await self._db.execute_query(
            """
            SELECT * FROM learned_fraud_patterns
            WHERE merchant_categories ? $1 OR merchant_categories = '[]'::jsonb
            ORDER BY confidence DESC, times_seen DESC
            """,
            mcc,
        )
        return [dict(row) for row in rows]

    async def get_patterns_by_type(self, fraud_type: FraudType) -> list[dict]:
        """Retrieve all patterns for a specific fraud type."""
        rows = await self._db.execute_query(
            """
            SELECT * FROM learned_fraud_patterns
            WHERE fraud_type = $1
            ORDER BY confidence DESC, times_seen DESC
            """,
            fraud_type.value,
        )
        return [dict(row) for row in rows]

    # ── Analysis Decisions (Feedback Loop) ────────────────────────────

    async def record_decision(
        self,
        decision_id: str,
        merchant_id: str,
        transaction_ids: list[str],
        fraud_type: Optional[FraudType],
        risk_score: int,
        decision: str,
    ) -> None:
        """Record an analysis decision for future feedback."""
        await self._db.execute_command(
            """
            INSERT INTO analysis_decisions
                (decision_id, merchant_id, transaction_ids, fraud_type,
                 risk_score, decision)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            decision_id,
            merchant_id,
            json.dumps(transaction_ids),
            fraud_type.value if fraud_type else None,
            risk_score,
            decision,
        )

    async def update_decision_feedback(
        self,
        decision_id: str,
        was_correct: bool,
        feedback_notes: str = "",
    ) -> None:
        """Update a previous decision with correctness feedback."""
        await self._db.execute_command(
            """
            UPDATE analysis_decisions
            SET was_correct = $2, feedback_notes = $3, feedback_at = NOW()
            WHERE decision_id = $1
            """,
            decision_id,
            was_correct,
            feedback_notes,
        )
        logger.info(
            "Decision feedback recorded: %s (correct=%s)", decision_id, was_correct
        )
