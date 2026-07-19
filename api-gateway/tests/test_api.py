from fastapi.testclient import TestClient

from app.main import app


def configured_client(monkeypatch, tmp_path):
    monkeypatch.setenv("PAYMENT_DATABASE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("PAYMENT_API_KEYS", '{"merchant-1":"api-secret"}')
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "webhook-secret")
    return TestClient(app)


def payment_payload(**overrides):
    payload = {
        "amount": "19.95",
        "currency": "usd",
        "merchant_id": "merchant-1",
        "card_token": "tok_synthetic",
    }
    payload.update(overrides)
    return payload


def headers(**overrides):
    values = {
        "X-Merchant-Id": "merchant-1",
        "X-API-Key": "api-secret",
        "Idempotency-Key": "checkout-12345",
    }
    values.update(overrides)
    return values


def test_api_creates_and_replays_payment(monkeypatch, tmp_path):
    with configured_client(monkeypatch, tmp_path) as client:
        first = client.post("/payments", json=payment_payload(), headers=headers())
        second = client.post("/payments", json=payment_payload(), headers=headers())

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert first.json()["currency"] == "USD"
    assert first.headers["Idempotent-Replayed"] == "false"
    assert second.headers["Idempotent-Replayed"] == "true"


def test_api_rejects_invalid_money_and_missing_idempotency_key(monkeypatch, tmp_path):
    with configured_client(monkeypatch, tmp_path) as client:
        invalid_amount = client.post(
            "/payments", json=payment_payload(amount="1.001"), headers=headers()
        )
        missing_key_headers = headers()
        missing_key_headers.pop("Idempotency-Key")
        missing_key = client.post(
            "/payments", json=payment_payload(), headers=missing_key_headers
        )

    assert invalid_amount.status_code == 422
    assert missing_key.status_code == 422


def test_api_rejects_bad_credentials_and_cross_merchant_body(monkeypatch, tmp_path):
    with configured_client(monkeypatch, tmp_path) as client:
        bad_key = client.post(
            "/payments",
            json=payment_payload(),
            headers=headers(**{"X-API-Key": "wrong-secret"}),
        )
        wrong_merchant = client.post(
            "/payments",
            json=payment_payload(merchant_id="merchant-2"),
            headers=headers(),
        )

    assert bad_key.status_code == 401
    assert wrong_merchant.status_code == 403
