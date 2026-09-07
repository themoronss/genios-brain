"""L2.7.8 · THE SITUATION PUBLISHER ON QES INPUT — doc 07's acceptance, driven.

    pytest tests/context/test_situation_publisher.py -q

    every published BSO carries >= 1 verified evidence span
    importance_bp is not 5000 unless the fallback path fired AND logged
    conflicts from L1 v2 arrive in metadata

plus the group gate's two rows that belong to this unit:

    BSOs with a verified evidence span      100%
    confidence vector axes present          all 6

THE ONE THAT MATTERS IS THE FIRST. Before this wave a situation's `evidence` was a list of event
REFERENCES: "there is an email about this". After it, it is a list of span-validated verbatim
quotes: *he wrote "we can move forward with the $84,000 annual contract"*. The gap between those
two sentences is the difference between a card a founder acts on and a card a founder opens their
mailbox to check, and the only thing that closes it honestly is a validator — L1's own ALG-08,
imported, never reimplemented. Half this file is therefore about the ways a quote can FAIL to be a
receipt: relocated, incoherent, unverifiable, or carrying a flag from a check nobody can repeat.

WHAT THIS FILE CANNOT MEASURE, AND THE COMMAND THAT CAN. H8 is the PILOT gate — its rows are
measured over seven days of one real tenant's data (`python scripts/l2_shadow_diff.py --org
<pilot> --days 7`), and no pilot tenant is connected to this repo. Three of its rows are therefore
open here for exactly the reason Layer 1's G10 is open in `docs/plans/L1_V2_BUILD_RECORD.md` §5.1:

    a DECLINING trend on a real account, series citable        >= 1   — needs a tenant + 7 days
    a cohort position on a real account, population named      >= 1   — needs a tenant + 7 days
    a pattern-matched situation with per-condition evidence    >= 1   — needs a tenant + 7 days

What is proven below instead is that each of those PATHS carries its receipt when the fact exists:
`analytic_context` publishes the trend and cohort receipts the composition leaned on, and
`gather_pattern_fires` + `_situation_type` publish the per-condition evidence and refuse to rename
a situation on an unactivated match. A seeded org can prove the mechanism; only a tenant can
supply the population. Neither this file nor anything in it may be read as a pilot measurement.

WHAT THE SEEDED ORG ACTUALLY MEASURED, stated because the number is not 100%. Driving the
production door end to end (the last test in this file, instrumented) published FOUR situations
for one captured email, and exactly ONE of them carried a verified span — two spans, both
regraded against the stored prepared text. The other three carry none, and the publisher is not
why: they were written by three of the OTHER FIVE writers of `context_situations`
(`periodic`, `meeting_touch`, `support_situations`, `outreach_situations`, `document_register`),
which mint their own synthetic correlations and rest on no `qualified_signals` row at all. Each of
those three published on the documented fallback and said so in the log, which is the second
acceptance row working exactly as written.

So the group gate's *"BSOs with a verified evidence span — 100%"* is a property of the SUPPLY
before it is a property of this unit: it can only be reached for situations Layer 1 published a
signal for, and reaching it everywhere is either L2.5.8's admission gate (specified, NOT BUILT —
`docs/plans/L2_MISSING_UNIT_SPECS.md` gives it 1 unit owed and 0 built) holding the others back,
or those five writers gaining a signal seam of their own. Neither is this wave's, and neither may
be faked by a publisher that stamps `verified` on a receipt it did not check.

The real-Postgres half at the bottom drives the PRODUCTION door — one email through `run_sync`,
the real drain, `reason/runner.run_all` — because "a test calls it" is not a caller.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from genios_engine.capture.validate.spans import SpanVerdict
from genios_engine.context.domain_spec import spec_for
from genios_engine.context.importance import (
    ComposedImportance,
    ModifierName,
    ModifierReason,
    ModifierTerm,
)
from genios_engine.context.situation_bso import (
    DEFAULT_IMPORTANCE_BP,
    EVIDENCE_POOL,
    MAX_CONFLICTS,
    MAX_EVIDENCE,
    MAX_MATCHED_CONDITIONS,
    RESOLVED_GRADES,
    TYPE_SOURCE_ANCHOR,
    TYPE_SOURCE_PATTERN,
    UNSCORED_VERSION,
    L1Signals,
    PatternFire,
    analytic_context,
    _graded_evidence,
    build_business_situation,
    importance_base,
    situation_confidence_vector,
    verify_evidence_spans,
)
from genios_engine.contracts.domain_expertise import BusinessSituationObject
from genios_engine.contracts.situation_evidence import (
    AXIS_UNKNOWN_BP,
    CONFIDENCE_AXES,
    VERDICT_INVALID_BOUNDS,
    VERIFICATION_L1,
    VERIFICATION_NONE,
    VERIFICATION_REVERIFIED,
    VERIFIED_VERDICTS,
    SituationConfidenceVector,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)

#: The sentence the whole wave is about. A card that can show THIS is a different product from one
#: that can only say "there is an email about the renewal".
SOURCE = ("Hi — legal signed off, so we can move forward with the $84,000 annual contract. "
          "I still need Finance to confirm.")
QUOTE = "we can move forward with the $84,000 annual contract"
REF = "prepared_content:evt_pub_1"


def _span(quote: str = QUOTE, *, ref: str = REF, verified: bool = False,
          start: int | None = None, end: int | None = None,
          signal_id: str = "sig_pub_1") -> dict:
    """One stored `qualified_signals.evidence_refs` entry, in Layer 1's own dumped shape."""
    at = SOURCE.index(quote) if start is None and quote in SOURCE else (start or 0)
    return {"source_ref": ref, "quote": quote, "start_offset": at,
            "end_offset": end if end is not None else at + len(quote),
            "verified": verified, "signal_id": signal_id}


