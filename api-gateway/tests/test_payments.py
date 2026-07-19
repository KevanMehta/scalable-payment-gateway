import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.store import IdempotencyConflict, PaymentStore, StateTransitionError


@pytest.fixture
def store(tmp_path):
    payment_store = PaymentStore(tmp_path / "payments.db")
    payment_store.initialize()
    return payment_store


def request(amount="10.00"):
    return {
        "amount": amount,
        "currency": "USD",
        "merchant_id": "merchant-1",
        "card_token": "tok_synthetic",
    }


def test_duplicate_request_returns_original_payment(store):
    first, first_replay = store.create_payment(request(), "idempotency-key-1")
    second, second_replay = store.create_payment(request(), "idempotency-key-1")

    assert first == second
    assert first_replay is False
    assert second_replay is True
    assert len(store.list_payments()) == 1
    assert store.outbox_counts() == {"pending": 1}


def test_reusing_key_for_different_request_is_rejected(store):
    store.create_payment(request("10.00"), "idempotency-key-1")

    with pytest.raises(IdempotencyConflict):
        store.create_payment(request("11.00"), "idempotency-key-1")


def test_equivalent_amount_representations_replay_same_payment(store):
    first, _ = store.create_payment(request("10.0"), "normalized-amount-key")
    second, replayed = store.create_payment(request("10.00"), "normalized-amount-key")

    assert first == second
    assert first["amount"] == "10.00"
    assert replayed is True


def test_concurrent_duplicate_requests_create_one_payment(store):
    def submit():
        return store.create_payment(request(), "concurrent-key")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: submit(), range(8)))

    assert len({result[0]["payment_id"] for result in results}) == 1
    assert sum(result[1] for result in results) == 7
    assert len(store.list_payments()) == 1
    assert store.outbox_counts()["pending"] == 1


def test_database_failure_rolls_back_payment_idempotency_and_outbox(store):
    def fail_before_commit():
        raise RuntimeError("simulated database failure")

    with pytest.raises(RuntimeError):
        store.create_payment(request(), "rollback-key", fail_before_commit)

    assert store.list_payments() == []
    assert store.outbox_counts() == {}
    result, replayed = store.create_payment(request(), "rollback-key")
    assert result["status"] == "pending"
    assert replayed is False


def test_state_machine_rejects_invalid_transition(store):
    payment, _ = store.create_payment(request(), "state-key")

    with pytest.raises(StateTransitionError):
        store.transition_payment(payment["payment_id"], "refunded", "payment.refunded")


def test_provider_reference_prevents_duplicate_provider_payments(store):
    first, _ = store.create_payment(request(), "provider-key-1")
    second, _ = store.create_payment(request(), "provider-key-2")
    store.transition_payment(
        first["payment_id"], "authorized", "payment.authorized", "provider-123"
    )

    with pytest.raises(sqlite3.IntegrityError):
        store.transition_payment(
            second["payment_id"], "authorized", "payment.authorized", "provider-123"
        )
