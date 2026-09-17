"""Fifty meetings, zero situations — the reading that was declared and never written.

WHAT WAS ALREADY TRUE BEFORE THIS UNIT. `domain_spec.py:553` declares `meeting_follow_through`
in full, field by field, with each field's meaning written out. Three of its four facts have
writers today: `meeting.start_at` and `meeting.status` from `capture/structured/registry.py`,
`meeting.external_counterparty` from `context/meeting_lifecycle.py`. `calendar.py` fetches with
`showDeleted` precisely "so a cancellation is an event we RECEIVE", and `meeting_touch._MEETINGS`
already joins the attendance edge correctly — a query whose comments record three separate bugs
found and fixed in it.

WHAT WAS MISSING. `outreach_situations.READINGS` has six entries and `meeting` is not one of
them. Sales has its own meeting reading (`refresh_channel_touch_situations`, `channel_touch`);
Admin — the only domain this tenant switched on — never got one. So fifty calendar events
produced facts, nodes and edges, and not one situation. Nothing downstream could route on a
meeting because there was nothing to route.

THE ONE CLAIM THIS READING MAY NOT MAKE. `meeting.recap_sent` has NO writer anywhere, and
`domain_spec` says why in its own comment: "an outbound after a meeting is not necessarily a
recap of it — so a card can say the follow-up is not visible and never that it was not sent."
Every finding here therefore declares `meeting.recap_sent` missing rather than inferring it from
the absence of a later message. A card built on this may say "no follow-up is visible"; it may
never say "you did not follow up".
"""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")

from genios_engine.context.meeting_situations import (  # noqa: E402
    read_meeting_follow_through,
)

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


def _meeting(**over) -> dict:
    row = {"node_id": "mtg_1", "display_name": "Intro: Neon Fund & Rohit",
           "start_at": (NOW - timedelta(days=18)).isoformat(),
           "status": "confirmed", "counterparties": ["siddhant@neon.fund"]}
    row.update(over)
    return row


def _facts(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


# ── a cancelled meeting that was never rebooked ───────────────────────────────────────────────

def test_a_cancelled_meeting_that_was_never_rebooked_is_a_finding():
    """Item 8, stated directly: 'the Neon Fund meeting was cancelled and never rebooked.'"""
    [finding] = read_meeting_follow_through([_meeting(status="cancelled")], NOW)

    facts = _facts(finding)
    assert facts["meeting.status"] == "cancelled"
    assert facts["meeting.rebooked"] is False
    assert facts["meeting.external_counterparty"] == "siddhant@neon.fund"


def test_a_cancelled_meeting_with_a_later_one_for_the_same_counterparty_is_not_a_finding():
    """Rebooked is the resolution. Reporting it would be a card about something already handled."""
    assert read_meeting_follow_through([
        _meeting(node_id="mtg_1", status="cancelled"),
        _meeting(node_id="mtg_2", start_at=(NOW + timedelta(days=3)).isoformat()),
    ], NOW) == []


def test_a_later_meeting_with_a_DIFFERENT_counterparty_does_not_count_as_rebooked():
    """Meeting somebody else is not rebooking this."""
    [finding] = read_meeting_follow_through([
        _meeting(node_id="mtg_1", status="cancelled"),
        _meeting(node_id="mtg_2", start_at=(NOW + timedelta(days=3)).isoformat(),
                 counterparties=["someone@else.com"]),
    ], NOW)
    assert _facts(finding)["meeting.rebooked"] is False


# ── a meeting that happened, with nothing visible after it ────────────────────────────────────

def test_a_past_meeting_is_reported_with_its_elapsed_days():
    [finding] = read_meeting_follow_through([_meeting()], NOW)
    assert _facts(finding)["meeting.days_since"] == 18


def test_a_future_meeting_is_not_a_follow_through_question_yet():
    """Nothing has happened, so there is nothing to have followed through on."""
    assert read_meeting_follow_through(
        [_meeting(start_at=(NOW + timedelta(days=4)).isoformat())], NOW) == []


# ── the claim it may never make ───────────────────────────────────────────────────────────────

def test_every_finding_declares_the_recap_it_cannot_see():
    """`meeting.recap_sent` has no writer. Absence of a recap fact is not evidence of no recap."""
    for finding in read_meeting_follow_through([_meeting(), _meeting(
            node_id="mtg_9", status="cancelled", counterparties=["x@y.com"])], NOW):
        assert "meeting.recap_sent" in finding.missing
        assert "meeting.recap_sent" not in _facts(finding)


# ── refusals ──────────────────────────────────────────────────────────────────────────────────

def test_a_meeting_with_no_external_counterparty_yields_nothing():
    """An internal calendar block is not an outside commitment."""
    assert read_meeting_follow_through([_meeting(counterparties=[])], NOW) == []


def test_a_meeting_with_no_start_time_yields_nothing():
    """Without a date there is no elapsed time and no claim to make."""
    assert read_meeting_follow_through([_meeting(start_at=None)], NOW) == []


def test_each_meeting_is_its_own_finding_keyed_on_its_own_node():
    findings = read_meeting_follow_through([
        _meeting(node_id="mtg_1"),
        _meeting(node_id="mtg_2", counterparties=["piyush@3one4capital.com"]),
    ], NOW)
    assert len(findings) == 2
    assert {f.canonical_key for f in findings} == {"meeting:mtg_1", "meeting:mtg_2"}
    assert all(f.anchor == "meeting" for f in findings)