def _situation(**over) -> dict:
    """A `context_situations` row as the six writers of that table actually shape it."""
    row = {
        "situation_id": "sit_pub_1",
        # From the registry, never hand-written: a literal here is how the producer's type
        # silently drifted out of the set the compiler can route (see `test_situation_bso.py`).
        "situation_type": spec_for("sales").type_for("company"),
        "domain": "sales", "status": "active", "correlation_id": "corr_pub_1",
        "confidence_overall": 82, "confidence_evidence": 90, "confidence_freshness": 70,
        "confidence_consistency": 80, "confidence_identity": 95, "coverage": 60,
        "confidence_analytic": 55, "resolved_by": None,
        "missing": None, "first_seen_at": NOW, "last_seen_at": NOW,
        "anchor_node_id": "node_acme", "anchor_name": "Acme", "anchor_type": "company",
    }
    row.update(over)
    return row


def _l1(*, spans=None, sources=None, importance_bp: int | None = 8_100, **over) -> L1Signals:
    """An `L1Signals` carrying the RAW stored spans, put through the production grading pass.

    `_graded_evidence` is the unit the readers call after folding — it grades, orders and caps —
    so a fixture that wrote the graded records itself would be testing a shape nothing produces
    (the exact failure `_situation` avoids for `situation_type`) and would silently skip the
    ordering this file is here to pin.
    """
    raw = spans if spans is not None else [_span(verified=True)]
    fields = dict(
        signal_ids=("sig_pub_1",), scored_signal_ids=("sig_pub_1",),
        importance_bp=importance_bp, importance_version="alg17.v2",
        components={"money_bp": 4_000}, signal_types=("commitment_made",),
        evidence=tuple(raw), signal_count=1, scored_count=1)
    fields.update(over)
    return _graded_evidence(L1Signals(**fields),
                            sources if sources is not None else {REF: SOURCE})


def _bso(**over) -> BusinessSituationObject:
    kwargs = dict(org_id="org_pub", situation=_situation(), signal_ids=["sig_pub_1"],
                  evidence=[{"event_id": "evt_pub_1", "source": "situation",
                             "reconstructed": True}],
                  trace_id="trace_pub_1", l1=_l1())
    kwargs.update(over)
    return build_business_situation(**kwargs)


# =================================================================================================
# THE VALIDATOR IS L1'S — and the four grades it accepts are L1's too
# =================================================================================================

def test_the_accepted_grades_are_alg08s_own_and_the_two_vocabularies_agree():
    """One policy, spelled twice — once as the enum Layer 1 owns and once as strings the contract
    layer may hold — and pinned together here for the reason `test_l2_reads_what_l1_publishes`
    pins `UNSCORED_VERSION`: a contract package that imported a capture module would invert the
    dependency direction `tests/test_layer_topology.py` enforces, so the second spelling is
    unavoidable and an untested second spelling is a policy that drifts."""
    assert {grade.value for grade in RESOLVED_GRADES} == set(VERIFIED_VERDICTS)
    # And they cover the cascade: a seventh grade must break a test rather than quietly land in
    # whichever branch the code happens to default to.
    assert RESOLVED_GRADES | {SpanVerdict.UNVERIFIED, SpanVerdict.INVALID_BOUNDS} == set(
        SpanVerdict), "ALG-08 grew a verdict and this publisher has no opinion about it"


def test_a_quote_that_is_in_the_source_publishes_as_a_reverified_span():
    """The upgrade itself: a stored reference becomes a receipt with the SENTENCE in it."""
    graded = verify_evidence_spans([_span()], {REF: SOURCE})
    assert len(graded) == 1
    span = graded[0]
    assert span.verified is True
    assert span.verification == VERIFICATION_REVERIFIED
    assert span.verdict == SpanVerdict.VERIFIED.value
    assert span.quote == QUOTE, "the receipt must carry the sentence, not a summary of it"
    assert SOURCE[span.start_offset:span.end_offset] == QUOTE, (
        "the offsets must point AT the quote — a card highlights by them")


def test_a_relocated_quote_publishes_at_the_offsets_that_actually_resolve():
    """ALG-08's correction is KEPT. A receipt whose numbers point at the wrong characters
    highlights the wrong sentence, which is worse than highlighting none: the quote looks
    substantiated and the underline lands on unrelated text."""
    wrong = _span(start=0, end=len(QUOTE))          # right words, wrong place
    graded = verify_evidence_spans([wrong], {REF: SOURCE})
    assert graded[0].verified is True
    assert graded[0].verdict == SpanVerdict.VERIFIED_RELOCATED.value
    assert graded[0].start_offset == SOURCE.index(QUOTE)
    assert SOURCE[graded[0].start_offset:graded[0].end_offset] == QUOTE


def test_layer_ones_flag_does_not_survive_a_failed_recheck():
    """**The doctrine, at its sharpest.** The span claims `verified=True` — only ALG-08 may set
    that — and the sentence is not in the text we hold. The check we can REPEAT outranks the flag
    we cannot: a prepared body that was re-masked, or a span stamped in another frame, is a
    receipt that no longer resolves, and carrying the flag would let it keep counting."""
    graded = verify_evidence_spans([_span("we are pausing until Q3", verified=True)],
                                   {REF: SOURCE})
    assert graded[0].verified is False
    assert graded[0].verification == VERIFICATION_NONE
    assert graded[0].verdict == SpanVerdict.UNVERIFIED.value
    assert graded[0].quote == "we are pausing until Q3", (
        "the unresolved assertion is still evidence about the extractor and must be stored")


def test_a_span_whose_source_text_is_gone_keeps_layer_ones_verdict():
    """Prepared content expires (180 days); a receipt does not stop being a receipt when the body
    it cites has aged out of retention. Layer 1's flag stands, labelled as what it is — a check
    that happened rather than one we repeated — and NO grade is invented for it."""
    graded = verify_evidence_spans([_span(verified=True)], {})
    assert graded[0].verified is True
    assert graded[0].verification == VERIFICATION_L1
    assert graded[0].verdict == "", "a grade we did not produce must not be copied"

    unflagged = verify_evidence_spans([_span(verified=False)], {})
    assert unflagged[0].verified is False, "no text and no flag is not a receipt"


