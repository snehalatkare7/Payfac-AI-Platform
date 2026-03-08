-- ============================================================
-- FRAUD CASES - Enhanced Schema (Industry Standard)
-- Compatible with: PostgreSQL + pgvector on Neon
-- ============================================================

-- Enable pgvector extension (required on Neon)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- DROP existing table if re-running
-- ============================================================
DROP TABLE IF EXISTS fraud_cases CASCADE;

-- ============================================================
-- ENHANCED fraud_cases TABLE
-- ============================================================
CREATE TABLE fraud_cases (
    -- Primary key (UUID preferred over serial for distributed systems)
    id                      UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Fraud classification
    fraud_type              TEXT            NOT NULL,           -- e.g. 'card_not_present', 'account_takeover'
    fraud_subtype           TEXT,                               -- e.g. 'phishing', 'sim_swap'
    description             TEXT            NOT NULL,           -- Human-readable narrative of the fraud case

    -- Merchant context
    mcc                     TEXT            NOT NULL,           -- Merchant Category Code (ISO 18245)
    mcc_description         TEXT,                               -- e.g. 'Airlines', 'Grocery Stores'
    merchant_name           TEXT,                               -- Synthetic merchant name
    merchant_id             TEXT,                               -- Synthetic merchant identifier

    -- Geography
    country                 TEXT            NOT NULL,           -- ISO 3166-1 alpha-2 e.g. 'US', 'NG'
    country_name            TEXT,                               -- Full country name
    city                    TEXT,                               -- City of transaction
    ip_country              TEXT,           -- Country of originating IP (useful for CNP fraud)

    -- Transaction details
    transaction_amount      NUMERIC(12, 2)  NOT NULL,           -- Amount in currency
    currency_code           TEXT            NOT NULL DEFAULT 'USD',  -- ISO 4217
    transaction_channel     TEXT,                               -- 'online', 'pos', 'atm', 'mobile'
    transaction_type        TEXT,                               -- 'purchase', 'withdrawal', 'transfer', 'refund'
    card_present            BOOLEAN         DEFAULT FALSE,

    -- Risk & scoring
    risk_level              SMALLINT        NOT NULL CHECK (risk_level BETWEEN 1 AND 10),
    risk_score              NUMERIC(5, 4),                      -- Normalized 0.0 - 1.0
    risk_label              TEXT GENERATED ALWAYS AS (
                                CASE
                                    WHEN risk_level <= 3 THEN 'LOW'
                                    WHEN risk_level <= 6 THEN 'MEDIUM'
                                    WHEN risk_level <= 8 THEN 'HIGH'
                                    ELSE 'CRITICAL'
                                END
                            ) STORED,

    -- Detection signals
    velocity_flag           BOOLEAN         DEFAULT FALSE,      -- Unusual transaction velocity
    geolocation_anomaly     BOOLEAN         DEFAULT FALSE,      -- Geographic impossibility
    device_fingerprint_match BOOLEAN        DEFAULT TRUE,
    unusual_hour            BOOLEAN         DEFAULT FALSE,      -- Transaction at odd hours

    -- Customer / account info (synthetic)
    customer_age_band       TEXT,                               -- '18-25', '26-35', '36-50', '51+'
    account_tenure_days     INT,                                -- Days since account opening
    is_first_offense        BOOLEAN         DEFAULT TRUE,

    -- Case status & resolution
    reported_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    detected_at             TIMESTAMPTZ,                        -- When fraud was detected
    resolved_at             TIMESTAMPTZ,
    detection_method        TEXT,                               -- 'ml_model', 'rule_engine', 'customer_report', 'manual_review'
    case_status             TEXT            NOT NULL DEFAULT 'open',  -- 'open', 'investigating', 'confirmed', 'dismissed'
    confirmed_fraud         BOOLEAN,                            -- NULL = pending, TRUE = confirmed, FALSE = false positive
    chargeback_filed        BOOLEAN         DEFAULT FALSE,
    loss_amount             NUMERIC(12, 2),                     -- Actual loss after resolution

    -- Regulatory / compliance
    sar_filed               BOOLEAN         DEFAULT FALSE,      -- Suspicious Activity Report
    aml_flag                BOOLEAN         DEFAULT FALSE,      -- Anti-Money Laundering flag
    regulatory_notes        TEXT,

    -- Vector embedding (for semantic search / ML similarity)
    embedding               VECTOR(384),                        -- sentence-transformers all-MiniLM-L6-v2 produces 384-dim

    -- Audit
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Standard indexes
CREATE INDEX idx_fraud_cases_fraud_type      ON fraud_cases (fraud_type);
CREATE INDEX idx_fraud_cases_country         ON fraud_cases (country);
CREATE INDEX idx_fraud_cases_mcc             ON fraud_cases (mcc);
CREATE INDEX idx_fraud_cases_risk_level      ON fraud_cases (risk_level);
CREATE INDEX idx_fraud_cases_risk_label      ON fraud_cases (risk_label);
CREATE INDEX idx_fraud_cases_case_status     ON fraud_cases (case_status);
CREATE INDEX idx_fraud_cases_reported_at     ON fraud_cases (reported_at DESC);
CREATE INDEX idx_fraud_cases_confirmed_fraud ON fraud_cases (confirmed_fraud);
CREATE INDEX idx_fraud_cases_aml_flag        ON fraud_cases (aml_flag) WHERE aml_flag = TRUE;

-- Vector similarity index (HNSW - best for pgvector on Neon)
CREATE INDEX idx_fraud_cases_embedding ON fraud_cases
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================
-- AUTO-UPDATE updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_fraud_cases_updated_at
    BEFORE UPDATE ON fraud_cases
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- COMMENTS (documentation)
-- ============================================================
COMMENT ON TABLE fraud_cases IS 'Synthetic fraud case dataset for ML training and rule engine development';
COMMENT ON COLUMN fraud_cases.embedding IS '384-dim vector from sentence-transformers all-MiniLM-L6-v2 on fraud description';
COMMENT ON COLUMN fraud_cases.risk_level IS 'Integer 1-10: 1-3=Low, 4-6=Medium, 7-8=High, 9-10=Critical';
COMMENT ON COLUMN fraud_cases.mcc IS 'ISO 18245 Merchant Category Code';
COMMENT ON COLUMN fraud_cases.sar_filed IS 'FinCEN Suspicious Activity Report filed';
