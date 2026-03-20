"""
fraud_data_generator.py
========================
Synthetic fraud transaction data generator for Neon PostgreSQL (pgvector).

SETUP:
    pip install psycopg2-binary faker numpy sentence-transformers

USAGE:
    # Set your Neon connection string first:
    export DATABASE_URL="postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require"

    python fraud_data_generator.py --count 1000 --batch-size 100

    # Or with inline connection string:
    python fraud_data_generator.py --count 500 --dsn "postgresql://..."
"""

import argparse
import json
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np

# --- Optional: sentence-transformers for real embeddings ---
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    USE_REAL_EMBEDDINGS = True
    print("✅ sentence-transformers loaded — using real embeddings")
except ImportError:
    USE_REAL_EMBEDDINGS = False
    print("⚠️  sentence-transformers not installed — using random embeddings (fine for dev)")

import psycopg2
import psycopg2.extras
from faker import Faker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)
fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)

# ============================================================
# REFERENCE DATA (industry standard values)
# ============================================================

FRAUD_TYPES = {
    "card_not_present": {
        "subtypes": ["phishing", "data_breach_reuse", "social_engineering", "enumeration_attack"],
        "channels": ["online", "mobile"],
        "card_present": False,
        "risk_range": (4, 9),
        "amount_range": (10, 3500),
        "description_templates": [
            "Unauthorized CNP transaction detected on e-commerce platform using stolen card credentials from a recent data breach.",
            "Card-not-present fraud attempt via mobile checkout; billing address mismatch and high-risk IP detected.",
            "Phishing attack led to credential theft; fraudster made online purchases before victim noticed.",
            "Automated card enumeration attack tested multiple CVV combinations before a successful charge.",
        ],
    },
    "account_takeover": {
        "subtypes": ["credential_stuffing", "sim_swap", "social_engineering", "malware"],
        "channels": ["online", "mobile", "pos"],
        "card_present": False,
        "risk_range": (6, 10),
        "amount_range": (50, 15000),
        "description_templates": [
            "Account taken over via SIM swap; fraudster changed contact details and drained account within 2 hours.",
            "Credential stuffing attack using leaked username/password pairs; multiple accounts compromised simultaneously.",
            "Malware on customer device captured session tokens allowing fraudster to bypass MFA.",
            "Social engineering call tricked customer service into resetting account credentials for fraudster.",
        ],
    },
    "identity_theft": {
        "subtypes": ["synthetic_identity", "true_name_fraud", "medical_identity", "tax_identity"],
        "channels": ["online", "pos", "mobile"],
        "card_present": False,
        "risk_range": (5, 9),
        "amount_range": (200, 25000),
        "description_templates": [
            "Synthetic identity constructed using real SSN of a minor combined with fabricated name and address.",
            "True-name identity theft; victim's full PII obtained from dark web used to open new credit accounts.",
            "Medical identity fraud: stolen credentials used to obtain prescription medications and medical devices.",
            "Fraudster filed tax return using stolen identity to claim refund before legitimate taxpayer filed.",
        ],
    },
    "friendly_fraud": {
        "subtypes": ["chargeback_abuse", "first_party_misrepresentation", "family_fraud"],
        "channels": ["online", "mobile"],
        "card_present": False,
        "risk_range": (2, 6),
        "amount_range": (15, 2000),
        "description_templates": [
            "Cardholder disputed legitimate purchase claiming non-receipt; merchant has proof of delivery.",
            "Customer made purchase then filed chargeback claiming fraud; transaction fingerprint matches prior purchases.",
            "Family member used cardholder's account without authorization; cardholder unwilling to press charges.",
            "Chargeback abuse pattern detected: third dispute in 90 days from same cardholder.",
        ],
    },
    "money_laundering": {
        "subtypes": ["smurfing", "structuring", "layering", "trade_based"],
        "channels": ["pos", "online", "atm"],
        "card_present": True,
        "risk_range": (7, 10),
        "amount_range": (500, 9999),
        "description_templates": [
            "Structuring detected: series of cash deposits just below $10,000 reporting threshold across multiple branches.",
            "Smurfing operation: funds split among multiple mule accounts then consolidated to a single beneficiary.",
            "Trade-based money laundering via over-invoiced cross-border electronics transactions.",
            "Layering through multiple rapid transfers across foreign jurisdictions to obscure fund origin.",
        ],
    },
    "card_present_fraud": {
        "subtypes": ["skimming", "counterfeit_card", "lost_stolen", "card_trapping"],
        "channels": ["pos", "atm"],
        "card_present": True,
        "risk_range": (4, 8),
        "amount_range": (20, 5000),
        "description_templates": [
            "Skimming device found on ATM; multiple cloned cards used at POS terminals across city.",
            "Counterfeit card created from skimmed magnetic stripe data; chip verification bypassed via fallback.",
            "Lost/stolen card used at multiple fuel stations exploiting no-PIN contactless limit.",
            "Card trapping device inserted in ATM to capture physical card; PIN observed via shoulder surfing.",
        ],
    },
    "refund_fraud": {
        "subtypes": ["return_fraud", "receipt_fraud", "wardrobing", "empty_box"],
        "channels": ["pos", "online"],
        "card_present": True,
        "risk_range": (2, 6),
        "amount_range": (25, 3000),
        "description_templates": [
            "Fraudster returned empty box claiming item was missing; refund processed before investigation.",
            "Stolen receipt used to return merchandise not purchased; cash refund issued.",
            "Wardrobing pattern: customer purchased expensive clothing, wore once, then returned used item.",
            "Refund issued to different payment method than original purchase — potential cash-out scheme.",
        ],
    },
    "bust_out_fraud": {
        "subtypes": ["credit_bust_out", "debit_bust_out", "authorized_push_payment"],
        "channels": ["online", "pos", "mobile"],
        "card_present": False,
        "risk_range": (7, 10),
        "amount_range": (1000, 50000),
        "description_templates": [
            "Bust-out fraud: account built positive history over 6 months then maxed all credit lines overnight.",
            "Authorized push payment scam: victim tricked into transferring funds to fraudster's account.",
            "Multiple credit accounts opened under same identity simultaneously; all maxed within 48 hours.",
            "Account showed perfect payment history for 12 months before sudden mass liquidation event.",
        ],
    },
}

