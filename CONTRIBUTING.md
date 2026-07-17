# Contributing

This repository is a portfolio reference implementation. Contributions that improve correctness, tests, documentation, or the completeness of an existing example are welcome. Please discuss substantial scope changes in an issue before implementing them.

## Development

1. Fork the repository and create a focused branch.
2. Use synthetic payment data only. Never commit credentials, account numbers, provider tokens, or customer data.
3. Install and run the checks relevant to your change:

   ```bash
   python -m pip install -r fraud-detection/requirements.txt pytest
   python -m compileall -q api-gateway fraud-detection load-test payment-service
   PYTHONPATH=fraud-detection python -m pytest fraud-detection/tests -q
   terraform fmt -check -recursive infra
   ```

4. Update documentation when behavior, assumptions, or limitations change.
5. Open a pull request using the repository template.

The API test is not part of the default suite because it requires a running API and Redis instance. Frontend, reconciliation, infrastructure, and end-to-end test harnesses have not yet been completed.

## Pull Request Expectations

- Keep changes narrow and explain why they are needed.
- Add or update tests for behavior changes where a runnable test boundary exists.
- Do not claim performance, coverage, deployment readiness, or provider behavior without reproducible evidence.
- Call out migrations, security impact, compatibility concerns, and follow-up work.

By contributing, you agree that your contribution is licensed under the repository's MIT License.
