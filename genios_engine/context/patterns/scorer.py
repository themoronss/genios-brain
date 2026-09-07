"""L2.6.3-U1 · the Candidate Scorer — is this candidate worth promoting? Integer, clockless,
modelless.

TWO NUMBERS, KEPT APART, AND THAT IS THE WHOLE DESIGN. *"Five conditions held"* and *"we are
confident about the facts underneath"* are different claims, and averaging them destroys both: a
strong pattern over thin evidence would score like a weak pattern over solid evidence, and a
reader could not tell which they had. `match_strength_bp` and `quality_carry` are therefore
separate fields, and nothing in this module combines them into one.

THIS SCORE NEVER REACHES `importance_bp`. `CandidateScore` has no such field, and the assertion is
enforced by a test rather than left to discipline. Importance is BLG-18's, composes from Layer 1
signal scores, and carries stored components that explain it; a candidate score leaking into
ranking would put a second, incompatible importance scale beside it with no components at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from genios_engine.context.patterns.candidate import SituationCandidate
from genios_engine.context.patterns.contract import (BASE_MATCH_STRENGTH_BP,
                                                     MAX_MATCH_STRENGTH_BP, combined_strength_bp)

#: The floor a candidate must reach to be worth promoting into the situation pipeline.
#:
#: Equal to `BASE_MATCH_STRENGTH_BP` on purpose, and that is a statement rather than a
#: coincidence: every required condition holding IS the bar. Optional signals raise a candidate
#: above the floor and can never be what carries it over — a pattern whose fire depended on an
#: optional signal would be a pattern that quietly required six conditions while declaring five.
PROMOTION_FLOOR_BP = BASE_MATCH_STRENGTH_BP

#: Quality axes below which a candidate is held back regardless of how many conditions held.
#: `identity` is the one that matters: a perfectly matched pattern about an entity we cannot
#: resolve is a card addressed to nobody, and `situations.identity_score` already measures it.
MIN_IDENTITY_SCORE = 25


@dataclass(frozen=True, slots=True)
class CandidateScore:
    """How strong the match is, how good the facts under it are, and whether to promote.

    Deliberately WITHOUT: `importance_bp`, `priority`, `risk`, `recommendation`. This layer
    answers "what is true and how sure are we"; every one of those four is a decision.
    """

    pattern_id: str
    anchor_node_id: str
    #: `BASE_MATCH_STRENGTH_BP` plus the satisfied optional weights, clamped at 10000.
    match_strength_bp: int
    #: The L2.5 confidence vector, CARRIED — not recomputed, not averaged into the strength.
    quality_carry: tuple[tuple[str, int], ...]
    #: The floor this decision was made against, stored so a promotion can be re-derived rather
    #: than re-guessed after the constant moves.
    floor_bp: int
    promote: bool
    #: Why not, when not. Empty on a promotion.
    withheld_reason: str = ""

    def as_record(self) -> dict[str, Any]:
        return {"pattern_id": self.pattern_id, "anchor_node_id": self.anchor_node_id,
                "match_strength_bp": self.match_strength_bp,
                "quality_carry": dict(self.quality_carry), "floor_bp": self.floor_bp,
                "promote": self.promote, "withheld_reason": self.withheld_reason}


def match_strength_bp(*, optional_weights_bp: tuple[int, ...] = ()) -> int:
    """The strength arithmetic, exposed for a caller that has weights but no candidate.

    One construction, two callers — the evaluator computes it while it is looking at the signals,
    and this module reports it. A second copy of the sum is how a candidate comes to disagree
    with the match that produced it about how strong the match was.
    """
    return combined_strength_bp(optional_weights_bp)


def score_candidate(candidate: SituationCandidate, quality: Mapping[str, int] | None = None, *,
                    floor_bp: int = PROMOTION_FLOOR_BP) -> CandidateScore:
    """Score one candidate. Pure: no clock, no database, no model, no float.

    `quality` is L2.5's vector for the situation's subject — `evidence`, `freshness`,
    `consistency`, `identity`, `coverage`, `analytic`. It is carried through and consulted for
    one refusal only (identity), never folded into the strength.
    """
    carried = tuple(sorted((str(k), int(v)) for k, v in (quality or {}).items()))
    for _, value in carried:
        if isinstance(value, float):                       # pragma: no cover — int() above
            raise TypeError("quality axes are integers on the 0..100 scale")

    strength = candidate.match_strength_bp
    if strength > MAX_MATCH_STRENGTH_BP:                   # a hand-built candidate, not the
        strength = MAX_MATCH_STRENGTH_BP                   # evaluator's; clamp rather than trust

    identity = dict(carried).get("identity")
    if strength < floor_bp:
        return CandidateScore(candidate.pattern_id, candidate.anchor_node_id, strength, carried,
                              floor_bp, False,
                              f"match strength {strength} is below the floor {floor_bp}")
    if identity is not None and identity < MIN_IDENTITY_SCORE:
        return CandidateScore(candidate.pattern_id, candidate.anchor_node_id, strength, carried,
                              floor_bp, False,
                              f"identity confidence {identity} < {MIN_IDENTITY_SCORE}: the "
                              "pattern held, but about an entity we cannot resolve")
    return CandidateScore(candidate.pattern_id, candidate.anchor_node_id, strength, carried,
                          floor_bp, True)


__all__ = ["MIN_IDENTITY_SCORE", "PROMOTION_FLOOR_BP", "CandidateScore", "match_strength_bp",
           "score_candidate"]
