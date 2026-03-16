-- ============================================================
-- VERIFICATION & SAMPLE QUERIES
-- Run these after loading data to validate & explore
-- ============================================================

-- 1. Row count
SELECT COUNT(*) AS total_cases FROM fraud_cases;

-- 2. Distribution by fraud type
SELECT
    fraud_type,
    COUNT(*) AS count,
    ROUND(AVG(risk_level), 2) AS avg_risk,
    ROUND(AVG(transaction_amount)::numeric, 2) AS avg_amount,
    SUM(CASE WHEN confirmed_fraud THEN 1 ELSE 0 END) AS confirmed_count
FROM fraud_cases
GROUP BY fraud_type
ORDER BY count DESC;

-- 3. Risk label breakdown
SELECT risk_label, COUNT(*) AS count
FROM fraud_cases
GROUP BY risk_label
ORDER BY count DESC;

-- 4. Top 10 countries by confirmed fraud
SELECT
    country_name,
    country,
    COUNT(*) AS total,
    SUM(CASE WHEN confirmed_fraud THEN 1 ELSE 0 END) AS confirmed,
    ROUND(AVG(loss_amount)::numeric, 2) AS avg_loss
FROM fraud_cases
WHERE confirmed_fraud IS NOT NULL
GROUP BY country_name, country
ORDER BY confirmed DESC
LIMIT 10;

-- 5. AML / high-risk cases
SELECT
    fraud_type,
    fraud_subtype,
    country,
    transaction_amount,
    currency_code,
    risk_level,
    sar_filed,
    regulatory_notes
FROM fraud_cases
WHERE aml_flag = TRUE
ORDER BY risk_level DESC, transaction_amount DESC
LIMIT 20;

-- 6. Detection method effectiveness
SELECT
    detection_method,
    COUNT(*) AS detected,
    SUM(CASE WHEN confirmed_fraud THEN 1 ELSE 0 END) AS true_positives,
    SUM(CASE WHEN confirmed_fraud = FALSE THEN 1 ELSE 0 END) AS false_positives,
    ROUND(
        100.0 * SUM(CASE WHEN confirmed_fraud THEN 1 ELSE 0 END) /
        NULLIF(COUNT(*), 0), 2
    ) AS precision_pct
FROM fraud_cases
WHERE detection_method IS NOT NULL
GROUP BY detection_method
ORDER BY true_positives DESC;

-- 7. Vector similarity search — find cases similar to a given embedding
-- (Replace the vector literal with an actual embedding from your model)
-- Example: find top 5 most similar fraud cases
/*
SELECT
    id,
    fraud_type,
    description,
    risk_level,
    1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS cosine_similarity
FROM fraud_cases
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
*/

-- 8. Monthly fraud trend
SELECT
    DATE_TRUNC('month', reported_at) AS month,
    COUNT(*) AS total_cases,
    ROUND(SUM(transaction_amount)::numeric, 2) AS total_amount,
    ROUND(AVG(risk_level)::numeric, 2) AS avg_risk
FROM fraud_cases
GROUP BY 1
ORDER BY 1 DESC;

-- 9. High-velocity fraud signals
SELECT
    fraud_type,
    transaction_channel,
    COUNT(*) AS cases,
    SUM(CASE WHEN velocity_flag THEN 1 ELSE 0 END) AS velocity_flagged,
    SUM(CASE WHEN geolocation_anomaly THEN 1 ELSE 0 END) AS geo_anomalies
FROM fraud_cases
GROUP BY fraud_type, transaction_channel
ORDER BY velocity_flagged DESC;

-- 10. MCC fraud hotspots
SELECT
    mcc,
    mcc_description,
    COUNT(*) AS cases,
    ROUND(AVG(transaction_amount)::numeric, 2) AS avg_txn,
    ROUND(AVG(risk_level)::numeric, 2) AS avg_risk
FROM fraud_cases
GROUP BY mcc, mcc_description
ORDER BY cases DESC
LIMIT 15;
