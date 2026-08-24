"""Signal Layer types — pure, no DB / no LLM (unit-testable in isolation)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class SignalKind(str, enum.Enum):
    """How a signal is produced (audit + scheduling)."""

    SYMBOLIC = "symbolic"  # pure function over facts/graph; no LLM; runs on tick
    NEURAL = "neural"  # cheap extraction cached at ingest; never re-run per query


# Open-vocab registry — kept as constants so detectors + rules key off one spelling.
# (Not an exhaustive Enum: modules may declare their own signal types.)
SIG_BALL_IN_COURT = "ball_in_court"  # value_num 0/1 — do YOU owe the next reply
SIG_MOMENTUM = "momentum"  # value_num -1..1 — cooling(<0) / warming(>0)
SIG_IMPORTANCE = "importance"  # value_num 0..1 — how much this subject matters
SIG_ENGAGEMENT = "engagement_level"  # value_num 0..1
SIG_SENTIMENT = "sentiment"  # value_num -1..1 (neural)
SIG_BUYING_INTENT = "buying_intent"  # value_num 0..1 (neural)
SIG_STAGE = "stage"  # value_cat — e.g. "negotiation"
SIG_DOMAIN = "domain"  # value_cat — investor|customer|hire|partner|team|vendor|other
SIG_OBJECTION = "objection"    # value_cat — counterpart's open objection/blocker (neural)
SIG_COMMITMENT = "commitment"  # value_cat — what WE owe them, still open (neural)
SIG_COMPETITOR = "competitor"  # value_cat — competing vendor/product named (neural)


@dataclass(frozen=True)
class SignalUpsert:
    """What a detector emits for one (subject, signal_type). Persisted via store.upsert_signal."""

    org_id: str
    subject_node_id: str
    subject_name: str
    signal_type: str
    produced_by: str  # detector id (audit)
    value_num: float | None = None
    value_cat: str | None = None
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)  # source fact/item/node ids (grounding)
    as_of_version: int | None = None
    half_life_days: float | None = None


@dataclass(frozen=True)
class Signal:
    """A current signal value read back from the store (decay already applied)."""

    org_id: str
    subject_node_id: str
    subject_name: str
    signal_type: str
    value_num: float | None
    value_cat: str | None
    confidence: float
    produced_by: str
    evidence: list[str]
    as_of_version: int | None
    computed_at: Any  # datetime; kept loose to avoid importing at type level


@dataclass(frozen=True)
class SignalSpec:
    """Module-declared signal a detector provides (loaded from modules/*/manifest)."""

    signal_type: str
    kind: SignalKind
    description: str = ""
