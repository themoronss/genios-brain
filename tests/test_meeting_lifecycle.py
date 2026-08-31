"""`meeting.status` was answering five separate questions at once.

`packs/general_v1`'s `meeting_no_followup` read it as though it answered all five:

    meeting.status = 'confirmed' AND hours_since(start_at) >= 24 AND no_obs followup_sent
      → "send a recap"

`confirmed` is an INVITATION state. Google sets it the moment the event exists and it survives
the meeting happening, so the rule asked "did this end with somebody waiting on me" and was told
"the event was not cancelled".

Live consequence on the design partner's real calendar: three cards told the founder to send a
recap of cohort workshops he attended as one participant among twenty — `[Session] Building Your
MVP | Launchpad 30`, `[Session] Early Finance AMA | Launchpad 30`, `[Session] Building Early
Metrics Stack`. A recap to that room is not merely useless; the recipient list discloses the
cohort to the cohort. Replay 05's assertion 3 forbids exactly this aliasing.
"""
from datetime import datetime, timezone

from genios_engine.context.meeting_lifecycle import BROADCAST_ATTENDEES, reduce_meeting

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)
INTERNAL = {"rohit@genios.com"}


def _meeting(**kw):
    base = dict(status="confirmed", start_at="2026-06-23T11:00:00+05:30",
                end_at="2026-06-23T11:45:00+05:30", attendees=["rohit@genios.com"],
                organizer="rohit@genios.com", internal=INTERNAL, now=NOW)
    return reduce_meeting(**{**base, **kw})


def test_a_cohort_workshop_is_not_an_open_loop():
    """The live bug, exactly. Everyone external in that room is a fellow participant, not a
    person on the other side of anything."""
    m = _meeting(attendees=[f"founder{i}@antler.co" for i in range(20)],
                 organizer="deepthi@antler.co")
    assert m["meeting.occurred"] is True          # it did happen …
    assert m["meeting.external_counterparty"] is False   # … with nobody to follow up WITH
    assert m["meeting.open_loop"] is False
    assert m["meeting.shape"] == "broadcast"


def test_a_one_to_one_with_a_buyer_is_an_open_loop():
    m = _meeting(attendees=["rohit@genios.com", "buyer@acme.com"])
    assert m["meeting.external_counterparty"] is True
    assert m["meeting.open_loop"] is True
    assert m["meeting.shape"] == "one_to_one"


def test_confirmed_does_not_mean_it_happened():
    """The whole defect in one assertion: an event scheduled for next month is `confirmed` now."""
    m = _meeting(start_at="2026-12-01T11:00:00+00:00", end_at="2026-12-01T12:00:00+00:00",
                 attendees=["rohit@genios.com", "buyer@acme.com"])
    assert m["meeting.scheduled"] is True
    assert m["meeting.occurred"] is False
    assert m["meeting.open_loop"] is False


def test_a_cancelled_meeting_is_neither_scheduled_nor_occurred():
    m = _meeting(status="cancelled", attendees=["rohit@genios.com", "buyer@acme.com"])
    assert m["meeting.scheduled"] is False
    assert m["meeting.occurred"] is False


def test_attendance_is_unknown_not_false_when_we_have_no_evidence():
    """Google's `confirmed` is set on the EVENT, not on the person, so it can never distinguish
    "he was there" from "he was invited". `False` would read as "he skipped it", which is a
    claim about the founder we have no basis for."""
    m = _meeting(attendees=["rohit@genios.com", "buyer@acme.com"], organizer="buyer@acme.com")
    assert m["meeting.attended"] is None


def test_you_do_not_miss_the_meeting_you_called():
    m = _meeting(attendees=["rohit@genios.com", "buyer@acme.com"], organizer="rohit@genios.com")
    assert m["meeting.attended"] is True


def test_a_followed_up_meeting_closes_its_own_loop():
    m = _meeting(attendees=["rohit@genios.com", "buyer@acme.com"], followed_up=True)
    assert m["meeting.open_loop"] is False


def test_the_broadcast_threshold_is_named_not_buried():
    assert BROADCAST_ATTENDEES >= 3
    m = _meeting(attendees=[f"p{i}@acme.com" for i in range(BROADCAST_ATTENDEES + 1)])
    assert m["meeting.external_counterparty"] is False


