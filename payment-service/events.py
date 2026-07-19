import json

from kafka import KafkaProducer


class KafkaEventPublisher:
    """Publisher adapter for OutboxWorker; consumers must deduplicate by event_id."""

    def __init__(self, bootstrap_servers="kafka:9092"):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            acks="all",
            value_serializer=lambda value: json.dumps(value).encode(),
        )

    def publish(self, event_id: str, event_type: str, payload: dict) -> None:
        future = self.producer.send(
            "payment-events",
            key=event_id.encode(),
            value={"event_id": event_id, "type": event_type, "data": payload},
        )
        future.get(timeout=10)
