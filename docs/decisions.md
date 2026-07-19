# Architecture Decisions

## ADR-001: Database-Scoped Effectively-Once Payment Creation

**Context:** Clients retry timed-out payment requests and can submit the same request concurrently.

**Decision:** Require merchant-scoped idempotency keys. Insert the key, payment, and initial outbox event in one transaction protected by a unique constraint. Bind the key to a canonical request hash.

**Alternatives:** A cache-only key can expire before the financial record and is difficult to commit atomically. A pre-insert lookup alone races under concurrency.

**Tradeoffs:** The key table grows and needs a documented retention policy. `BEGIN IMMEDIATE` serializes SQLite writers.

**Consequences:** Creation is effectively once inside this database. This does not create exactly-once behavior at external providers or consumers.

## ADR-002: Integer Minor Units and Explicit State Transitions

**Context:** Binary floating-point values and unrestricted status writes create financial and workflow ambiguity.

**Decision:** Validate two-decimal inputs at the API, persist integer minor units, and allow only declared state transitions. Use a version column for optimistic update checks.

**Alternatives:** Fixed-precision database decimals are suitable with explicit currency rules. Floating point was rejected for stored amounts.

**Tradeoffs:** The current conversion assumes currencies with two minor-unit digits; a currency metadata table is needed for currencies with different exponents.

**Consequences:** Invalid transitions fail without an outbox event, and concurrent modifications are detectable.

## ADR-003: Transactional Outbox with At-Least-Once Delivery

**Context:** Writing payment state and publishing directly to Kafka is a dual write; either side can succeed alone.

**Decision:** Persist event intent with payment state, then publish asynchronously. Retry transient failures with exponential delay, recover stale claims, and dead-letter exhausted events. Publish a stable event ID.

**Alternatives:** Distributed transactions are poorly supported across typical databases and brokers. Change-data capture can remove polling but adds infrastructure.

**Tradeoffs:** A crash after publish and before acknowledgement causes duplicate delivery. Consumers must atomically record processed event IDs with their own updates.

**Consequences:** Events are not lost after a committed payment update, but end-to-end exactly-once is not claimed.

## ADR-004: Signed, Replay-Protected Provider Webhooks

**Context:** Webhook endpoints are public, can be forged, and providers retry deliveries.

**Decision:** Verify HMAC-SHA256 over `timestamp.raw_body`, enforce a five-minute window, and insert the provider event ID in the same transaction as the state transition.

**Alternatives:** Source-IP allowlists are brittle and insufficient alone. Parsed-body signatures can change byte representation.

**Tradeoffs:** Clock skew must remain within tolerance and secret rotation needs an overlap strategy not yet implemented.

**Consequences:** Tampered, stale, and replayed events are rejected before duplicate state changes.

## ADR-005: SQLite for the Runnable Reference Boundary

**Context:** Reliability behavior should run locally and in CI without external services.

**Decision:** Use SQLite WAL mode, foreign keys, unique constraints, and explicit transactions for the implemented store.

**Alternatives:** PostgreSQL provides stronger multi-client deployment characteristics but requires test infrastructure. Redis cannot serve as the authoritative relational payment record used here.

**Tradeoffs:** SQLite has a single-writer model and is not a high-availability database.

**Consequences:** The correctness patterns are executable, but a multi-replica deployment requires a PostgreSQL port and equivalent integration tests.

## ADR-006: Report-Only Reconciliation

**Context:** Provider and internal states can diverge because of delayed webhooks, outages, or manual provider actions.

**Decision:** Compare provider snapshots with internal payments and persist mismatches without automatic repair.

**Alternatives:** Automatic correction is faster but can overwrite correct state using delayed or incomplete provider data.

**Tradeoffs:** Operators need a separate review and repair workflow.

**Consequences:** Every run records counts and discrepancy reasons, providing a safe basis for later remediation tooling.
