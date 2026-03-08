# Payfac AI Platform

This project contains components for the Payfac AI Platform, including:

- **payfac-layman-explainer.jsx**: A component or module for explaining Payfac concepts in layman's terms.
- **payfac-llm-architecture.jsx**: A component or module describing the LLM (Large Language Model) architecture for the platform.

## Project Structure

- `payfac-layman-explainer.jsx`  
  Explains Payfac concepts in simple language, likely for educational or onboarding purposes.
- `payfac-llm-architecture.jsx`  
  Details the architecture and design of the LLM integration within the Payfac AI Platform.

## Getting Started

1. **Clone the repository**
2. **Install dependencies** (if using Node.js/React):
   ```bash
   npm install
   ```
3. **Run the project** (if applicable):
   ```bash
   npm start
   ```

## Contributing

Feel free to open issues or submit pull requests for improvements or bug fixes.

## License

Specify your license here (e.g., MIT, Apache 2.0, etc.).

## ChatGPT Link
https://chatgpt.com/gg/69abd19308788197b256d14094c38329

# Fraud Cases — Synthetic Data Generator

A production-grade synthetic fraud dataset generator for **Neon PostgreSQL + pgvector**.

## Files

| File | Purpose |
|------|---------|
| `schema.sql` | Enhanced table DDL — run this first on Neon |
| `fraud_data_generator.py` | Python script to generate & insert synthetic records |
| `sample_queries.sql` | Analytical queries to explore and validate data |

---

## Quick Start

### 1. Install dependencies

```bash
pip install psycopg2-binary faker numpy sentence-transformers
```

> `sentence-transformers` is optional but recommended — it generates real 384-dim semantic embeddings.  
> Without it, the script falls back to deterministic random embeddings (fine for dev/testing).

### 2. Set up Neon DB

On your Neon console, open the SQL editor and run:

```sql
-- schema.sql (full file)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- ... (rest of schema.sql)
```

### 3. Run the generator

```bash
export DATABASE_URL="postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require"

# Generate 1,000 records (default)
python fraud_data_generator.py

# Generate 10,000 records in batches of 200
python fraud_data_generator.py --count 10000 --batch-size 200

# Inline DSN
python fraud_data_generator.py --dsn "postgresql://..." --count 5000
```

---

## Schema Overview

```
fraud_cases
├── Identity         id (UUID PK)
├── Classification   fraud_type, fraud_subtype, description
├── Merchant         mcc, mcc_description, merchant_name, merchant_id
├── Geography        country, country_name, city, ip_country
├── Transaction      amount, currency, channel, type, card_present
├── Risk             risk_level (1–10), risk_score (0–1), risk_label (computed)
├── Signals          velocity_flag, geolocation_anomaly, device_fingerprint_match, unusual_hour
├── Customer         customer_age_band, account_tenure_days, is_first_offense
├── Case Lifecycle   reported_at, detected_at, resolved_at, detection_method, case_status
├── Outcomes         confirmed_fraud, chargeback_filed, loss_amount
├── Compliance       sar_filed, aml_flag, regulatory_notes
└── ML               embedding (vector 384-dim)
```

### Risk Level Scale

| Level | Label    | Meaning                          |
|-------|----------|----------------------------------|
| 1–3   | LOW      | Suspicious but low confidence    |
| 4–6   | MEDIUM   | Clear signals, investigating     |
| 7–8   | HIGH     | Strong indicators, likely fraud  |
| 9–10  | CRITICAL | Confirmed or near-certain fraud  |

### Fraud Types Generated

- `card_not_present` — CNP, phishing, enumeration
- `account_takeover` — SIM swap, credential stuffing
- `identity_theft` — Synthetic IDs, true-name fraud
- `friendly_fraud` — Chargeback abuse
- `money_laundering` — Structuring, smurfing (AML flagged)
- `card_present_fraud` — Skimming, counterfeit cards
- `refund_fraud` — Return abuse, wardrobing
- `bust_out_fraud` — Credit bust-out, APP scams

---

## Vector Similarity Search (pgvector)

After loading data, find semantically similar fraud cases:

```sql
-- Find 5 cases most similar to a given embedding
SELECT id, fraud_type, description, risk_level,
       1 - (embedding <=> $1::vector) AS similarity
FROM fraud_cases
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

The index uses **HNSW** (Hierarchical Navigable Small World) for fast approximate nearest-neighbor search.

---

## Sample Output Record

```json
{
  "fraud_type": "account_takeover",
  "fraud_subtype": "sim_swap",
  "mcc": "6011",
  "mcc_description": "Automated Cash Disbursements",
  "country": "GB",
  "transaction_amount": 4823.50,
  "currency_code": "GBP",
  "risk_level": 9,
  "risk_label": "CRITICAL",
  "risk_score": 0.9234,
  "velocity_flag": true,
  "geolocation_anomaly": true,
  "aml_flag": false,
  "sar_filed": false,
  "case_status": "confirmed",
  "confirmed_fraud": true,
  "detection_method": "ml_model"
}
```

