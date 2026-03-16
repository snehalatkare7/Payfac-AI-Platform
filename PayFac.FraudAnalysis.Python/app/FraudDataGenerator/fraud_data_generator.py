"""
Synthetic fraud transaction data generator for PayFac Fraud Analysis Platform.

Populates the app's RAG table `synthetic_transactions` (id, embedding, content, metadata)
so that search_similar_transactions and agents can find historical fraud patterns.

Uses app config from .env: NEONDB_CONNECTION_STRING; optional Azure OpenAI for embeddings.

USAGE (from project root):
    # Ensure .env has NEONDB_CONNECTION_STRING (and optionally Azure OpenAI for real embeddings)
    python -m app.FraudDataGenerator.fraud_data_generator --count 1000 --batch-size 100

    # Override DSN
    python -m app.FraudDataGenerator.fraud_data_generator --count 500 --dsn "postgresql://..."
"""

import argparse
import json
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
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

# Optional: sentence-transformers for local embeddings (384-dim, padded to 1536 to match app table)
try:
    from sentence_transformers import SentenceTransformer
    _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    _USE_SENTENCE_TRANSFORMERS = True
    log.info("sentence-transformers loaded (all-MiniLM-L6-v2) — using real embeddings, padded to 1536")
except ImportError:
    _ST_MODEL = None
    _USE_SENTENCE_TRANSFORMERS = False
    log.info("sentence-transformers not installed — using random 1536-dim embeddings when Azure not configured")

# Matches app table synthetic_transactions (Azure text-embedding-3-small)
EMBEDDING_DIM = 1536

# App config and optional Azure embeddings
def _get_settings():
    try:
        from app.config import get_settings
        return get_settings()
    except Exception as e:
        log.warning("Could not load app config: %s. Use --dsn or DATABASE_URL.", e)
        return None

def _generate_embedding_azure(text: str, settings: Any) -> Optional[list[float]]:
    """Generate 1536-dim embedding via Azure OpenAI if configured."""
    if not (settings and getattr(settings, "azure_openai_api_key", None)):
        return None
    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=getattr(settings, "azure_openai_api_version", "2024-10-21"),
        )
        r = client.embeddings.create(
            input=text,
            model=settings.azure_openai_embedding_deployment or "text-embedding-3-small",
        )
        return r.data[0].embedding
    except Exception as e:
        log.warning("Azure embedding failed: %s. Using random embeddings.", e)
        return None

def _embed_sentence_transformer(text: str) -> list[float]:
    """Generate 384-dim embedding with sentence-transformers, then pad to 1536 for app table."""
    emb = _ST_MODEL.encode(text, normalize_embeddings=True)
    emb = np.array(emb, dtype=np.float32)
    # Pad to 1536 to match app's synthetic_transactions schema (Azure text-embedding-3-small dim)
    if len(emb) < EMBEDDING_DIM:
        padding = np.zeros(EMBEDDING_DIM - len(emb), dtype=np.float32)
        emb = np.concatenate([emb, padding])
        emb = emb / np.linalg.norm(emb)  # re-normalize after padding
    return emb.tolist()


def generate_embedding_1536(text: str, settings: Any = None) -> list[float]:
    """Generate 1536-dim embedding. Priority: Azure OpenAI > sentence-transformers (padded) > random."""
    emb = _generate_embedding_azure(text, settings)
    if emb is not None:
        return emb
    if _USE_SENTENCE_TRANSFORMERS and _ST_MODEL is not None:
        return _embed_sentence_transformer(text)
    seed = hash(text) % (2**32)
    rng = np.random.default_rng(seed)
    emb = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    emb = emb / np.linalg.norm(emb)
    return emb.tolist()


# ============================================================
# REFERENCE DATA (same as before)
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

MCC_DATA = [
    ("5411", "Grocery Stores, Supermarkets"),
    ("5912", "Drug Stores, Pharmacies"),
    ("5812", "Eating Places, Restaurants"),
    ("5999", "Miscellaneous and Specialty Retail Stores"),
    ("5310", "Discount Stores"),
    ("5651", "Family Clothing Stores"),
    ("5732", "Electronics Stores"),
    ("5944", "Jewelry Stores, Watches, Clocks, and Silverware Stores"),
    ("6011", "Automated Cash Disbursements – Customer Financial Institution"),
    ("7011", "Lodging – Hotels, Motels, Resorts"),
    ("7372", "Computer Programming, Data Processing"),
    ("7995", "Gambling Transactions"),
    ("5541", "Service Stations"),
    ("4511", "Airlines, Air Carriers"),
]

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
    ("MX", "Mexico", "MXN"),
    ("ZA", "South Africa", "ZAR"),
]

