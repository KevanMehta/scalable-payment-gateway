# Contributing

Contributions should improve correctness, failure handling, tests, or documentation within the existing payment flow. Discuss substantial scope changes in an issue first.

## Development

1. Fork the repository and create a focused branch.
2. Use Python 3.11 and synthetic payment data only.
3. Install and run the checks:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements-dev.txt
   python -m compileall -q api-gateway fraud-detection load-test payment-service reconciliation
   PYTHONPATH=api-gateway:fraud-detection python -m pytest api-gateway/tests fraud-detection/tests -q
   terraform fmt -check -recursive infra
   ```

4. Update the README, changelog, release notes, and decision records when contracts or guarantees change.
5. Open a pull request using the template.

## Correctness Expectations

- Put payment state and event intent in one database transaction.
- Add a unique constraint or atomic conditional write for deduplication; do not rely on a check followed by an unprotected insert.
- Use integer minor units or an explicitly bounded decimal type for money.
- Treat remote calls and event delivery as retryable and potentially duplicated.
- Verify webhooks over the raw request body before parsing them.
- Test rollback, concurrency, replay, retry exhaustion, and invalid state transitions when changing those paths.
- Do not claim exactly-once behavior across independent systems. State the transaction boundary and consumer obligations.
- Do not claim throughput, latency, coverage, or deployment readiness without reproducible evidence.

Never commit credentials, account numbers, real provider tokens, local database files, or customer data. By contributing, you agree that your contribution is licensed under the MIT License.
