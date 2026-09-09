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
    ABSENCE_RECEIPT_FIELDS,
    MAX_ABSENCE_RECEIPTS,
    absence_receipt_event_ids,
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
        c.execute(text(
            "create table graph_edges (org_id text, edge_type text, from_node_id text, "
            "to_node_id text, valid_to timestamp)"))
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


def _concerns(c, outreach_node: str, target_node: str, *, org: str = ORG, valid_to=None) -> None:
    """The edge an `outreach` node carries. It holds the waiting arithmetic; the messages live on
    the thread or person it points at."""
    c.execute(text("insert into graph_edges values (:o, 'concerns', :f, :t, :v)"),
              {"o": org, "f": outreach_node, "t": target_node, "v": valid_to})


def _superseded(c, node: str, event: str, field: str = "thread.last_outbound") -> None:
    fv = f"fvold_{event}"
    c.execute(text("insert into graph_facts values (:f, :o, :n, :fl, 'superseded')"),
              {"f": fv, "o": ORG, "n": node, "fl": field})
    c.execute(text("insert into graph_source_refs values (:o, :e, :f, 'gmail', :s, '{}')"),
              {"o": ORG, "e": event, "f": fv, "s": f"src_{event}"})


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
    """Mirrors `SituationSubject` in the three fields the backfill reads. `situation_type` is one
    of them and defaults to the commonest absence, because the direction of the receipt is chosen
    from it — a double without it silently resolves nothing."""

    def __init__(self, correlation_id, anchor_node_id, situation_type="awaiting_response"):
        self.correlation_id = correlation_id
        self.anchor_node_id = anchor_node_id
        self.situation_type = situation_type


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
# M2.C1.L-data.V0.U10 — THE DIRECTION, and the hop. Retired U07's read was one-directional and
# anchor-only, and on the pilot that found ZERO receipts for all 84 held absences. Measured there:
#
#   awaiting_response      41 situations  anchor node_type = outreach  → only `outreach.*` facts
#   first_response_overdue 40 situations  anchor node_type = thread    → `thread.last_inbound`,
#                                                                        never `last_outbound`
#
# Both reach a real qualified signal — 41/41 and 40/40 — but only through the right field, and for
# the first only after one hop across `concerns`. These tests pin both, and pin that widening
# either one into a union would readmit the marketing the branch exists to keep out.
# =============================================================================================
def test_an_outreach_anchor_reaches_our_message_one_hop_away(db):
    """The 41. The `outreach` node holds the waiting arithmetic and no messages at all; the
    thread it `concerns` holds the message we sent."""
    _concerns(db, "n_outreach", "n_thread")
    _we_wrote(db, "n_thread", "evt_1")

    assert absence_receipt_event_ids(db, ORG, "n_outreach", "awaiting_response") == ("evt_1",)


def test_first_response_overdue_is_grounded_by_THEIR_message(db):
    """The 40, and the direction that was backwards. "They wrote and we have not answered" is a
    claim ABOUT their message, so their message is the receipt — the mirror image of
    `awaiting_response`, not an exception to it."""
    _they_wrote(db, "n_thread", "evt_in")

    assert absence_receipt_event_ids(db, ORG, "n_thread",
                                     "first_response_overdue") == ("evt_in",)


def test_an_awaiting_response_claim_is_never_grounded_by_INBOUND_mail(db):
    """THE MARKETING GUARD, restated for the new read. Every marketing sender produces inbound
    mail and nothing else. If inbound counted as a receipt for `awaiting_response`, every blast
    would arrive holding one — which is the failure this whole branch exists to stop."""
    _they_wrote(db, "n_marketer", "evt_spam")

    assert absence_receipt_event_ids(db, ORG, "n_marketer", "awaiting_response") == ()


def test_a_first_response_claim_is_not_grounded_by_our_own_message(db):
    """The direction is a choice per type, not a union. Widening it to "any message on the thread"
    would make both types pass on either leg and would collapse the guard above."""
    _we_wrote(db, "n_thread", "evt_out")

    assert absence_receipt_event_ids(db, ORG, "n_thread", "first_response_overdue") == ()


def test_a_situation_type_that_is_not_an_absence_gets_nothing(db):
    """`commitment_overdue` is the third held type on the pilot, and its anchor is a `commitment`
    node reaching only a `company`. There is no message path, so it is not in the table and it
    stays held — honestly, on a receipt that genuinely does not exist."""
    _we_wrote(db, "n_thread", "evt_1")

    assert absence_receipt_event_ids(db, ORG, "n_thread", "commitment_overdue") == ()
    assert absence_receipt_event_ids(db, ORG, "n_thread", "") == ()
    assert "commitment_overdue" not in ABSENCE_RECEIPT_FIELDS


def test_the_anchors_own_messages_win_over_the_neighbours(db):
    """The hop is a fallback, never a substitute. A node that holds its own messages is never
    traded for whatever its neighbour happens to hold."""
    _we_wrote(db, "n_anchor", "evt_own")
    _concerns(db, "n_anchor", "n_other")
    _we_wrote(db, "n_other", "evt_neighbour")

    assert absence_receipt_event_ids(db, ORG, "n_anchor", "awaiting_response") == ("evt_own",)


def test_a_superseded_fact_version_is_not_a_receipt(db):
    """New, and a tightening. The pilot's anchors carry 19 `superseded` and 3 `historical`
    versions of the same field. "Nothing has happened since X" dated to a message that was itself
    replaced is a claim about the wrong instant."""
    _superseded(db, "n_thread", "evt_old")

    assert absence_receipt_event_ids(db, ORG, "n_thread", "awaiting_response") == ()


def test_a_retired_concerns_edge_is_not_followed(db):
    _concerns(db, "n_outreach", "n_thread", valid_to="2026-01-01")
    _we_wrote(db, "n_thread", "evt_1")

    assert absence_receipt_event_ids(db, ORG, "n_outreach", "awaiting_response") == ()


def test_the_hop_never_crosses_a_tenant(db):
    """Tenancy on the new join. Both legs filter org, and dropping either half would walk one
    tenant's edge into another tenant's messages."""
    _concerns(db, "n_outreach", "n_thread", org=OTHER)
    _we_wrote(db, "n_thread", "evt_1", org=OTHER)

    assert absence_receipt_event_ids(db, ORG, "n_outreach", "awaiting_response") == ()


def test_the_hop_receipt_count_is_bounded_too(db):
    _concerns(db, "n_outreach", "n_thread")
    for i in range(MAX_ABSENCE_RECEIPTS + 3):
        _we_wrote(db, "n_thread", f"evt_{i:02d}")

    got = absence_receipt_event_ids(db, ORG, "n_outreach", "awaiting_response")
    assert len(got) == MAX_ABSENCE_RECEIPTS


def test_the_backfill_reads_the_direction_from_the_situation_type(db):
    """The end-to-end shape of the correction: the same anchor, the same graph, two situation
    types, and only the one whose claim points at the stored message gets a bundle."""
    _they_wrote(db, "n_thread", "evt_in")
    _signal(db, "evt_in", quote="Can you confirm the pricing by Friday?")

    overdue = backfill_absence_l1(
        db, ORG, [_Subject("corr_a", "n_thread", "first_response_overdue")], {})
    awaiting = backfill_absence_l1(
        db, ORG, [_Subject("corr_b", "n_thread", "awaiting_response")], {})

    assert overdue["corr_a"].signal_ids == ("sig1",)
    assert awaiting == {}


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
