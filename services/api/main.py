from fastapi import FastAPI
from pydantic import BaseModel
from shared.kafka_producer import publish_event

app = FastAPI()

class Transaction(BaseModel):
    transaction_id: str
    card_token: str
    amount: float
    merchant_id: str
    mcc: str
    device_id: str
    ip_address: str
    geo_location: str


@app.post("/authorize")
async def authorize(txn: Transaction):

    publish_event("txn_authorization_events", txn.dict())

    return {
        "status": "received",
        "transaction_id": txn.transaction_id
    }