def test_the_rule_no_longer_reads_meeting_status():
    """A rule that can still reach `meeting.status` can still alias it."""
    from genios_engine.packs.general_v1 import GENERAL_V1

    rule = next(r for r in GENERAL_V1["rules"] if r["id"] == "meeting_no_followup")
    paths = {c.get("path") for c in rule["when"]}
    assert "meeting.status" not in paths
    assert "meeting.open_loop" in paths
    # and the clock is the meeting's END, not its start
    assert rule["urgency"]["path"] == "meeting.end_at"


# ── a card expiring is not a request being answered ─────────────────────────────
def test_a_subject_with_no_new_evidence_does_not_get_the_same_signal_again():
    """Card expiry is a DISPLAY lifecycle. It says the surface stopped showing something and
    says nothing about whether the underlying request was ever answered.

    Live: `boardy@boardy.ai` holds `unanswered_email` twice (one expired, one open) and
    `commitment_overdue` twice; the identical expired/reopened pairing recurs for eleven other
    subjects. HEAD commit b739bd5 is titled "Let a signal get a fresh card once its old one
    expires" — the resurfacing was intentional, and it is why the founder kept being shown
    threads he had already dealt with.
    """
    from datetime import timedelta

    from genios_engine.reason.engine import NodeContext
    from genios_engine.reason.runner import _newest_evidence_at

    stale = NOW - timedelta(days=10)
    ctx = NodeContext(node_id="n1", node_type="person",
                      facts={"thread.last_inbound": {"value": "x", "occurred_at": stale}},
                      obs=[{"kind": "question", "occurred_at": stale}])
    assert _newest_evidence_at(ctx) == stale
    # the prior signal is NEWER than every piece of evidence → re-emitting would repeat itself
    assert _newest_evidence_at(ctx) <= NOW


def test_a_reply_arriving_after_the_signal_does_reopen_it():
    """The guard must not freeze a subject forever — new evidence is exactly what makes a fresh
    judgment a judgment rather than a repeat."""
    from datetime import timedelta

    from genios_engine.reason.engine import NodeContext
    from genios_engine.reason.runner import _newest_evidence_at

    fresh = NOW + timedelta(days=1)
    ctx = NodeContext(node_id="n1", node_type="person",
                      facts={"thread.last_inbound": {"value": "x", "occurred_at": fresh}}, obs=[])
    assert _newest_evidence_at(ctx) == fresh


def test_a_subject_with_no_timestamps_at_all_is_not_re_emitted():
    """Absence of evidence is not evidence of change. `None` must fail closed."""
    from genios_engine.reason.engine import NodeContext
    from genios_engine.reason.runner import _newest_evidence_at

    assert _newest_evidence_at(NodeContext(node_id="n1", node_type="person")) is None


# ── a cancellation is an event we RECEIVE, not an absence we infer ──────────────
def test_a_cancelled_calendar_stub_still_lands_as_an_event():
    """`showDeleted=True` makes Google return cancellations — often as bare stubs (id + status +
    updated, no summary or start). The connector must land that stub rather than choke: its new
    `updated` re-keys the dedup, the mapping writes meeting.status='cancelled', and the reducer
    turns that into scheduled=False — so the rule that would have said "send a recap" goes
    quiet. This is the calendar half of the revocation path, working by composition."""
    from genios_engine.capture.connectors.calendar import ComposioCalendarConnector

    stub = {"id": "ev_cancelled", "status": "cancelled",
            "updated": "2026-08-20T10:00:00Z"}
    raw = ComposioCalendarConnector.__new__(ComposioCalendarConnector)._to_raw(stub)
    assert raw is not None
    assert raw.raw["status"] == "cancelled"
    assert raw.content_version == "2026-08-20T10:00:00Z"   # the cancellation re-lands
    assert raw.occurred_at is not None                     # falls back to `updated`


def test_a_cancelled_meeting_can_never_carry_an_open_loop():
    m = reduce_meeting(status="cancelled", start_at="2026-06-23T11:00:00+05:30",
                       end_at="2026-06-23T11:45:00+05:30",
                       attendees=["rohit@genios.com", "buyer@acme.com"],
                       organizer="rohit@genios.com", internal=INTERNAL, now=NOW)
    assert m["meeting.scheduled"] is False
    assert m["meeting.open_loop"] is False
