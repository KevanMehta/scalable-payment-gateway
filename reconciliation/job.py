class ReconciliationJob:
    """Compares internal payment state with a provider-supplied status snapshot."""

    def __init__(self, store, provider_statuses):
        self.store = store
        self.provider_statuses = provider_statuses

    def run(self) -> dict:
        run_id = self.store.create_reconciliation_run()
        payments = self.store.list_payments()
        mismatches = []
        for payment in payments:
            provider_status = self.provider_statuses.get(payment["payment_id"])
            if provider_status is None:
                mismatches.append(
                    {
                        "payment_id": payment["payment_id"],
                        "internal_status": payment["status"],
                        "provider_status": None,
                        "reason": "missing_from_provider_snapshot",
                    }
                )
            elif provider_status != payment["status"]:
                mismatches.append(
                    {
                        "payment_id": payment["payment_id"],
                        "internal_status": payment["status"],
                        "provider_status": provider_status,
                        "reason": "status_mismatch",
                    }
                )
        self.store.complete_reconciliation(run_id, len(payments), mismatches)
        return {"run_id": run_id, "checked": len(payments), "mismatches": mismatches}
