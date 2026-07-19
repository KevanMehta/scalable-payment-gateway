import importlib.util
import sys
from pathlib import Path

import pytest

from app.rate_limit import InMemoryRateLimiter
from app.security import verify_api_key
from app.store import PaymentStore
from reconciliation.job import ReconciliationJob


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


outbox_module = load_module(
    "outbox_worker", REPOSITORY_ROOT / "payment-service" / "outbox_worker.py"
)
saga_module = load_module("saga", REPOSITORY_ROOT / "payment-service" / "saga.py")


@pytest.fixture
def store(tmp_path):
    value = PaymentStore(tmp_path / "reliability.db")
    value.initialize()
    value.create_payment(
        {
            "amount": "25.00",
            "currency": "USD",
            "merchant_id": "merchant-1",
            "card_token": "tok_synthetic",
        },
        "reliability-key",
    )
    return value


def test_network_failures_retry_then_dead_letter(store):
    def unavailable_publisher(*_):
        raise ConnectionError("simulated provider network failure")

    worker = outbox_module.OutboxWorker(
        store, unavailable_publisher, max_attempts=3, base_delay_seconds=0
    )

    assert worker.run_once() == 1
    assert worker.run_once() == 1
    assert worker.run_once() == 1
    assert store.outbox_counts() == {"dead_letter": 1}
    assert store.requeue_dead_letters() == 1
    assert store.outbox_counts() == {"pending": 1}


def test_successful_publish_records_event_id_for_consumer_deduplication(store):
    published = []
    worker = outbox_module.OutboxWorker(
        store,
        lambda event_id, event_type, payload: published.append(
            (event_id, event_type, payload)
        ),
    )

    worker.run_once()
    worker.run_once()

    assert len(published) == 1
    assert published[0][1] == "payment.created"
    assert store.outbox_counts() == {"published": 1}


def test_reconciliation_records_status_mismatch(store):
    payment = store.list_payments()[0]
    result = ReconciliationJob(
        store, {payment["payment_id"]: "captured"}
    ).run()

    assert result["checked"] == 1
    assert result["mismatches"][0]["reason"] == "status_mismatch"


def test_saga_retries_and_compensates_in_reverse_order():
    calls = []

    class Step:
        def __init__(self, name, failures=0):
            self.name = name
            self.failures = failures

        def execute(self):
            calls.append(f"execute:{self.name}")
            if self.failures:
                self.failures -= 1
                raise ConnectionError(self.name)

        def compensate(self):
            calls.append(f"compensate:{self.name}")

    saga = saga_module.Saga(
        "payment-1", [Step("reserve"), Step("charge", failures=3)], max_step_attempts=3
    )

    with pytest.raises(saga_module.SagaExecutionError):
        saga.execute()

    assert calls == [
        "execute:reserve",
        "execute:charge",
        "execute:charge",
        "execute:charge",
        "compensate:reserve",
    ]
    assert saga.status is saga_module.SagaStatus.COMPENSATED


def test_rate_limiter_enforces_sliding_window():
    limiter = InMemoryRateLimiter(requests=2, window_seconds=10)
    assert limiter.allow("merchant", now=0)
    assert limiter.allow("merchant", now=1)
    assert not limiter.allow("merchant", now=2)
    assert limiter.allow("merchant", now=11)


def test_api_key_verification_is_merchant_scoped():
    keys = {"merchant-1": "secret-one", "merchant-2": "secret-two"}
    assert verify_api_key("merchant-1", "secret-one", keys)
    assert not verify_api_key("merchant-1", "secret-two", keys)
    assert not verify_api_key("unknown", "secret-one", keys)