def test_an_incoherent_span_is_graded_invalid_bounds_and_kept():
    """A quote whose length disagrees with its offsets was never resolvable. ALG-08's own name for
    it, and kept rather than dropped for ALG-08's own reason — it is evidence about the extractor
    — so that a fabricating prompt is visible instead of merely producing thinner cards."""
    graded = verify_evidence_spans([_span(start=10, end=12, verified=True)], {REF: SOURCE})
    assert graded[0].verdict == VERDICT_INVALID_BOUNDS
    assert graded[0].verified is False
    assert len(graded) == 1


def test_a_span_that_names_nothing_is_not_carried_at_all():
    """Three ways a row is not a receipt in any state, and none of them may reach a card."""
    assert verify_evidence_spans([{"quote": QUOTE, "signal_id": "sig_pub_1"}], {}) == ()
    assert verify_evidence_spans([{"source_ref": REF, "quote": "   ",
                                   "signal_id": "sig_pub_1"}], {}) == ()
    assert verify_evidence_spans([{"source_ref": REF, "quote": QUOTE}], {}) == (), (
        "a quote with no signal behind it cannot be explained backwards")


# =================================================================================================
# ACCEPTANCE 1 — every published BSO carries >= 1 verified evidence span
# =================================================================================================

def test_every_published_bso_carries_a_verified_evidence_span():
    bso = _bso()
    verified = [e for e in bso.evidence if e.get("verified")]
    assert verified, "the acceptance row: >= 1 VERIFIED evidence span"
    assert verified[0]["quote"] == QUOTE
    assert verified[0]["source"] == "l1_qualified_signal"
    assert bso.metadata["evidence_verified_spans"] == 1
    assert bso.metadata["evidence_spans"] == 1
    # The reconstruction is dropped once there is something real to show — it exists only so the
    # contract's non-empty rule holds when there is not.
    assert not any(e.get("reconstructed") for e in bso.evidence)


def test_a_verified_span_beyond_the_publishing_cap_still_reaches_the_bso():
    """**The ordering bug this wave had to avoid.** The cap used to be applied before anything was
    graded, so which receipts a BSO carried was decided by which signals scored highest. A
    situation whose one verified quote sat in position 34 published as though it had none — a 0%
    row on the acceptance gate produced by an ordering, not by the evidence."""
    spans = [_span(f"filler sentence {n}", verified=False, signal_id=f"sig_f{n}")
             for n in range(MAX_EVIDENCE + 14)]
    spans.append(_span(verified=True))
    l1 = _l1(spans=spans, sources={REF: SOURCE})
    bso = _bso(l1=l1)
    assert len(bso.evidence) == MAX_EVIDENCE
    assert bso.evidence[0]["quote"] == QUOTE, "the verified receipt must lead"
    assert bso.metadata["evidence_verified_spans"] == 1
    assert bso.metadata["evidence_spans"] == len(spans)
    assert EVIDENCE_POOL > MAX_EVIDENCE, "the pool must be wider than the cap or this is moot"


# =================================================================================================
# ACCEPTANCE 2 — importance_bp is not 5000 unless the fallback fired AND logged
# =================================================================================================

def test_importance_is_layer_ones_number_when_layer_one_scored_it(caplog):
    with caplog.at_level(logging.INFO, logger="genios.context.situation_bso"):
        bso = _bso()
    assert bso.importance_bp == 8_100 != DEFAULT_IMPORTANCE_BP
    assert bso.metadata["importance_source"] == "l1_qualified_signals"
    assert bso.metadata["importance_fallback"] is False
    assert "FALLBACK" not in caplog.text, (
        "a scored situation logged the fallback — the line would then mean nothing")


#: The three arms that may still publish the constant, and what each one MEANS. They are different
#: facts about a tenant and the log line has to say which: "nobody scored this", "everything this
#: situation had has been retired", "there is no Layer 1 supply here at all".
_FALLBACK_ARMS = [
    ("l1_unscored", L1Signals(signal_ids=("sig_u",), importance_bp=None,
                              importance_version=UNSCORED_VERSION, signal_count=1)),
    ("l1_all_retired", L1Signals(signal_ids=("sig_r",), importance_bp=None,
                                 importance_version="alg17.v2", signal_count=0)),
    ("default", None),
]


@pytest.mark.parametrize("source,l1", _FALLBACK_ARMS, ids=[a[0] for a in _FALLBACK_ARMS])
def test_the_constant_publishes_only_when_the_fallback_fired_and_logged(source, l1, caplog):
    """Doc 07's acceptance row, and X5's four-branch guarantee in the same assertion.

    The number alone can never be audited — a composed 5000 and a defaulted one are the same
    integer — so the publisher has to SAY which it is, in two places: on the object for whoever
    holds it, and in the log for the operator who does not. A tenant printing this line for every
    situation has no Layer 1 supply reaching Layer 2, which is a deployment fact that is otherwise
    invisible (a flat distribution looks like a flat business) and is the state that persisted long
    enough for 193 of 223 signals to share one score.
    """
    with caplog.at_level(logging.INFO, logger="genios.context.situation_bso"):
        bso = _bso(l1=l1, evidence=[{"event_id": "evt_pub_1", "source": "situation",
                                     "reconstructed": True}])
    assert bso.importance_bp == DEFAULT_IMPORTANCE_BP
    assert bso.metadata["importance_source"] == source
    assert bso.metadata["importance_fallback"] is True
    assert importance_base(l1).source == source, (
        "the builder and the sweep's composer must agree about which arm fired")
    assert "FALLBACK" in caplog.text and source in caplog.text, (
        "the constant published with no log line — 'fired AND logged' is one requirement")
    assert "sit_pub_1" in caplog.text, "a fallback nobody can attribute to a situation"


