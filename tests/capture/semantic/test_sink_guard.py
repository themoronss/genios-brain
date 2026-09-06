"""L1.4.5-U0 · THE SINK GUARD — the three untyped lanes, closed.

    pytest tests/capture/semantic/test_sink_guard.py -q

Two defects are pinned here, and they are the same defect seen from its two ends.

**D3 — the sink was bypassable.** `ExtractionResult` declares three fields whose own contract
docstring calls them "the three untyped lanes": `roles`, `relationships` and
`scheduling_proposals`, each `list[dict[str, Any]]`. Between the model and storage NOTHING asked
what the keys of those dicts were:

* the prompt invited invention — `schema_gen` rendered all three as
  `[{"<key>": "<any JSON value>"}]`, and `profiles.py` points the chat profile at
  `scheduling_proposals` and the transcript profile at `roles`, so two of the five registered
  profiles actively ask the model to fill an open object;
* the extractor kept every key it was given (`_open_lane_entries`: `{str(key): item for ...}`);
* the schema validator's S-2 checked only that the keys were STRINGS (`_Shape.MAPPING_LIST`),
  and S-3 — the membership rule, the reason W3 exists — was never applied to them at all.

So `roles: [{"deal_stage": "negotiation"}]` was a conforming extraction, cached permanently in
`l1_extraction_results`, with a field name no consumer reads and nothing anywhere recording that
it was seen. That is `context/extract/vocab.py`'s 268-invented-names failure restored intact,
one layer inside the unit built to prevent it.

**D6a — the discovery lane had no producer.** `capture_unclassified` was written, tested and
imported by nothing: `grep -rn capture_unclassified genios_engine/` returned its own definition
and its own `__all__`. The lane could not receive a row, so the vocabulary could not grow from
evidence, and the failure was invisible in exactly the way the open lane's own module docstring
warns about — nothing breaks when a discovery mechanism silently stops discovering.

The two are one fix. The point where the closed key set REFUSES a key is the natural producer
for the lane that exists to hold what the vocabulary has no word for, so the guard sifts the
three dicts and hands what it took out to `capture_unclassified`. The load-bearing assertion in
this file is `test_an_unknown_field_lands_in_the_open_lane_and_nowhere_else`: the refused name is
in the store and in the typed observation, and it is not in any dict on the result.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from genios_engine.capture.semantic.open_lane import InMemoryOpenLaneStore, canonical_kind
from genios_engine.capture.semantic.sink_guard import (REFUSED_KEY_CONFIDENCE_BP, WHOLE_ENTRY,
                                                       WHOLE_LANE, RefusedKey, guard_typed_sink,
                                                       sift_untyped_lanes)
from genios_engine.capture.semantic.vocabulary import (UNTYPED_LANES, untyped_lane_sets,
                                                       vocabulary_sets)
from genios_engine.capture.validate.schema import (ExtractionVocabulary, ValidationStage,
                                                   validate_extraction_schema)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (MAX_UNCLASSIFIED_PER_EXTRACTION, ExtractionResult,
                                                UnclassifiedObservation)

ORG = "org_sink_guard_tests"
EVENT = "evt_sink_guard"
SOURCE_REF = f"prepared_content:{EVENT}"

#: The substrate every probe in this file resolves against. Each phrase occurs exactly once, so a
#: verified grade is unambiguous and an UNVERIFIED grade means the text really is absent.
SOURCE = ("Priya introduced us to the fund and said they evaluate us this quarter. "
          "Any time next week works for the follow-up call. "
          "Procurement froze the budget until April.")


def _span(quote: str) -> EvidenceSpan:
    found = SOURCE.find(quote)
    assert found >= 0, f"{quote!r} is not in the source, so no span can point at it"
    return EvidenceSpan(source_ref=SOURCE_REF, quote=quote, start_offset=found,
                        end_offset=found + len(quote))


def _result(**overrides) -> ExtractionResult:
    """A minimal C-09. Provenance is required by the contract; the rest is what a test sets."""
    fields = dict(intent="inform", stance="neutral", model_snapshot="fake-model-1",
                  prompt_version="p1", schema_version="s1", extraction_profile="email",
                  input_tokens=10, output_tokens=5)
    fields.update(overrides)
    return ExtractionResult(**fields)


def _observation(kind: str, quote: str, *, confidence_bp: int = 9000) -> UnclassifiedObservation:
    return UnclassifiedObservation(proposed_kind=kind, description="the model noticed something",
                                   evidence=[_span(quote)], confidence_bp=confidence_bp)


@pytest.fixture
def store() -> InMemoryOpenLaneStore:
    return InMemoryOpenLaneStore()


def _guard(result: ExtractionResult, store: InMemoryOpenLaneStore, eval_time):
    return guard_typed_sink(result, org_id=ORG, event_id=EVENT, source_ref=SOURCE_REF,
                            source_text=SOURCE, eval_time=eval_time, store=store)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# D3 · the bypass, closed
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_an_unknown_field_lands_in_the_open_lane_and_nowhere_else(store, eval_time):
    """THE defect. A field name outside the closed key set reaches the discovery lane, the typed
    observation list — and NOT any dict on the result, which is the only place it used to go.

    Asserted over the serialised result rather than over the three fields by name, because the
    claim being made is about the whole object: the name is not in `roles`, and it is also not in
    a fourth lane somebody adds next year.
    """
    result = _result(roles=[{"party": "priya@fund.com", "role": "introducer",
                             "deal_stage": "negotiation",
                             "evidence_text": "Priya introduced us to the fund"}])

    guarded = _guard(result, store, eval_time)

    kept = guarded.result.roles
    assert kept == [{"party": "priya@fund.com", "role": "introducer",
                     "evidence_text": "Priya introduced us to the fund"}], kept

    lane_json = json.dumps([guarded.result.roles, guarded.result.relationships,
                            guarded.result.scheduling_proposals, guarded.result.field_confidence])
    assert "deal_stage" not in lane_json, lane_json

    rows = store.observations_for(org_id=ORG, event_id=EVENT)
    assert [row.proposed_kind for row in rows] == [canonical_kind("deal_stage")]
    assert rows[0].proposed_kind_raw == "deal_stage"
    assert [o.proposed_kind for o in guarded.result.unclassified_observations] == ["deal_stage"]


@pytest.mark.parametrize("lane, entry, unknown", [
    ("roles", {"party": "priya@fund.com", "role": "introducer", "deal_stage": "negotiation"},
     "deal_stage"),
    ("relationships", {"party": "priya@fund.com", "nature": "investor",
                       "check_size": "they evaluate us this quarter"}, "check_size"),
    ("scheduling_proposals", {"proposer": "us", "text": "Any time next week works",
                              "urgency": "Any time next week works"}, "urgency"),
])
def test_every_untyped_lane_is_sifted_not_just_the_first(store, eval_time, lane, entry, unknown):
    """All THREE lanes, one row each. A guard that closed `roles` and left the other two would
    pass any test written about the lane the author happened to think of first."""
    guarded = _guard(_result(**{lane: [entry]}), store, eval_time)

    assert unknown not in json.dumps(getattr(guarded.result, lane))
    assert [row.proposed_kind_raw for row in store.observations_for(org_id=ORG, event_id=EVENT)] \
        == [unknown]
    assert [refused.lane for refused in guarded.refused] == [lane]


def test_a_recognised_entry_is_returned_byte_identical(store, eval_time):
    """The guard is a sieve, never a rewriter. An entry using only declared keys must come back
    as it went in — a guard that reorders or re-types conforming data would change the content
    address of every extraction that has one."""
    entry = {"proposer": "us", "text": "Any time next week works",
             "evidence_text": "Any time next week works"}
    guarded = _guard(_result(scheduling_proposals=[entry]), store, eval_time)

    assert guarded.result.scheduling_proposals == [entry]
    assert guarded.refused == ()
    assert guarded.capture.rows == ()
    assert store.observations_for(org_id=ORG, event_id=EVENT) == ()


def test_an_entry_made_entirely_of_refused_keys_leaves_no_empty_object_behind(store, eval_time):
    """Every key refused means the entry said nothing the lane declares. The keys go to the open
    lane; what must NOT be left is `{}` — an empty object is a row every consumer iterates over
    and none can read, and it would make the lane look populated while carrying nothing."""
    guarded = _guard(_result(roles=[{"deal_stage": "negotiation"},
                                    {"party": "priya@fund.com", "role": "introducer"}]),
                     store, eval_time)

    assert guarded.result.roles == [{"party": "priya@fund.com", "role": "introducer"}]
    assert [refused.key for refused in guarded.refused] == ["deal_stage"]


def test_the_guarded_result_still_conforms_to_the_schema_validator(store, eval_time):
    """The thing that reaches storage is a typed `ExtractionResult` that passes S-1..S-9, not a
    dict the guard assembled. A sift that produced a conforming-looking object which the
    validator then refused would move the bypass rather than close it."""
    guarded = _guard(_result(roles=[{"party": "priya@fund.com", "role": "introducer",
                                     "deal_stage": "negotiation",
                                     "evidence_text": "Priya introduced us to the fund"}]),
                     store, eval_time)

    report = validate_extraction_schema(
        guarded.result, vocabulary=ExtractionVocabulary(**vocabulary_sets()),
        stage=ValidationStage.EXTRACTOR_OUTPUT)
    assert report.conforms, [str(v) for v in report.violations]


def test_a_refused_key_carrying_no_quotable_text_is_still_taken_out_and_named(store, eval_time):
    """`UnclassifiedObservation` refuses a receiptless observation — "the one thing this lane
    must not accumulate". So a key whose entry holds no text at all cannot become a row, and the
    guard must still REMOVE it and NAME it rather than pass it through for want of a receipt."""
    guarded = _guard(_result(roles=[{"party": "priya@fund.com", "role": "introducer",
                                     "priority_rank": 3}]), store, eval_time)

    assert guarded.result.roles == [{"party": "priya@fund.com", "role": "introducer"}]
    assert [r.key for r in guarded.unreceiptable] == ["priority_rank"]
    assert guarded.result.unclassified_observations == []
    assert store.observations_for(org_id=ORG, event_id=EVENT) == ()


def test_the_probe_quote_is_regraded_against_the_source_never_trusted(store, eval_time):
    """The guard mints a PROBE span (offsets 0..len, `verified=False`), exactly as the extractor
    does for a model that quoted well and counted badly. `capture_unclassified` re-grades it, so
    a real sentence stores RELOCATED and a fabricated one stores flagged — the guard never gets
    to assert that its own salvage was checked."""
    real = _guard(_result(roles=[{"party": "us", "role": "owner",
                                  "deal_stage": "Procurement froze the budget"}]), store,
                 eval_time)
    row = store.observations_for(org_id=ORG, event_id=EVENT)[0]
    assert row.verified is True
    assert row.span_verdict == "verified_relocated"
    assert row.start_offset == SOURCE.find("Procurement froze the budget")
    assert real.result.unclassified_observations[0].evidence[0].verified is False

    invented = InMemoryOpenLaneStore()
    guard_typed_sink(_result(roles=[{"party": "us", "role": "owner",
                                     "deal_stage": "a sentence nobody wrote"}]),
                     org_id=ORG, event_id=EVENT, source_ref=SOURCE_REF, source_text=SOURCE,
                     eval_time=eval_time, store=invented)
    flagged = invented.observations_for(org_id=ORG, event_id=EVENT)[0]
    assert flagged.verified is False and flagged.span_verdict == "unverified"


def test_the_entrys_own_receipt_is_preferred_over_the_refused_value(store, eval_time):
    """`evidence_text` is the receipt convention every one of the three lanes carries. When the
    entry has one, the probe cites THAT — the refused value is a label, and citing a label as
    though it were source text is the fabrication the lane is supposed to detect."""
    _guard(_result(relationships=[{"party": "priya@fund.com", "nature": "investor",
                                   "check_size": "500k",
                                   "evidence_text": "they evaluate us this quarter"}]),
           store, eval_time)

    row = store.observations_for(org_id=ORG, event_id=EVENT)[0]
    assert row.quote == "they evaluate us this quarter"
    assert row.verified is True


def test_the_model_s_own_observations_survive_the_merge(store, eval_time):
    """The guard ADDS to the open lane; it does not replace it. A model that both noticed
    something and mis-keyed something must end with both, and the model's own noticing must come
    first so the cap's tie-break keeps it."""
    guarded = _guard(_result(unclassified_observations=[_observation("budget_freeze",
                                                                    "Procurement froze")],
                             roles=[{"party": "us", "role": "owner", "deal_stage": "Priya"}]),
                     store, eval_time)

    assert [o.proposed_kind for o in guarded.result.unclassified_observations] \
        == ["budget_freeze", "deal_stage"]


