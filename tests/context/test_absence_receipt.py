"""M2.C1 · An absence carries the receipt for the message that created it.

    pytest tests/context/test_absence_receipt.py -q

THE 114. `awaiting_response` and `first_response_overdue` are the two commonest readings in any
inbox, and on the pilot tenant 114 of them were held by the publisher and never once shown, while
eight pieces of marketing were. The feed was exactly inverted.

The obvious diagnosis is wrong. It is NOT that a silence cannot be quoted, and the fix is NOT to
widen `_preflight` so claims without receipts may publish — that gate is correct and this branch
does not touch it.

What actually happened is that nobody fetched the receipt. These situations anchor on a synthetic
correlation the correlation engine deliberately cannot reach, so `gather_l1_signals_bulk` misses,
`l1` is None, and `evidence_verified_spans` is written as 0. The publisher then refuses the claim
on the strength of a number that was never computed for it. Meanwhile the claim's first half — WE
WROTE TO THEM — is a real message, extracted like any other, carrying real spans quoting text we
actually typed.

These tests run the real reads against a real database. The span-GRADING pass
(`gather_span_sources`) is Postgres-only in its existing form and is not exercised here; what is
exercised is that the events are found, the bundle is folded, and the backfill is additive.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.situation_bso import (
    MAX_ABSENCE_RECEIPTS,
    backfill_absence_l1,
    gather_l1_signals_for_events,
    outbound_event_ids,
)

ORG = "org_pilot"
OTHER = "org_other"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table graph_facts (fact_version_id text, org_id text, subject_node_id text, "
            "field text, status text)"))
        c.execute(text(
            "create table graph_source_refs (org_id text, event_id text, fact_version_id text, "
            "source text, source_object_id text, evidence text)"))
        c.execute(text(
            "create table qualified_signals (org_id text, event_id text, signal_id text, "
            "state text, importance_bp int, importance_version text, importance_components text, "
            "evidence_refs text, conflict_ids text, signal_type text, coverage_ready int)"))
    with engine.begin() as c:
        yield c


def _we_wrote(c, node: str, event: str, *, org: str = ORG) -> None:
    """The outbound leg: `thread.last_outbound` on the RECIPIENT's node, and a source ref that
    maps that fact version back to the message it came from."""
    fv = f"fv_{event}"
    c.execute(text("insert into graph_facts values (:f, :o, :n, 'thread.last_outbound', 'active')"),
              {"f": fv, "o": org, "n": node})
    c.execute(text("insert into graph_source_refs values (:o, :e, :f, 'gmail', :s, '{}')"),
              {"o": org, "e": event, "f": fv, "s": f"src_{event}"})


def _they_wrote(c, node: str, event: str) -> None:
    fv = f"fvin_{event}"
    c.execute(text("insert into graph_facts values (:f, :o, :n, 'thread.last_inbound', 'active')"),
              {"f": fv, "o": ORG, "n": node})
    c.execute(text("insert into graph_source_refs values (:o, :e, :f, 'gmail', :s, '{}')"),
              {"o": ORG, "e": event, "f": fv, "s": f"src_{event}"})


def _signal(c, event: str, *, signal_id: str = "sig1", quote: str = "Sending the deck today.",
            state: str = "active", importance_bp: int = 7000) -> None:
    """A qualified signal on one of our outbound messages, carrying a span that quotes what we
    wrote. `verified` is False here exactly as an extractor leaves it — only L1.5.1 may set it."""
    span = {"source_ref": f"chunk:doc_{event}:0", "quote": quote,
            "start_offset": 0, "end_offset": len(quote), "verified": False}
    c.execute(text(
        "insert into qualified_signals values (:o, :e, :sid, :st, :bp, 'v1', '{}', :ev, '[]', "
        "'commitment', 1)"),
        {"o": ORG, "e": event, "sid": signal_id, "st": state, "bp": importance_bp,
         "ev": json.dumps([span])})


class _Subject:
    def __init__(self, correlation_id, anchor_node_id):
        self.correlation_id = correlation_id
        self.anchor_node_id = anchor_node_id


# =============================================================================================
# M2.C1.L-data.V0.U07/U08 — which messages did we send this person.
# =============================================================================================
def test_an_anchor_we_wrote_to_yields_its_outbound_events(db):
    _we_wrote(db, "n_investor", "evt_1")

    assert outbound_event_ids(db, ORG, "n_investor") == ("evt_1",)


def test_an_anchor_that_only_ever_wrote_at_us_yields_nothing(db):
    """Every marketing sender on the pilot is in this state, and it is why none of them can
    produce an absence situation: nothing was ever awaited from them."""
    _they_wrote(db, "n_marketer", "evt_spam")

    assert outbound_event_ids(db, ORG, "n_marketer") == ()


def test_an_unknown_anchor_yields_nothing(db):
    assert outbound_event_ids(db, ORG, "n_nobody") == ()
    assert outbound_event_ids(db, ORG, "") == ()


def test_another_orgs_outbound_is_never_visible(db):
    """Tenancy. The join filters org on BOTH tables; dropping either half leaks a counterparty
    from one tenant into another's feed."""
    _we_wrote(db, "n_shared", "evt_other", org=OTHER)

    assert outbound_event_ids(db, ORG, "n_shared") == ()


def test_the_receipt_count_is_bounded(db):
    """A decade-long thread must not drag its whole history into one card."""
    for i in range(MAX_ABSENCE_RECEIPTS + 4):
        _we_wrote(db, "n_chatty", f"evt_{i:02d}")

    assert len(outbound_event_ids(db, ORG, "n_chatty")) == MAX_ABSENCE_RECEIPTS


