"""Validate signal-based scorer against all demo test cases.

Simulates the _compute_signal_based_score() logic with plausible
fraud_result / compliance_result dicts for each test case scenario.
"""

import json, sys, re

# Replicate the scorer constants
HIGH_RISK_MCC = {
    "7995", "7994", "5967", "5966", "5816", "5912",
    "5962", "5993", "6051", "6211", "6012", "4829",
}
HIGH_RISK_COUNTRIES = {
    "RU", "NG", "KP", "IR", "SY", "CU", "VE", "MM", "BY", "SD",
    "SO", "YE", "LY", "AF", "IQ", "PK", "UA",
}

_NEG_RE = re.compile(
    r"\b(no|not|without|nor|neither|lack\s+of|absence\s+of|no\s+abnormal)\b"
)

def _has_affirmative_mention(text_lower: str, keyword: str) -> bool:
    """Mirror of RiskScoringAgent._has_affirmative_mention."""
    idx = 0
    while True:
        pos = text_lower.find(keyword, idx)
        if pos == -1:
            return False
        sent_start = max(
            text_lower.rfind(".", 0, pos),
            text_lower.rfind("!", 0, pos),
            text_lower.rfind("\n", 0, pos),
        )
        prefix = text_lower[sent_start + 1 : pos]
        if not _NEG_RE.search(prefix):
            return True
        idx = pos + len(keyword)

def risk_level(score):
    if score <= 20: return "low"
    if score <= 40: return "medium"
    if score <= 60: return "high"
    if score <= 80: return "critical"
    return "severe"


def compute_signal_score(fraud_analysis_text: str, is_compliant: bool,
                         violations_count: int, txn: dict) -> dict:
    """Mirror of _compute_signal_based_score (signal-accumulation version)."""
    low = fraud_analysis_text.lower()
    breakdown = []

    # Baseline — negation-aware matching
    fraud_type_bases = [
        ("bin attack", 38),
        ("transaction laundering", 35),
        ("velocity abuse", 30),
        ("card testing", 24),
    ]
    score = 15
    matched_type = "unknown"
    fraud_type_matched = False
    for keyword, base in fraud_type_bases:
        if _has_affirmative_mention(low, keyword):
            score = base
            matched_type = keyword
            fraud_type_matched = True
            break
    breakdown.append(f"base({matched_type})={score}")

    # Confidence
    conf = 0.5  # assume default
    if fraud_type_matched:
        conf_pts = int(conf * 15)
        score += conf_pts
        breakdown.append(f"confidence({conf},fraud)=+{conf_pts}")
    else:
        conf_pts = int(conf * 10)
        score -= conf_pts
        breakdown.append(f"confidence({conf},no_fraud)=-{conf_pts}")

    # --- Collect risk signals with weights ---
    signals: list[tuple[str, int]] = []

    # -- Raw transaction field signals (authoritative) --
    entry_mode = str(txn.get("entry_mode", "") or "").lower()
    manual_keyed = "manual" in entry_mode or entry_mode == "manual_keyed"
    if manual_keyed:
        signals.append(("manual_keyed", 8))

    is_card_present = txn.get("is_card_present")
    cnp = is_card_present is False or str(is_card_present).lower() == "false"
    if cnp:
        signals.append(("cnp", 8))

    mcc = str(txn.get("merchant_category_code", "")).strip()
    if mcc in HIGH_RISK_MCC:
        signals.append(("high_risk_mcc", 12))

    try:
        amount_cents = int(txn.get("amount_cents", 0) or 0)
    except (TypeError, ValueError):
        amount_cents = 0
    if amount_cents >= 500_000:
        signals.append(("very_high_amount", 10))
    elif amount_cents >= 200_000:
        signals.append(("high_amount", 8))
    elif amount_cents >= 50_000:
        signals.append(("elevated_amount", 5))

    billing = str(txn.get("billing_country", "") or "").strip().upper()
    shipping_raw = txn.get("shipping_country")
    shipping = str(shipping_raw).strip().upper() if shipping_raw else ""
    cross_border = billing and shipping and billing != shipping
    if cross_border:
        if shipping in HIGH_RISK_COUNTRIES:
            signals.append(("cross_border_high_risk", 12))
        else:
            signals.append(("cross_border", 6))

    ip_country = str(txn.get("ip_country", "") or "").strip().upper()
    if ip_country and billing and ip_country != billing:
        signals.append(("ip_mismatch", 5))

    is_recurring = txn.get("is_recurring")
    if is_recurring is False or str(is_recurring).lower() == "false":
        signals.append(("non_recurring", 2))

    # -- Text-based signals (only when raw fields didn't already cover it) --
    if not manual_keyed and ("manual_keyed" in low or "manual keyed" in low):
        signals.append(("manual_keyed_text", 8))

    if not cross_border and "billing country" in low and "shipping country" in low and (
        "mismatch" in low or "cross-border" in low or "international shipping" in low
    ):
        signals.append(("cross_border_text", 8))

    # -- Aggregate signals with compound multiplier --
    signal_sum = sum(w for _, w in signals)
    n = len(signals)
    if n >= 5:
        signal_sum = int(signal_sum * 1.5)
    elif n >= 3:
        signal_sum = int(signal_sum * 1.3)

    for name, w in signals:
        breakdown.append(f"signal:{name}=+{w}")
    breakdown.append(f"signals({n})×{'1.5' if n >= 5 else '1.3' if n >= 3 else '1.0'}={signal_sum}")

    score += signal_sum

    # Compliance
    if not is_compliant:
        score += 8; breakdown.append("compliance:non_compliant=+8")
        score += min(violations_count * 3, 9)
        breakdown.append(f"compliance:violations({violations_count})=+{min(violations_count*3,9)}")

    score = max(0, min(score, 100))
    return {"score": score, "level": risk_level(score), "breakdown": breakdown}