def test_the_composed_number_wins_over_layer_ones_base():
    """X5, unregressed: when the composition exists, `importance_bp` is the COMPOSED number and
    the stored record is the whole arithmetic. The BSO must not re-derive or re-explain it."""
    composed = ComposedImportance(
        importance_bp=7_400, version="blg18.v1", base_bp=8_100,
        base_source="l1_qualified_signals", base_signal_id="sig_pub_1", base_version="alg17.v2",
        corroboration_bp=0, distinct_source_count=1, source_systems=("gmail",),
        modifiers=(), modifier_total_bp=0, modifier_cap_removed_bp=0, subtotal_bp=7_400,
        coverage_ready=True, coverage_domain="sales", coverage_penalty_bp=0, clamp_delta_bp=0)
    bso = _bso(composed=composed)
    assert bso.importance_bp == 7_400
    assert bso.metadata["importance_version"] == "blg18.v1"
    assert bso.metadata["importance_components"]["base_bp"] == 8_100
    assert bso.metadata["importance_fallback"] is False


# =================================================================================================
# ACCEPTANCE 3 — conflicts from L1 v2 arrive in metadata
# =================================================================================================

def test_conflicts_arrive_as_records_and_not_only_as_pointers():
    """An id alone arrives nowhere. Layer 3 may not read past Layer 2, so a situation resting on a
    contested claim used to reach the compiler looking exactly as settled as one that was never
    contested. What travels is which FIELD disagreed and how Layer 1 resolved it."""
    conflict = {"conflict_id": "cft_1", "signal_id": "sig_pub_1", "field": "amount",
                "subject_key": "deal:acme", "resolution": "unresolved_surface_both",
                "resolved_value": None, "event_ids": ["evt_pub_1", "evt_pub_2"],
                "claim_count": 2}
    bso = _bso(l1=_l1(conflict_ids=("cft_1",), conflicts=(conflict,)))
    assert bso.metadata["conflict_ids"] == ("cft_1",)
    carried = bso.metadata["conflicts"]
    assert len(carried) == 1
    assert carried[0]["field"] == "amount"
    assert carried[0]["resolution"] == "unresolved_surface_both"
    assert carried[0]["claim_count"] == 2
    assert "detected_at" not in carried[0], (
        "a clock in metadata re-mints the expertise package on every sweep — the 995 MB incident")


def test_a_situation_with_no_conflicts_says_so_rather_than_omitting_the_key():
    """An absent key and a key saying "nothing" read identically to a consumer and mean opposite
    things — and this mapping is content-addressed, so a key that appears only sometimes makes two
    situations with the same facts hash differently."""
    assert _bso().metadata["conflicts"] == ()


# =================================================================================================
# THE GROUP GATE — the confidence VECTOR, all six axes
# =================================================================================================

def test_the_published_situation_carries_all_six_confidence_axes():
    vector = SituationConfidenceVector.from_record(_bso().metadata["confidence_vector"])
    assert set(_bso().metadata["confidence_vector"]) == set(CONFIDENCE_AXES)
    assert vector.complete is True
    assert vector.evidence == 9_000 and vector.analytic == 5_500, (
        "the axes are percent in the table and basis points on the object")
    assert _bso().metadata["confidence_vector_complete"] is True
    # Never collapsed to a scalar (doc 09, must-not-regress row 3): `confidence_bp` stays the
    # minimum-of-axes number the contract already carried, and the vector sits BESIDE it.
    assert _bso().confidence_bp == 8_200


def test_an_unassessed_axis_publishes_as_unknown_and_never_as_zero():
    """`confidence_analytic` is null on any sweep older than migration 0099 and carries
    `COVERAGE_UNKNOWN` when the composition leaned on no comparison. Both are "we did not measure",
    and a 0 would rank an unmeasured situation below every measured one."""
    vector = situation_confidence_vector(_situation(confidence_analytic=None))
    assert vector.analytic == AXIS_UNKNOWN_BP
    assert vector.complete is False
    assert situation_confidence_vector(_situation(confidence_analytic=-1)).analytic == (
        AXIS_UNKNOWN_BP)


# =================================================================================================
# THE ANALYTIC CONTEXT — H8's two bold rows, mechanism proven, POPULATION STILL OWED
# =================================================================================================

def _composed_with(term: ModifierTerm) -> ComposedImportance:
    return ComposedImportance(
        importance_bp=8_600, version="blg18.v1", base_bp=8_100,
        base_source="l1_qualified_signals", base_signal_id="sig_pub_1", base_version="alg17.v2",
        corroboration_bp=0, distinct_source_count=1, source_systems=("gmail",),
        modifiers=(term,), modifier_total_bp=term.delta_bp, modifier_cap_removed_bp=0,
        subtotal_bp=8_600, coverage_ready=True, coverage_domain="sales",
        coverage_penalty_bp=0, clamp_delta_bp=0)


def test_the_trend_that_moved_the_number_travels_with_it():
    """H8 row: *"a DECLINING trend on a real account, series citable"*. The series is citable
    because the modifier's receipt travels — metric, direction, the confidence and the point count
    the decision turned on. **This proves the path, not the row.** The row is a count over one
    tenant's seven days and no tenant is connected here; see the module docstring."""
    term = ModifierTerm(name=ModifierName.TREND, fired=True, delta_bp=500,
                        reason=ModifierReason.FIRED,
                        evidence={"metric": "reply_latency_hours", "direction": "declining",
                                  "trend_confidence_bp": 7_000, "point_count": 6})
    bso = _bso(composed=_composed_with(term))
    assert bso.metadata["trends"] == ({"metric": "reply_latency_hours",
                                       "direction": "declining",
                                       "trend_confidence_bp": 7_000, "point_count": 6},)
    assert bso.metadata["cohort_positions"] == () and bso.metadata["anomalies"] == ()


def test_a_modifier_that_did_not_fire_contributes_no_comparison():
    """A trend found and then judged too thin to act on is not a trend this situation leaned on.
    The reason stays on the stored term, where a reader who wants it can read it."""
    term = ModifierTerm(name=ModifierName.TREND, fired=False, delta_bp=0,
                        reason=ModifierReason.TREND_CONFIDENCE_BELOW_FLOOR,
                        evidence={"metric": "reply_latency_hours"})
    assert analytic_context(_composed_with(term))["trends"] == []
    assert analytic_context(None) == {"trends": [], "cohort_positions": [], "anomalies": []}


# =================================================================================================
# THE PATTERN — L2.6's fire, and the migration rule it must obey
# =================================================================================================

