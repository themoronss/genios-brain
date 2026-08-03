from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StageAction(str, Enum):
    pass_ = "pass"
    drop = "drop"
    park = "park"
    emit = "emit"
    short_circuit = "short_circuit"


class StageRecord(BaseModel):
    stage: str                              # "landing", "S0", "S1", ...
    action: StageAction
    reason_code: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventTrace(BaseModel):
    """Per-event, per-stage visibility — the debug core.

    Every L1 stage appends exactly what it did and why, so you can answer:
    "what came in, which stage filtered it, why, and how much" for any event.
    """

    org_id: str
    event_id: str
    dedup_key: str | None = None
    source: str | None = None
    records: list[StageRecord] = Field(default_factory=list)

    def record(self, stage: str, action: str, reason_code: str | None = None,
               **detail: Any) -> "EventTrace":
        self.records.append(
            StageRecord(stage=stage, action=StageAction(action),
                        reason_code=reason_code, detail=detail)
        )
        return self

    @property
    def final_action(self) -> StageAction | None:
        return self.records[-1].action if self.records else None
