import psycopg2
import os

PGVECTOR_URL = os.environ.get("DATABASE_URL")

if not PGVECTOR_URL:
    raise ValueError("PGVECTOR_URL not set in environment")

conn = psycopg2.connect(PGVECTOR_URL)

def retrieve_policies(query_embedding, brand, top_k=5):

    cur = conn.cursor()
    # Flatten embedding for SQL ARRAY
    embedding_str = ','.join(str(x) for x in query_embedding)
    sql = f"""
        SELECT rule_text, rule_type
        FROM policy_rules
        WHERE brand = %s
        ORDER BY embedding <-> (ARRAY[{embedding_str}]::vector)
        LIMIT %s
    """
    cur.execute(sql, (brand, top_k))
    rows = cur.fetchall()
    policies = []
    for r in rows:
        policies.append({
            "rule_text": r[0],
            "rule_type": r[1]
        })
    return policies