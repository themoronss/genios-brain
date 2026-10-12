"""A review's check, for the tests whose subject is not the check (STEP-13).

Not a test module. `reason/expert/decide` decides a review only through its check (`contracts/claim_check`,
kept on the row since migration 0200). A test of what a DECISION does with a review — not of the check —
gives it the check a review that stands whole would get: every line kept, its own words, the ids its facts
cite. Production never takes this path: the expert pass checks every review before it covers a file
(`reason/expert/sweep`), and `request_for` refuses a row with no check.
"""
from __future__ import annotations

from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert.decide import cited_ids


def as_written(review: ExpertReview) -> C.CheckedReview:
    """The check of a review every line of which stands: shown, in its own words."""
    move = review.next_move
    headline = move.what if move is not None else review.frames.primary
    return C.CheckedReview(
        verdicts=(), fate=C.SHOWN, cited=cited_ids(review),
        question=headline if review.mode == "find_out" else None,
        words=C.CardWords(headline=headline, situation=review.frames.primary, done_when=review.done_when,
                          draft=review.draft, to=move.to if move is not None else None,
                          evidence=cited_ids(review),
                          quotes=tuple(f.quote for f in review.facts if f.quote)))


__all__ = ["as_written"]