def test_a_salvaged_key_never_evicts_the_model_s_own_noticing_at_the_cap(store, eval_time):
    """`_most_significant` keeps the five most confident and the guard's salvage is scored at a
    flat, deliberately modest `REFUSED_KEY_CONFIDENCE_BP`. Five real observations plus one
    salvaged key must store the five real ones: a guard whose bookkeeping outranked the model's
    noticing would quietly turn a discovery lane into a defect log."""
    quotes = ["Priya introduced us", "they evaluate us", "next week works", "the follow-up call",
              "froze the budget"]
    assert len(quotes) == MAX_UNCLASSIFIED_PER_EXTRACTION
    observations = [_observation(f"kind_{i}", quote, confidence_bp=REFUSED_KEY_CONFIDENCE_BP + 1)
                    for i, quote in enumerate(quotes)]

    guarded = _guard(_result(unclassified_observations=observations,
                             roles=[{"party": "us", "role": "owner", "deal_stage": "Priya"}]),
                     store, eval_time)

    stored = {row.proposed_kind for row in store.observations_for(org_id=ORG, event_id=EVENT)}
    assert stored == {f"kind_{i}" for i in range(MAX_UNCLASSIFIED_PER_EXTRACTION)}
    assert guarded.capture.over_cap == 1


def test_the_sift_is_pure_and_idempotent(store, eval_time):
    """`sift_untyped_lanes` reads no clock, touches no store and calls no model, so a second pass
    over its own output must be a no-op. Idempotence is what makes the guard safe to place at a
    seam that may run twice — a replay, a repair retry, a re-drain."""
    once = sift_untyped_lanes(_result(roles=[{"party": "us", "role": "owner",
                                              "deal_stage": "Priya"}]), source_ref=SOURCE_REF)
    twice = sift_untyped_lanes(once.result, source_ref=SOURCE_REF)

    assert twice.refused == ()
    assert twice.result.roles == once.result.roles
    assert twice.result.unclassified_observations == once.result.unclassified_observations


