import os
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.rate_limit import InMemoryRateLimiter
from app.security import authenticate_merchant
from app.store import (
    IdempotencyConflict,
    PaymentNotFound,
    PaymentStore,
    StateTransitionError,
)
from app.webhooks import InvalidWebhook, WebhookReplay, process_provider_webhook


class PaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    merchant_id: str = Field(min_length=1, max_length=100)
    card_token: str = Field(min_length=1, max_length=255)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must be a three-letter alphabetic code")
        return value.upper()


class WebhookResponse(BaseModel):
    accepted: bool


def get_store(request: Request) -> PaymentStore:
    return request.app.state.store


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_path = os.getenv("PAYMENT_DATABASE_PATH", "payment_gateway.db")
    app.state.store = PaymentStore(database_path)
    app.state.store.initialize()
    app.state.rate_limiter = InMemoryRateLimiter(
        requests=int(os.getenv("RATE_LIMIT_REQUESTS", "60")),
        window_seconds=60,
    )
    yield


app = FastAPI(title="Payment Gateway Reference API", lifespan=lifespan)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    identity = request.client.host if request.client else "unknown"
    if not request.app.state.rate_limiter.allow(identity):
        return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/payments", status_code=status.HTTP_201_CREATED)
def create_payment(
    payment: PaymentRequest,
    response: Response,
    idempotency_key: str = Header(
        min_length=8, max_length=255, alias="Idempotency-Key"
    ),
    authenticated_merchant: str = Depends(authenticate_merchant),
    store: PaymentStore = Depends(get_store),
):
    if payment.merchant_id != authenticated_merchant:
        raise HTTPException(status_code=403, detail="merchant identity does not match request")
    request_data = payment.model_dump()
    try:
        result, replayed = store.create_payment(request_data, idempotency_key)
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response.headers["Idempotent-Replayed"] = str(replayed).lower()
    return result


@app.get("/payments/{payment_id}")
def get_payment(
    payment_id: str,
    merchant_id: str = Depends(authenticate_merchant),
    store: PaymentStore = Depends(get_store),
):
    try:
        payment = store.get_payment(payment_id)
    except PaymentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if payment["merchant_id"] != merchant_id:
        raise HTTPException(status_code=404, detail=f"payment {payment_id} was not found")
    return payment


@app.post("/payments/{payment_id}/cancel")
def cancel_payment(
    payment_id: str,
    merchant_id: str = Depends(authenticate_merchant),
    store: PaymentStore = Depends(get_store),
):
    try:
        payment = store.get_payment(payment_id)
        if payment["merchant_id"] != merchant_id:
            raise PaymentNotFound(f"payment {payment_id} was not found")
        return store.transition_payment(payment_id, "cancelled", "payment.cancelled")
    except PaymentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/webhooks/provider", response_model=WebhookResponse)
async def provider_webhook(
    request: Request,
    x_webhook_signature: str = Header(
        min_length=1, max_length=1024, alias="X-Webhook-Signature"
    ),
    store: PaymentStore = Depends(get_store),
):
    payload = await request.body()
    secret = os.getenv("PAYMENT_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="webhook secret is not configured")
    try:
        process_provider_webhook(store, payload, x_webhook_signature, secret)
    except InvalidWebhook as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except WebhookReplay as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PaymentNotFound, StateTransitionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WebhookResponse(accepted=True)
