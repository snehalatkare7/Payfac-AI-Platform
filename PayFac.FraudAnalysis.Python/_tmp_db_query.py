import asyncio, asyncpg, json, os
from dotenv import load_dotenv
load_dotenv()

async def main():
    conn = await asyncpg.connect(os.getenv("NEONDB_CONNECTION_STRING"))
    
    # 1. fraud_patterns (all 7)
    rows = await conn.fetch("SELECT id, content, metadata FROM fraud_patterns ORDER BY id")
    print("=== FRAUD_PATTERNS ===")
    for r in rows:
        print(f"ID: {r['id']}")
        print(f"Content: {r['content'][:300]}")
        meta = r['metadata']
        if isinstance(meta, str):
            meta = json.loads(meta)
        print(f"Metadata: {json.dumps(meta, indent=2)}")
        print("---")
    
    # 2. compliance_documents (all 5)
    rows = await conn.fetch("SELECT id, content, metadata FROM compliance_documents ORDER BY id")
    print("\n=== COMPLIANCE_DOCUMENTS ===")
    for r in rows:
        print(f"ID: {r['id']}")
        print(f"Content: {r['content'][:300]}")
        meta = r['metadata']
        if isinstance(meta, str):
            meta = json.loads(meta)
        print(f"Metadata: {json.dumps(meta, indent=2)}")
        print("---")
    
    # 3. episodic_memory (all 6)
    rows = await conn.fetch("SELECT id, content, metadata FROM episodic_memory ORDER BY id")
    print("\n=== EPISODIC_MEMORY ===")
    for r in rows:
        print(f"ID: {r['id']}")
        print(f"Content: {r['content'][:400]}")
        meta = r['metadata']
        if isinstance(meta, str):
            meta = json.loads(meta)
        print(f"Metadata: {json.dumps(meta, indent=2)}")
        print("---")
    
    # 4. analysis_decisions (all 6)
    rows = await conn.fetch("SELECT * FROM analysis_decisions ORDER BY analyzed_at DESC LIMIT 10")
    print("\n=== ANALYSIS_DECISIONS ===")
    for r in rows:
        print(dict(r))
        print("---")
    
    # 5. Sample fraud_cases
    rows = await conn.fetch("SELECT id, content, metadata FROM fraud_cases LIMIT 5")
    print("\n=== FRAUD_CASES (sample 5) ===")
    for r in rows:
        print(f"ID: {r['id']}")
        print(f"Content: {r['content'][:200]}")
        meta = r['metadata']
        if isinstance(meta, str):
            meta = json.loads(meta)
        print(f"Metadata: {json.dumps(meta, indent=2)}")
        print("---")
    
    # 6. policy_rules sample
    rows = await conn.fetch("SELECT COUNT(*) as cnt, COUNT(DISTINCT brand) as brands FROM policy_rules")
    print(f"\n=== POLICY_RULES: count={rows[0]['cnt']}, brands={rows[0]['brands']} ===")
    rows = await conn.fetch("SELECT id, brand, rule_category, rule_text FROM policy_rules LIMIT 5")
    for r in rows:
        print(dict(r))
        print("---")
    
    # 7. merchant_risk_profiles
    rows = await conn.fetch("SELECT COUNT(*) as cnt FROM merchant_risk_profiles")
    print(f"\n=== MERCHANT_RISK_PROFILES: count={rows[0]['cnt']} ===")
    if rows[0]['cnt'] > 0:
        rows2 = await conn.fetch("SELECT * FROM merchant_risk_profiles LIMIT 5")
        for r in rows2:
            print(dict(r))
    
    # 8. learned_fraud_patterns
    try:
        rows = await conn.fetch("SELECT COUNT(*) as cnt FROM learned_fraud_patterns")
        print(f"\n=== LEARNED_FRAUD_PATTERNS: count={rows[0]['cnt']} ===")
        if rows[0]['cnt'] > 0:
            rows2 = await conn.fetch("SELECT * FROM learned_fraud_patterns LIMIT 5")
            for r in rows2:
                print(dict(r))
    except Exception as e:
        print(f"\nLEARNED_FRAUD_PATTERNS: table may not exist - {e}")
    
    await conn.close()

asyncio.run(main())