# ISO 18245 - Representative MCCs
MCC_DATA = [
    ("5411", "Grocery Stores, Supermarkets"),
    ("5912", "Drug Stores, Pharmacies"),
    ("4111", "Transportation – Suburban & Local Commuter Passenger"),
    ("4112", "Passenger Railways"),
    ("4511", "Airlines, Air Carriers"),
    ("5812", "Eating Places, Restaurants"),
    ("5999", "Miscellaneous and Specialty Retail Stores"),
    ("5310", "Discount Stores"),
    ("5651", "Family Clothing Stores"),
    ("5732", "Electronics Stores"),
    ("5944", "Jewelry Stores, Watches, Clocks, and Silverware Stores"),
    ("6011", "Automated Cash Disbursements – Customer Financial Institution"),
    ("6012", "Merchandise and Services – Customer Financial Institution"),
    ("6051", "Non-Financial Institutions – Foreign Currency, Money Orders"),
    ("7011", "Lodging – Hotels, Motels, Resorts"),
    ("7372", "Computer Programming, Data Processing"),
    ("7995", "Gambling Transactions"),
    ("5045", "Computers, Peripherals and Software"),
    ("5094", "Jewelry, Watches, Clocks, and Silverware"),
    ("8099", "Health and Medical Services"),
    ("5541", "Service Stations"),
    ("5211", "Lumber and Building Material Stores"),
    ("5661", "Shoe Stores"),
    ("5122", "Drugs, Drug Proprietaries and Druggist Sundries"),
]

# High-risk countries for fraud (ISO 3166-1 alpha-2)
COUNTRY_DATA = [
    ("US", "United States", "USD"),
    ("GB", "United Kingdom", "GBP"),
    ("DE", "Germany", "EUR"),
    ("FR", "France", "EUR"),
    ("NG", "Nigeria", "NGN"),
    ("RU", "Russia", "RUB"),
    ("CN", "China", "CNY"),
    ("BR", "Brazil", "BRL"),
    ("IN", "India", "INR"),
    ("CA", "Canada", "CAD"),
    ("AU", "Australia", "AUD"),
    ("GH", "Ghana", "GHS"),
    ("UA", "Ukraine", "UAH"),
    ("MX", "Mexico", "MXN"),
    ("ZA", "South Africa", "ZAR"),
    ("KE", "Kenya", "KES"),
    ("PH", "Philippines", "PHP"),
    ("VN", "Vietnam", "VND"),
    ("PK", "Pakistan", "PKR"),
    ("ID", "Indonesia", "IDR"),
]

