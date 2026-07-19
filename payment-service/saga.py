from dataclasses import dataclass, field
from enum import Enum
from time import sleep


class SagaStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"


class SagaExecutionError(Exception):
    def __init__(self, message, cause, compensation_errors):
        super().__init__(message)
        self.cause = cause
        self.compensation_errors = compensation_errors


@dataclass
class Saga:
    payment_id: str
    steps: list
    max_step_attempts: int = 3
    retry_delay_seconds: float = 0
    status: SagaStatus = SagaStatus.PENDING
    completed_steps: list = field(default_factory=list)

    def execute(self):
        if self.status is not SagaStatus.PENDING:
            raise RuntimeError("saga can only be executed once")
        self.status = SagaStatus.RUNNING
        try:
            for step in self.steps:
                self._execute_with_retry(step)
                self.completed_steps.append(step)
        except Exception as exc:
            errors = self._compensate()
            raise SagaExecutionError(
                f"saga for payment {self.payment_id} failed",
                exc,
                errors,
            ) from exc
        self.status = SagaStatus.COMPLETED
        return self.status

    def _execute_with_retry(self, step):
        for attempt in range(1, self.max_step_attempts + 1):
            try:
                step.execute()
                return
            except Exception:
                if attempt == self.max_step_attempts:
                    raise
                if self.retry_delay_seconds:
                    sleep(self.retry_delay_seconds * (2 ** (attempt - 1)))

    def _compensate(self):
        self.status = SagaStatus.COMPENSATING
        errors = []
        for step in reversed(self.completed_steps):
            try:
                step.compensate()
            except Exception as exc:
                errors.append((step, exc))
        self.status = (
            SagaStatus.COMPENSATION_FAILED if errors else SagaStatus.COMPENSATED
        )
        return errors
