"""Shared types for the proactive analysis layer."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InsightType(StrEnum):
    """Per MD g-i-4 §3 data model."""

    RISK = "risk"
    OPPORTUNITY = "opportunity"
    MISALIGNMENT = "misalignment"


class DeliveryRoute(StrEnum):
    """Per MD g-i-4 — 80/20 routing + channel discipline."""

    AUTONOMOUS = "autonomous"
    NOTIFY = "notify"
    FLAG = "flag"
    DIGEST = "digest"


class InsightSignature(BaseModel):
    """Semantic identity of an insight — used for dedupe + per-user suppression.

    Per MD §1.1.1: signature = (type, primary_entity, root_cause_edge).
    Same signature within window → suppressed (with hysteresis).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: InsightType
    primary_entity: str
    root_cause_edge: str  # edge id from g-i-2 derivation chain (or "" if symbolic-only)

    def hash(self) -> str:
        """Deterministic short hash for storage in feedback table."""
        s = f"{self.type.value}|{self.primary_entity}|{self.root_cause_edge}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]


class Insight(BaseModel):
    """The proactive output before delivery routing.

    Per MD g-i-4 §3 data model. Frozen — once generated, immutable until feedback.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    org_id: str
    type: InsightType
    primary_entity: str
    root_cause_edge: str = ""
    derivation_chain: list[dict[str, Any]] = Field(default_factory=list)
    foresight: dict[str, Any] | None = Field(
        default=None,
        description="{mode: base_rate|qualitative, value, basis, sample_size?}",
    )
    grounding_refs: list[str] = Field(default_factory=list)
    created_at: datetime
    # Scoring + routing filled later in the pipeline
    scores: dict[str, float] | None = None
    delivery_route: DeliveryRoute | None = None

    @property
    def signature(self) -> InsightSignature:
        return InsightSignature(
            type=self.type,
            primary_entity=self.primary_entity,
            root_cause_edge=self.root_cause_edge,
        )
