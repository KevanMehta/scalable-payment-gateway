# api-gateway/tests/test_payments.py
import httpx
import pytest

@pytest.mark.asyncio
async def test_payment_processing():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post("/payments", json={
            "amount": 100,
            "card_token": "tok_visa_test"
        }, headers={"Idempotency-Key": "test123"})
        
    assert response.status_code == 200
    assert "transaction_id" in response.json()