def test_a_non_object_entry_is_refused_whole_rather_than_indexed_into(store, eval_time):
    """The contract's own `_open_lane_dicts` raises on a non-mapping entry, so one cannot arrive
    through the constructor — but `model_construct` and a rehydrated cache row both skip it, and
    the schema validator names those two routes for exactly this reason. The guard must survive
    the object it is defending against."""
    unchecked = ExtractionResult.model_construct(
        **{**{name: getattr(_result(), name) for name in ExtractionResult.model_fields},
           "roles": ["not an object", {"party": "us", "role": "owner"}]})

    guarded = _guard(unchecked, store, eval_time)

    assert guarded.result.roles == [{"party": "us", "role": "owner"}]
    assert [r.key for r in guarded.unreceiptable] == [WHOLE_ENTRY]
    assert [r.path for r in guarded.unreceiptable] == ["roles[0].<entry>"]


def test_a_lane_that_is_not_a_list_at_all_is_named_rather_than_silently_emptied(store, eval_time):
    """Same two unvalidated routes, one level up. A lane holding a bare object instead of a list
    has no entry to point at, so the record carries no index — and it must still be a RECORD.
    Returning an empty lane with nothing said would be the sink dropping data in silence, which
    is the shape of the defect, not a fix for it."""
    unchecked = ExtractionResult.model_construct(
        **{**{name: getattr(_result(), name) for name in ExtractionResult.model_fields},
           "relationships": {"party": "priya@fund.com", "nature": "investor"}})

    guarded = _guard(unchecked, store, eval_time)

    assert guarded.result.relationships == []
    assert [(r.entry_index, r.key, r.path) for r in guarded.refused] \
        == [(None, WHOLE_LANE, "relationships.<lane>")]
    assert guarded.unreceiptable == guarded.refused


