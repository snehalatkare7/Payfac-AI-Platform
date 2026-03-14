from confluent_kafka import Consumer
import json

from fraud_agent import fraud_check
from fraud_detection_agent import detect_fraud
from risk_agent import risk_score
from decision_engine import decide

consumer = Consumer(
    {
        "bootstrap.servers": "pkc-619z3.us-east1.gcp.confluent.cloud:9092",
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "PLAIN",
        "sasl.username": "HOKWAU32T376W7EM",
        "sasl.password": "cfltqaD9k6l8DoVY9ULLxB7twaeCFpqeb8MTiTaANtFvoVFrZm3rvDnZDentQTFw",
        "group.id": "fraud-engine",
        "auto.offset.reset": "earliest"
    }
)
consumer.subscribe(["txn_authorization_events"])

while True:
    message = consumer.poll(1.0)
    if message is None:
        continue
    if message.error():
        print(message.error())
        continue
    print(message.value())

    txn = json.loads(message.value())

    fraud_result = fraud_check(txn)
    velocity = fraud_result.get("velocity", 0)
    detection = detect_fraud(txn, velocity=velocity)
    risk = risk_score(txn)

    # Combine fraud signals: pattern-based detection + velocity-based + rule-based risk
    fraud_risk = max(fraud_result["risk"], detection["risk"])
    final_score = fraud_risk + risk

    decision = decide(final_score)

    print({
        "transaction_id": txn["transaction_id"],
        "risk_score": final_score,
        "decision": decision,
        "fraud_signals": detection.get("fraud_types", []),
        "fraud_reason": detection.get("reason"),
    })