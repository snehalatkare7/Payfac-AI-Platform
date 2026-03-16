import redis
import json

r = redis.Redis(host="redis-17979.c279.us-central1-1.gce.cloud.redislabs.com", port=17979, username="default", password="LlpB0kR8tMe1wkIdyoVT4sIPB5gKqT7u", decode_responses=True)

def store_transaction(card_token, txn):

    key = f"card:{card_token}:recent"

    r.lpush(key, json.dumps(txn))
    r.expire(key, 1800)


def get_velocity(card_token):

    key = f"card:{card_token}:recent"

    return r.llen(key)