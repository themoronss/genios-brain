from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace


def _event(email: str, actor_type: str = "external_contact") -> SourceEvent:
    return SourceEvent(
        event_id="evt_x", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type=actor_type, email=email), occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )


def _trace() -> EventTrace:
    return EventTrace(org_id="o", event_id="evt_x")


def test_business_email_routes_to_extraction():
    ctx = GateContext(event=_event("priya@acme.com"),
                      raw={"subject": "Revised contract",
                           "snippet": "Can you send the contract by Friday?"})
    tr = _trace()
    res = run_gate(ctx, tr)
    assert res.action == "route" and res.route == "needs_extraction"
    assert [r.stage for r in tr.records] == ["S0", "S1", "S2"]


class _DropClassifier:
    """Stub S2 LLM junk-gate that drops (stands in for the real LLM in a hermetic test)."""

    def classify(self, ctx, prepared):
        from genios_engine.capture.gate.relevance import RelevanceVerdict
        return RelevanceVerdict(False, 0.1, disposition="drop", reason="marketing")


def test_dead_sender_dropped_at_s1():
    # bounce / mailer-daemon carries no business signal ever → still a hard S1 drop (N-03).
    ctx = GateContext(event=_event("mailer-daemon@newsletter.com"),
                      raw={"subject": "Delivery failed", "snippet": "..."})
    tr = _trace()
    res = run_gate(ctx, tr)
    assert res.action == "drop" and res.reason_code == "N-03"
    assert tr.records[-1].stage == "S1" and tr.records[-1].action.value == "drop"


def test_plain_no_reply_dropped_at_s1():
    # DESIGN CHANGE (rules-first junk removal): a no-reply/newsletter sender with NO attachment is
    # now deterministically dropped at S1 (N-03), so obvious bulk mail never costs an S2 LLM gate
    # call. The old concern — a receipt/invoice also comes from noreply@ — is preserved by the
    # has_attachment exemption (see test_no_reply_with_attachment_survives_s1), not by sending every
    # no-reply to the LLM.
    ctx = GateContext(event=_event("no-reply@newsletter.com"),
                      raw={"subject": "Weekly digest", "snippet": "..."})
    res = run_gate(ctx, _trace())
    assert res.action == "drop" and res.reason_code == "N-03"


def test_no_reply_with_attachment_survives_s1():
    # A receipt/invoice from noreply@ carries a PDF → has_attachment exempts it from the N-03 drop,
    # so it routes on to relevance/L2 rather than being lost. This is the invoice-safety guarantee.
    ctx = GateContext(event=_event("no-reply@vendor.com"),
                      raw={"subject": "Invoice #221", "snippet": "Amount due by Friday",
                           "has_attachment": True})
    res = run_gate(ctx, _trace())
    assert res.action == "route"


def test_llm_gate_drops_marketing_at_s2():
    # The S2 LLM junk-gate is the one filter allowed to drop on JUDGMENT. Use a NON-automated sender
    # so it passes S1's deterministic rules and actually reaches S2 (an automated no-reply sender is
    # now dropped at S1 by N-03 before the LLM ever runs).
    ctx = GateContext(event=_event("sales@brightco.com"),
                      raw={"subject": "Sale!", "snippet": "50% off this week"})
    tr = _trace()
    res = run_gate(ctx, tr, relevance=_DropClassifier())
    assert res.action == "drop" and res.reason_code == "llm_junk"
    assert tr.records[-1].stage == "S2"


def test_known_sender_bypasses_bulk_drop():
    # bulk marker present, but sender is known → whitelist W-01 bypasses the drop
    ctx = GateContext(event=_event("news@acme.com"), sender_known=True,
                      raw={"subject": "Product update",
                           "headers": {"List-Unsubscribe": "<mailto:u@acme.com>"},
                           "snippet": "New feature launched."})
    res = run_gate(ctx, _trace())
    assert res.action == "route"


