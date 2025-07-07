# payment-service/events.py
from kafka import KafkaProducer

producer = KafkaProducer(bootstrap_servers='kafka:9092')

def emit_payment_event(event_type, payload):
    producer.send(
        'payment-events',
        key=event_type.encode(),
        value=json.dumps(payload).encode()
    )