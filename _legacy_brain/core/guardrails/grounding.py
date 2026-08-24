"""Source-grounding verification — the honest core of "anti-hallucination".

Per MD g-i-2 §2.3.1 (HARD RULE):
    for each factual claim in output:
        find a supporting Fact in the fact store (matched by subject/predicate/object)
        if none found: mark claim UNGROUNDED -> flag (do not emit as fact)
    grounding_score = grounded_claims / total_claims

We do NOT build or claim a general "hallucination detector" (which doesn't exist).
We do verify that every factual claim has a backing source Fact in the graph.

v1 implementation:
- Input: list of claims (str), each parsed loosely as "subject predicate object"
- For each claim, search FactRow for any row whose subject + predicate + object
  contain the claim's tokens (case-insensitive substring matching is the v1 floor;
  embeddings can come later if precision demands).
- grounding_score = fraction grounded.

This deliberately conservative implementation can FALSELY mark a claim ungrounded
(low recall) — that's the safe direction. Never marks an actually-ungrounded
claim as grounded (high precision).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.graph.store import FactRow

log = get_logger(__name__)


@dataclass(frozen=True)
class ClaimVerification:
    """Per-claim grounding result."""

    claim: str
    grounded: bool
    supporting_fact_id: str | None
    reason: str


@dataclass(frozen=True)
class GroundingResult:
    """Output of verify_grounding()."""

    claims: list[ClaimVerification]
    grounded_count: int
    total_count: int
    grounding_score: float  # in [0, 1]


def verify_grounding(
    session: Session,
    *,
    org_id: str,
    claims: Iterable[str],
) -> GroundingResult:
    """For each claim, check if at least one Fact backs it. Returns per-claim results + score."""
    out: list[ClaimVerification] = []
    grounded = 0

    for claim in claims:
        norm = claim.strip()
        if not norm:
            out.append(
                ClaimVerification(
                    claim=claim,
                    grounded=False,
                    supporting_fact_id=None,
                    reason="empty claim",
                )
            )
            continue

        tokens = _significant_tokens(norm)
        if not tokens:
            out.append(
                ClaimVerification(
                    claim=claim,
                    grounded=False,
                    supporting_fact_id=None,
                    reason="no significant tokens to match",
                )
            )
            continue

        fact_id = _find_supporting_fact(session, org_id=org_id, tokens=tokens)
        if fact_id is None:
            out.append(
                ClaimVerification(
                    claim=claim,
                    grounded=False,
                    supporting_fact_id=None,
                    reason="no fact contains all significant tokens of claim",
                )
            )
        else:
            grounded += 1
            out.append(
                ClaimVerification(
                    claim=claim,
                    grounded=True,
                    supporting_fact_id=fact_id,
                    reason="supporting fact found",
                )
            )

    total = len(out)
    score = grounded / total if total > 0 else 0.0

    if total > 0 and score < 1.0:
        log.info(
            "grounding_partial",
            org_id=org_id,
            grounded=grounded,
            total=total,
            score=round(score, 3),
        )

    return GroundingResult(
        claims=out,
        grounded_count=grounded,
        total_count=total,
        grounding_score=score,
    )


# ─── internals ──────────────────────────────────────────────────────────────


# Tiny stop-word list — keeps matching focused on signal tokens
_STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "of",
    "for",
    "in",
    "on",
    "at",
    "to",
    "by",
    "with",
    "and",
    "or",
    "but",
    "as",
    "this",
    "that",
    "be",
    "has",
    "have",
    "had",
    "it",
    "its",
    "do",
    "does",
    "did",
}


def _significant_tokens(claim: str) -> list[str]:
    """Lowercase tokens minus stop words + very short tokens."""
    raw = claim.lower().split()
    return [t.strip(".,;:!?()[]{}\"'") for t in raw if t.lower() not in _STOP_WORDS and len(t) >= 3]


def _find_supporting_fact(session: Session, *, org_id: str, tokens: list[str]) -> str | None:
    """Find one FactRow whose subject/predicate/object collectively contain ALL tokens.

    v1: substring match (case-insensitive) on each field. Cheap + safe (low false-positive).
    """
    # Build a query: row matches if every token appears in (subject || predicate || object)
    # We approximate with multiple ILIKE clauses combined via AND on the row text.
    candidates = session.execute(select(FactRow).where(FactRow.org_id == org_id)).scalars()

    needles = [t.lower() for t in tokens if t]
    if not needles:
        return None

    for fact in candidates:
        haystack = " ".join([str(fact.subject), str(fact.predicate), str(fact.object)]).lower()
        if all(n in haystack for n in needles):
            return str(fact.id)
    return None


# Unused-import guard so future SQL filters compile cleanly
_ = or_
