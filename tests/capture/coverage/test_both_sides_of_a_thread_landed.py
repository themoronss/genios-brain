"""Step 5 · 5-U4 — a sweep can exhaust its cursor honestly and still land half a conversation.

    pytest tests/capture/coverage/test_both_sides_of_a_thread_landed.py -q

`cursor_exhausted` answers *"did we read every page the provider offered?"* This answers the
question that sits beside it and which no page count can reach: **were we offered both sides?**

A Gmail connection scoped to `in:inbox`, a label filter that excludes `SENT`, an OAuth grant
narrowed after the fact — every one of them produces a sweep that exhausts its cursor honestly and
lands one side. `cursor_exhausted=true` is then perfectly true and perfectly misleading.

WHAT IT COSTS is specific, and it is the worst failure mode this product has. L1 derives
`ball_in_court` from a thread's messages and L2 builds `awaiting_response` and
`first_response_overdue` on top of it. A thread whose outbound half never landed reads as *"they
wrote, we never answered"* — so the product tells a founder they owe a reply **they already
sent**. The `Commitment` contract already says what that costs: *"the second false chase is the
last time that founder reads a nudge from us."*
"""
from __future__ import annotations

import pytest

from genios_engine.capture.coverage.symmetry import (ONLY_INBOUND, ONLY_OUTBOUND, check_symmetry)

pytestmark = pytest.mark.unit


def _m(thread: str, direction: str):
    return {"thread_key": thread, "direction": direction}


# =============================================================================================
# The finding
# =============================================================================================
def test_a_thread_with_both_sides_is_not_reported():
    """The floor. A healthy thread must produce nothing, or the report is noise and gets muted —
    and a muted report is worse than no report, because it looks like coverage."""
    report = check_symmetry([_m("t1", "inbound"), _m("t1", "outbound")])

    assert report.one_sided == ()
    assert (report.threads, report.two_sided) == (1, 1)


def test_a_thread_that_landed_only_inbound_is_reported_as_such():
    """THE LOAD-BEARING ROW. Two messages in, none out — this is the shape that makes the product
    tell a founder they owe a reply they already sent."""
    report = check_symmetry([_m("t1", "inbound"), _m("t1", "inbound")])

    assert len(report.one_sided) == 1
    finding = report.one_sided[0]
    assert (finding.thread_key, finding.reason) == ("t1", ONLY_INBOUND)
    assert (finding.inbound, finding.outbound) == (2, 0)


def test_a_thread_that_landed_only_outbound_is_reported_separately():
    """The mirror image, and NOT the same defect. Missing inbound means we cannot see a reply we
    were sent; missing outbound means we cannot see what we said. They point at different scope
    misconfigurations, so one "asymmetric" label for both sends an operator to the wrong setting.
    """
    report = check_symmetry([_m("t1", "outbound"), _m("t1", "outbound")])

    assert report.one_sided[0].reason == ONLY_OUTBOUND


# =============================================================================================
# The judgement calls — each one is a way this check could have become useless
# =============================================================================================
def test_a_single_message_thread_is_not_evidence_of_a_missing_side():
    """THE ONE THAT DECIDES WHETHER ANYONE READS THIS REPORT.

    A newsletter, a notification and a cold email that got no reply are all legitimately one
    message long. Counting them as asymmetry puts a permanent 60% alarm on a healthy mailbox and
    trains every operator to ignore the number — so singletons are excluded from the DENOMINATOR.

    They are still counted and still reported as one-sided, because a thread that should have had
    a reply and did not is exactly what `awaiting_response` is about. The judgement is about the
    RATE, not about hiding the row.
    """
    report = check_symmetry([_m(f"t{i}", "inbound") for i in range(3)]
                            + [_m("t9", "inbound"), _m("t9", "outbound")])

    assert report.singleton == 3
    assert report.asymmetry_bp == 0, (
        "three newsletters made a healthy mailbox look 75% broken")
    assert len(report.one_sided) == 3, "the rows are still there to read"


def test_the_rate_is_integer_basis_points_and_never_a_float():
    """V-7. One one-sided thread out of three eligible is 3333 bp, truncated — never 0.3333, and
    never a percentage rounded on the way out. A float here reaches jsonb and comes back as a
    number nobody can trace to a count."""
    messages = []
    for i in range(3):
        messages += [_m(f"two{i}", "inbound"), _m(f"two{i}", "outbound")]
    messages += [_m("one", "inbound"), _m("one", "inbound")]

    report = check_symmetry(messages)

    assert isinstance(report.asymmetry_bp, int)
    assert report.asymmetry_bp == 2500, f"1 of 4 eligible, got {report.asymmetry_bp}"


def test_a_thread_with_no_derivable_direction_is_a_different_finding():
    """Not "we are missing a side" but "we cannot tell which side anything is" — which points at
    `org_identities` being empty rather than at the mailbox scope. Filing it as a missing side
    sends an operator to re-scope a connection when the fix is to tell us who "us" is."""
    report = check_symmetry([_m("t1", "unknown"), _m("t1", "unknown")])

    assert report.undirected == 1
    assert report.one_sided == (), "a configuration fault was reported as missing mail"


def test_a_message_with_no_thread_key_is_skipped_not_pooled():
    """Pooling them under a placeholder key would report one enormous one-sided thread and drown
    every real finding beneath it."""
    report = check_symmetry([{"direction": "inbound"}, {"thread_key": "  ", "direction": "inbound"},
                             _m("t1", "inbound"), _m("t1", "outbound")])

    assert report.threads == 1 and report.one_sided == ()


def test_an_unrecognised_direction_is_never_guessed_into_a_side():
    """A stored value this module does not know is UNKNOWN. Coercing it to a side would invent the
    very evidence the check exists to find missing."""
    report = check_symmetry([_m("t1", "INBOUND"), _m("t1", "sent"), _m("t1", None)])

    finding = report.one_sided[0]
    assert (finding.inbound, finding.outbound, finding.unknown) == (1, 0, 2), (
        "'sent' was read as outbound — this check may not know provider dialects")


def test_the_report_is_deterministic_and_sorted():
    """Two runs over one corpus must produce byte-identical output, so a diff between two sweeps
    means something changed rather than that a dict iterated differently."""
    messages = [_m("z", "inbound"), _m("a", "inbound"), _m("m", "outbound")]

    keys = [f.thread_key for f in check_symmetry(messages).one_sided]
    assert keys == sorted(keys) == ["a", "m", "z"]
    assert check_symmetry(messages) == check_symmetry(reversed(messages))


def test_an_empty_corpus_reports_zero_rather_than_dividing_by_it():
    """And zero here means "nothing to say", not "symmetrical" — which is why a caller has to read
    `asymmetry_bp` beside `threads`."""
    report = check_symmetry([])

    assert (report.threads, report.asymmetry_bp) == (0, 0)


def test_the_module_reads_no_clock_and_touches_no_storage():
    """It is handed rows and returns a finding. A check that queried for its own input could not
    be run against a fixture, and the one thing this must survive is being pointed at a corpus
    somebody is worried about."""
    import inspect

    from genios_engine.capture.coverage import symmetry

    source = inspect.getsource(symmetry)
    for forbidden in ("datetime.now", "utcnow", "import requests", "sqlalchemy", "text("):
        assert forbidden not in source, f"`{forbidden}` makes this unrunnable against a fixture"
