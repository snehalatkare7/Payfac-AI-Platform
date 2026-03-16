from services.memory.redis_store import store_transaction, get_velocity

def fraud_check(txn):
    store_transaction(txn["card_token"], txn)
    velocity = get_velocity(txn["card_token"])

    if velocity > 5:
        return {"risk": 800, "reason": "velocity attack", "velocity": velocity}
    return {"risk": 100, "reason": "normal activity", "velocity": velocity}