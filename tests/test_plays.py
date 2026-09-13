"""P6 §3.2 plays (frozen): strict validation, the words a human approves, the frozen request bytes,
the producers' delegate action — and the act lane's own retry ladder (hermetic, no database)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from genios_engine.deliver import outbox as OB
from genios_engine.deliver.channels.base import ChannelResult
from genios_engine.executive import plays as P

RES, RA, FU = P.PLAY_RESCHEDULE, P.PLAY_REASSIGN, P.PLAY_FOLLOW_UP
W = {"start": "2026-09-15T10:00:00Z", "end": "2026-09-15T10:30:00Z"}


def resched(**over) -> dict:
    p = {"meeting_ref": {"provider": "google", "event_id": "evt_1"}, "attendees": ["a@x.com"],
         "current_start": "2026-09-14T10:00:00+05:30", "proposed_windows": [W],
         "message_draft": "Could we move?", "timezone": "Asia/Kolkata"}
    p.update(over)
    return p


VALID = {
    RES: resched(),
    RA: {"task_ref": {"provider": "linear", "id": "LIN-42"}, "from_seat_email": "ani@v.test",
         "to_seat_email": "sha@v.test", "note": ""},
    FU: {"thread_ref": {"provider": "gmail", "thread_id": "t_1"}, "to": ["priya@acme.test"],
         "subject": "Re: pack", "body_draft": "Hi Priya — update.", "send": False},
}


@pytest.mark.parametrize("use_js", [False, True])
@pytest.mark.parametrize("play", sorted(P.PLAYS))
def test_valid_params_pass(play, use_js):
    assert P.validate(play, VALID[play], use_jsonschema=use_js) == []


BAD = [
    (RES, resched(extra=1), "unknown field"),
    (RES, resched(meeting_ref={"provider": "google", "event_id": "e", "x": 1}), "unknown field"),
    (RES, resched(proposed_windows=[]), "at least"),
    (RES, resched(proposed_windows=[W, W, W, W]), "at most"),
    (RES, resched(meeting_ref={"provider": "zoom", "event_id": "e"}), "one of"),
    (RES, resched(current_start="tomorrow"), "date-time"),
    (RES, resched(current_start="2026-09-14T10:00:00"), "offset"),
    (RES, resched(attendees=["not-an-email"]), "email"),
    (RES, resched(timezone="Mars/Olympus"), "IANA"),
    (RES, resched(proposed_windows=[{"start": W["end"], "end": W["start"]}]), "after start"),
    (RES, {k: v for k, v in resched().items() if k != "timezone"}, "required"),
    (RES, resched(message_draft="   "), "too short"),
    (FU, {**VALID[FU], "send": True}, "must be false"),
    (FU, {**VALID[FU], "send": 0}, "expected boolean"),
    (FU, {**VALID[FU], "thread_ref": {"provider": "yahoo", "thread_id": "t"}}, "one of"),
    (FU, {**VALID[FU], "to": []}, "at least"),
    (RA, {**VALID[RA], "to_seat_email": "ANI@v.test"}, "differ"),
    (RA, {**VALID[RA], "note": 5}, "expected string"),
    (RA, "not a dict", "expected object"),
    ("email.delete_everything", {}, "unknown play"),
]


@pytest.mark.parametrize("play,params,needle", BAD)
def test_invalid_params_are_refused_by_the_built_in_check(play, params, needle):
    """Production runs this path (jsonschema is a dev-only dependency)."""
    errors = P.validate(play, params, use_jsonschema=False)
    assert errors and any(needle in e for e in errors), errors


@pytest.mark.parametrize("play,params,needle", BAD)
def test_jsonschema_never_loosens_the_check(play, params, needle):
    assert P.validate(play, params, use_jsonschema=True)


def test_instruction_names_only_what_params_carry():
    text_ = P.instruction(RES, VALID[RES])
    for part in ("evt_1", "google", W["start"], "Asia/Kolkata", "Could we move?", "a@x.com"):
        assert part in text_
    assert "do not send" in P.instruction(FU, VALID[FU]).lower()
    assert "LIN-42" in P.instruction(RA, VALID[RA]) and "sha@v.test" in P.instruction(RA, VALID[RA])


def test_request_bytes_are_frozen_in_the_pinned_field_order():
    kw = dict(delegation_id="dlg_1", org_id="org_1", agent_id="hermes", play=RES,
              params=VALID[RES], context={"moment_id": "mom_1", "headline": "Acme in 15 min",
                                          "evidence": [{"node_id": "n", "field": "f"}]},
              approved_by="a@x.com", approved_at=datetime(2026, 9, 13, 9, tzinfo=timezone.utc),
              expires_at=datetime(2026, 9, 14, 9, tzinfo=timezone.utc),
              result_url="https://api.test/v1/delegations/dlg_1/result")
    body = P.request_body(P.request_document(**kw))
    assert body == P.request_body(P.request_document(**kw))          # deterministic bytes
    doc = json.loads(body)
    assert list(doc) == ["type", "version", "delegation_id", "org_id", "agent_id", "play",
                         "params", "context", "approved_by", "approved_at", "expires_at",
                         "result_url"]
    assert doc["type"] == "action.requested" and doc["version"] == 1
    assert doc["context"] == {"moment_id": "mom_1", "card_id": None,
                              "headline": "Acme in 15 min",
                              "evidence": [{"node_id": "n", "field": "f"}]}
    assert doc["approved_at"] == "2026-09-13T09:00:00.000Z"
    body.decode("ascii")
    assert len(P.body_sha256(body)) == 64


def test_reschedule_windows_are_the_next_weekdays_same_time_and_length():
    fri = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)          # a Friday
    out = P.reschedule_windows(fri, fri.replace(hour=11), now=fri)
    assert out == [{"start": "2026-09-21T10:00:00.000Z", "end": "2026-09-21T11:00:00.000Z"},
                   {"start": "2026-09-22T10:00:00.000Z", "end": "2026-09-22T11:00:00.000Z"}]
    assert P.validate(RES, resched(proposed_windows=out)) == []


def test_delegate_action_only_for_a_valid_request_with_an_agent():
    act = P.delegate_action(RES, VALID[RES], "hermes")
    assert act == {"id": "delegate", "label": "Ask my agent",
                   "payload": {"play": RES, "params": VALID[RES], "agent_id": "hermes"}}
    assert P.delegate_action(RES, VALID[RES], None) is None
    assert P.delegate_action(RES, resched(extra=1), "hermes") is None


def test_the_act_lane_has_its_own_short_ladder_and_cards_keep_theirs():
    assert [OB.act_retry_delay(n) for n in range(1, 6)] == [10, 30, 120, 600, None]
    assert OB.act_retry_delay(0) is None
    assert OB.BACKOFF_MINUTES == (5, 30, 120, 720)          # the card ladder is untouched
    assert sum(OB.ACT_BACKOFF_SECONDS) < 24 * 3600          # gives up inside the approval window


@pytest.mark.parametrize("res,expected", [
    (True, (True, False, "")),
    (False, (False, False, "agent webhook refused the request")),
    (ChannelResult(ok=True), (True, False, "")),
    (ChannelResult(ok=False, detail="503"), (False, False, "503")),
    ({"ok": False, "error": "timeout"}, (False, False, "timeout")),
    ({"ok": False, "status": "parked", "detail": "egress refused"}, (False, True, "egress refused")),
    ({"ok": True, "parked": True}, (False, True, "")),
])
def test_any_send_action_outcome_shape_is_understood(res, expected):
    assert OB._action_outcome(res) == expected
