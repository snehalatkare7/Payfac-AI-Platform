from confluent_kafka import Producer

conf = {
    'bootstrap.servers': 'pkc-619z3.us-east1.gcp.confluent.cloud:9092',
    'security.protocol': 'SASL_SSL',
    'sasl.mechanism': 'PLAIN',
    'sasl.username': 'HOKWAU32T376W7EM',
    'sasl.password': 'cfltqaD9k6l8DoVY9ULLxB7twaeCFpqeb8MTiTaANtFvoVFrZm3rvDnZDentQTFw',
}

# Producer — simulate a payment transaction event

p = Producer(conf)

def publish_event(topic, payload):
    p.produce(topic, payload)
    p.flush()