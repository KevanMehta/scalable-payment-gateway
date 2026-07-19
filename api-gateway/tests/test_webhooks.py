import json
import time

import pytest

from app.store import PaymentStore
from app.webhooks import (
    InvalidWebhook,
    WebhookReplay,
    process_provider_webhook,
    sign_webhook,
    verify_webhook,
)


@pytest.fixture
def payment_store(tmp_path):
    store = PaymentStore(tmp_path / "webhooks.db")
    store.initialize()
    return store


def create_payment(store):
    return store.create_payment(
        {
            "amount": "20.00",
            "currency": "USD",
            "merchant_id": "merchant-1",
            "card_token": "tok_synthetic",
        },
        "webhook-payment-key",
    )[0]


def test_signed_webhook_transitions_payment(payment_store):
    payment = create_payment(payment_store)
    payload = json.dumps(
        {
            "id": "event-1",
            "type": "payment.authorized",
            "data": {
                "payment_id": payment["payment_id"],
                "provider_reference": "provider-1",
            },
        }
    ).encode()
    signature = sign_webhook(payload, "secret", int(time.time()))

    result = process_provider_webhook(payment_store, payload, signature, "secret")

    assert result["status"] == "authorized"
    assert result["provider_reference"] == "provider-1"


def test_webhook_replay_is_rejected(payment_store):
    payment = create_payment(payment_store)
    payload = json.dumps(
        {
            "id": "event-replay",
            "type": "payment.authorized",
            "data": {"payment_id": payment["payment_id"]},
        }
    ).encode()
    signature = sign_webhook(payload, "secret", int(time.time()))
    process_provider_webhook(payment_store, payload, signature, "secret")

    with pytest.raises(WebhookReplay):
        process_provider_webhook(payment_store, payload, signature, "secret")


def test_tampered_and_stale_webhooks_are_rejected():
    payload = b'{"id":"event"}'
    signature = sign_webhook(payload, "secret", 1000)

    with pytest.raises(InvalidWebhook, match="timestamp"):
        verify_webhook(payload, signature, "secret", now=2000)
    with pytest.raises(InvalidWebhook, match="signature"):
        verify_webhook(payload, sign_webhook(payload, "wrong", 2000), "secret", now=2000)
