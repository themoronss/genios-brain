from pydantic import BaseModel
from typing import List


class MemoryUpdate(BaseModel):
    field: str
    new_value: str
    confidence: float


class LearningReport(BaseModel):
    outcome: str
    memory_updates: List[MemoryUpdate]