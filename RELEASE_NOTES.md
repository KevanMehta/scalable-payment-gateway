# Release Notes

## Unreleased: Payment Reliability Foundation

This change turns the payment API from a Redis-write demonstration into a locally runnable correctness-focused reference implementation.

### Highlights

- Payment creation, idempotency, and event intent now commit atomically.
- Signed provider webhooks are timestamp-checked and replay-protected.
- Payment status changes follow an explicit state machine.
- Outbox delivery supports retry, recovery of abandoned work, dead-lettering, and explicit requeue.
- Reconciliation records provider/internal state differences without silently repairing them.
- Tests exercise concurrent duplicate requests and injected failure paths.

### Compatibility

- `POST /payments` now requires `X-Merchant-Id`, `X-API-Key`, and `Idempotency-Key` headers.
- Amounts must have at most two decimal places and currency must be a three-letter code.
- Redis is no longer used by the implemented payment path.
- The default local persistence backend is SQLite. Existing Redis demo state is not migrated.

### Operational Notes

- Set `PAYMENT_API_KEYS` and `PAYMENT_WEBHOOK_SECRET` before starting the API.
- Back up the SQLite file before upgrading a persistent local environment.
- Kafka consumers must deduplicate the stable event ID. Delivery is at-least-once, not exactly-once across systems.
- The Terraform and Kubernetes files remain partial examples and are not deployed by CI.