CASE_STATUSES = ["open", "investigating", "confirmed", "dismissed"]
AGE_BANDS = ["18-25", "26-35", "36-50", "51-65", "65+"]
TRANSACTION_TYPES = ["purchase", "withdrawal", "transfer", "refund", "payment"]

# Table used by the app's RAG (vector_store.py)
SYNTHETIC_TRANSACTIONS_TABLE = "synthetic_transactions"


def generate_fraud_case() -> dict:
    """Generate a single synthetic fraud case (same structure as before)."""
    fraud_type = random.choice(list(FRAUD_TYPES.keys()))
    fraud_meta = FRAUD_TYPES[fraud_type]

    fraud_subtype = random.choice(fraud_meta["subtypes"])
    channel = random.choice(fraud_meta["channels"])
    card_present = fraud_meta["card_present"]
    risk_level = random.randint(*fraud_meta["risk_range"])
    amount = round(random.uniform(*fraud_meta["amount_range"]), 2)

    mcc_code, mcc_desc = random.choice(MCC_DATA)
    country_code, country_name, currency = random.choice(COUNTRY_DATA)
    ip_country = random.choice(COUNTRY_DATA)[0] if random.random() < 0.3 else country_code

    base_desc = random.choice(fraud_meta["description_templates"])
    merchant = fake.company()
    description = f"{base_desc} Merchant: {merchant} ({mcc_desc}). Amount: {currency} {amount:,.2f}."

    reported_at = fake.date_time_between(
        start_date="-2y", end_date="now", tzinfo=timezone.utc
    )
    detection_delay = timedelta(hours=random.randint(0, 72))
    detected_at = reported_at + detection_delay if random.random() > 0.1 else None
    resolved_at = None
    if detected_at and random.random() > 0.4:
        resolved_at = detected_at + timedelta(days=random.randint(1, 30))

    case_status = random.choice(CASE_STATUSES)
    confirmed_fraud = None
    if case_status in ("confirmed", "dismissed"):
        confirmed_fraud = case_status == "confirmed"
    chargeback_filed = confirmed_fraud is True and random.random() > 0.3
    loss_amount = round(amount * random.uniform(0.5, 1.0), 2) if confirmed_fraud else None

    velocity_flag = risk_level >= 7 or random.random() < 0.2
    geo_anomaly = ip_country != country_code or random.random() < 0.15
    unusual_hour = random.random() < 0.25
    device_match = random.random() > 0.3
    aml_flag = fraud_type == "money_laundering" or (risk_level >= 8 and random.random() < 0.3)
    sar_filed = aml_flag and random.random() > 0.2
    risk_score = round(min(1.0, max(0.0, risk_level / 10 + random.gauss(0, 0.05))), 4)
    account_tenure = random.randint(1, 3650)
    merchant_id = f"MER-{fake.bothify('??####').upper()}"
    city = fake.city()

    return {
        "id": str(uuid.uuid4()),
        "fraud_type": fraud_type,
        "fraud_subtype": fraud_subtype,
        "description": description,
        "mcc": mcc_code,
        "mcc_description": mcc_desc,
        "merchant_name": merchant,
        "merchant_id": merchant_id,
        "country": country_code,
        "country_name": country_name,
        "city": city,
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
        "detection_method": random.choice(["ml_model", "rule_engine", "customer_report", "manual_review"]) if detected_at else None,
        "case_status": case_status,
        "confirmed_fraud": confirmed_fraud,
        "chargeback_filed": chargeback_filed,
        "loss_amount": loss_amount,
        "sar_filed": sar_filed,
        "aml_flag": aml_flag,
        "regulatory_notes": (f"SAR filed under FinCEN reference {fake.bothify('SAR-####-???').upper()}" if sar_filed else None),
    }


def case_to_synthetic_transaction_record(case: dict, settings: Any) -> dict:
    """
    Map a fraud case to the app's synthetic_transactions row.
    Schema: id, embedding vector(1536), content TEXT, metadata JSONB.
    """
    # Searchable content (what RAG will match on)
    content_parts = [
        case["description"],
        f"Fraud type: {case['fraud_type']} ({case['fraud_subtype']}).",
        f"Merchant: {case['merchant_name']} ({case['merchant_id']}). MCC: {case['mcc']} {case['mcc_description']}.",
        f"Country: {case['country']} ({case['country_name']}), city: {case['city']}. IP country: {case['ip_country']}.",
        f"Amount: {case['currency_code']} {case['transaction_amount']}. Channel: {case['transaction_channel']}, card_present: {case['card_present']}.",
        f"Risk level: {case['risk_level']}, velocity: {case['velocity_flag']}, geo_anomaly: {case['geolocation_anomaly']}.",
    ]
    content = " ".join(content_parts)

    embedding = generate_embedding_1536(content, settings)

    # Metadata for filtering (merchant_id, card_brand, etc.) — matches vector_store search_similar_transactions
    metadata = {
        "merchant_id": case["merchant_id"],
        "merchant_name": case["merchant_name"],
        "fraud_type": case["fraud_type"],
        "fraud_subtype": case["fraud_subtype"],
        "mcc": case["mcc"],
        "country": case["country"],
        "transaction_amount": float(case["transaction_amount"]),
        "currency_code": case["currency_code"],
        "risk_level": case["risk_level"],
        "transaction_channel": case["transaction_channel"],
        "case_status": case["case_status"],
        "reported_at": case["reported_at"].isoformat() if hasattr(case["reported_at"], "isoformat") else str(case["reported_at"]),
    }

    return {
        "id": case["id"],
        "content": content,
        "metadata": metadata,
        "embedding": embedding,
    }


