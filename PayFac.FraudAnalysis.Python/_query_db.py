"""Temporary script to query NeonDB for synthetic data analysis."""
import psycopg2
import json

CONN = "postgresql://neondb_owner:npg_NwqA5n9YgkXl@ep-soft-heart-a85a6azm-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"

def main():
    conn = psycopg2.connect(CONN)
    cur = conn.cursor()

    # 1. All tables
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    print("=== TABLES ===")
    for r in cur.fetchall():
        print(f"  {r[0]}")

    # 2. fraud_cases by type
    cur.execute("SELECT COUNT(*) FROM fraud_cases")
    print(f"\n=== fraud_cases: {cur.fetchone()[0]} rows ===")
    cur.execute("""
        SELECT fraud_type, COUNT(*),
               MIN(transaction_amount)::int, MAX(transaction_amount)::int, AVG(transaction_amount)::int,
               MIN(risk_level), MAX(risk_level)
        FROM fraud_cases GROUP BY fraud_type ORDER BY COUNT(*) DESC
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:30s} cnt={r[1]:4d} amt=[{r[2]},{r[3]}] avg={r[4]} risk=[{r[5]},{r[6]}]")

    # 3. Columns in fraud_cases
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='fraud_cases' ORDER BY ordinal_position")
    cols = [r[0] for r in cur.fetchall()]
    print(f"\n=== fraud_cases columns ({len(cols)}) ===")
    print(f"  {cols}")

    # MCCs
    cur.execute("SELECT DISTINCT mcc, mcc_description FROM fraud_cases ORDER BY mcc LIMIT 30")
    print("\n=== MCCs ===")
    for r in cur.fetchall():
        print(f"  {r[0]} - {r[1]}")

    # 4. Sample records per type
    for ftype in ['card_not_present','account_takeover','identity_theft','friendly_fraud','money_laundering','card_present_fraud','refund_fraud','bust_out_fraud']:
        cur.execute("""
            SELECT id, transaction_amount, mcc, country, currency_code,
                   transaction_channel, risk_level, confirmed_fraud, detection_method
            FROM fraud_cases WHERE fraud_type=%s LIMIT 2
        """, (ftype,))
        rows = cur.fetchall()
        if rows:
            print(f"\n--- {ftype} samples ---")
            for r in rows:
                print(f"  id={r[0]} amt={r[1]} mcc={r[2]} country={r[3]} curr={r[4]} entry={r[5]} risk={r[6]} confirmed={r[7]} detect={r[8]}")

    # 5. fraud_patterns - get columns first
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='fraud_patterns' ORDER BY ordinal_position")
    fp_cols = [r[0] for r in cur.fetchall()]
    print(f"\n=== fraud_patterns columns: {fp_cols} ===")
    cur.execute("SELECT * FROM fraud_patterns LIMIT 7")
    for r in cur.fetchall():
        print(f"  {r}")

    # 6. compliance_documents - get columns first
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='compliance_documents' ORDER BY ordinal_position")
    cd_cols = [r[0] for r in cur.fetchall()]
    print(f"\n=== compliance_documents columns: {cd_cols} ===")
    cur.execute("SELECT id, title, card_brand FROM compliance_documents" if 'title' in cd_cols and 'card_brand' in cd_cols else "SELECT * FROM compliance_documents LIMIT 5")
    for r in cur.fetchall():
        print(f"  {r[:4]}...")

    # 7. episodic_memory
    cur.execute("SELECT COUNT(*) FROM episodic_memory")
    print(f"\n=== episodic_memory: {cur.fetchone()[0]} rows ===")
    cur.execute("SELECT id, metadata FROM episodic_memory LIMIT 5")
    for r in cur.fetchall():
        meta = r[1] if isinstance(r[1], dict) else json.loads(r[1]) if r[1] else {}
        print(f"  {r[0]} | fraud_type={meta.get('fraud_type')} | merchant={meta.get('merchant_id')} | outcome={meta.get('outcome')}")

    # 8. merchant_risk_profiles
    cur.execute("SELECT COUNT(*) FROM merchant_risk_profiles")
    print(f"\n=== merchant_risk_profiles: {cur.fetchone()[0]} rows ===")
    cur.execute("SELECT merchant_id, merchant_name, mcc, is_high_risk, average_risk_score, historical_fraud_count FROM merchant_risk_profiles LIMIT 15")
    for r in cur.fetchall():
        print(f"  {r[0]} | {r[1]} | mcc={r[2]} | high_risk={r[3]} | avg_score={r[4]} | fraud_cnt={r[5]}")

    # 9. analysis_decisions
    cur.execute("SELECT COUNT(*) FROM analysis_decisions")
    print(f"\n=== analysis_decisions: {cur.fetchone()[0]} rows ===")
    cur.execute("SELECT decision_id, merchant_id, fraud_type, risk_score, was_correct FROM analysis_decisions ORDER BY decided_at DESC LIMIT 10")
    for r in cur.fetchall():
        print(f"  {r[0][:30]}... | {r[1]} | type={r[2]} | score={r[3]} | correct={r[4]}")

    # 10. policy counts
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT brand) FROM policy_rules")
    row = cur.fetchone()
    print(f"\n=== policy_rules: {row[0]} rows, {row[1]} brands ===")
    cur.execute("SELECT COUNT(*) FROM policy_documents")
    print(f"=== policy_documents: {cur.fetchone()[0]} rows ===")

    # 11. learned_fraud_patterns
    cur.execute("SELECT COUNT(*) FROM learned_fraud_patterns")
    print(f"\n=== learned_fraud_patterns: {cur.fetchone()[0]} rows ===")

    conn.close()

if __name__ == "__main__":
    main()