_FIRE = PatternFire(
    pattern_id="renewal_at_risk", pattern_version=3, situation_type="renewal_at_risk",
    match_strength_bp=7_200, activated=False,
    matched_conditions=({"index": 0, "kind": "fact", "field": "subscription.auto_renew",
                         "value": False, "fact_version_id": "fv_1"},
                        {"index": 1, "kind": "absence", "field": "meeting.scheduled",
                         "absence_type": "genuinely_absent"}))


def test_a_shadow_fire_annotates_the_situation_and_may_not_rename_it():
    """`context/patterns/store.py`'s own migration rule: *"compare fire sets on a pilot for 7 days
    before switching. Do not delete the anchor path in this wave."* An unactivated pattern is
    evidence for that comparison, not authority over the routing identity every layer above uses."""
    bso = _bso(pattern=_FIRE)
    assert bso.type == spec_for("sales").type_for("company"), (
        "a shadow fire renamed the situation — routing moved on evidence nobody activated")
    assert bso.metadata["pattern_id"] == "renewal_at_risk"
    assert bso.metadata["pattern_activated"] is False
    assert bso.metadata["pattern_match_strength_bp"] == 7_200
    assert len(bso.metadata["matched_conditions"]) == 2, (
        "H8: 'a pattern-matched situation with PER-CONDITION evidence' — without these, a match "
        "is an assertion")
    assert bso.metadata["matched_conditions"][0]["field"] == "subscription.auto_renew"


def test_an_activated_pattern_names_the_situation():
    bso = _bso(pattern=replace(_FIRE, activated=True))
    assert bso.type == "renewal_at_risk"
    assert bso.metadata["pattern_activated"] is True


def test_the_object_says_which_detection_path_named_it():
    """The pilot comparison's key. Doc 06 requires both paths to run for seven days before either
    replaces the other, and a fire-set comparison needs a per-situation answer to "who said so":
    counted only in aggregate, a pattern naming the wrong thing and the anchor naming the right
    thing cancel each other out and the week reads as agreement."""
    assert _bso().metadata["type_source"] == TYPE_SOURCE_ANCHOR
    assert _bso(pattern=_FIRE).metadata["type_source"] == TYPE_SOURCE_ANCHOR, (
        "a shadow fire did not name this situation and must not claim to have")
    assert _bso(pattern=replace(_FIRE, activated=True)).metadata["type_source"] == (
        TYPE_SOURCE_PATTERN)


def test_only_the_receipts_that_fit_are_carried_and_the_caps_are_stated():
    """Three caps, one argument: a BSO is a summary a human or an LLM reads, not the evidence
    table, the conflict table or the pattern registry. Asserted rather than assumed because a cap
    that silently is not applied is a 238 kB metadata blob per situation in a content-addressed
    row — the shape of the incident this module's docstrings keep naming."""
    l1 = _l1(conflict_ids=tuple(f"cft_{n}" for n in range(MAX_CONFLICTS + 5)),
             conflicts=tuple({"conflict_id": f"cft_{n}", "field": "amount",
                              "resolution": "resolved_by_recency", "claim_count": 2}
                             for n in range(MAX_CONFLICTS + 5)))
    assert len(_bso(l1=l1).metadata["conflicts"]) == MAX_CONFLICTS

    crowded = replace(_FIRE, matched_conditions=tuple(
        {"index": n, "kind": "fact", "field": f"f{n}"}
        for n in range(MAX_MATCHED_CONDITIONS + 5)))
    assert len(_bso(pattern=crowded).metadata["matched_conditions"]) == MAX_MATCHED_CONDITIONS


def test_layer_ones_coverage_verdict_is_carried_and_never_re_derived():
    """Doc 08's addition list says `coverage_ready` is *"carried from the QES, never re-derived"*.
    Tri-state, and the third state is the one that matters: `None` means Layer 1 did not assess,
    which must not reach a predicate as False — that is how every `no_obs` rule silently stops for
    a tenant whose coverage row has simply not been filed yet."""
    assert _bso(l1=_l1(coverage_ready=True)).metadata["coverage_ready"] is True
    assert _bso(l1=_l1(coverage_ready=False)).metadata["coverage_ready"] is False
    assert _bso(l1=_l1()).metadata["coverage_ready"] is None
    assert _bso(l1=None).metadata["coverage_ready"] is None


def test_a_situation_no_pattern_matched_still_carries_every_pattern_key():
    bso = _bso()
    assert bso.metadata["pattern_id"] is None
    assert bso.metadata["pattern_activated"] is False
    assert bso.metadata["matched_conditions"] == ()


def test_layer_ones_signal_type_travels_but_does_not_rename_the_situation():
    """Doc 07 pairs `signal_type` with the pattern match in the `type` row, and only one of the two
    may decide it. Layer 1 names what kind of SIGNAL an email carried (`commitment_made`); this
    names what kind of THING the situation is, and they are different vocabularies — routing on the
    first is a silent, total route miss into a capability set that does not exist."""
    bso = _bso()
    assert bso.metadata["signal_types"] == ("commitment_made",)
    assert bso.type == spec_for("sales").type_for("company")


# =================================================================================================
# X6 — the lifecycle states must survive a publish
# =================================================================================================

def test_a_partially_resolved_situation_publishes_as_partial():
    """Neither fully open nor fully closed. Read as open it is a nag about work that is mostly
    done; read as closed it is work silently dropped. `partial` + who closed it, verbatim."""
    bso = _bso(situation=_situation(status="partial", resolved_by="statement"))
    assert bso.state == "partial"
    assert bso.metadata["partially_resolved"] is True
    assert bso.metadata["resolved_by"] == "statement", (
        "RESOLVED_BY_STATEMENT must survive the publish — M-4's verdict is the only record of it")


def test_a_statement_resolved_situation_keeps_its_resolver():
    bso = _bso(situation=_situation(status="resolved", resolved_by="statement"))
    assert bso.state == "resolved"
    assert bso.metadata["resolved_by"] == "statement"
    assert bso.metadata["partially_resolved"] is False


