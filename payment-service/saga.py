from dataclasses import dataclass
from enum import Enum

class SagaStatus(Enum):
    PENDING = 1
    COMPLETED = 2
    FAILED = 3

@dataclass
class Saga:
    payment_id: str
    steps: list
    current_step: int = 0
    
    def execute(self):
        try:
            for step in self.steps:
                step.execute()
                self.current_step += 1
            self.status = SagaStatus.COMPLETED
        except Exception as e:
            self._compensate()
            self.status = SagaStatus.FAILED
    
    def _compensate(self):
        for step in reversed(self.steps[:self.current_step]):
            step.compensate()