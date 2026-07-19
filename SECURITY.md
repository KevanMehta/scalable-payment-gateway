# Security Policy

## Supported Versions

This reference implementation has no released or hosted version. Security fixes are applied to the latest commit on `main`; older commits are not supported.

## Reporting a Vulnerability

Do not open a public issue. Use **Report a vulnerability** in the repository's Security tab. If private vulnerability reporting is unavailable, contact the maintainer through the method on their GitHub profile.

Include the affected revision, synthetic reproduction steps, impact, and a suggested mitigation if available. Never submit real cardholder data, credentials, API keys, provider tokens, or customer information. This project has no response-time SLA.

## Implemented Controls

- Merchant API keys are scoped by merchant ID and compared in constant time.
- Payment access is restricted to the authenticated merchant.
- Idempotency keys and provider references have database uniqueness constraints.
- Webhooks use HMAC-SHA256 over the raw body and timestamp, a five-minute tolerance, and unique event IDs.
- Payment changes are constrained by an explicit state machine.
- Card tokens are accepted as synthetic opaque inputs and are not persisted.
- Payment state and outbox events share one transaction.

## Assumptions and Limitations

- This project must not process real payments or cardholder data and has not been assessed for PCI DSS compliance.
- API keys are loaded from environment configuration as plaintext. A deployment needs hashed or managed secrets, rotation, revocation, scopes, and audit trails.
- TLS termination, network policy, database encryption, backup, restore, and host hardening are outside this repository.
- SQLite is for local execution. It does not provide the availability or multi-node behavior expected of a deployed payment platform.
- Rate limiting is per process and can be bypassed across replicas. Use a shared limiter or API gateway policy in a distributed deployment.
- Outbox delivery is at-least-once. Consumers must transactionally deduplicate `event_id` values.
- Reconciliation reports discrepancies but does not repair them automatically.
- The pickle-based fraud-model example must never load an untrusted artifact; Python pickle can execute code while loading.
- Terraform and Kubernetes files are partial examples. Review IAM, exposure, secrets, image provenance, resources, and state before use.

## Secret Handling

Use different secrets for merchant authentication and webhook signing. Do not commit `.env` files or local database files. Rotate any credential immediately if it appears in logs, an issue, a pull request, or Git history.