# =============================================================================================
# M2.C1.L-logic.V0.U09 — Layer 1's verdicts for those events.
# =============================================================================================
def test_the_events_l1_verdicts_are_folded_into_a_bundle(db):
    _we_wrote(db, "n_investor", "evt_1")
    _signal(db, "evt_1", quote="I'll send the updated deck tomorrow.")

    bundle = gather_l1_signals_for_events(db, ORG, ["evt_1"])

    assert bundle is not None
    assert bundle.signal_ids == ("sig1",)
    assert any(span.get("quote") == "I'll send the updated deck tomorrow."
               for span in bundle.evidence), "the receipt must quote what WE wrote"


def test_events_with_no_qualified_signal_fold_to_none(db):
    """The honest absence, same as the correlation read returns. A situation with nothing behind
    it must keep its None so the gate keeps holding it."""
    _we_wrote(db, "n_investor", "evt_1")

    assert gather_l1_signals_for_events(db, ORG, ["evt_1"]) is None


def test_no_events_folds_to_none_without_touching_the_database(db):
    assert gather_l1_signals_for_events(db, ORG, []) is None
    assert gather_l1_signals_for_events(db, ORG, [""]) is None


# =============================================================================================
# M2.C1.L-logic.V1.U10 — the backfill, and the two ways it must refuse to act.
# =============================================================================================
def test_a_missed_correlation_is_backfilled_from_the_outbound_events(db):
    _we_wrote(db, "n_investor", "evt_1")
    _signal(db, "evt_1")
    subjects = [_Subject("corr_synthetic", "n_investor")]

    out = backfill_absence_l1(db, ORG, subjects, {})

    assert "corr_synthetic" in out, "the situation that was held forever now has a bundle"
    assert out["corr_synthetic"].signal_ids == ("sig1",)


def test_a_correlation_the_bulk_read_already_answered_is_never_touched(db):
    """ADDITIVE ONLY. Every situation that publishes today must publish on exactly the evidence
    it publishes on today, so an existing bundle is left alone even when outbound events exist."""
    _we_wrote(db, "n_investor", "evt_1")
    _signal(db, "evt_1")
    sentinel = object()
    subjects = [_Subject("corr_real", "n_investor")]

    out = backfill_absence_l1(db, ORG, subjects, {"corr_real": sentinel})

    assert out["corr_real"] is sentinel


def test_an_anchor_we_never_wrote_to_is_left_held(db):
    """The gate must still refuse a claim with no receipt, and after this change it still does.
    This is the assertion that says the fix fed the gate rather than opening it."""
    _they_wrote(db, "n_marketer", "evt_spam")
    _signal(db, "evt_spam")
    subjects = [_Subject("corr_marketing", "n_marketer")]

    out = backfill_absence_l1(db, ORG, subjects, {})

    assert out == {}, "no outbound means no receipt means still held"


def test_an_anchorless_subject_is_skipped(db):
    subjects = [_Subject("corr_x", None), _Subject(None, "n_investor")]

    assert backfill_absence_l1(db, ORG, subjects, {}) == {}


# =============================================================================================
# M2.C1.L-logic.V1.U04 — the payoff, and the proof the gate was FED rather than opened.
#
# These two run against the real `decide_publication`, unchanged by this branch. The first is the
# card the pilot never saw. The second is the reason widening the gate would have been the wrong
# fix: a claim with no receipt is still refused, exactly as before.
# =============================================================================================
def _absence_bso(*, evidence, verified_spans: int):
    from genios_engine.contracts.domain_expertise import BusinessSituationObject

    return BusinessSituationObject(
        org_id=ORG, trace_id="trace_absence_1", visibility={"scope": "org"},
        id="sit_absence_1", signal_ids=("evt_1",), type="awaiting_response",
        confidence_bp=7_400, importance_bp=6_800, evidence=evidence,
        metadata={"domain_ids": ["admin"],
                  "importance_source": "l1_qualified_signals",
                  "evidence_verified_spans": verified_spans})


_OUR_SENTENCE = "I'll send the updated deck tomorrow."
_REAL_RECEIPT = ({"source_ref": "chunk:doc_evt_1:0", "quote": _OUR_SENTENCE,
                  "start_offset": 0, "end_offset": len(_OUR_SENTENCE), "verified": True,
                  "event_id": "evt_1", "source": "gmail"},)
#: What `_signals_and_evidence` supplies when the correlation lookup finds nothing. No quote, so
#: `_receipts` is empty and the situation is held — which is what happened 114 times.
_PLACEHOLDER = ({"event_id": "sig:sit_absence_1", "source": "situation",
                 "reconstructed": True},)


def test_an_absence_carrying_our_own_sentence_publishes():
    """THE CARD THE PILOT NEVER SAW. "We wrote this, and since then nothing" — quoting the half
    that can be quoted, which is the half we wrote."""
    from genios_engine.context.situation_publisher import decide_publication

    result = decide_publication(_absence_bso(evidence=_REAL_RECEIPT, verified_spans=1))

    assert result.admitted, f"still held: {result.reasons}"


def test_an_absence_with_only_the_placeholder_is_still_held():
    """The gate was FED, not opened. A claim whose only evidence is a synthetic record with no
    quote is still refused — and this is the exact state all 114 situations were in."""
    from genios_engine.context.situation_publisher import HoldReason, decide_publication

    result = decide_publication(_absence_bso(evidence=_PLACEHOLDER, verified_spans=0))

    assert not result.admitted
    assert HoldReason.VERIFIED_EVIDENCE_REQUIRED.value in result.reasons
