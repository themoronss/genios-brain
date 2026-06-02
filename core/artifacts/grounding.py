"""Grounding verifier for artifact claims.

Per MD g-i-6 §6.1.1 (HARD GATE):
    for each factual claim in narrator output:
        find a supporting Fact in the fact store
        if none found -> mark claim UNGROUNDED -> reject + regenerate

This is the same gate as core.guardrails.grounding, applied here at the artifact
boundary. We wrap that module so artifacts have a clean per-artifact API.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.guardrails.grounding import GroundingResult, verify_grounding


@dataclass(frozen=True)
class GroundingVerification:
    """Outcome of verifying an artifact's claims against the fact store."""

    all_grounded: bool
    grounding_score: float
    ungrounded_claims: list[str]
    delegated: GroundingResult  # the underlying core.guardrails result


def verify_grounding_of_claims(
    session: Session,
    *,
    org_id: str,
    claims: Iterable[str],
) -> GroundingVerification:
    """Run the grounding check. Return per-claim verdicts + summary."""
    g = verify_grounding(session, org_id=org_id, claims=claims)
    ungrounded = [c.claim for c in g.claims if not c.grounded]
    return GroundingVerification(
        all_grounded=(g.grounded_count == g.total_count and g.total_count > 0),
        grounding_score=g.grounding_score,
        ungrounded_claims=ungrounded,
        delegated=g,
    )
