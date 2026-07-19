import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable, Iterator


class IdempotencyConflict(Exception):
    pass


class PaymentNotFound(Exception):
    pass


class StateTransitionError(Exception):
    pass


ALLOWED_TRANSITIONS = {
    "pending": {"authorized", "failed", "cancelled"},
    "authorized": {"captured", "failed", "cancelled"},
    "captured": {"refunded"},
    "failed": set(),
    "cancelled": set(),
    "refunded": set(),
}


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency TEXT NOT NULL CHECK (length(currency) = 3),
    status TEXT NOT NULL,
    provider_reference TEXT UNIQUE,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    merchant_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_json TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (merchant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS outbox_events (
    id TEXT PRIMARY KEY,
    aggregate_id TEXT NOT NULL REFERENCES payments(id),
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    last_error TEXT,
    claimed_at TEXT,
    created_at TEXT NOT NULL,
    published_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbox_delivery
ON outbox_events(status, next_attempt_at);

CREATE TABLE IF NOT EXISTS webhook_events (
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    PRIMARY KEY (provider, event_id)
);

CREATE TABLE IF NOT EXISTS reconciliation_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    checked_count INTEGER NOT NULL DEFAULT 0,
    mismatch_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reconciliation_mismatches (
    run_id TEXT NOT NULL REFERENCES reconciliation_runs(id),
    payment_id TEXT NOT NULL REFERENCES payments(id),
    internal_status TEXT NOT NULL,
    provider_status TEXT,
    reason TEXT NOT NULL,
    PRIMARY KEY (run_id, payment_id)
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_hash(data: dict) -> str:
    encoded = json.dumps(
        data, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def amount_to_minor_units(amount: str | Decimal) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), ROUND_HALF_UP))


class PaymentStore:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._initialize_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self) -> None:
        with self._initialize_lock, self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_payment(
        self,
        request_data: dict,
        idempotency_key: str,
        before_commit: Callable[[], None] | None = None,
    ) -> tuple[dict, bool]:
        amount_minor = amount_to_minor_units(request_data["amount"])
        normalized_request = {
            **request_data,
            "amount": None,
            "amount_minor": amount_minor,
        }
        request_hash = canonical_hash(normalized_request)
        merchant_id = request_data["merchant_id"]

        with self.transaction() as connection:
            existing = connection.execute(
                """SELECT request_hash, response_json FROM idempotency_keys
                   WHERE merchant_id = ? AND idempotency_key = ?""",
                (merchant_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key was already used with a different request"
                    )
                if not existing["response_json"]:
                    raise IdempotencyConflict("matching request is still being processed")
                return json.loads(existing["response_json"]), True

            now = utc_now()
            connection.execute(
                """INSERT INTO idempotency_keys
                   (merchant_id, idempotency_key, request_hash, created_at)
                   VALUES (?, ?, ?, ?)""",
                (merchant_id, idempotency_key, request_hash, now),
            )

            payment_id = str(uuid.uuid4())
            connection.execute(
                """INSERT INTO payments
                   (id, merchant_id, amount_minor, currency, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    payment_id,
                    merchant_id,
                    amount_minor,
                    request_data["currency"],
                    now,
                    now,
                ),
            )
            self._insert_outbox(
                connection,
                payment_id,
                "payment.created",
                {"payment_id": payment_id, "status": "pending"},
                now,
            )
            response = {
                "payment_id": payment_id,
                "status": "pending",
                "amount": f"{Decimal(amount_minor) / 100:.2f}",
                "currency": request_data["currency"],
            }
            connection.execute(
                """UPDATE idempotency_keys SET response_json = ?
                   WHERE merchant_id = ? AND idempotency_key = ?""",
                (json.dumps(response), merchant_id, idempotency_key),
            )
            if before_commit:
                before_commit()
            return response, False

    def get_payment(self, payment_id: str) -> dict:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM payments WHERE id = ?", (payment_id,)
            ).fetchone()
        if not row:
            raise PaymentNotFound(f"payment {payment_id} was not found")
        return self._payment_dict(row)

    def transition_payment(
        self,
        payment_id: str,
        target_status: str,
        event_type: str,
        provider_reference: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> dict:
        if connection is None:
            with self.transaction() as owned_connection:
                return self.transition_payment(
                    payment_id,
                    target_status,
                    event_type,
                    provider_reference,
                    owned_connection,
                )

        row = connection.execute(
            "SELECT * FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()
        if not row:
            raise PaymentNotFound(f"payment {payment_id} was not found")
        if target_status == row["status"]:
            return self._payment_dict(row)
        if target_status not in ALLOWED_TRANSITIONS[row["status"]]:
            raise StateTransitionError(
                f"cannot transition payment from {row['status']} to {target_status}"
            )

        now = utc_now()
        updated = connection.execute(
            """UPDATE payments
               SET status = ?, provider_reference = COALESCE(?, provider_reference),
                   version = version + 1, updated_at = ?
               WHERE id = ? AND version = ?""",
            (target_status, provider_reference, now, payment_id, row["version"]),
        )
        if updated.rowcount != 1:
            raise StateTransitionError("payment was concurrently modified")
        self._insert_outbox(
            connection,
            payment_id,
            event_type,
            {"payment_id": payment_id, "status": target_status},
            now,
        )
        result = connection.execute(
            "SELECT * FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()
        return self._payment_dict(result)

    def record_webhook(
        self,
        provider: str,
        event_id: str,
        payment_id: str,
        target_status: str,
        provider_reference: str | None,
    ) -> dict:
        with self.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO webhook_events(provider, event_id, received_at) VALUES (?, ?, ?)",
                    (provider, event_id, utc_now()),
                )
            except sqlite3.IntegrityError as exc:
                from app.webhooks import WebhookReplay

                raise WebhookReplay("webhook event has already been processed") from exc
            return self.transition_payment(
                payment_id,
                target_status,
                f"payment.{target_status}",
                provider_reference,
                connection,
            )

    def claim_outbox(self, limit: int = 100) -> list[dict]:
        with self.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM outbox_events
                   WHERE status = 'pending' AND next_attempt_at <= ?
                   ORDER BY created_at LIMIT ?""",
                (utc_now(), limit),
            ).fetchall()
            if not rows:
                return []
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" for _ in ids)
            connection.execute(
                f"""UPDATE outbox_events SET status = 'processing', claimed_at = ?
                    WHERE id IN ({placeholders})""",
                [utc_now(), *ids],
            )
            return [dict(row) for row in rows]

    def mark_outbox_published(self, event_id: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                """UPDATE outbox_events
                   SET status = 'published', published_at = ?, last_error = NULL, claimed_at = NULL
                   WHERE id = ? AND status = 'processing'""",
                (utc_now(), event_id),
            )

    def mark_outbox_failed(
        self, event_id: str, error: str, max_attempts: int, base_delay_seconds: int
    ) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT attempts FROM outbox_events WHERE id = ?", (event_id,)
            ).fetchone()
            attempts = row["attempts"] + 1
            status = "dead_letter" if attempts >= max_attempts else "pending"
            delay = base_delay_seconds * (2 ** (attempts - 1))
            next_attempt = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
            connection.execute(
                """UPDATE outbox_events
                   SET status = ?, attempts = ?, next_attempt_at = ?, last_error = ?, claimed_at = NULL
                   WHERE id = ?""",
                (status, attempts, next_attempt, error[:1000], event_id),
            )

    def recover_stale_outbox(self, older_than_seconds: int = 300) -> int:
        cutoff = (datetime.now(UTC) - timedelta(seconds=older_than_seconds)).isoformat()
        with self.transaction() as connection:
            result = connection.execute(
                """UPDATE outbox_events SET status = 'pending', claimed_at = NULL
                   WHERE status = 'processing' AND claimed_at < ?""",
                (cutoff,),
            )
            return result.rowcount

    def requeue_dead_letters(self, limit: int = 100) -> int:
        """Explicitly requeues failed events after an operator resolves the cause."""
        with self.transaction() as connection:
            rows = connection.execute(
                """SELECT id FROM outbox_events WHERE status = 'dead_letter'
                   ORDER BY created_at LIMIT ?""",
                (limit,),
            ).fetchall()
            if not rows:
                return 0
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" for _ in ids)
            connection.execute(
                f"""UPDATE outbox_events
                    SET status = 'pending', attempts = 0, next_attempt_at = ?,
                        last_error = NULL, claimed_at = NULL
                    WHERE id IN ({placeholders})""",
                [utc_now(), *ids],
            )
            return len(ids)

    def outbox_counts(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM outbox_events GROUP BY status"
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    def list_payments(self) -> list[dict]:
        with self.connect() as connection:
            return [
                self._payment_dict(row)
                for row in connection.execute("SELECT * FROM payments ORDER BY created_at")
            ]

    def create_reconciliation_run(self) -> str:
        run_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO reconciliation_runs(id, started_at, status)
                   VALUES (?, ?, 'running')""",
                (run_id, utc_now()),
            )
        return run_id

    def complete_reconciliation(
        self, run_id: str, checked: int, mismatches: list[dict]
    ) -> None:
        with self.transaction() as connection:
            for mismatch in mismatches:
                connection.execute(
                    """INSERT INTO reconciliation_mismatches
                       (run_id, payment_id, internal_status, provider_status, reason)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        mismatch["payment_id"],
                        mismatch["internal_status"],
                        mismatch.get("provider_status"),
                        mismatch["reason"],
                    ),
                )
            connection.execute(
                """UPDATE reconciliation_runs
                   SET completed_at = ?, checked_count = ?, mismatch_count = ?, status = 'completed'
                   WHERE id = ?""",
                (utc_now(), checked, len(mismatches), run_id),
            )

    @staticmethod
    def _insert_outbox(
        connection: sqlite3.Connection,
        payment_id: str,
        event_type: str,
        payload: dict,
        now: str,
    ) -> None:
        connection.execute(
            """INSERT INTO outbox_events
               (id, aggregate_id, event_type, payload_json, next_attempt_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), payment_id, event_type, json.dumps(payload), now, now),
        )

    @staticmethod
    def _payment_dict(row: sqlite3.Row) -> dict:
        return {
            "payment_id": row["id"],
            "merchant_id": row["merchant_id"],
            "amount": f"{Decimal(row['amount_minor']) / 100:.2f}",
            "currency": row["currency"],
            "status": row["status"],
            "provider_reference": row["provider_reference"],
            "version": row["version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
