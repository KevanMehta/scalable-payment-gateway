from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import uuid
from circuitbreaker import circuit

app = FastAPI()
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

class PaymentRequest(BaseModel):
    amount: float
    card_token: str
    merchant_id: str

@app.post("/payments")
@circuit(failure_threshold=5, recovery_timeout=30)
async def process_payment(payment: PaymentRequest):
    transaction_id = str(uuid.uuid4())
    
    # Basic fraud check
    if payment.amount > 10_000:  # Example rule
        raise HTTPException(status_code=400, detail="Potential fraud detected")
    
    # Store in Redis (simulate processing)
    redis_client.hset(
        f"txn:{transaction_id}",
        mapping={
            "amount": payment.amount,
            "status": "processed"
        }
    )
    
    return {"transaction_id": transaction_id, "status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)