"""Initialize NeonDB schema and seed data.

Run this script to set up the NeonDB vector tables and
optionally seed with sample fraud patterns.

Usage:
    python -m scripts.init_neondb
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.infrastructure.neondb import NeonDbClient
from app.infrastructure.llm_client import LLMClient
from app.rag.vector_store import VectorStore
from app.memory.long_term import LongTermMemory
from app.memory.episodic import EpisodicMemory


# Sample fraud patterns for seeding
SAMPLE_FRAUD_PATTERNS = [
    {
        "id": "pattern-card-testing-001",
        "content": (
            "Card Testing Pattern: Multiple small transactions ($0.50-$2.00) from the same "
            "merchant within a 5-minute window, using sequential card numbers from the same "
            "BIN range. Typically card-not-present transactions with different billing addresses "
            "but same IP address. Decline rate exceeds 70%."
        ),
        "metadata": {
            "fraud_type": "card_testing",
            "severity": "high",
            "indicators": "small_amounts,rapid_succession,same_bin,high_decline_rate",
        },
    },
    {
        "id": "pattern-transaction-laundering-001",
        "content": (
            "Transaction Laundering Pattern: Merchant registered as a retail store but "
            "processing transactions that don't match their MCC. Average ticket size inconsistent "
            "with merchant category. No refund activity. High percentage of international cards. "
            "Website content doesn't match registered business description."
        ),
        "metadata": {
            "fraud_type": "transaction_laundering",
            "severity": "critical",
            "indicators": "mcc_mismatch,no_refunds,international_cards,website_mismatch",
        },
    },
    {
        "id": "pattern-velocity-abuse-001",
        "content": (
            "Velocity Abuse Pattern: Transaction count exceeds 200% of merchant's 30-day "
            "rolling average. Sudden spike in volume without corresponding marketing or seasonal "
            "explanation. Transactions concentrated in off-business hours. Multiple transactions "
            "with identical amounts."
        ),
        "metadata": {
            "fraud_type": "velocity_abuse",
            "severity": "medium",
            "indicators": "volume_spike,off_hours,identical_amounts",
        },
    },
    {
        "id": "pattern-synthetic-identity-001",
        "content": (
            "Synthetic Identity Fraud Pattern: Customer profile created with SSN that has "
            "limited credit history. Address is a PO Box or commercial mail receiving agency. "
            "Multiple accounts opened in short timeframe. Credit profile built up slowly with "
            "small purchases before large transactions."
        ),
        "metadata": {
            "fraud_type": "synthetic_identity",
            "severity": "high",
            "indicators": "thin_credit_file,po_box_address,rapid_account_creation,bust_out",
        },
    },
    {
        "id": "pattern-friendly-fraud-001",
        "content": (
            "Friendly Fraud Pattern: Legitimate cardholder makes a purchase, receives the goods "
            "or services, then files a chargeback claiming unauthorized transaction. Often seen "
            "with digital goods, subscription services, and online gambling. Cardholder has "
            "history of previous chargebacks across multiple merchants."
        ),
        "metadata": {
            "fraud_type": "friendly_fraud",
            "severity": "medium",
            "indicators": "repeat_chargebacks,digital_goods,subscription,delivery_confirmed",
        },
    },
    {
        "id": "pattern-bin-attack-001",
        "content": (
            "BIN Attack Pattern: Automated testing of card numbers generated from a single BIN "
            "range. Hundreds of authorization attempts in minutes with incrementing card numbers. "
            "Small test amounts ($0.01-$1.00). Same merchant, same terminal ID. Very high "
            "decline rate (95%+). Often followed by larger fraudulent charges on validated cards."
        ),
        "metadata": {
            "fraud_type": "bin_attack",
            "severity": "critical",
            "indicators": "sequential_pans,micro_amounts,automated_speed,high_decline_rate",
        },
    },
    {
        "id": "pattern-cross-merchant-collusion-001",
        "content": (
            "Cross-Merchant Collusion Pattern: Multiple merchants sharing common ownership, "
            "bank accounts, or IP addresses. Circular transactions between merchants (A charges "
            "card, refunds to B). Merchants in different categories but same physical location. "
            "Coordinated transaction timing suggesting automated orchestration."
        ),
        "metadata": {
            "fraud_type": "cross_merchant_collusion",
            "severity": "critical",
            "indicators": "shared_ownership,circular_transactions,common_ip,coordinated_timing",
        },
    },
]

SAMPLE_COMPLIANCE_DOCS = [
    {
        "id": "compliance-visa-vdmp-001",
        "content": (
            "Visa Dispute Monitoring Program (VDMP): A merchant enters the VDMP when their "
            "dispute ratio exceeds 0.9% AND they have more than 100 disputes in a calendar month. "
            "The dispute ratio is calculated as: total disputes / total sales transactions. "
            "Stage 1 (Standard): 0.9%-1.8% ratio, Stage 2 (Excessive): >1.8% ratio. "
            "Fines escalate from $50/dispute at Stage 1 to $100/dispute at Stage 2."
        ),
        "metadata": {"card_brand": "visa", "program": "VDMP", "category": "disputes"},
    },
    {
        "id": "compliance-visa-vfmp-001",
        "content": (
            "Visa Fraud Monitoring Program (VFMP): Monitors merchants with excessive fraud. "
            "Threshold: fraud amount exceeds $75,000 AND fraud-to-sales ratio exceeds 0.9% "
            "in a calendar month. Acquirers must submit remediation plans within 10 business days. "
            "Non-compliance fines start at $25,000/month and escalate to $75,000/month."
        ),
        "metadata": {"card_brand": "visa", "program": "VFMP", "category": "fraud"},
    },
    {
        "id": "compliance-mc-ecm-001",
        "content": (
            "Mastercard Excessive Chargeback Merchant (ECM) Program: A merchant is identified "
            "as ECM when they exceed BOTH thresholds: more than 100 chargebacks AND a chargeback "
            "ratio above 1.5% in a calendar month. ECM merchants face fines of $1,000-$200,000 "
            "and must implement a chargeback reduction plan within 45 days."
        ),
        "metadata": {"card_brand": "mastercard", "program": "ECM", "category": "chargebacks"},
    },
    {
        "id": "compliance-mc-bram-001",
        "content": (
            "Mastercard Business Risk Assessment and Mitigation (BRAM): Requires acquirers to "
            "perform due diligence on high-risk merchants before boarding. High-risk MCCs include: "
            "5912 (Drug Stores), 5122 (Pharmaceuticals), 5993 (Tobacco), 7995 (Gambling), "
            "5967 (Inbound Telemarketing). Acquirers must maintain quarterly risk assessments "
            "and can face penalties up to $100,000 for non-compliance."
        ),
        "metadata": {"card_brand": "mastercard", "program": "BRAM", "category": "risk_assessment"},
    },
    {
        "id": "compliance-amex-optblue-001",
        "content": (
            "American Express OptBlue Program: Allows acquirers to sign merchants for Amex "
            "acceptance with simplified pricing. Merchants must maintain a chargeback ratio "
            "below 1% of total Amex transactions. Merchants with annual Amex volume exceeding "
            "$1 million must transition to a direct Amex relationship. OptBlue merchants must "
            "display the Amex logo and accept all Amex card types."
        ),
        "metadata": {"card_brand": "amex", "program": "OptBlue", "category": "merchant_acceptance"},
    },
]


async def main():
    """Initialize NeonDB schema and seed with sample data."""
    settings = get_settings()

    print("=" * 60)
    print("PayFac Fraud Analysis - NeonDB Initialization")
    print("=" * 60)

    # Connect to NeonDB
    print("\n1. Connecting to NeonDB...")
    neondb = NeonDbClient(settings.neondb_connection_string)
    await neondb.connect()
    print("   ✅ Connected")

    # Initialize LLM for embeddings
    print("\n2. Initializing embedding model...")
    llm = LLMClient()
    print("   ✅ Initialized")

    # Create vector store tables
    print("\n3. Creating vector store collections...")
    vector_store = VectorStore(neondb, llm)
    await vector_store.initialize_collections()
    print("   ✅ Collections created: synthetic_transactions, compliance_documents, fraud_patterns")

    # Create long-term memory tables
    print("\n4. Creating long-term memory tables...")
    long_term = LongTermMemory(neondb)
    await long_term.initialize_tables()
    print("   ✅ Tables created: merchant_risk_profiles, learned_fraud_patterns, analysis_decisions")

    # Create episodic memory table
    print("\n5. Creating episodic memory table...")
    episodic = EpisodicMemory(neondb, llm)
    await episodic.initialize_table()
    print("   ✅ Table created: episodic_memory")

    # Seed fraud patterns
    print("\n6. Seeding fraud patterns...")
    for pattern in SAMPLE_FRAUD_PATTERNS:
        await vector_store.ingest_fraud_pattern(
            pattern_id=pattern["id"],
            text=pattern["content"],
            metadata=pattern["metadata"],
        )
        print(f"   ✅ {pattern['id']}")

    # Seed compliance documents
    print("\n7. Seeding compliance documents...")
    for doc in SAMPLE_COMPLIANCE_DOCS:
        await vector_store.ingest_compliance_doc(
            chunk_id=doc["id"],
            text=doc["content"],
            metadata=doc["metadata"],
        )
        print(f"   ✅ {doc['id']}")

    # Close connection
    await neondb.close()

    print("\n" + "=" * 60)
    print("✅ NeonDB initialization complete!")
    print(f"   Fraud patterns seeded: {len(SAMPLE_FRAUD_PATTERNS)}")
    print(f"   Compliance docs seeded: {len(SAMPLE_COMPLIANCE_DOCS)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
