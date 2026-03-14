"""
Fraud Detection Agent
====================
Uses all fraud categories and data from fraud_data_generator to identify fraudulent transactions.
Checks against: money_laundering, card_present_fraud, refund_fraud, card_not_present,
account_takeover, identity_theft, friendly_fraud (chargeback), bust_out_fraud.
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Full FRAUD_TYPES from fraud_data_generator - each category with specific rules
# ---------------------------------------------------------------------------

FRAUD_TYPES = {
    "money_laundering": {
        "amount_range": (500, 9999),
        "risk_range": (7, 10),
        "channels": ["pos", "online", "atm"],
        "card_present": True,
        "mccs": {"6051", "6011", "6012"},  # money orders, ATM - structuring, smurfing
    },
    "bust_out_fraud": {
        "amount_range": (1000, 50000),
        "risk_range": (7, 10),
        "channels": ["online", "pos", "mobile"],
        "card_present": False,
        "mccs": {"5944", "5094", "4511", "7011"},  # jewelry, airlines, lodging - high-ticket
    },
    "account_takeover": {
        "amount_range": (50, 15000),
        "risk_range": (6, 10),
        "channels": ["online", "mobile", "pos"],
        "card_present": False,
        "mccs": {"5812", "5045", "7372", "7011"},  # online/e-commerce common
    },
    "identity_theft": {
        "amount_range": (200, 25000),
        "risk_range": (5, 9),
        "channels": ["online", "pos", "mobile"],
        "card_present": False,
        "mccs": {"5122", "8099", "5912"},  # medical, health, drugs
    },
    "card_not_present": {
        "amount_range": (10, 3500),
        "risk_range": (4, 9),
        "channels": ["online", "mobile"],
        "card_present": False,
        "mccs": {"5045", "7372", "5812", "5732", "5999"},  # e-commerce, electronics
    },
    "friendly_fraud": {
        "amount_range": (15, 2000),
        "risk_range": (2, 6),
        "channels": ["online", "mobile"],
        "card_present": False,
        "mccs": {"5999", "5310", "5732"},  # chargeback abuse common in retail
    },
    "card_present_fraud": {
        "amount_range": (20, 5000),
        "risk_range": (4, 8),
        "channels": ["pos", "atm"],
        "card_present": True,
        "mccs": {"6011", "5541", "5411", "5912"},  # ATM, fuel, grocery - skimming, lost/stolen
    },
    "refund_fraud": {
        "amount_range": (25, 3000),
        "risk_range": (2, 6),
        "channels": ["pos", "online"],
        "card_present": True,
        "mccs": {"5651", "5661", "5732", "5944"},  # clothing, shoes, electronics, jewelry - wardrobing
    },
}

# High-risk MCCs regardless of category (gambling, jewelry)
HIGH_RISK_MCCS = {"7995", "6051", "6011", "5944", "5094", "4829"}
MEDIUM_RISK_MCCS = {"5732", "5045", "7011", "5661"}

# Countries from fraud_data_generator COUNTRY_DATA
HIGH_RISK_COUNTRIES = {"NG", "RU", "GH", "PK", "VN", "ID"}
MEDIUM_RISK_COUNTRIES = {"BR", "MX", "ZA", "KE", "PH"}


def _get_db_connection():
    """Lazy DB connection for optional PostgreSQL fraud_cases lookup."""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return None
    try:
        import psycopg2

        return psycopg2.connect(dsn)
    except Exception as e:
        logger.warning("Could not connect to fraud_cases DB: %s", e)
        return None


def _query_fraud_by_type_and_mcc(conn, mcc: str, amount: float) -> Optional[dict]:
    """
    Query fraud_cases for each fraud_type matching MCC and amount.
    Returns per-category match counts and avg risk.
    """
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT fraud_type, COUNT(*) AS match_count, AVG(risk_score)::float AS avg_risk
            FROM fraud_cases
            WHERE mcc = %s
              AND transaction_amount BETWEEN %s AND %s
            GROUP BY fraud_type
            """,
            (mcc, amount * 0.5, amount * 1.5),
        )
        rows = cur.fetchall()
        cur.close()
        if rows:
            return {
                row[0]: {"match_count": row[1], "avg_risk": row[2]} for row in rows
            }
    except Exception as e:
        logger.debug("fraud_cases query failed: %s", e)
    return None


def _channel_matches(fraud_channels: list[str], txn_channel: Optional[str]) -> bool:
    """True if txn channel matches fraud type, or if txn has no channel (assume match)."""
    if not txn_channel:
        return True
    txn_ch = txn_channel.lower().strip()
    return txn_ch in [c.lower() for c in fraud_channels]


def _card_present_matches(fraud_card_present: bool, txn_card_present: Optional[bool]) -> bool:
    """True if card_present aligns, or if txn has no flag (assume match)."""
    if txn_card_present is None:
        return True
    return txn_card_present == fraud_card_present


