import os
import uuid

from locust import HttpUser, between, task


class PaymentLoadTest(HttpUser):
    """Workload definition only; it does not establish a throughput claim."""

    wait_time = between(0.1, 0.5)

    @task
    def create_payment(self):
        merchant_id = os.environ["LOAD_TEST_MERCHANT_ID"]
        headers = {
            "X-Merchant-Id": merchant_id,
            "X-API-Key": os.environ["LOAD_TEST_API_KEY"],
            "Idempotency-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        self.client.post(
            "/payments",
            json={
                "amount": "100.00",
                "currency": "USD",
                "merchant_id": merchant_id,
                "card_token": f"tok_synthetic_{uuid.uuid4()}",
            },
            headers=headers,
        )
