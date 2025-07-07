from locust import HttpUser, task, between

class PaymentLoadTest(HttpUser):
    wait_time = between(0.1, 0.5)  # Simulate 10K TPS
    
    @task
    def process_payment(self):
        headers = {
            "Idempotency-Key": "test-${uuid.uuid4()}",
            "Content-Type": "application/json"
        }
        self.client.post("/payments", json={
            "amount": 100,
            "card_token": "tok_visa_${uuid.uuid4()}"
        }, headers=headers)