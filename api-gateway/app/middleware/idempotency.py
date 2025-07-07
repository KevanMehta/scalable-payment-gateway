# api-gateway/middleware/idempotency.py
from fastapi import Request, Response
from redis import Redis

redis = Redis(host='redis')

async def idempotency_middleware(request: Request, call_next):
    idempotency_key = request.headers.get('Idempotency-Key')
    if idempotency_key:
        cached_response = redis.get(f"idempotent:{idempotency_key}")
        if cached_response:
            return Response(content=cached_response)
    
    response = await call_next(request)
    
    if idempotency_key:
        redis.setex(f"idempotent:{idempotency_key}", 86400, response.body)
    
    return response