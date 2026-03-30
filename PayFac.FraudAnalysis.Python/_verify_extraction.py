"""Quick verification of fraud type extraction after fix."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Minimal stub to avoid heavy imports
class Stub:
    pass

agent = Stub()

# Paste the method directly to avoid import chain
import re

def _extract_fraud_type(result: dict) -> str:
    analysis = result.get("analysis", "").lower()
    no_fraud_patterns = [
        r"\bno fraud detected\b",
        r"\bfraud not detected\b",
        r"\bfraud type[:\s]*no fraud\b",
        r"\bfraud type[:\s]*none\b",
        r"\bdetermination[:\s]*no fraud\b",
    ]
    risk_contradictions = [
        "high risk", "transaction laundering", "suspicious",
        "country mismatch", "manual keyed", "manual_keyed",
        "elevated risk", "card-not-present", "cross-border",
    ]
    has_no_fraud_conclusion = any(re.search(p, analysis) for p in no_fraud_patterns)
    has_risk_signals = any(sig in analysis for sig in risk_contradictions)
    if has_no_fraud_conclusion and not has_risk_signals:
        return "unknown"

    type_map = {
        "card testing": "card_testing",
        "bin attack": "bin_attack",
        "transaction laundering": "transaction_laundering",
        "velocity abuse": "velocity_abuse",
        "synthetic identity": "synthetic_identity",
        "account takeover": "account_takeover",
        "friendly fraud": "friendly_fraud",
        "collusion": "cross_merchant_collusion",
    }
    for keyword, fraud_type in type_map.items():
        if keyword in analysis:
            return fraud_type

    if (
        "mcc mismatch" in analysis
        and any(sig in analysis for sig in ("international shipping", "cross-border", "shipping country", "billing country"))
    ):
        return "transaction_laundering"

    if "undisclosed business" in analysis or "merchant category mismatch" in analysis:
        return "transaction_laundering"

    high_risk_mcc_keywords = ["7995", "gambling", "casino", "6051", "money transfer"]
    has_high_risk_mcc = any(k in analysis for k in high_risk_mcc_keywords)
    has_cross_border = any(
        sig in analysis
        for sig in ("country mismatch", "cross-border", "shipping country", "billing country")
    )
    has_manual_cnp = ("manual keyed" in analysis or "manual_keyed" in analysis) and (
        "card-not-present" in analysis or "card not present" in analysis or "cnp" in analysis
    )
    if has_high_risk_mcc and (has_cross_border or has_manual_cnp):
        return "transaction_laundering"

    strong_signals = [
        "high risk", "suspicious", "elevated risk",
        "country mismatch", "manual keyed", "flagged",
    ]
    signal_count = sum(1 for s in strong_signals if s in analysis)
    if signal_count >= 3:
        return "transaction_laundering"

    return "unknown"


# === TEST CASES ===

# 1) High-risk gambling transaction (your failing case)
high_risk = {"analysis": """
Merchant "Lucky Strike Digital" is flagged high risk with a history of 1 fraud incident.
Transaction is high value ($5000) and manual keyed card-not-present, which is inherently higher risk.
Billing country (US) and shipping country (RU) mismatch is a known risk factor.
No similar past fraud cases or investigations found matching this exact pattern.
No compliance documents or known fraud patterns specifically address this scenario.
MCC 7995 is a gambling category. High transaction amount manually keyed.
Billing and shipping country mismatch (US to Russia).
Merchant flagged as high risk.
"""}
result1 = _extract_fraud_type(high_risk)
print(f"HIGH-RISK GAMBLING:  fraud_type = {result1}")
assert result1 != "unknown", f"FAIL: high-risk should NOT be unknown, got {result1}"

# 2) Transaction with "no fraud" substring in passing (should NOT be unknown)
passing_mention = {"analysis": """
No fraud patterns found in the database matching this transaction.
However, the billing country (US) and shipping country (GB) mismatch
combined with manual keyed entry and high risk merchant raises concern.
Transaction laundering indicators present.
"""}
result2 = _extract_fraud_type(passing_mention)
print(f"PASSING MENTION:     fraud_type = {result2}")
assert result2 == "transaction_laundering", f"FAIL: expected transaction_laundering, got {result2}"

# 3) Genuinely clean transaction (should be unknown)
clean = {"analysis": """
No fraud detected. The transaction is a normal grocery purchase.
Card-present chip transaction at a well-known merchant.
All indicators are within normal ranges.
Fraud Type: No fraud
"""}
result3 = _extract_fraud_type(clean)
print(f"CLEAN GROCERY:       fraud_type = {result3}")
assert result3 == "unknown", f"FAIL: clean should be unknown, got {result3}"

# 4) MCC mismatch laundering (previous fix)
mcc_mismatch = {"analysis": """
Evidence: MCC mismatch with international shipping; billing country US
while shipping country GB; manual-keyed CNP pattern observed.
"""}
result4 = _extract_fraud_type(mcc_mismatch)
print(f"MCC MISMATCH:        fraud_type = {result4}")
assert result4 == "transaction_laundering", f"FAIL: expected transaction_laundering, got {result4}"

# 5) Country mismatch + manual keyed + flagged (generic high risk)
generic_risk = {"analysis": """
Merchant is flagged as high risk. Manual keyed entry with country mismatch
between billing and shipping. Suspicious activity detected. Elevated risk.
"""}
result5 = _extract_fraud_type(generic_risk)
print(f"GENERIC HIGH-RISK:   fraud_type = {result5}")
assert result5 != "unknown", f"FAIL: generic high-risk should NOT be unknown, got {result5}"

print("\n✅ ALL TESTS PASSED")
