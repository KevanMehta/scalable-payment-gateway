import uuid
from pybreaker import CircuitBreaker
from redis import Redis
from kafka import KafkaProducer
import json

class PaymentProcessor:
    def __init__(self):
        self.redis = Redis(host='redis', port=6379)
        self.kafka = KafkaProducer(
            bootstrap_servers='kafka:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.breaker = CircuitBreaker(
            fail_max=3, 
            reset_timeout=60,
            exclude=[redis.ConnectionError]
        )

    @circuit_breaker
    async def process_payment(self, payment_data: dict):
        # Generate idempotency key if not provided
        idempotency_key = payment_data.get('idempotency_key', str(uuid.uuid4()))
        
        # Check for duplicate request
        if self.redis.get(f"idempotent:{idempotency_key}"):
            return {"status": "already_processed"}
        
        # Process payment (simplified)
        txn_id = str(uuid.uuid4())
        self.redis.setex(f"txn:{txn_id}", 86400, json.dumps(payment_data))
        
        # Emit Kafka event
        self.kafka.send('payment-events', value={
            'transaction_id': txn_id,
            'amount': payment_data['amount']
        })
        
        return {"transaction_id": txn_id}