# Architecture Decisions

These records describe decisions visible in the repository. They document the current examples rather than a deployed system.

## ADR-001: FastAPI for the HTTP Boundary

**Status:** Accepted for the reference implementation

**Context:** The project needs a small HTTP boundary with a typed payment request and generated API documentation.

**Decision:** Use FastAPI and Pydantic for the payment endpoint.

**Alternatives:** Flask would reduce framework concepts but require additional validation code. Spring Boot would offer a larger ecosystem for service standardization at the cost of more setup for this example.

**Tradeoffs:** FastAPI keeps the example compact, but synchronous Redis calls inside an async route can block the event loop.

**Consequences:** Request validation is explicit. A fuller implementation should either use an async Redis client or move blocking work off the event loop.

## ADR-002: Redis for Ephemeral State and Idempotency Examples

**Status:** Accepted with limitations

**Context:** The examples need quick lookup of transaction state and duplicate request keys.

**Decision:** Use Redis with 24-hour keys in the payment processor and idempotency middleware examples.

**Alternatives:** PostgreSQL could provide durable transactional records. An in-memory map would be simpler but would not survive restarts or work across processes.

**Tradeoffs:** Redis provides simple TTL operations, but the current check-then-write flow is not atomic and Redis is not an authoritative ledger.

**Consequences:** The implementation demonstrates the data-access pattern only. A financial workflow needs atomic reservation, request fingerprinting, durable results, and explicit failure behavior.

## ADR-003: Kafka as the Asynchronous Event Boundary

**Status:** Proposed; not integrated into the main request path

**Context:** Payment state changes often need to notify independent downstream components such as reconciliation or audit processing.

**Decision:** Represent that boundary with a `payment-events` Kafka topic in the processor and event helper examples.

**Alternatives:** A direct service call would be simpler but couple availability and latency. A managed queue could reduce operational work for a single-consumer workflow.

**Tradeoffs:** Kafka supports replayable streams, but adds operational complexity and does not by itself make database writes and event publication atomic.

**Consequences:** Before integration, the project would need event schemas, delivery acknowledgement, retries, consumers, and an outbox or equivalent consistency mechanism.

## ADR-004: In-Process Saga Compensation

**Status:** Accepted for demonstration

**Context:** A multi-step payment workflow needs to show how completed actions can be undone after a later failure.

**Decision:** Execute steps in order and compensate completed steps in reverse order.

**Alternatives:** A durable orchestrator such as Temporal could persist workflow progress. Choreographed events could avoid a central coordinator but make the overall flow harder to inspect.

**Tradeoffs:** The in-process coordinator makes compensation semantics readable, but loses state on process failure and has no retry or timeout policy.

**Consequences:** It is suitable as a pattern example only. Durable execution would require persisted state, idempotent steps, retry classification, and operational visibility.

## ADR-005: PostgreSQL Migration for Reconciliation Records

**Status:** Accepted for the schema example

**Context:** Reconciliation records have structured identifiers, amounts, dates, and discrepancy details that benefit from relational constraints and indexed queries.

**Decision:** Define the schema in PostgreSQL and version it with Flyway.

**Alternatives:** A document database would allow looser records but provide less value for the structured relationships shown here. Raw SQL initialization would omit migration history.

**Tradeoffs:** The relational schema is explicit, but the Maven module is only a dependency sketch and contains no application or migration runner.

**Consequences:** The migration communicates the intended data model. It is not evidence that reconciliation processing is implemented.

## ADR-006: Kubernetes and Terraform as Separate Deployment Examples

**Status:** Incomplete

**Context:** The project explores how an API might declare replicas, autoscaling, networking, and an EKS target.

**Decision:** Keep Kubernetes manifests under `k8s/` and AWS infrastructure definitions under `infra/`.

**Alternatives:** Docker Compose would be better for a complete local environment. A managed application platform would reduce cluster administration.

**Tradeoffs:** The files make infrastructure concerns visible but currently reference missing resources and configuration.

**Consequences:** CI performs formatting and parsing only. It deliberately does not apply infrastructure. IAM, Terraform state, providers, images, Redis, secrets, and runtime validation must be completed before deployment.
