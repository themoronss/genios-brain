"""M1.C3 · a message blasted to a list must not outrank one addressed to a person.

    pytest tests/capture/esqe/test_audience_size.py -q

THE HOLE. `NormalizedSignal.recipients` is the To+Cc tuple the connector captured, and until this
change the only thing in the system that read it was `capture/visibility_rules` — which decides
who may SEE a result. So the engine knew how many people a message went to and used that solely
for permissions, never for how much the message mattered. A send to five thousand strangers and a
note written to the founder scored on identical terms.

WHAT THIS IS NOT. It is not a sixth weight. `ImportanceWeights` is total-checked at import because
`// 10000` is a weighted mean only while the five weights sum to 10000, so a sixth term would
silently rescale every score in the product with nothing going red. Audience is a MULTIPLIER on
the finished mean, which is the shape this module already uses for `evidence_authority`.

The property that matters most is the first test: with no recipient information the arithmetic is
bit-identical to what it was, so every score already stored, and every replay of one, stays valid.
"""

from __future__ import annotations

import dataclasses

import pytest

from genios_engine.capture.esqe import importance as I

from tests.capture.esqe.test_importance import NOW, _baseline, _signal


def _score(*, signal=None, **over) -> int:
    """`_signal` in the sibling module does not expose `recipients` or `internal_kind` — the two
    fields this term reads — so those cases are built by replacing them on a real signal rather
    than by hand-rolling a second NormalizedSignal that could drift from the shape in use."""
    base = _signal()
    if signal:
        base = dataclasses.replace(base, **signal)
    return I.score_importance(base, _baseline(), eval_time=NOW, **over).importance_bp


# =============================================================================================
# The ladder.
# =============================================================================================
@pytest.mark.parametrize("size, expected", [
    (None, I.AUDIENCE_NEUTRAL_BP),   # absent — the honest unknown
    (0, I.AUDIENCE_NEUTRAL_BP),      # and a nonsensical count is treated the same way
    (1, I.AUDIENCE_NEUTRAL_BP),      # written to one person
    (10, I.AUDIENCE_NEUTRAL_BP),     # a person and a cc list is still a message
    (11, 8000),
    (50, 8000),
    (51, 6000),
    (500, 6000),
    (501, 4000),
    (5000, 4000),
    (5001, I.AUDIENCE_FLOOR_BP),
    (250_000, I.AUDIENCE_FLOOR_BP),
])
def test_the_ladder_reads_as_specified(size, expected):
    assert I.audience_multiplier_bp(size) == expected


def test_the_floor_is_not_zero():
    """A 20,000-recipient send can still carry a real obligation — a provider's breach notice
    reaches everyone. It must rank low, not vanish, or this term becomes the same mistake in the
    other direction."""
    assert I.AUDIENCE_FLOOR_BP > 0


# =============================================================================================
# The property that keeps every stored score valid.
# =============================================================================================
def test_absent_audience_scores_exactly_as_before():
    """Neutral is 10000, and `x * 10000 // 10000 == x` for every integer x. Not approximately
    unchanged — identical."""
    with_recipients = _score()
    explicit_absent = _score(audience_size=None)

    assert with_recipients == explicit_absent
    assert I.audience_multiplier_bp(None) == I.BP_MAX


def test_a_source_with_no_recipient_list_is_absent_rather_than_zero():
    """A webhook, a CRM row, an uploaded document. None of them can be a blast, and none of them
    may be ranked below an email for being unable to answer the question."""
    assert _score(signal={"recipients": ()}) == _score(signal={"recipients": ("a@b.com",)})


# =============================================================================================
# The defect, stated as a comparison.
# =============================================================================================
def test_a_blast_ranks_strictly_below_the_same_message_addressed_to_one_person():
    """Identical claim, identical amount, identical deadline, identical sender. The ONLY
    difference is how many people it went to."""
    addressed = _score(audience_size=1)
    blast = _score(audience_size=5_000)

    assert blast < addressed, "a send list must cost the sender rank"


def test_the_discount_is_monotonic():
    """Bigger audience never scores higher. A ladder that inverted anywhere would be worse than
    no ladder, because it would be unpredictable rather than merely wrong."""
    scores = [_score(audience_size=n) for n in (1, 11, 51, 501, 5_001)]

    assert scores == sorted(scores, reverse=True)


def test_the_company_talking_to_itself_is_never_discounted():
    """An all-hands to 200 colleagues is a large audience and a real one. `internal_kind` is the
    flag that says the company wrote this, and punishing it would be the opposite of the fix."""
    internal = _score(signal={"internal_kind": "policy",
                              "recipients": tuple(f"p{i}@acme.ai" for i in range(200))})
    alone = _score(signal={"internal_kind": "policy", "recipients": ("one@acme.ai",)})

    assert internal == alone


# =============================================================================================
# The components carry it, and old rows still load.
# =============================================================================================
def test_the_score_carries_the_audience_it_was_judged_on():
    parts = I.score_importance(_signal(), _baseline(), eval_time=NOW,
                               audience_size=5_000).components

    assert parts.audience_size == 5_000
    assert parts.audience_multiplier_bp == 4000


def test_a_record_written_before_this_term_still_loads():
    """`qualification_drops.components` is jsonb written months before it is read. A row from
    before this change is not malformed — it predates the term — and must load as absent/neutral,
    which is exactly the score it was given."""
    record = I.score_importance(_signal(), _baseline(), eval_time=NOW).components.as_record()
    del record["audience_size"]
    del record["audience_multiplier_bp"]

    restored = I.ImportanceComponents.from_record(record)

    assert restored.audience_size is None
    assert restored.audience_multiplier_bp == I.AUDIENCE_NEUTRAL_BP


def test_the_components_round_trip():
    parts = I.score_importance(_signal(), _baseline(), eval_time=NOW,
                               audience_size=120).components

    assert I.ImportanceComponents.from_record(parts.as_record()) == parts
