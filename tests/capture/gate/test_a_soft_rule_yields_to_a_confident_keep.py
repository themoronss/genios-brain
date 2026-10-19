"""L1 rebuild B1/B2 — a traffic-shape rule is a signal; the junk filter's confident KEEP overrules it.

Measured on production 18 Oct (one org, 755 Gmail): 330 mails were archived by a noise rule and
never read by anything — among them an investor at a VC firm (`N-02`, an ESP's unsubscribe header),
an accelerator's decisions from a no-reply address (`N-03`) and a founder whose mail client stamps
`Auto-Submitted` (`N-01`). The page's junk-filter batch had ASKED about most of them and its answer
was thrown away: S1 archived the mail before S2 could read the verdict.

What these tests pin:
  * a SOFT rule (`rules.SOFT_NOISE`) + a cached KEEP at or above `RESCUE_AT` → the mail is routed;
  * a weaker keep, a drop, or no verdict at all → archived exactly as before;
  * a FINAL rule (SPAM/TRASH, blocklist) is never overruled — and its mail is never even asked;
  * the overrule reads only a verdict already bought — it never buys a call of its own.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.connectors.composio import ComposioGmailConnector
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import (RESCUE_AT, LLMRelevanceClassifier,
                                                  RelevanceVerdict)
from genios_engine.capture.gate.rules import FINAL_NOISE, SOFT_NOISE, final_noise
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace


class _Primed:
    """A classifier whose page batch already answered; `classify` counts any fresh call."""

    def __init__(self, verdict: RelevanceVerdict | None):
        self._v = verdict
        self.fresh_calls = 0

    def verdict_for(self, oid):
        return self._v

    def classify(self, ctx, prepared):
        if self._v is not None:
            return self._v
        self.fresh_calls += 1
        return RelevanceVerdict(True, 0.5, disposition="keep")


def _ctx(raw: dict, email: str) -> GateContext:
    event = SourceEvent(
        event_id="evt_b1", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type="external_contact", email=email),
        occurred_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc))
    text = f"{raw.get('subject', '')}\n\n{raw.get('body', '')}"
    return GateContext(event=event, prepared=preprocess(text, event_id="evt_b1"), raw=raw)


def _gate(raw, email, verdict):
    trace = EventTrace(org_id="o", event_id="evt_b1")
    gate = _Primed(verdict)
    result = run_gate(_ctx(raw, email), trace, relevance=gate)
    return result, trace, gate


#: An investor writing through an ESP: a real person, an unsubscribe header (N-02).
INVESTOR = ({"subject": "Following up on our call", "body": "Happy to take this forward.",
             "headers": {"List-Unsubscribe": "<mailto:u@esp.test>"}, "labelIds": ["INBOX"]},
            "sama@ankurcapital.test")
#: An accelerator's decision from a no-reply address (N-03).
ACCELERATOR = ({"subject": "Your interview", "body": "We would like to invite you.",
                "labelIds": ["INBOX"]}, "no-reply@ycombinator.test")
#: Gmail's Promotions tab (N-06).
PROMO = ({"subject": "Event update", "body": "See you there", "labelIds": ["CATEGORY_PROMOTIONS"]},
         "theresa@antler.test")
SPAM = ({"subject": "Intro", "body": "Hi", "labelIds": ["SPAM"]}, "theresa@antler.test")

KEEP = RelevanceVerdict(True, 0.85, disposition="keep", reason="named person writing")


@pytest.mark.parametrize("case, code", [(INVESTOR, "N-02"), (ACCELERATOR, "N-03"), (PROMO, "N-06")])
def test_a_confident_keep_overrules_a_soft_rule(case, code):
    result, trace, gate = _gate(*case, KEEP)
    assert (result.action, result.route) == ("route", "needs_extraction")
    s1 = next(r for r in trace.records if r.stage == "S1")
    assert s1.action.value == "pass" and s1.detail.get("overruled") == code, (
        "the overruled rule must be countable from the trace")
    assert gate.fresh_calls == 0, "the overrule bought no call of its own"


@pytest.mark.parametrize("verdict", [
    RelevanceVerdict(True, RESCUE_AT - 0.01, disposition="keep"),     # a keep, but not sure enough
    RelevanceVerdict(False, 0.9, disposition="drop"),                  # the filter agrees: junk
    RelevanceVerdict(True, None, disposition="keep"),                  # no score at all
    None,                                                              # never asked
])
def test_anything_short_of_a_confident_keep_leaves_the_rule_standing(verdict):
    result, _trace, gate = _gate(*INVESTOR, verdict)
    assert (result.action, result.reason_code) == ("archive", "N-02")
    assert gate.fresh_calls == 0, "a rule's mail never buys a fresh call at S1"


def test_a_final_rule_is_never_overruled():
    result, _trace, _gate_ = _gate(*SPAM, KEEP)
    assert (result.action, result.reason_code) == ("archive", "N-09")


def test_without_a_classifier_nothing_changes():
    trace = EventTrace(org_id="o", event_id="evt_b1")
    result = run_gate(_ctx(*INVESTOR), trace)
    assert (result.action, result.reason_code) == ("archive", "N-02")


def test_the_two_sets_partition_the_noise_codes():
    from genios_engine.capture.gate.rules import REASON_LABELS
    noise = {c for c in REASON_LABELS if c.startswith("N-")} - {"N-05", "N-10"}
    assert not (FINAL_NOISE & SOFT_NOISE)
    assert noise <= FINAL_NOISE | SOFT_NOISE, noise - (FINAL_NOISE | SOFT_NOISE)


# ── the batch: a FINAL rule's mail is never asked ────────────────────────────────────────────

class _LLM:
    model = "m"

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, prompt, max_tokens=0):
        from types import SimpleNamespace
        self.prompts.append(prompt)
        return SimpleNamespace(ok=False, parsed=None)


def _raw(oid: str, labels: list[str]) -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id=oid,
                     actor_type="human", actor_email="a@b.test",
                     occurred_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                     raw={"subject": f"s {oid}", "snippet": "hello", "labelIds": labels})


def test_spam_and_trash_are_never_sent_to_the_junk_filter():
    llm = _LLM()
    gate = LLMRelevanceClassifier(llm)
    gate.prime([_raw("spam1", ["SPAM"]), _raw("trash1", ["TRASH"])])
    assert llm.prompts == [], "SPAM/TRASH are archived at S1 whatever the model says"
    assert final_noise({"labelIds": ["CATEGORY_PROMOTIONS"]}) is None
    assert final_noise({"sender_blocked": True}) == "N-08"


# ── the connector: a rescued mail is fetched whole ───────────────────────────────────────────

class _Batch:
    """A primed batch: `keep_ids` get a confident keep, the rest a confident drop."""

    def __init__(self, keep_ids, relevance=0.9):
        self.keep_ids, self.rel = set(keep_ids), relevance
        self.primed: list[str] = []

    def prime(self, objects):
        self.primed.extend(o.source_object_id for o in objects)

    def verdict_for(self, oid):
        if oid in self.keep_ids:
            return RelevanceVerdict(True, self.rel, disposition="keep")
        return RelevanceVerdict(False, 0.05, disposition="drop")


class _Gmail(ComposioGmailConnector):
    def __init__(self, relevance):
        self._ocr = None
        self._relevance = relevance
        self._account = None
        self.full_fetches: list[str] = []

    def _full_message(self, mid):
        self.full_fetches.append(mid)
        return {"id": mid, "from": "sama@ankurcapital.test", "subject": "s",
                "messageText": "full body"}


def _entry(mid: str, labels: list[str]) -> dict:
    return {"id": mid, "from": "sama@ankurcapital.test", "subject": "s", "messageText": "snip",
            "labelIds": labels}


def test_a_promotions_mail_the_filter_keeps_is_fetched_whole():
    batch = _Batch(keep_ids={"p1"})
    conn = _Gmail(batch)
    conn._to_batch({"data": {"messages": [_entry("p1", ["CATEGORY_PROMOTIONS"]),
                                          _entry("p2", ["CATEGORY_PROMOTIONS"]),
                                          _entry("s1", ["SPAM"])]}})
    assert conn.full_fetches == ["p1"], "only the rescued promotions mail pays for its body"
    assert set(batch.primed) == {"p1", "p2"}, "SPAM is never asked; soft-rule mail is asked once"


def test_a_weak_keep_does_not_buy_the_body():
    batch = _Batch(keep_ids={"p1"}, relevance=RESCUE_AT - 0.05)
    conn = _Gmail(batch)
    conn._to_batch({"data": {"messages": [_entry("p1", ["CATEGORY_PROMOTIONS"])]}})
    assert conn.full_fetches == []