DETECTION_METHODS = [
    "ml_model", "rule_engine", "customer_report",
    "manual_review", "partner_alert", "real_time_monitoring"
]

CASE_STATUSES = ["open", "investigating", "confirmed", "dismissed"]
AGE_BANDS = ["18-25", "26-35", "36-50", "51-65", "65+"]
TRANSACTION_TYPES = ["purchase", "withdrawal", "transfer", "refund", "payment"]


# ============================================================
# EMBEDDING GENERATION
# ============================================================

def generate_embedding(text: str) -> list[float]:
    """Generate 384-dim embedding. Uses real model if available, else random."""
    if USE_REAL_EMBEDDINGS:
        emb = EMBEDDING_MODEL.encode(text, normalize_embeddings=True)
        return emb.tolist()
    else:
        # Deterministic random embedding for reproducibility in dev
        seed = hash(text) % (2**32)
        rng = np.random.default_rng(seed)
        emb = rng.standard_normal(384).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        return emb.tolist()


# ============================================================
# SYNTHETIC RECORD GENERATION
# ============================================================

def generate_fraud_case() -> dict:
    """Generate a single synthetic fraud case record."""
    fraud_type = random.choice(list(FRAUD_TYPES.keys()))
    fraud_meta = FRAUD_TYPES[fraud_type]

    fraud_subtype = random.choice(fraud_meta["subtypes"])
    channel = random.choice(fraud_meta["channels"])
    card_present = fraud_meta["card_present"]
    risk_level = random.randint(*fraud_meta["risk_range"])
    amount = round(random.uniform(*fraud_meta["amount_range"]), 2)

    # MCC
    mcc_code, mcc_desc = random.choice(MCC_DATA)

    # Country
    country_code, country_name, currency = random.choice(COUNTRY_DATA)

    # IP country may differ from transaction country (CNP fraud signal)
    ip_country = random.choice(COUNTRY_DATA)[0] if random.random() < 0.3 else country_code

    # Description
    base_desc = random.choice(fraud_meta["description_templates"])
    merchant = fake.company()
    description = f"{base_desc} Merchant: {merchant} ({mcc_desc}). Amount: {currency} {amount:,.2f}."

    # Timestamps
    reported_at = fake.date_time_between(
        start_date="-2y", end_date="now", tzinfo=timezone.utc
    )
    detection_delay = timedelta(hours=random.randint(0, 72))
    detected_at = reported_at + detection_delay if random.random() > 0.1 else None
    resolved_at = None
    if detected_at and random.random() > 0.4:
        resolved_at = detected_at + timedelta(days=random.randint(1, 30))

    # Case outcomes
    case_status = random.choice(CASE_STATUSES)
    confirmed_fraud = None
    if case_status in ("confirmed", "dismissed"):
        confirmed_fraud = case_status == "confirmed"
    chargeback_filed = confirmed_fraud is True and random.random() > 0.3
    loss_amount = round(amount * random.uniform(0.5, 1.0), 2) if confirmed_fraud else None

    # Risk signals
    velocity_flag = risk_level >= 7 or random.random() < 0.2
    geo_anomaly = ip_country != country_code or random.random() < 0.15
    unusual_hour = random.random() < 0.25  # ~25% of fraud happens odd hours
    device_match = random.random() > 0.3

    # AML / regulatory
    aml_flag = fraud_type == "money_laundering" or (risk_level >= 8 and random.random() < 0.3)
    sar_filed = aml_flag and random.random() > 0.2

    # Risk score (normalized, slightly noisy)
    risk_score = round(min(1.0, max(0.0, risk_level / 10 + random.gauss(0, 0.05))), 4)

    # Account tenure
    account_tenure = random.randint(1, 3650)

    # Embedding
    embedding = generate_embedding(description)

    return {
        "id": str(uuid.uuid4()),
        "fraud_type": fraud_type,
        "fraud_subtype": fraud_subtype,
        "description": description,
        "mcc": mcc_code,
        "mcc_description": mcc_desc,
        "merchant_name": merchant,
        "merchant_id": f"MER-{fake.bothify('??####').upper()}",
        "country": country_code,
        "country_name": country_name,
        "city": fake.city(),
        "ip_country": ip_country,
        "transaction_amount": amount,
        "currency_code": currency,
        "transaction_channel": channel,
        "transaction_type": random.choice(TRANSACTION_TYPES),
        "card_present": card_present,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "velocity_flag": velocity_flag,
        "geolocation_anomaly": geo_anomaly,
        "device_fingerprint_match": device_match,
        "unusual_hour": unusual_hour,
        "customer_age_band": random.choice(AGE_BANDS),
        "account_tenure_days": account_tenure,
        "is_first_offense": random.random() > 0.35,
        "reported_at": reported_at,
        "detected_at": detected_at,
        "resolved_at": resolved_at,
        "detection_method": random.choice(DETECTION_METHODS) if detected_at else None,
        "case_status": case_status,
        "confirmed_fraud": confirmed_fraud,
        "chargeback_filed": chargeback_filed,
        "loss_amount": loss_amount,
        "sar_filed": sar_filed,
        "aml_flag": aml_flag,
        "regulatory_notes": (
            f"SAR filed under FinCEN reference {fake.bothify('SAR-####-???').upper()}"
            if sar_filed else None
        ),
        "embedding": embedding,
    }


