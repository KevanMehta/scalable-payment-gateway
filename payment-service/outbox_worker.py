import json
from collections.abc import Callable


class OutboxWorker:
    def __init__(self, store, publisher: Callable[[str, str, dict], None], max_attempts=5, base_delay_seconds=1):
        self.store = store
        self.publisher = publisher
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    def run_once(self, limit: int = 100) -> int:
        events = self.store.claim_outbox(limit)
        for event in events:
            try:
                self.publisher(
                    event["id"],
                    event["event_type"],
                    json.loads(event["payload_json"]),
                )
            except Exception as exc:
                self.store.mark_outbox_failed(
                    event["id"],
                    str(exc),
                    self.max_attempts,
                    self.base_delay_seconds,
                )
            else:
                self.store.mark_outbox_published(event["id"])
        return len(events)
