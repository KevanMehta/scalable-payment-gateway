import hashlib
import hmac
import json
import time

from app.store import PaymentStore


class InvalidWebhook(Exception):
    pass


class WebhookReplay(Exception):
    pass


PROVIDER_STATUS_MAP = {
    "payment.authorized": "authorized",
    "payment.captured": "captured",
    "payment.failed": "failed",
    "payment.refunded": "refunded",
}


def sign_webhook(payload: bytes, secret: str, timestamp: int) -> str:
    signed_payload = str(timestamp).encode() + b"." + payload
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_webhook(
    payload: bytes,
    signature_header: str,
    secret: str,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> None:
    values = {}
    for item in signature_header.split(","):
        key, separator, value = item.partition("=")
        if separator:
            values.setdefault(key, []).append(value)
    try:
        timestamp = int(values["t"][0])
        signatures = values["v1"]
    except (KeyError, ValueError, IndexError) as exc:
        raise InvalidWebhook("malformed webhook signature") from exc

    current_time = int(time.time()) if now is None else now
    if abs(current_time - timestamp) > tolerance_seconds:
        raise InvalidWebhook("webhook timestamp is outside the allowed window")

    expected = sign_webhook(payload, secret, timestamp).split("v1=", 1)[1]
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise InvalidWebhook("webhook signature is invalid")


def process_provider_webhook(
    store: PaymentStore, payload: bytes, signature_header: str, secret: str
) -> dict:
    verify_webhook(payload, signature_header, secret)
    try:
        event = json.loads(payload)
        event_id = event["id"]
        event_type = event["type"]
        data = event["data"]
        payment_id = data["payment_id"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise InvalidWebhook("webhook payload is malformed") from exc

    if event_type not in PROVIDER_STATUS_MAP:
        raise InvalidWebhook("webhook event type is not supported")
    return store.record_webhook(
        "provider",
        str(event_id),
        str(payment_id),
        PROVIDER_STATUS_MAP[event_type],
        data.get("provider_reference"),
    )