# ============================================================
# DATABASE OPERATIONS (synthetic_transactions = app RAG table)
# ============================================================

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {SYNTHETIC_TRANSACTIONS_TABLE} (
    id TEXT PRIMARY KEY,
    embedding vector({EMBEDDING_DIM}),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{{}}'
);
"""

CREATE_EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS vector;"

INSERT_SQL = f"""
INSERT INTO {SYNTHETIC_TRANSACTIONS_TABLE} (id, embedding, content, metadata)
VALUES (%(id)s, %(embedding)s::vector, %(content)s, %(metadata)s::jsonb)
ON CONFLICT (id) DO NOTHING;
"""


def serialize_record(record: dict) -> dict:
    """Prepare record for psycopg2: embedding as vector string, metadata as JSON string."""
    r = record.copy()
    r["embedding"] = "[" + ",".join(f"{v:.6f}" for v in r["embedding"]) + "]"
    r["metadata"] = json.dumps(r["metadata"], default=str)
    return r


def ensure_table(conn) -> None:
    """Ensure pgvector extension and synthetic_transactions table exist."""
    with conn.cursor() as cur:
        cur.execute(CREATE_EXTENSION_SQL)
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    log.info("Table %s ensured (embedding dim=%d).", SYNTHETIC_TRANSACTIONS_TABLE, EMBEDDING_DIM)


def insert_batch(cursor, records: list[dict]) -> int:
    """Insert a batch into synthetic_transactions."""
    serialized = [serialize_record(r) for r in records]
    psycopg2.extras.execute_batch(cursor, INSERT_SQL, serialized, page_size=50)
    return len(records)


def run(dsn: str, count: int, batch_size: int, settings: Any = None) -> None:
    log.info("Connecting to Neon PostgreSQL...")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    ensure_table(conn)

    log.info("Generating %d synthetic fraud cases (batch_size=%d)...", count, batch_size)
    total_inserted = 0
    batch = []

    for i in range(1, count + 1):
        case = generate_fraud_case()
        record = case_to_synthetic_transaction_record(case, settings)
        batch.append(record)

        if len(batch) >= batch_size:
            insert_batch(cur, batch)
            conn.commit()
            total_inserted += len(batch)
            log.info("  Inserted %d/%d records", total_inserted, count)
            batch = []

    if batch:
        insert_batch(cur, batch)
        conn.commit()
        total_inserted += len(batch)

    cur.close()
    conn.close()
    log.info("Done! Total records inserted into %s: %d", SYNTHETIC_TRANSACTIONS_TABLE, total_inserted)


# ============================================================
# ENTRY POINT
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic fraud data into PayFac app RAG table (synthetic_transactions)."
    )
    settings = _get_settings()
    default_dsn = (
        (settings.neondb_connection_string if settings else None)
        or os.environ.get("NEONDB_CONNECTION_STRING")
        or os.environ.get("DATABASE_URL")
    )
    parser.add_argument(
        "--dsn",
        default=default_dsn,
        help="PostgreSQL DSN (default: from .env NEONDB_CONNECTION_STRING or DATABASE_URL)",
    )
    parser.add_argument("--count", type=int, default=1000, help="Number of records to generate (default: 1000)")
    parser.add_argument("--batch-size", type=int, default=100, help="Insert batch size (default: 100)")
    args = parser.parse_args()

    if not args.dsn:
        print("ERROR: Provide --dsn or set NEONDB_CONNECTION_STRING (or DATABASE_URL) in .env")
        print("Example: postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require")
        exit(1)

    if settings and getattr(settings, "azure_openai_api_key", None):
        log.info("Using Azure OpenAI for embeddings (1536-dim).")
    else:
        log.info("Using random 1536-dim embeddings (set Azure OpenAI in .env for real embeddings).")

    run(dsn=args.dsn, count=args.count, batch_size=args.batch_size, settings=settings)


if __name__ == "__main__":
    main()
