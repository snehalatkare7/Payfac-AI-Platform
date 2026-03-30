"""Reset merchant_risk_profiles so fresh test runs start clean."""
import asyncio
import asyncpg
from app.config import get_settings


async def main():
    s = get_settings()
    dsn = s.neondb_connection_string
    # asyncpg needs a proper DSN; fix common URI issues
    conn = await asyncpg.connect(dsn)

    # Show current state
    rows = await conn.fetch(
        "SELECT merchant_id, average_risk_score, historical_fraud_count, is_high_risk "
        "FROM merchant_risk_profiles ORDER BY merchant_id"
    )
    print("=== BEFORE RESET ===")
    for r in rows:
        print(dict(r))
    print(f"Total: {len(rows)} profiles\n")

    # Delete all profiles
    result = await conn.execute("DELETE FROM merchant_risk_profiles")
    print(f"Deleted: {result}\n")

    # Verify
    rows = await conn.fetch("SELECT COUNT(*) AS cnt FROM merchant_risk_profiles")
    print(f"=== AFTER RESET === Remaining: {rows[0]['cnt']}")

    await conn.close()


asyncio.run(main())