def test_a_non_string_key_is_refused_under_the_name_it_is_probed_under(store, eval_time):
    """`extractor._open_lane_entries` stringifies keys, so a lane can legitimately arrive with
    `"5"` where the model wrote `5`. The guard normalises ONCE and reads everything off the
    normalised entry — refusing a key under its stringified name and then probing the entry under
    a name that entry does not have would lose the receipt for every such key."""
    unchecked = ExtractionResult.model_construct(
        **{**{name: getattr(_result(), name) for name in ExtractionResult.model_fields},
           "roles": [{"party": "us", "role": "owner", 5: "Procurement froze the budget"}]})

    guarded = _guard(unchecked, store, eval_time)

    assert [r.key for r in guarded.refused] == ["5"]
    assert guarded.unreceiptable == ()
    row = store.observations_for(org_id=ORG, event_id=EVENT)[0]
    assert row.proposed_kind_raw == "5" and row.quote == "Procurement froze the budget"


# ═════════════════════════════════════════════════════════════════════════════════════════════
# The closed key sets themselves
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_lane_key_sets_cover_exactly_the_three_untyped_lanes():
    """Named against the contract, not against a list in the guard. A fourth `list[dict]` field
    added to `ExtractionResult` must make this go red on the day it lands — an unguarded lane is
    the whole defect, and the newest field is the one nobody remembers to add."""
    from typing import Any, get_args, get_origin
    declared = tuple(name for name, field in ExtractionResult.model_fields.items()
                     if get_origin(field.annotation) is list
                     and get_args(field.annotation) == (dict[str, Any],))
    assert declared == UNTYPED_LANES
    assert tuple(sorted(untyped_lane_sets())) == tuple(sorted(UNTYPED_LANES))


