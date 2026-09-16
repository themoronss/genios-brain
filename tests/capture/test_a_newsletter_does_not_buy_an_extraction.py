"""L1.6.5 asked BEFORE S2 — the envelope half only, and what it is not allowed to decide.

MEASURED, NOT SUPPOSED. On the pilot org, 102 events that S4 refused with `bulk_headers` had
already cost 522,143 input and 231,725 output tokens — 30% of all extraction input spend — for a
verdict `_has_bulk_headers` reaches from headers alone. The spend was the smaller half: their
claims still entered the conflict lane, and 22 of 66 detected conflicts had one of those senders
on EVERY side. A newsletter disagreeing with a newsletter was holding real situations shut.

The danger in moving a rule earlier is that it decides MORE than it did before. Three of the four
tests below exist to pin what this must NOT do: it must not refuse a known counterparty who mails
through a broadcast platform, it must not answer the service-account rule whose second half S2
has not produced yet, and it must not claim an event is RELEVANT — that is S4's call, made once,
on the full candidate. The fourth pins the call site, because a unit test that never reaches one
is how this branch shipped two dead functions already.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.esqe.relevance import (RULE_BULK_HEADERS, RelevanceCandidate,
                                                  refused_without_extraction)
from genios_engine.contracts.source_event import SourceEvent

NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)
BULK = {"List-Unsubscribe": "<mailto:stop@newsletter.test>", "Precedence": "bulk"}


class _ModelWasCalled(Exception):
    """Raised BY the double, so "did we spend" is a fact about control flow rather than a mock's
    call count — and so the known-counterparty test can assert the model WAS reached."""


class _ModelReached:
    """A model that answers nothing and only reports that it was asked."""

    #: read while the cache key is built, before any call — an envelope skip never gets this far.
    model = "double"

    def call(self, *a, **k):
        raise _ModelWasCalled

    complete = call
    __call__ = call


def _event(sender: str = "news@newsletter.test") -> SourceEvent:
    return SourceEvent(
        event_id="evt_envelope", org_id="org_envelope", connection_id="con_envelope",
        source="gmail", object_type="email_message", source_object_id="msg_1",
        dedup_key="dedup_envelope", occurred_at=NOW,
        actor={"email": sender, "name": "Newsletter", "type": "person"})


def _raw(headers: dict[str, str], sender: str = "news@newsletter.test") -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id="msg_1",
                     occurred_at=NOW, actor_email=sender,
                     raw={"subject": "Your weekly digest",
                          "body": "Renewal due 30 September for $84,000.",
                          "headers": headers})


def _prepared() -> P.PreparedContent:
    return P.PreparedContent(prepared_content_id="prep_1", event_id="evt_envelope",
                             clean_text="Renewal due 30 September for $84,000.", language="en")


def _lane() -> P.SemanticLane:
    return P.SemanticLane(llm=_ModelReached(), eval_time=NOW)


def _run(*, sender_known: bool, headers: dict[str, str], sender: str = "news@newsletter.test"):
    event, raw = _event(sender), _raw(headers, sender)
    return P.run_semantic_lane(
        event, _prepared(), raw, lane=_lane(), is_structured=False, mailbox_owner="me@genios.test",
        envelope=P.envelope_candidate(event, raw.raw, sender_known=sender_known,
                                      is_structured=False))


# =============================================================================================
# (a) the point of the change — the spend does not happen
# =============================================================================================
def test_a_newsletter_does_not_buy_an_extraction():
    """A `List-Unsubscribe` header is a complete verdict. It must cost nothing to reach it."""
    verdict = _run(sender_known=False, headers=BULK)

    assert verdict.skipped == f"{P.ENVELOPE_SKIP_PREFIX}{RULE_BULK_HEADERS}", (
        "the lane extracted an event S4 refuses on its headers alone; the 522,143 input tokens "
        f"this test exists to stop are still being spent — skipped={verdict.skipped!r}")
    assert verdict.result is None, "a skipped lane must not also produce an extraction"
    # `_ModelReached` raises the moment it is asked, so arriving here at all is the saving.


def test_the_skip_is_on_the_trace_and_says_which_rule():
    """A skip that leaves no record is indistinguishable from a lane that was never wired — the
    module's own words. The prefix is what separates "never spent" from "spent, then refused"."""
    recorded: list[tuple] = []

    class _Trace:
        def record(self, stage, action, **fields):
            recorded.append((stage, action, fields.get("reason_code")))

    P._record_semantic(_Trace(), _run(sender_known=False, headers=BULK))

    assert recorded == [(P.SEMANTIC_STAGE, "short_circuit", "envelope_bulk_headers")], recorded


# =============================================================================================
# (b) what it must NOT decide — three ways this goes wrong by deciding too much
# =============================================================================================
def test_a_known_counterparty_keeps_their_extraction():
    """N-12's order is the whole of it: a customer who mails through a broadcast platform is
    still a customer. If the cascade were asked out of order this is the event that is lost."""
    with pytest.raises(_ModelWasCalled):
        _run(sender_known=True, headers=BULK)


def test_the_envelope_does_not_answer_the_rule_that_needs_the_extraction():
    """`service_account_no_claims` has two halves and S2 supplies the second. Asked early with a
    0 it would fire on every machine sender — including the billing system whose invoice carries
    a real amount and a real due date, which is the payables mailbox going dark."""
    machine = RelevanceCandidate(event_id="evt", sender="billing@vendor.test",
                                 typed_claim_count=0, headers={})

    assert refused_without_extraction(machine) is None, (
        "the envelope answered a rule only S2 can answer; a service account with claims would "
        "now never be extracted, so it could never be shown to have them")


def test_the_envelope_never_says_relevant():
    """One question, one answer. `True` is S4's to give, once, on the full candidate — a second
    place that can conclude RELEVANT is two answers to one question."""
    known = RelevanceCandidate(event_id="evt", sender="cfo@customer.test", sender_known=True,
                               headers=BULK)

    assert refused_without_extraction(known) is None
    assert refused_without_extraction(RelevanceCandidate(event_id="evt", headers={})) is None


# =============================================================================================
# (c) the call site — twice on this branch a passing unit test guarded a function nobody called
# =============================================================================================
def test_the_capture_pipeline_actually_builds_the_envelope():
    """`envelope=None` is a safe default, which is exactly why it is a silent one: every test
    above still passes if `capture_event` never supplies it, and nothing anywhere goes red."""
    tree = ast.parse(inspect.getsource(P))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "capture_event")
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "run_semantic_lane"]

    assert calls, "capture_event no longer calls run_semantic_lane at all"
    for call in calls:
        assert any(kw.arg == "envelope" for kw in call.keywords), (
            "capture_event calls run_semantic_lane without `envelope=`, so the skip can never "
            "fire in production no matter what the unit tests above say")


def test_the_only_refusal_an_envelope_can_reach_is_the_bulk_rule():
    """The safety property the probe buys, stated as a test rather than left in a docstring: with
    `typed_claim_count` forced to at least 1, no other refusing rule is reachable."""
    reached = set()
    for known in (True, False):
        for service in ("news@newsletter.test", "noreply@vendor.test", "cfo@customer.test"):
            for headers in (BULK, {}, {"Precedence": "list"}):
                rule = refused_without_extraction(RelevanceCandidate(
                    event_id="evt", sender=service, sender_known=known, headers=headers))
                if rule is not None:
                    reached.add(rule)

    assert reached <= {RULE_BULK_HEADERS}, f"an envelope reached {reached - {RULE_BULK_HEADERS}}"