# Define each test case with plausible analysis text
TEST_CASES = [
    {
        "id": "TC-002",
        "title": "Legitimate grocery — low risk",
        "fraud_text": "No significant fraud indicators detected. Legitimate in-store chip transaction.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5411", "amount_cents": 4599,
                "billing_country": "US", "shipping_country": None,
                "entry_mode": "chip"},
        "expected_max": 35, "expected_levels": ["low", "medium"],
    },
    {
        "id": "TC-003",
        "title": "Card testing — micro CNP",
        "fraud_text": "Suspected card testing pattern. Sub-dollar CNP transaction with known BIN.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "4814", "amount_cents": 99,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "ecommerce"},
        "expected_min": 20, "expected_levels": ["medium", "high"],
    },
    {
        "id": "TC-004",
        "title": "BIN attack — MCC 5816 digital goods",
        "fraud_text": "Suspected bin attack. Sequential PAN testing with micro amounts at digital goods merchant.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5816", "amount_cents": 100,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "ecommerce"},
        "expected_max_desired": 60,  # should NOT trigger investigation
        "expected_levels": ["medium", "high"],
    },
    {
        "id": "TC-005",
        "title": "Transaction laundering — MCC mismatch US→GB",
        "fraud_text": "Transaction laundering detected. MCC mismatch with international shipping. "
                      "Manual keyed entry. Billing country US, shipping country GB mismatch.",
        "is_compliant": False, "violations": 2,
        "txn": {"merchant_category_code": "5947", "amount_cents": 98500,
                "billing_country": "US", "shipping_country": "GB",
                "entry_mode": "manual_keyed", "is_card_present": False,
                "is_recurring": False},
        "expected_min": 41, "expected_levels": ["high", "critical", "severe"],
    },
    {
        "id": "TC-006",
        "title": "Velocity abuse — fuel station",
        "fraud_text": "Suspected velocity abuse. Sudden volume spike at fuel station.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5541", "amount_cents": 5000,
                "billing_country": "US", "shipping_country": None,
                "entry_mode": "contactless"},
        "expected_levels": ["low", "medium"],
    },
    {
        "id": "TC-007",
        "title": "Visa VDMP — supplements US→CA",
        "fraud_text": "No clear fraud pattern. Cross-border ecommerce transaction.",
        "is_compliant": False, "violations": 1,
        "txn": {"merchant_category_code": "5499", "amount_cents": 3099,
                "billing_country": "US", "shipping_country": "CA",
                "entry_mode": "ecommerce"},
        "expected_levels": ["medium", "high"],
    },
    {
        "id": "TC-008",
        "title": "MC ECM — subscription US→US",
        "fraud_text": "No significant fraud indicators. Recurring subscription payment.",
        "is_compliant": False, "violations": 1,
        "txn": {"merchant_category_code": "4899", "amount_cents": 1299,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "card_on_file"},
        "expected_levels": ["low", "medium"],
    },
    {
        "id": "TC-009",
        "title": "Synthetic identity — electronics $749.99",
        "fraud_text": "Possible synthetic identity. High-value first purchase from new customer.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5732", "amount_cents": 74999,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "ecommerce"},
        "expected_levels": ["low", "medium", "high"],
    },
    {
        "id": "TC-010",
        "title": "Friendly fraud — gaming subscription",
        "fraud_text": "No clear fraud pattern. Recurring digital subscription.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5815", "amount_cents": 1999,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "card_on_file"},
        "expected_levels": ["low", "medium"],
    },
    {
        "id": "TC-011",
        "title": "Cross-merchant collusion — MCC 5999",
        "fraud_text": "Network analysis pending. Catch-all merchant category.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5999", "amount_cents": 25500,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "ecommerce"},
        "expected_levels": ["low", "medium"],
    },
    {
        "id": "TC-012",
        "title": "Account takeover — airline $2450 US→FR",
        "fraud_text": "Possible account takeover. High-value CNP with cross-border shipping.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "4511", "amount_cents": 245000,
                "billing_country": "US", "shipping_country": "FR",
                "entry_mode": "ecommerce"},
        "expected_levels": ["medium", "high"],
    },
    {
        "id": "TC-013",
        "title": "Amex travel — MCC 4511 US→DE",
        "fraud_text": "No clear fraud pattern. Travel booking with cross-border delivery.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "4511", "amount_cents": 132400,
                "billing_country": "US", "shipping_country": "DE",
                "entry_mode": "ecommerce"},
        "expected_levels": ["low", "medium", "high"],
    },
    {
        "id": "TC-014",
        "title": "HIGH-RISK — MCC 7995 $5000 manual_keyed US→RU",
        "fraud_text": "Transaction laundering detected. MCC mismatch, manual keyed CNP, "
                      "billing country US, shipping country RU cross-border mismatch. "
                      "Gambling merchant with high-value manual-keyed CNP.",
        "is_compliant": False, "violations": 3,
        "txn": {"merchant_category_code": "7995", "amount_cents": 500000,
                "billing_country": "US", "shipping_country": "RU",
                "entry_mode": "manual_keyed", "is_card_present": False,
                "is_recurring": False},
        "expected_min": 61, "expected_levels": ["critical", "severe"],
    },
    {
        "id": "TC-017",
        "title": "Cleanup probe — generic low risk",
        "fraud_text": "No significant fraud indicators detected.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5999", "amount_cents": 2500,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "ecommerce"},
        "expected_levels": ["low", "medium"],
    },
    {
        "id": "TC-024",
        "title": "Velocity burst — MCC 5999 $99.99",
        "fraud_text": "Velocity monitoring active. Repeated same-merchant requests.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5999", "amount_cents": 9999,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "ecommerce"},
        "expected_levels": ["low", "medium"],
    },
    # --- User-reported transaction (txn-demo-0004) ---
    # LLM returned score 26 / medium; should be high.
    # No fraud type detected in LLM analysis, but raw signals stack.
    {
        "id": "TC-USR",
        "title": "Urban Gift Shop — CNP manual_keyed US→GB $985",
        "fraud_text": "No strong fraud indicators. Normal velocity. "
                      "High transaction amount with manual keyed entry mode. "
                      "Cross-border shipping differing from billing country.",
        "is_compliant": False, "violations": 1,
        "txn": {"merchant_category_code": "5947", "amount_cents": 98500,
                "billing_country": "US", "shipping_country": "GB",
                "entry_mode": "manual_keyed", "is_card_present": False,
                "is_recurring": False, "card_brand": "mastercard"},
        "expected_min": 41, "expected_levels": ["high", "critical"],
    },
    # --- Negation edge cases ---
    {
        "id": "NEG-001",
        "title": "Grocery — LLM says 'no velocity abuse' (user's exact bug)",
        "fraud_text": "Velocity check shows only 1 transaction in the last 60 minutes for "
                      "merchant FreshCart Market (m-grocery-101), indicating no abnormal "
                      "transaction frequency or velocity abuse. No fraud detected.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5411", "amount_cents": 4599,
                "billing_country": "US", "shipping_country": None,
                "entry_mode": "chip"},
        "expected_max": 30, "expected_levels": ["low", "medium"],
    },
    {
        "id": "NEG-002",
        "title": "Negated laundering + affirmed velocity abuse",
        "fraud_text": "No transaction laundering detected. However, velocity abuse pattern "
                      "is confirmed with 15 transactions in 5 minutes.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5999", "amount_cents": 5000,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "ecommerce"},
        "expected_min": 30, "expected_levels": ["medium", "high"],
    },
    {
        "id": "NEG-003",
        "title": "All fraud types negated — should use default base 15",
        "fraud_text": "No card testing, no bin attack, no velocity abuse, no transaction "
                      "laundering. Legitimate chip transaction.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5411", "amount_cents": 2500,
                "billing_country": "US", "shipping_country": None,
                "entry_mode": "chip"},
        "expected_max": 30, "expected_levels": ["low", "medium"],
    },
    {
        "id": "NEG-004",
        "title": "Affirmed laundering — should still score high",
        "fraud_text": "Transaction laundering detected with high confidence. "
                      "MCC mismatch, manual keyed entry, billing country US, "
                      "shipping country RU cross-border mismatch.",
        "is_compliant": False, "violations": 3,
        "txn": {"merchant_category_code": "7995", "amount_cents": 500000,
                "billing_country": "US", "shipping_country": "RU",
                "entry_mode": "manual_keyed"},
        "expected_min": 61, "expected_levels": ["critical", "severe"],
    },
    {
        "id": "NEG-005",
        "title": "Mixed: 'not card testing' but then 'bin attack detected'",
        "fraud_text": "This is not card testing. Bin attack detected with sequential PANs.",
        "is_compliant": True, "violations": 0,
        "txn": {"merchant_category_code": "5816", "amount_cents": 100,
                "billing_country": "US", "shipping_country": "US",
                "entry_mode": "ecommerce"},
        "expected_min": 38, "expected_levels": ["medium", "high"],
    },
]


def main():
    all_pass = True
    print(f"{'ID':<10} {'Score':>5} {'Level':<10} {'Expected Levels':<30} {'Pass?':<6} Title")
    print("=" * 110)

    for tc in TEST_CASES:
        r = compute_signal_score(
            fraud_analysis_text=tc["fraud_text"],
            is_compliant=tc["is_compliant"],
            violations_count=tc["violations"],
            txn=tc["txn"],
        )
        score = r["score"]
        level = r["level"]
        exp_levels = tc["expected_levels"]
        ok = level in exp_levels

        # Additional checks
        if "expected_max" in tc and score > tc["expected_max"]:
            ok = False
        if "expected_min" in tc and score < tc["expected_min"]:
            ok = False

        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False

        print(f"{tc['id']:<10} {score:>5} {level:<10} {str(exp_levels):<30} {status:<6} {tc['title']}")
        if not ok:
            print(f"  >> BREAKDOWN: {', '.join(r['breakdown'])}")

    print()
    if all_pass:
        print("ALL TEST CASES PASS")
    else:
        print("SOME TEST CASES FAILED - review above")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