def test_structured_event_with_mapping_short_circuits():
    ev = SourceEvent(
        event_id="evt_d", org_id="o", connection_id="c", source="hubspot",
        object_type="deal", source_object_id="deal_1", dedup_key="hubspot:deal:deal_1",
        actor=Actor(type="system"), occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    tr = _trace()
    # A real HubSpot deal carries `updatedAt`; the registry declares the source mutable, so a
    # fixture without one is asserting a state that in production means "this deal will freeze
    # at its first-seen stage".
    res = run_gate(GateContext(event=ev, is_structured=True,
                               content_version="2026-07-28T09:00:00Z"), tr)
    assert res.action == "short_circuit" and res.route == "structured"
    assert tr.records[-1].reason_code == "structured_mapped"


def test_unknown_structured_type_parks_for_mapping_review():
    ev = SourceEvent(
        event_id="evt_u", org_id="o", connection_id="c", source="weirdapp",
        object_type="thing", source_object_id="t1", dedup_key="weirdapp:thing:t1",
        actor=Actor(type="system"), occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    tr = _trace()
    res = run_gate(GateContext(event=ev, is_structured=True), tr)
    assert res.action == "park" and res.reason_code == "visibility_unknown"


class _Verdict:
    """Minimal stand-in for a classifier so the gate's own arithmetic is what is under test."""

    def __init__(self, disposition, relevance):
        self._d, self._r = disposition, relevance

    def classify(self, _ctx, _prepared):
        from genios_engine.capture.gate.relevance import RelevanceVerdict
        return RelevanceVerdict(self._d == "keep", self._r, disposition=self._d, reason="stub")


def test_a_whitelisted_sender_cannot_skip_the_document_park():
    """A whitelist says the SENDER matters. It must never answer "can we read this?".

    The whitelist short-circuited the whole hard-rule block, and the document park lived inside
    it — so an unreadable contract or deck PDF from a KNOWN investor, the highest-value
    attachment class there is, was emitted with an empty body while the same file from a
    stranger was correctly parked. 108 attachment events landed this way.
    """
    ctx = GateContext(event=_event("partner@vc.com"),
                      raw={"subject": "Term sheet", "has_attachment": True,
                           "labelIds": ["STARRED"],            # → W-02
                           "document": {"status": "unsupported"}})
    res = run_gate(ctx, _trace())
    assert res.action == "park" and res.reason_code == "DOC-02"


def test_a_whitelisted_sender_still_bypasses_noise_rules():
    """The split must not cost the whitelist its actual job."""
    ctx = GateContext(event=_event("partner@vc.com"),
                      raw={"subject": "Fund update", "snippet": "Our Q3 letter is attached.",
                           "labelIds": ["STARRED", "CATEGORY_PROMOTIONS"]})   # N-06 without W-02
    res = run_gate(ctx, _trace())
    assert res.action == "route", "a starred sender's mail must survive a PROMOTIONS label"


def test_an_unconfident_junk_verdict_parks_instead_of_deleting():
    """`disposition` alone must not authorise an irreversible delete.

    The gate branched on disposition and never compared `relevance` to any threshold, so 109
    emails were deleted with no body retained — 33 of them at exactly the parse default, i.e.
    the model had returned no score at all. An investor on an unfamiliar domain is precisely
    the case a junk gate gets wrong.
    """
    ctx = GateContext(event=_event("stranger@unknownvc.com"),
                      raw={"subject": "Following up", "snippet": "Loved the deck, let's talk."})
    res = run_gate(ctx, _trace(), relevance=_Verdict("drop", 0.45))
    assert res.action == "park" and res.reason_code == "llm_junk_unconfident"


def test_a_confident_junk_verdict_still_drops():
    """The threshold must not turn the junk gate off."""
    ctx = GateContext(event=_event("promo@newsletter.io"),
                      raw={"subject": "50% off", "snippet": "Limited time offer!"})
    res = run_gate(ctx, _trace(), relevance=_Verdict("drop", 0.02))
    assert res.action == "drop" and res.reason_code == "llm_junk"


def test_a_missing_relevance_score_never_authorises_a_delete():
    """Silence from the model is not evidence of junk."""
    from genios_engine.capture.gate.relevance import _verdict_from

    v = _verdict_from({"disposition": "drop"})            # no `relevance` key at all
    assert v.reason == "no_relevance_returned"
    ctx = GateContext(event=_event("stranger@unknownvc.com"),
                      raw={"subject": "Intro", "snippet": "Connecting you two."})

    class _AsParsed:
        def classify(self, _c, _p):
            return v

    res = run_gate(ctx, _trace(), relevance=_AsParsed())
    assert res.action == "park", "an absent score must park, never delete"


def test_a_changing_object_with_no_version_is_parked_not_frozen():
    """A mutable object with no version stamp is undedupable, and the failure is total.

    The dedup ledger answers "already seen" on every later sync, so the object freezes at
    whatever state it happened to be in the first time — a HubSpot deal stuck at its first-seen
    stage reports a pipeline that stopped moving the day it was connected, with every generic
    test still green because gmail (immutable) is what the tests exercise.
    """
    from genios_engine.capture.gate.gate import run_gate

    ctx = GateContext(event=_event("crm@vendor.com"), raw={"stage": "won"}, is_structured=True)
    object.__setattr__(ctx.event, "source", "hubspot") if False else None
    ev = _event("crm@vendor.com").model_copy(update={"source": "hubspot", "object_type": "deal"})
    res = run_gate(GateContext(event=ev, raw={"stage": "won"}, is_structured=True), _trace())
    assert res.action == "park" and res.reason_code == "MUT-01"


def test_the_versionability_check_runs_before_the_structured_short_circuit():
    """Ordering IS the fix. Every source this rule exists for is structured.

    Placed after S1.5, the check could never fire for calendar, HubSpot or the client database —
    correct and unreachable, which is the same as absent but harder to notice.
    """
    from genios_engine.capture.gate.gate import run_gate

    versioned = _event("cal@x.com").model_copy(
        update={"source": "gcal", "object_type": "calendar_event"})
    ok = run_gate(GateContext(event=versioned, raw={"summary": "Meet"}, is_structured=True,
                              content_version="2026-08-01T10:00Z"), _trace())
    assert ok.action == "short_circuit", "a versioned mutable object must flow normally"


def test_an_immutable_source_is_never_asked_for_a_version():
    """An email does not change after it is sent — requiring a version would park the inbox."""
    from genios_engine.capture.gate.gate import run_gate

    res = run_gate(GateContext(event=_event("priya@acme.com"),
                               raw={"subject": "Hi", "snippet": "Can you send the contract?"}),
                   _trace())
    assert res.action == "route"
