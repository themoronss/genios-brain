"""STEP-03 · the gate never deletes a mail — what a rule or the model calls noise is ARCHIVED, with its code.

    pytest tests/capture/gate/test_the_gate_never_deletes_mail.py -q

`capture/gate/gate.run_gate` (tree `yc2_w27_s03/M21.C2.L-logic.V1.U01`). Every noise rule was a drop and a
drop kept no body: on the golden set 33 of 86 mails — Boardy's introductions (N-02), the government
portal's updates (N-06, N-03), a bounce (N-03) — were gone for good. The Atlas, RULE 04: uncertainty
routes, it never deletes.

One mutation per rule: each N-code, the empty mail (N-10) and the model's confident junk (`llm_junk`)
lands as `archive` with its code, in the result and in the trace. What does not change: a whitelist
still bypasses the noise rules, the model's unconfident junk still parks, an unreadable attachment
still parks, and S0 `out_of_scope` — a scope exclusion, not a judgment about the mail — still drops.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace


def _event(email: str = "person@realco.test") -> SourceEvent:
    return SourceEvent(
        event_id="evt_g", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type="external_contact", email=email),
        occurred_at=datetime(2026, 10, 6, tzinfo=timezone.utc))


def _run(raw: dict, *, email: str = "person@realco.test", relevance=None, **ctx):
    trace = EventTrace(org_id="o", event_id="evt_g")
    result = run_gate(GateContext(event=_event(email), raw=raw, **ctx), trace,
                      relevance=relevance)
    return result, trace.records[-1]


_BODY = {"subject": "Intro: Pankaj, meet the founder", "snippet": "Happy to connect you both."}


@pytest.mark.parametrize("code, raw, email", [
    ("N-09", {**_BODY, "labelIds": ["SPAM"]}, "person@realco.test"),
    ("N-08", {**_BODY, "sender_blocked": True}, "person@realco.test"),
    ("N-06", {**_BODY, "labelIds": ["CATEGORY_PROMOTIONS"]}, "updates@portal.test"),
    ("N-07", {**_BODY, "labelIds": ["CATEGORY_SOCIAL"]}, "person@realco.test"),
    ("N-01", {**_BODY, "headers": {"Auto-Submitted": "auto-generated"}}, "person@realco.test"),
    ("N-03", _BODY, "no-reply@portal.test"),
    ("N-04", {**_BODY, "headers": {"Precedence": "bulk"}}, "person@realco.test"),
    ("N-02", {**_BODY, "headers": {"List-Unsubscribe": "<mailto:u@boardy.test>"}},
     "intros@boardy.test"),
])
def test_every_noise_rule_archives_and_names_itself(code, raw, email):
    result, last = _run(raw, email=email)
    assert (result.action, result.reason_code) == ("archive", code)
    assert (last.stage, last.action.value, last.reason_code) == ("S1", "archive", code)


def test_an_empty_mail_is_archived_not_deleted():
    result, last = _run({"subject": "Re:", "snippet": ""})
    assert (result.action, result.reason_code) == ("archive", "N-10")
    assert last.action.value == "archive"


class _Junk:
    def __init__(self, relevance: float) -> None:
        self.relevance = relevance

    def classify(self, ctx, prepared):
        return RelevanceVerdict(False, self.relevance, disposition="drop", reason="marketing")


def test_the_models_confident_junk_is_archived_with_its_reason():
    result, last = _run(_BODY, relevance=_Junk(0.1))
    assert (result.action, result.reason_code) == ("archive", "llm_junk")
    assert (last.stage, last.action.value, last.detail.get("reason")) == ("S2", "archive",
                                                                          "marketing")


def test_the_models_unconfident_junk_still_parks():
    result, _ = _run(_BODY, relevance=_Junk(0.4))
    assert (result.action, result.reason_code) == ("park", "llm_junk_unconfident")


def test_a_known_sender_still_bypasses_the_noise_rules():
    result, _ = _run({**_BODY, "headers": {"List-Unsubscribe": "<mailto:u@boardy.test>"}},
                     email="intros@boardy.test", sender_known=True)
    assert result.action == "route" and result.whitelist_code == "W-01"


def test_an_unreadable_attachment_still_parks():
    result, _ = _run({**_BODY, "document": {"status": "fetch_failed"}})
    assert (result.action, result.reason_code) == ("park", "DOC-05")


def test_out_of_scope_is_a_scope_exclusion_and_still_drops():
    result, last = _run(_BODY, in_scope=False)
    assert (result.action, result.reason_code) == ("drop", "out_of_scope")
    assert last.action.value == "drop"


def test_nothing_the_gate_returns_for_mail_is_a_drop_except_scope():
    """⛔ The sweep of the whole rule table: no input above but S0 produces `drop`."""
    for raw, email, kw in [({**_BODY, "labelIds": ["TRASH"]}, "a@b.test", {}),
                           ({**_BODY, "headers": {"List-Id": "x"}}, "a@b.test", {}),
                           ({**_BODY, "headers": {"Feedback-ID": "x"}}, "a@b.test", {}),
                           (_BODY, "mailer-daemon@b.test", {})]:
        result, _ = _run(raw, email=email, **kw)
        assert result.action == "archive", (raw, result)
