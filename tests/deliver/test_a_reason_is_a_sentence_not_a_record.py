"""An evidence value reaches the card as something a person can read — never a record.

    pytest tests/deliver/test_a_reason_is_a_sentence_not_a_record.py -q

⛔ WHY THIS FILE EXISTS. Measured on the design partner's org, 2026-10-04: FOUR of the five open
cards would not open. The dashboard showed "This card could not be opened" and the queue behind it
was fine, which is exactly what a render crash looks like from the outside.

`why[].value` is typed and documented as a value a person reads. The engine was putting reasoning
records in it:

    {"axis": "consistency", "value_bp": 10000}
    {"fact": "situation.trend", "reason": "trend_confidence_below_floor", "absence": …}
    {"spans": 5, "verified_spans": 5}
    {"source": "l1_qualified_signals", "base_bp": 3880, "version": "l2-situation-importance.v1"}

The dashboard renders that field as `{w.value}`. React refuses an object as a child, the drawer
threw, and `CardErrorBoundary` replaced the whole card. The ONE card that opened was the only one
whose `why` carried no object — not a coincidence, the discriminator.

⛔ THIS IS THE THIRD TIME THIS SHAPE HAS SHIPPED. `_plain_value`'s own docstring records the
first: *"the live app showed 'momentum: [object Object]' where a number belonged"* — fixed, but
only for the single-key `{"$decimal": …}` wrapper, so a multi-key structure still travelled whole.
`api-cards.ts` records the second, where a new evidence shape met `humanize(undefined)` and "took
the whole dashboard down with it — every card, not just the one carrying doctrine". Same boundary,
same failure, three times. This test is the boundary, asserted.

⛔ NOTHING HERE INVENTS A READING, and `test_the_structure_still_says_what_it_said` is why. Basis
points become the percentage they already mean; every other pair is rendered in its own key order.
A reason the reader cannot check is worse than no reason.
"""

from __future__ import annotations

import pytest

from genios_engine.deliver.card_builder import _plain_value, _why

pytestmark = pytest.mark.unit

#: The exact shapes production was sending, copied off the four cards that would not open.
_REAL_SHAPES = [
    {"axis": "consistency", "value_bp": 10000},
    {"axis": "evidence", "value_bp": 3300},
    {"fact": "situation.trend", "reason": "trend_confidence_below_floor",
     "absence": "genuinely_absent"},
    {"spans": 5, "verified_spans": 5},
    {"state": "active", "resolved_by": None, "partially_resolved": False},
    {"source": "l1_qualified_signals", "base_bp": 3880,
     "version": "l2-situation-importance.v1"},
]


def _renderable(value) -> bool:
    """What React will accept as a child without throwing."""
    return value is None or isinstance(value, (str, int, float, bool))


@pytest.mark.parametrize("shape", _REAL_SHAPES)
def test_a_reasoning_record_never_reaches_the_card_as_a_record(shape):
    """⛔ THE MUTATION THIS FILE REJECTS: letting a structure through `_plain_value`. Four live
    cards stop opening the moment it does."""
    assert _renderable(_plain_value(shape)), (
        f"{shape} reaches the card as an object — React throws on it and the whole card is "
        "replaced by 'This card could not be opened'")


def test_every_why_row_is_renderable():
    """The gate at the level the dashboard actually reads: the `why` list itself."""
    evidence = [{"field": f"f{i}", "value": shape} for i, shape in enumerate(_REAL_SHAPES)]
    for row in _why(evidence, {}):
        assert _renderable(row.get("value")), row
        assert _renderable(row.get("field")), row
        assert _renderable(row.get("source")), row


def test_the_structure_still_says_what_it_said():
    """Readable is not the same as lossy. Every non-empty pair survives, and basis points are
    rendered as the ratio they already encode rather than an unexplained five-digit integer."""
    out = _plain_value({"axis": "evidence", "value_bp": 3300})
    assert "evidence" in out
    assert "33%" in out, f"3300 bp must read as 33%, got {out!r}"

    out = _plain_value({"spans": 5, "verified_spans": 5})
    assert "5" in out and "verified" in out


def test_a_null_is_dropped_not_printed():
    """`{"state": "active", "resolved_by": None}` must not render the word "None" at a reader."""
    out = _plain_value({"state": "active", "resolved_by": None, "partially_resolved": False})
    assert "None" not in out and "False" not in out
    assert "active" in out


def test_an_empty_structure_yields_nothing_to_show():
    """Better an absent row than an empty quotation mark."""
    assert _plain_value({}) is None


def test_the_original_wrapper_case_still_works():
    """The fix this one completes must not regress: `canonicalize`'s tag wrappers still unwrap to
    the bare value, or every Decimal reads as "decimal 0.42"."""
    assert _plain_value({"$decimal": "0.42"}) == "0.42"
    assert _plain_value({"$date": "2026-10-04"}) == "2026-10-04"


def test_a_plain_value_is_left_alone():
    """The common path must stay untouched — this function sits on every evidence row."""
    assert _plain_value("they asked for pricing") == "they asked for pricing"
    assert _plain_value(42) == 42
    assert _plain_value(None) is None


def test_a_list_renders_as_a_list_not_a_repr():
    """A sequence had the same failure mode and no test; `['a','b']` as a React child throws too."""
    assert _plain_value(["alpha", "beta"]) == "alpha, beta"
