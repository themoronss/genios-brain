"""A small move is a line in the morning brief, never a card (STEP-15, s15-D3; `06` D66).

`speedrun008/YC-II W27/` STEP-15 §8.6, tree `yc2_w27_s15` M45.C4.L-integration.V0.U03. Rohit's labels answered it on
12 Oct: F20's meetup on 27 Sep and F23's registration complete — 2 of the 94 authored reviews — are `act` reviews the
expert appraised LOW stakes and LOW urgency, and the founder's answer to them is a line in the brief, not a card. This is
the one place that says which review that is: an `act` — as its check leaves it (`reason/expert/decide.mode_of`: a move
the check held is a question, a suppressed one nothing) — whose appraisal is low on both AND whose move writes to no
one (`next_move.to` empty).

⛔ THE LAST CLAUSE IS NOT D66's WORDS, AND WHY (03 s15-F24). Built on D66's words alone — act, low, low — the rule also
took F61's two silent introductions (STEP-14's case, replay 02 m02: *"Write to Omkar Joshi offering a call…"*, appraised
low/low), whose labelled answer is a card each: must-detect 47 → 46 and the Atlas 12 → 11 on the measurement. What
tells F20's meetup and F23's registration apart is what a card is FOR: it puts a draft to a person in front of you. A
small move with nothing to send (no addressee, no draft) is a line; one that writes to someone stays a card. Whether
D66 meant that is the lead's to confirm (s15-D6); both labels hold as built. The covered-file decision
(`reason/domain_shadow._decide_covered_files`) asks it; the brief (`executive/morning_day`) needs no answer of its own,
since a file with a shown `act` and no card is already a line without one.

Pure: a stored review in, a boolean out.
"""
from __future__ import annotations

from genios_engine.reason.expert.decide import mode_of

#: The appraisal level a small move holds on both of its axes.
LOW = "low"


def is_small_move(stored) -> bool:
    """Whether a stored review is an `act` appraised low stakes AND low urgency, through its check."""
    review, checked = stored.review, stored.checked
    if review is None or checked is None:
        return False
    move = review.next_move
    return (mode_of(review, checked) == "act"
            and review.appraisal.stakes == LOW and review.appraisal.urgency == LOW
            and (move is None or not move.to))


__all__ = ["LOW", "is_small_move"]