# =================================================================================================
# H0 and the content address — what may not move
# =================================================================================================

def test_an_old_shaped_business_situation_object_still_constructs():
    """H0's row, held against everything above. The v2 material travels in `metadata` and inside
    `evidence` — both already free-shaped on the frozen contract — so an object built the way this
    module built one before the wave is still a legal `BusinessSituationObject`."""
    old = BusinessSituationObject(
        org_id="org_pub", trace_id="trace_pub_1", visibility={"scope": "org"}, id="sit_old",
        signal_ids=("evt_1",), type="deal", confidence_bp=8_200,
        importance_bp=DEFAULT_IMPORTANCE_BP,
        evidence=({"event_id": "evt_1", "source": "gmail"},),
        metadata={"domain_ids": ["sales"], "shadow": True})
    assert old.importance_bp == DEFAULT_IMPORTANCE_BP
    assert old.domain_hints == ("sales",)
    assert "confidence_vector" not in old.metadata
    assert old.semantic_hash


def test_two_publishes_of_an_unchanged_situation_address_the_same_content():
    """The 995 MB guard, applied to everything this wave adds. `metadata` and `evidence` are both
    hashed into the expertise package's content address, so ONE per-sweep value here mints a fresh
    ~238 kB package row per situation per sweep. Different trace ids, identical hash."""
    first = _bso(trace_id="trace_a", pattern=_FIRE)
    second = _bso(trace_id="trace_b", pattern=_FIRE)
    assert first.semantic_hash == second.semantic_hash


def test_nothing_the_publisher_adds_is_a_float():
    """Doctrine 2, enforced by the contract itself (`canonicalize` refuses floats) and asserted
    here so the failure names the publisher rather than a hashing call three layers away."""
    def walk(value):
        if isinstance(value, float):
            raise AssertionError(f"a float reached the BSO: {value!r}")
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    bso = _bso(pattern=_FIRE, composed=_composed_with(
        ModifierTerm(name=ModifierName.ANOMALY, fired=True, delta_bp=300,
                     reason=ModifierReason.FIRED,
                     evidence={"metric": "open_loops", "z_like_bp": 2_400, "periods_used": 8})))
    walk(dict(bso.metadata))
    walk([dict(e) for e in bso.evidence])
    assert bso.metadata["anomalies"][0]["z_like_bp"] == 2_400


# =================================================================================================
# REAL POSTGRES — the readers, against the tables they actually read
# =================================================================================================

pg = pytest.mark.pg

ORG_PG = "l2_publisher_pg"


def _fresh(pg_store, org: str) -> None:
    """One clean tenant per run. The scratch database outlives a pytest process and every table
    here is content-addressed or keyed, so a second run would upsert onto its own first run's rows
    and prove nothing."""
    from sqlalchemy import text as sql
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'l2 publisher') "
                         "on conflict (id) do nothing"), {"o": org})
        for table in ("prepared_content", "signal_conflicts", "pattern_fires",
                      "qualified_signals", "context_correlation_members", "source_events"):
            conn.execute(sql(f"delete from {table} where org_id = :o"), {"o": org})


@pg
def test_span_sources_resolve_both_spellings_of_the_reference(pg_store):
    """TWO SPELLINGS ARE IN CIRCULATION and both must resolve. `capture/pipeline` stamps
    `prepared_content:<prepared_content_id>`; `context/lifecycle/contract` and doc 08 use
    `prepared_content:<event_id>`. A resolver that knew one of them would grade half the corpus as
    unverifiable, and WHICH half would depend on the lane that captured it — a 50% acceptance row
    with no visible cause."""
    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import gather_span_sources

    _fresh(pg_store, ORG_PG)
    with pg_store.engine.begin() as conn:
        conn.execute(sql(
            "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
            "values (:e, :o, :p, :t)"),
            {"e": "evt_pc_1", "o": ORG_PG, "p": "pc_1", "t": SOURCE})

    with pg_store.engine.connect() as conn:
        found = gather_span_sources(conn, ORG_PG, ["prepared_content:evt_pc_1",
                                                   "prepared_content:pc_1",
                                                   "prepared_content:nothing",
                                                   "chunk:doc_1:4"])
    assert found["prepared_content:evt_pc_1"] == SOURCE
    assert found["prepared_content:pc_1"] == SOURCE
    assert "prepared_content:nothing" not in found
    assert "chunk:doc_1:4" not in found, (
        "there is no chunk store at Layer 2; a frame we cannot resolve falls back to L1's verdict "
        "rather than being answered wrongly")