@pytest.mark.parametrize("lane, key", [
    ("roles", "party"), ("roles", "role"), ("roles", "evidence_text"),
    ("relationships", "party"), ("relationships", "nature"), ("relationships", "direction"),
    ("relationships", "evidence_text"),
    ("scheduling_proposals", "proposer"), ("scheduling_proposals", "text"),
    ("scheduling_proposals", "evidence_text"),
])
def test_every_key_a_real_consumer_reads_is_in_the_closed_set(lane, key):
    """The sets are derived from what the shipping consumer actually reads off these lanes —
    `context/pipeline.py`, over the v1 extraction that carries the same three lane names — not
    invented here. A key a consumer reads but the set refuses would be the sink deleting working
    data: the opposite failure, and the more expensive one."""
    assert key in untyped_lane_sets()[lane]


# ═════════════════════════════════════════════════════════════════════════════════════════════
# D6a · the discovery lane has a producer
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_open_lane_has_a_producer_in_the_shipped_tree():
    """`capture_unclassified` must be CALLED by shipping code, not only defined and exported.

    This is D6a as a property of the source tree, asserted with `ast` the way
    `test_import_graph.py` asserts the fence around the same module — no imports executed. Before
    the sink guard landed, `grep -rn capture_unclassified genios_engine/` returned the definition,
    a docstring and an `__all__` entry: the discovery table could not receive a row, so the
    vocabulary could not grow from evidence, and NOTHING failed while that was true. A lane with
    no producer is the one defect in this subsystem that raises no alarm of its own, so it gets
    an assertion of its own.
    """
    root = Path(__file__).resolve().parents[3] / "genios_engine"
    callers = set()
    for py in root.rglob("*.py"):
        if py.name == "open_lane.py":
            continue                       # its own definition is not a call site
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "capture_unclassified"):
                callers.add(str(py.relative_to(root.parent)))
    assert callers, ("nothing in genios_engine/ calls capture_unclassified — the open lane cannot "
                     "receive a row, and a discovery mechanism that stops discovering breaks "
                     "nothing and reports nothing")
    assert "genios_engine/capture/semantic/sink_guard.py" in callers, callers


def test_the_extractor_has_actually_taken_the_wiring_seam():
    """The seam this module's docstring names is TAKEN, and both statements say the same thing.

    REWRITTEN. The earlier version of this row asserted the opposite fact — that
    `_run_calls` still contained the bare `return parsed.result` — because when it was written
    the guard could not wire itself (`extractor.py` belongs to another unit) and the honest thing
    to pin was the seam's location. Kept unchanged it would now be an assertion that the fix has
    NOT landed: the guard's only caller was itself uncalled, so `capture_unclassified` still had
    no reachable producer and the discovery table still could not receive a row from a real
    extraction. That is a test encoding a bug, so it is inverted rather than deleted — the seam
    is still pinned, it is just pinned to the wired line instead of the unwired one.
    """
    import inspect

    from genios_engine.capture.semantic import extractor, sink_guard

    named = inspect.getdoc(sink_guard) or ""
    assert "_run_calls" in named, "the guard no longer says where it is called from"

    source = inspect.getsource(extractor._run_calls)
    assert "if parsed.usable and parsed.result is not None:\n            return _guarded(" \
        in source, ("the extractor returns a parsed result without passing it through the sink "
                    "guard; the three untyped lanes are open again")
    assert "return parsed.result" not in source, (
        "an unguarded return survives in _run_calls — one of the two paths still caches the "
        "unsifted dicts")

    guarded = inspect.getsource(extractor._guarded)
    assert "sift_untyped_lanes" in guarded and "guard_typed_sink" in guarded, (
        "the store-less path must still CLOSE the lanes; only the keeping of refused names is "
        "conditional on there being a store")


def test_a_refused_key_record_names_where_it_came_from():
    """`RefusedKey` is a typed record, not a string. The lane, the entry index and the key are
    the three things a reviewer needs to find the prompt that produced it."""
    refused = RefusedKey(lane="roles", entry_index=2, key="deal_stage",
                         reason="not in the closed key set for roles")
    assert (refused.lane, refused.entry_index, refused.key) == ("roles", 2, "deal_stage")
