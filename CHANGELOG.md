# Changelog

Notable changes are documented here. The project does not currently publish versioned releases.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- Atomic merchant-scoped idempotency keys and duplicate-payment prevention.
- SQLite-backed payment state machine using integer minor units and optimistic versions.
- HMAC webhook verification with timestamp and replay protection.
- Transactional outbox, exponential retry, stale-claim recovery, dead-letter handling, and requeue.
- Reconciliation run and mismatch persistence.
- Merchant API-key verification and per-process rate limiting.
- Failure-path tests covering concurrency, rollback, retry, replay, and compensation.
- Updated the fraud-rule test dependency to a non-vulnerable scikit-learn release.

### Changed

- Saga execution now retries steps, compensates in reverse order, and reports compensation failures.
- Kafka events carry a stable event ID for consumer deduplication.
- README now documents the reliability model, security boundaries, and exact limitations.

### Removed

- Unwired Redis idempotency and payment-processor examples that conflicted with the database-backed flow.
