"""A card's profile never shows `[object Object]`, and never shows the engine's own metrics.

    pytest tests/test_card_profile_rows.py -q

Both defects were seen on a real card in the desktop app, on a real founder's inbox:

    anomaly.engagement.days since contact      [object Object]
    anomaly.engagement.inbound count 28d       [object Object]
    engagement                                 1.8868
    momentum                                   0
    sentiment                                  1

`graph_facts.value` is jsonb, so `derived.trend.*` and `derived.anomaly.*` are OBJECTS, and the
card detail passed every fact through untouched — a row that takes up a line, says nothing, and
reads to the person holding it as a broken product. The scalars beside them are real numbers and
equally wrong to show: they are Layer 2's analytic working state, which RANKS the card. They are
not a description of the person the card is about.

Two rules, and the first is the one that must hold for facts nobody has invented yet: **a value
that has no honest string form is dropped, never rendered.**
"""

from __future__ import annotations

import pytest

from genios_engine.api.routes import _fact_display, _profile_rows


# =============================================================================================
# Rule 1 — nothing leaves without a string form
# =============================================================================================
@pytest.mark.parametrize("value", [
    {"z_score": 2.1, "baseline": 4},          # derived.anomaly.* — the exact shape that leaked
    [1, 2, 3],
    None,
    "",
    "   ",
])
def test_a_value_with_no_honest_string_form_is_dropped(value):
    assert _fact_display(value) is None


@pytest.mark.parametrize("value, shown", [
    ("Sehan Sanjula", "Sehan Sanjula"),
    (42, "42"),
    (1.8868, "1.8868"),
    (True, "yes"),
    (False, "no"),                            # not "False", and not dropped — it is an answer
    ("  Founder  ", "Founder"),
])
def test_a_scalar_is_rendered_the_way_a_person_reads_it(value, shown):
    assert _fact_display(value) == shown


def test_an_object_fact_never_reaches_the_client():
    """The whole bug in one assertion. If this ever returns a row, the app prints `[object
    Object]` — and the person reading the card cannot tell that from a crash."""
    rows = _profile_rows({"derived.anomaly.engagement.days_since_contact": {"z": 2.1}})
    assert rows == []


# =============================================================================================
# Rule 2 — the engine's working state is not a profile
# =============================================================================================
def test_the_analytic_stratum_is_not_offered_as_profile():
    """`derived.*` ranks the card. Showing it as "who this person is" is a category error, and the
    numbers are unreadable out of context — `momentum 0` tells a founder nothing."""
    rows = _profile_rows({
        "derived.sentiment": 1, "derived.engagement": 1.8868, "derived.momentum": 0,
        "derived.trend.engagement.touch_count_28d": {"delta": -2},
    })
    assert rows == []


def test_thread_bookkeeping_stays_out_too():
    """It is already on the card's own subject line and why rows; repeating it under Context is
    the same fact twice with a machine's name on it the second time."""
    assert _profile_rows({"thread.ball_in_court": "us", "thread.last_heard_days": 10}) == []


def test_what_a_human_would_recognise_survives():
    rows = _profile_rows({
        "outreach.counterparty": "Sehan Sanjula",
        "outreach.response_expected": True,
        "role": "Founder",
        "derived.momentum": 0,                          # dropped
        "meeting.title": "Intro call",                  # already in the headline
    })
    assert rows == [
        {"field": "outreach.counterparty", "value": "Sehan Sanjula"},
        {"field": "outreach.response_expected", "value": "yes"},
        {"field": "role", "value": "Founder"},
    ]


def test_the_order_the_graph_returned_is_kept():
    """A profile that re-sorts itself between two reads of the same card looks like the data
    changed. Insertion order is the graph's, and it is left alone."""
    facts = {"company": "Acme", "role": "CFO", "phone": "+91…"}
    assert [r["field"] for r in _profile_rows(facts)] == ["company", "role", "phone"]