def detect_fraud(txn: dict, velocity: int = 0) -> dict[str, Any]:
    """
    Identify fraud risk using all fraud categories from fraud_data_generator.

    Expected txn keys: transaction_id, amount, mcc, geo_location, card_token
    Optional: transaction_channel, card_present, transaction_type (refund, purchase, etc.)

    Returns:
        {
            "risk": int (0-1000),
            "reason": str,
            "fraud_types": list[str],
            "signals": dict,
        }
    """
    amount = float(txn.get("amount", 0))
    mcc = str(txn.get("mcc", "")).strip()
    geo = str(txn.get("geo_location", "unknown")).strip().lower()
    txn_channel = txn.get("transaction_channel") or txn.get("channel")
    txn_card_present = txn.get("card_present")
    txn_type = str(txn.get("transaction_type", "purchase")).lower().strip()

    signals: dict[str, Any] = {}
    fraud_types: list[str] = []
    risk = 0
    reasons: list[str] = []

    # 1. Velocity
    if velocity > 5:
        risk += 400
        fraud_types.append("velocity_attack")
        reasons.append("velocity attack")
    elif velocity > 2:
        risk += 150
        reasons.append("elevated velocity")

    # 2. Per-fraud-type checks (all 8 categories from fraud_data_generator)
    for fraud_type, meta in FRAUD_TYPES.items():
        min_amt, max_amt = meta["amount_range"]
        if not (min_amt <= amount <= max_amt):
            continue
        if not _channel_matches(meta["channels"], txn_channel):
            continue
        if not _card_present_matches(meta["card_present"], txn_card_present):
            continue

        # Refund fraud: prioritize when transaction_type is refund
        if fraud_type == "refund_fraud":
            if txn_type == "refund" or mcc in meta["mccs"]:
                risk += 180
                fraud_types.append(fraud_type)
                reasons.append(f"refund_fraud: amount + {'refund type' if txn_type == 'refund' else f'MCC {mcc}'}")
                continue

        # Money laundering: structure amounts 500-9999, specific MCCs
        if fraud_type == "money_laundering" and mcc in meta["mccs"]:
            risk += 280
            fraud_types.append(fraud_type)
            reasons.append(f"money_laundering: MCC {mcc} + amount range")
            continue

        # Card present fraud: ATM/fuel skimming, lost/stolen
        if fraud_type == "card_present_fraud" and mcc in meta["mccs"]:
            risk += 220
            fraud_types.append(fraud_type)
            reasons.append(f"card_present_fraud: MCC {mcc} (pos/atm)")
            continue

        # Bust-out: high amounts, jewelry/airlines/lodging
        if fraud_type == "bust_out_fraud" and mcc in meta["mccs"]:
            risk += 300
            fraud_types.append(fraud_type)
            reasons.append(f"bust_out_fraud: high-ticket MCC {mcc}")
            continue

        # Identity theft: medical/health MCCs
        if fraud_type == "identity_theft" and mcc in meta["mccs"]:
            risk += 200
            fraud_types.append(fraud_type)
            reasons.append(f"identity_theft: MCC {mcc}")
            continue

        # Card not present: e-commerce MCCs
        if fraud_type == "card_not_present" and mcc in meta["mccs"]:
            risk += 200
            fraud_types.append(fraud_type)
            reasons.append(f"card_not_present: MCC {mcc}")
            continue

        # Friendly fraud / chargeback: retail MCCs
        if fraud_type == "friendly_fraud" and mcc in meta["mccs"]:
            risk += 120
            fraud_types.append(fraud_type)
            reasons.append(f"friendly_fraud/chargeback: MCC {mcc}")
            continue

        # Account takeover: online channels + matching MCC
        if fraud_type == "account_takeover" and mcc in meta["mccs"]:
            risk += 200
            fraud_types.append(fraud_type)
            reasons.append(f"account_takeover: MCC {mcc}")
            continue

    # 3. Amount in high-risk fraud range when no specific match
    # money_laundering: 500-9999 (structuring), bust_out: 1000-50000
    if not fraud_types and (
        (2000 <= amount <= 9999) or (10000 <= amount <= 50000)
    ):
        risk += 50
        reasons.append("amount in high-risk fraud range")

    # 4. Standalone high/medium risk MCC (if no category match yet)
    if not fraud_types:
        if mcc in HIGH_RISK_MCCS:
            risk += 250
            fraud_types.append("high_risk_mcc")
            reasons.append(f"high-risk MCC {mcc}")
        elif mcc in MEDIUM_RISK_MCCS:
            risk += 100
            reasons.append(f"medium-risk MCC {mcc}")

    # 5. Geo anomaly
    geo_upper = geo.upper() if geo else ""
    if geo not in ("home_country", "home", "") and "home" not in geo:
        risk += 200
        signals["geo_anomaly"] = True
        reasons.append("geo mismatch")
    if geo_upper in HIGH_RISK_COUNTRIES:
        risk += 150
        reasons.append("high-risk country")
    elif geo_upper in MEDIUM_RISK_COUNTRIES:
        risk += 75
        reasons.append("medium-risk country")

    # 6. DB: fraud_cases per fraud_type (data from fraud_data_generator)
    conn = _get_db_connection()
    if conn:
        try:
            db_results = _query_fraud_by_type_and_mcc(conn, mcc, amount)
            if db_results:
                for ftype, data in db_results.items():
                    if data["match_count"] > 0:
                        db_risk = int(data["avg_risk"] * 400)
                        risk += min(250, db_risk)
                        if ftype not in fraud_types:
                            fraud_types.append(ftype)
                        signals[f"db_{ftype}"] = data["match_count"]
                        reasons.append(f"{data['match_count']} {ftype} case(s) in DB")
        finally:
            conn.close()

    risk = min(1000, risk)
    reason = "; ".join(reasons) if reasons else "normal activity"

    return {
        "risk": risk,
        "reason": reason,
        "fraud_types": list(dict.fromkeys(fraud_types)),
        "signals": signals,
    }