@pg
def test_the_seam_read_grades_its_spans_against_the_stored_source(pg_store):
    """`gather_l1_signals` — the one production reader of `qualified_signals` — now returns
    RECEIPTS. Two signals on one correlation: one quoting the email truthfully, one quoting a
    sentence nobody wrote, and the second carrying `verified=True` anyway."""
    import json

    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import gather_l1_signals

    _fresh(pg_store, ORG_PG)
    correlation = "corr_pg_grade"
    with pg_store.engine.begin() as conn:
        # A disagreement the top signal took part in. Seeded HERE, on the seam read, because the
        # builder-level test constructs its `L1Signals` directly and therefore cannot prove that
        # the reader turns Layer 1's POINTERS into records at all.
        conn.execute(sql(
            "insert into signal_conflicts (conflict_id, org_id, signal_id, field, subject_key, "
            " claims, resolution, event_ids) values (:c, :o, 'sig_grade_0', 'amount', "
            " 'deal:acme', cast(:cl as jsonb), 'resolved_by_authority', cast(:ev as jsonb)) "
            "on conflict (conflict_id) do nothing"),
            {"c": "cft_seam_1", "o": ORG_PG, "cl": '[{"v": 1}, {"v": 2}]',
             "ev": '["evt_grade_0"]'})
        for index, (quote, importance) in enumerate(
                ((QUOTE, 8_100), ("we are pausing until Q3", 6_000))):
            event = f"evt_grade_{index}"
            conn.execute(sql(
                "insert into source_events (event_id, org_id, connection_id, source, "
                " object_type, source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, 'conn', 'gmail', 'email_message', :e, :e, '{}'::jsonb, :t) "
                "on conflict (event_id) do nothing"),
                {"e": event, "o": ORG_PG, "t": NOW})
            conn.execute(sql(
                "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text)"
                " values (:e, :o, :p, :t)"),
                {"e": event, "o": ORG_PG, "p": f"pc_{index}", "t": SOURCE})
            conn.execute(sql(
                "insert into context_correlation_members (org_id, correlation_id, event_id) "
                "values (:o, :c, :e)"), {"o": ORG_PG, "c": correlation, "e": event})
            start = SOURCE.index(quote) if quote in SOURCE else 0
            conn.execute(sql(
                "insert into qualified_signals (signal_id, org_id, event_id, trace_id, "
                " signal_type, importance_bp, importance_version, confidence_bp, visibility, "
                " extraction_ref, evidence_refs, conflict_ids, coverage_ready, state, "
                " occurred_at) values "
                "(:s, :o, :e, :e, 'commitment_made', :i, 'alg17.v2', 7000, "
                " '{\"scope\": \"org\"}'::jsonb, :x, cast(:ev as jsonb), "
                " cast(:cf as jsonb), :cr, 'active', :t)"),
                {"s": f"sig_grade_{index}", "o": ORG_PG, "e": event, "i": importance,
                 "x": f"l1x_{index}", "t": NOW,
                 "cf": '["cft_seam_1"]' if index == 0 else "[]",
                 "cr": True if index == 0 else None,
                 "ev": json.dumps([{"source_ref": f"prepared_content:{event}", "quote": quote,
                                    "start_offset": start, "end_offset": start + len(quote),
                                    "verified": True}])})

    with pg_store.engine.connect() as conn:
        l1 = gather_l1_signals(conn, ORG_PG, correlation)

    assert l1 is not None
    assert l1.span_count == 2 and l1.verified_span_count == 1, (
        "one of these two sentences is not in the email; Layer 1's flag says both are")
    verified = [span for span in l1.evidence if span["verified"]]
    assert verified[0]["quote"] == QUOTE
    assert verified[0]["verification"] == VERIFICATION_REVERIFIED
    assert l1.evidence[0]["verified"] is True, "the receipt that resolves must lead"
    assert l1.signal_types == ("commitment_made",)

    # The pointers became RECORDS on the same read — Layer 3 may not reach past Layer 2 to
    # resolve them, so a conflict that arrives as an id alone arrives nowhere.
    assert l1.conflict_ids == ("cft_seam_1",)
    assert [c["field"] for c in l1.conflicts] == ["amount"]
    assert l1.conflicts[0]["resolution"] == "resolved_by_authority"

    # And Layer 1's coverage verdict is CARRIED off the signal that set the score, never
    # re-derived here (doc 08's addition list).
    assert l1.coverage_ready is True


@pg
def test_conflicts_are_read_as_records_from_the_table_layer_one_writes(pg_store):
    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import gather_conflicts

    _fresh(pg_store, ORG_PG)
    with pg_store.engine.begin() as conn:
        conn.execute(sql(
            "insert into signal_conflicts (conflict_id, org_id, signal_id, field, subject_key, "
            " claims, resolution, resolved_value, event_ids) values "
            "(:c, :o, :s, 'amount', 'deal:acme', cast(:cl as jsonb), "
            " 'unresolved_surface_both', cast(:rv as jsonb), cast(:ev as jsonb))"),
            {"c": "cft_pg_1", "o": ORG_PG, "s": "sig_grade_0",
             "cl": '[{"value": 8400000}, {"value": 9000000}]', "rv": "null",
             "ev": '["evt_grade_0", "evt_grade_1"]'})

    with pg_store.engine.connect() as conn:
        records = gather_conflicts(conn, ORG_PG, ["cft_pg_1", "cft_missing"])

    assert set(records) == {"cft_pg_1"}
    record = records["cft_pg_1"]
    assert record["field"] == "amount" and record["claim_count"] == 2
    assert record["event_ids"] == ["evt_grade_0", "evt_grade_1"]
    assert "detected_at" not in record, "a clock here re-mints every package on every sweep"


@pg
def test_an_activated_fire_outranks_a_shadow_one_on_the_same_anchor(pg_store):
    """Two patterns can match one anchor. WHICH names the situation must be decided by a stated
    rule — activated, then strength, then recency, then id — and not by whichever row Postgres
    returned first: an order that is not stable between two reads of an unchanged database flips a
    BSO's content address on a sweep that changed nothing."""
    from datetime import timedelta

    from sqlalchemy import text as sql

    from genios_engine.context.situation_bso import gather_pattern_fires

    _fresh(pg_store, ORG_PG)
    with pg_store.engine.begin() as conn:
        for fire_id, pattern, strength, activated, at in (
                ("fire_a", "renewal_at_risk", 9_000, False, NOW),
                ("fire_b", "unowned_subscription", 6_000, True, NOW - timedelta(days=1))):
            conn.execute(sql(
                "insert into pattern_fires (fire_id, org_id, pattern_id, pattern_version, "
                " anchor_node_id, anchor_node_type, situation_type, match_strength_bp, "
                " activated, evidence, evaluated_at) values "
                "(:f, :o, :p, 1, 'node_acme', 'company', :p, :m, :a, "
                " cast(:ev as jsonb), :t)"),
                {"f": fire_id, "o": ORG_PG, "p": pattern, "m": strength, "a": activated,
                 "t": at, "ev": '[{"index": 0, "kind": "fact", "field": "deal.stage"}]'})

    with pg_store.engine.connect() as conn:
        fires = gather_pattern_fires(conn, ORG_PG, ["node_acme", "node_nothing"])

    assert set(fires) == {"node_acme"}, "an anchor nothing matched is ABSENT, never empty"
    assert fires["node_acme"].pattern_id == "unowned_subscription", (
        "a stronger SHADOW match outranked an activated one — activation is the tenant's own "
        "statement that a pattern has earned the right to name a situation")
    assert fires["node_acme"].activated is True
    assert fires["node_acme"].matched_conditions[0]["field"] == "deal.stage"


