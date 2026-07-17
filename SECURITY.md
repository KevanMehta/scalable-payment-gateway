# Security Policy

## Supported Versions

This portfolio project has no released or deployed version. Security fixes are applied to the latest commit on `main`; older commits are not supported.

## Reporting a Vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's **Report a vulnerability** option under the repository's Security tab. If private vulnerability reporting is not enabled, contact the repository owner through the contact method listed on their GitHub profile and include:

- the affected file, endpoint, or configuration;
- steps to reproduce the issue with synthetic data;
- the potential impact; and
- any suggested mitigation.

Do not include real cardholder data, credentials, access tokens, or other sensitive information. Acknowledgement and remediation timing depend on maintainer availability; this repository has no security SLA.

## Security Assumptions and Limitations

- The code is an educational reference implementation and must not process real payments or cardholder data.
- There is no authentication, authorization, TLS termination, secret management, audit log, durable ledger, or payment-provider integration.
- The API accepts an opaque demo card token but does not verify it. Never submit a primary account number or real provider token.
- Redis and Kafka hostnames assume a trusted local network. Their examples do not configure encryption or authentication.
- Idempotency is incomplete and not registered with the API. It should not be relied on to prevent duplicate financial operations.
- The pickle-based model-loading example is unsafe for untrusted artifacts. Python pickle can execute code during deserialization; only locally created, reviewed artifacts should ever be loaded.
- Terraform and Kubernetes files are partial examples. Review IAM, network exposure, image provenance, resource limits, secrets, and state handling before using any part of them.
- Dependencies are pinned for repeatability but still require regular vulnerability review. Dependabot is configured to propose updates.
