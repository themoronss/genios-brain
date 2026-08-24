"""The canonical envelope — every output must carry this.

Per MD g-i-7 §0 + acceptance:
    Envelope {
      recommendation:   any
      confidence:       band     (high|medium|low — qualitative until calibrated;
                                  raw float stays internal in DecisionRow per
                                  GENIOS_BRIEFING §5 Gate 1 / §8 Task 2)
      derivation:       proof tree
      uncertainty:      flag list (visible weak parts)
      route:            autonomous | notify | flag
      triggered_by:     query | proactive | webhook
      asOf:             { graph_version, timestamp }
      decision_id:      for replay + feedback linking
    }

NAKED OUTPUTS (anything without all required fields) are REJECTED at the
boundary. The Pydantic model enforces shape; build_envelope() enforces
non-empty derivation when the route is autonomous (cannot act on nothing).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.delivery.bands import ConfidenceBand, to_band


class EnvelopeRoute(StrEnum):
    AUTONOMOUS = "autonomous"
    NOTIFY = "notify"
    FLAG = "flag"


class EnvelopeTriggeredBy(StrEnum):
    QUERY = "query"
    PROACTIVE = "proactive"
    WEBHOOK = "webhook"


class AsOfPin(BaseModel):
    """Reproducibility pin (engine replay)."""

    model_config = ConfigDict(frozen=True)

    graph_version: int
    timestamp: datetime


class Envelope(BaseModel):
    """Canonical wrapper for every delivered intelligence output. Frozen + strict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation: dict[str, Any]
    confidence: ConfidenceBand = Field(
        ...,
        description="Qualitative confidence band (high|medium|low). The raw float "
        "is NOT exposed here — it stays internal in DecisionRow.confidence_score "
        "until calibrated (GENIOS_BRIEFING §5 Gate 1).",
    )
    derivation: list[dict[str, Any]] = Field(
        ...,
        description="Proof tree steps (rule_id, conclusion, matched_facts, ...).",
    )
    uncertainty: list[dict[str, Any]] = Field(
        ...,
        description="Visible weak-spot flags. Empty list OK; field is required.",
    )
    route: EnvelopeRoute
    triggered_by: EnvelopeTriggeredBy
    as_of: AsOfPin
    decision_id: str = Field(..., min_length=1)
    org_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _autonomous_must_have_derivation(self) -> Envelope:
        """Per MD: autonomous route REQUIRES non-empty derivation chain.
        An agent cannot act on nothing."""
        if self.route == EnvelopeRoute.AUTONOMOUS and not self.derivation:
            raise ValueError(
                "AUTONOMOUS route requires non-empty derivation chain (cannot act on no proof)"
            )
        return self


class NakedOutputError(Exception):
    """Raised at delivery boundary when envelope shape fails."""


def build_envelope(
    *,
    org_id: str,
    decision_id: str,
    recommendation: dict[str, Any] | None,
    confidence: float,
    derivation: list[dict[str, Any]] | None,
    uncertainty: list[dict[str, Any]] | None,
    route: str,
    triggered_by: str,
    as_of_version: int,
    as_of_timestamp: datetime,
) -> Envelope:
    """Construct an Envelope with validation. Raises NakedOutputError on missing fields.

    The caller (engine, narrator, proactive layer) MUST go through this — direct
    Envelope() construction would skip the helpful error.
    """
    if recommendation is None:
        raise NakedOutputError("recommendation is required (got None)")
    if derivation is None:
        raise NakedOutputError("derivation is required (use [] if symbolic produced no steps)")
    if uncertainty is None:
        raise NakedOutputError("uncertainty is required (use [] if no flags)")
    # The raw float is validated here but NOT carried into the Envelope — the
    # customer-facing surface gets the qualitative band. The float lives on in
    # DecisionRow.confidence_score for later calibration (§5 Gate 1).
    if not 0.0 <= confidence <= 1.0:
        raise NakedOutputError(f"confidence must be in [0, 1]; got {confidence}")

    try:
        return Envelope(
            recommendation=recommendation,
            confidence=to_band(confidence),
            derivation=derivation,
            uncertainty=uncertainty,
            route=EnvelopeRoute(route),
            triggered_by=EnvelopeTriggeredBy(triggered_by),
            as_of=AsOfPin(graph_version=as_of_version, timestamp=as_of_timestamp),
            decision_id=decision_id,
            org_id=org_id,
        )
    except Exception as e:  # Pydantic ValidationError or enum coercion
        raise NakedOutputError(f"Envelope shape invalid: {e}") from e