# =================================================================================================
# THE REAL PATH — one email through the production door, out the other side as a quoted receipt
# =================================================================================================

@pg
def test_the_production_reasoning_pass_publishes_a_quoted_receipt(pg_store, monkeypatch):
    """**"A test calls it" is not a caller.** Everything above proves the units; this proves the
    PATH: `run_sync` (the sync door) -> `context/runner.process_pending` (the drain) ->
    `reason/runner.run_all` -> `domain_shadow.shadow_compile` -> `build_business_situation`. The
    only thing constructed by hand is the mailbox and the model.

    What it asserts is the acceptance row and the group gate row together, on an object built by
    production code from an email nobody hand-shaped: a verified span carrying a sentence out of
    the email, and six confidence axes.
    """
    from sqlalchemy import text as sql

    from genios_engine.platform.activation import activate_semantic
    from genios_engine.reason import domain_shadow, runner
    from tests.test_l2_reads_what_l1_publishes import _capture, _drain

    org = "l2_publisher_live"
    url = pg_store.engine.url.render_as_string(hide_password=False)
    with pg_store.engine.begin() as conn:
        conn.execute(sql("delete from l1_semantic_activation where org_id = :o"), {"o": org})
    try:
        _capture(url, pg_store, org, monkeypatch, object_id="msg_publisher_1")
        drained = _drain(pg_store, org)
        assert drained["situation_rows"] >= 1, f"the drain built no situation: {drained}"

        # A SHADOW pattern fire on the situation's own anchor, so the fire reader is on the path
        # too. Written after the drain because the anchor is minted by it — and left unactivated,
        # which is what makes this the migration rule's own test: the fire must reach the BSO's
        # metadata (H8's per-condition-evidence row) and must NOT rename the situation.
        with pg_store.engine.begin() as conn:
            anchor = conn.execute(sql(
                "select anchor_node_id from context_situations where org_id = :o "
                "and anchor_node_id is not null order by situation_id limit 1"),
                {"o": org}).scalar()
            assert anchor, "the drain built no anchored situation to hang a pattern on"
            # The anchor is a freshly minted node id on every run of this file, so a fire keyed on
            # anything but the anchor would be inserted once and then skipped by its own
            # `on conflict` for ever — pointing at last run's node while this run reads a new one.
            conn.execute(sql("delete from pattern_fires where org_id = :o"), {"o": org})
            conn.execute(sql(
                "insert into pattern_fires (fire_id, org_id, pattern_id, pattern_version, "
                " anchor_node_id, anchor_node_type, situation_type, match_strength_bp, "
                " activated, evidence, evaluated_at) values "
                "(:f, :o, 'renewal_at_risk', 2, :a, 'company', 'renewal_at_risk', 7200, false, "
                " cast(:ev as jsonb), :t) on conflict do nothing"),
                {"f": f"fire_{anchor}", "o": org, "a": anchor, "t": NOW,
                 "ev": '[{"index": 0, "kind": "fact", "field": "subscription.auto_renew", '
                       '"value": false}]'})

        # The seam is a ROW, not a flag — the build order's activation rule. Without it
        # `run_all` never enters the compile and this test would prove nothing about anybody.
        activate_semantic(pg_store.engine, org, by="founder@genios.test",
                          notes="X8: the situation publisher on QES input")

        seen: list = []
        real = domain_shadow.build_business_situation

        def _spy(**kwargs):
            bso = real(**kwargs)
            seen.append(bso)
            return bso

        monkeypatch.setattr(domain_shadow, "build_business_situation", _spy)
        runner.run_all(org_id=org, store=pg_store, eval_time=NOW)
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from l1_semantic_activation where org_id = :o"), {"o": org})

    assert seen, "the reasoning pass published no BusinessSituationObject at all"
    scored = [b for b in seen if b.metadata.get("importance_source") == "l1_qualified_signals"]
    assert scored, "no situation reached Layer 3 carrying Layer 1's verdict"

    quoted = [b for b in scored if b.metadata["evidence_verified_spans"] >= 1]
    assert quoted, (
        "every situation published without a single verified evidence span — the acceptance row "
        f"is 100%. Spans seen: {[b.metadata['evidence_spans'] for b in scored]}")

    bso = quoted[0]
    receipt = next(e for e in bso.evidence if e.get("verified"))
    assert receipt["quote"].strip(), "a verified span with no sentence in it"
    assert receipt["source"] == "l1_qualified_signal"
    assert receipt["verification"] == VERIFICATION_REVERIFIED, (
        "the source text is still in retention, so this must be OUR check and not a flag we "
        "inherited")

    # The group gate's second row, on the object the production pass built — which is the only
    # place it can be measured, because the select that feeds it lives in `domain_shadow`.
    vector = SituationConfidenceVector.from_record(bso.metadata["confidence_vector"])
    for axis in CONFIDENCE_AXES[:5]:
        assert getattr(vector, axis) != AXIS_UNKNOWN_BP, (
            f"axis {axis} arrived unassessed on the live path — the publisher can only carry what "
            "`_ACTIVE_SITUATIONS` selects")
    assert bso.importance_bp != DEFAULT_IMPORTANCE_BP
    assert bso.metadata["importance_fallback"] is False

    # The fire reached the object, through `domain_shadow`'s own bulk read — and did not rename
    # anything. Both halves matter: without the first, H8's per-condition-evidence row can never
    # be counted on a pilot; without the second, an unactivated pattern is already deciding
    # routing while the two detection paths are supposed to be running side by side.
    matched = [b for b in seen if b.metadata.get("pattern_id")]
    assert matched, (
        "no published situation carried the pattern fire sitting on its own anchor — the "
        "publisher can only carry what `domain_shadow` reads")
    assert matched[0].metadata["pattern_activated"] is False
    assert matched[0].metadata["matched_conditions"][0]["field"] == "subscription.auto_renew"
    assert matched[0].type != "renewal_at_risk", (
        "an unactivated fire renamed a live situation")