# ============================================================
# DATABASE OPERATIONS
# ============================================================

INSERT_SQL = """
INSERT INTO fraud_cases (
    id, fraud_type, fraud_subtype, description,
    mcc, mcc_description, merchant_name, merchant_id,
    country, country_name, city, ip_country,
    transaction_amount, currency_code, transaction_channel, transaction_type, card_present,
    risk_level, risk_score,
    velocity_flag, geolocation_anomaly, device_fingerprint_match, unusual_hour,
    customer_age_band, account_tenure_days, is_first_offense,
    reported_at, detected_at, resolved_at,
    detection_method, case_status, confirmed_fraud,
    chargeback_filed, loss_amount,
    sar_filed, aml_flag, regulatory_notes,
    embedding
) VALUES (
    %(id)s, %(fraud_type)s, %(fraud_subtype)s, %(description)s,
    %(mcc)s, %(mcc_description)s, %(merchant_name)s, %(merchant_id)s,
    %(country)s, %(country_name)s, %(city)s, %(ip_country)s,
    %(transaction_amount)s, %(currency_code)s, %(transaction_channel)s, %(transaction_type)s, %(card_present)s,
    %(risk_level)s, %(risk_score)s,
    %(velocity_flag)s, %(geolocation_anomaly)s, %(device_fingerprint_match)s, %(unusual_hour)s,
    %(customer_age_band)s, %(account_tenure_days)s, %(is_first_offense)s,
    %(reported_at)s, %(detected_at)s, %(resolved_at)s,
    %(detection_method)s, %(case_status)s, %(confirmed_fraud)s,
    %(chargeback_filed)s, %(loss_amount)s,
    %(sar_filed)s, %(aml_flag)s, %(regulatory_notes)s,
    %(embedding)s::vector
)
ON CONFLICT (id) DO NOTHING;
"""


def serialize_record(record: dict) -> dict:
    """Convert embedding list to pgvector string format."""
    r = record.copy()
    r["embedding"] = "[" + ",".join(f"{v:.6f}" for v in r["embedding"]) + "]"
    return r


def insert_batch(cursor, records: list[dict]) -> int:
    """Insert a batch of records, return count inserted."""
    serialized = [serialize_record(r) for r in records]
    psycopg2.extras.execute_batch(cursor, INSERT_SQL, serialized, page_size=50)
    return len(records)


def run(dsn: str, count: int, batch_size: int):
    log.info(f"Connecting to Neon PostgreSQL...")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    log.info(f"Generating {count} synthetic fraud cases (batch_size={batch_size})...")
    total_inserted = 0
    batch = []

    for i in range(1, count + 1):
        record = generate_fraud_case()
        batch.append(record)

        if len(batch) >= batch_size:
            insert_batch(cur, batch)
            conn.commit()
            total_inserted += len(batch)
            log.info(f"  ✅ Inserted {total_inserted}/{count} records")
            batch = []

    # Remaining
    if batch:
        insert_batch(cur, batch)
        conn.commit()
        total_inserted += len(batch)

    cur.close()
    conn.close()

    log.info(f"🎉 Done! Total records inserted: {total_inserted}")


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic fraud data into Neon PostgreSQL")
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"),
                        help="PostgreSQL DSN (or set DATABASE_URL env var)")
    parser.add_argument("--count", type=int, default=1000,
                        help="Number of fraud cases to generate (default: 1000)")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Insert batch size (default: 100)")
    args = parser.parse_args()

    if not args.dsn:
        print("❌ ERROR: Provide --dsn or set DATABASE_URL environment variable")
        print("   Example DSN: postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require")
        exit(1)

    run(dsn=args.dsn, count=args.count, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
