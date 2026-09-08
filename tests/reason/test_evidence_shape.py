"""Group L4.3 gate, half one — S1 (Finding as THE emission) and S2 (one builder, one seed).

Doc 03's acceptance rows tested here:

    evidence id identical across all three lanes for one fact ....... exact
    Findings carrying a resolvable unit_ref ......................... 100%

Both are proved against the REAL lanes. "The lane I refactored agrees with itself" is not the
claim; the claim is that the composition lane, the legacy adapter and the native adapter now
answer with the same identity for one fact, and that is only meaningful if all three are driven.
"""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    EvidenceRef,
    Finding,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ResultStatus,
    unit_ref,
)
from genios_engine.platform.canonical import canonicalize, decanonicalize
from genios_engine.reason import composer
from genios_engine.reason.adapters import legacy_context, native
from genios_engine.reason.engine import NodeContext
from genios_engine.reason.evidence import (
    EVIDENCE_SEED_VERSION,
    RENDERED_TEXT_CAP,
    UNOBSERVED,
    build_evidence_ref,
    canonical_evidence_id_for,
    digest_row,
    digest_set_hash,
    digests_for_payload,
    emissions,
    evidence_id,
    neighborhood_ref,
    observed_at_key,
    rendered_text,
    unit_refs_by_evidence,
    value_digest,
)
from genios_engine.reason.rules import Rule

NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
OBSERVED = NOW - timedelta(hours=3)

#: The ONE fact all three lanes are handed. Same tenant, same entity, same field name, same
#: source record, same observation time — which is the entire definition of "the same fact".
#:
#: It carries NO observation time, and that is fidelity rather than convenience: the composition
#: lane reads `signals` rows that have no per-observation timestamp to offer, so a fixture that
#: gave one to the other two lanes would be testing a fact the composition lane cannot ever
#: produce. `observed_at`'s effect on the identity is proved separately, one test below.
ORG = "org_z2"
ENTITY = "deal_1"
FIELD = "signals.open"
SOURCE = "sig_1"


# ── S2 · one builder, one seed, three lanes ──────────────────────────────────────────────

def _legacy_lane_id() -> str:
    rule = Rule(id="r_open", level="prescriptive", scope="deal",
                when=[{"has_obs": "signal"}], urgency={"type": "elapsed", "h": 24},
                reason_code="open_signal", evidence_fields=["signals.open"])
    context = NodeContext(
        node_id=ENTITY, node_type="deal",
        facts={FIELD: {"value": {"signal_id": SOURCE, "score": 70},
                       "source_ref_id": SOURCE,
                       "fact_version_id": "rrun_legacy", "confidence_bp": 7_000}},
        obs=[], neighbor_facts={}, neighbor_obs=set(), edge_count=0, baselines={})
    snapshot = legacy_context.legacy_context_snapshot(
        org_id=ORG, context=context, rule=rule, evaluation_time=NOW)
    return snapshot.evidence[0].evidence_id


def _native_lane_id() -> str:
    capability = CapabilityManifest(
        capability_id="test.signals", version="1.0.0", domain="test", root_entity_type="deal",
        goal=Goal(goal_id="g", statement="Read one fact."),
        reasoners=(ReasonerSpec(reasoner_id="core.context", version="1.0.0"),),
        plays=(PlayDefinition(play_id="p", version="1.0.0", label="P", steps=("one",)),),
        required_fields=(FIELD,), policies=(), live_delivery_enabled=False,
        metadata={"context_selector": {"root": [FIELD]}})
    context = NodeContext(
        node_id=ENTITY, node_type="deal",
        facts={FIELD: {"value": {"signal_id": SOURCE, "score": 70},
                       "source_ref_id": SOURCE,
                       "fact_version_id": "rrun_native", "confidence_bp": 9_000,
                       "authority_rank": 3}},
        obs=[], neighbor_facts={}, neighbor_obs=set(), edge_count=0, baselines={})
    snapshot = native.native_context_snapshot(
        org_id=ORG, context=context, capability=capability, evaluation_time=NOW, graph_version=1)
    return snapshot.evidence[0].evidence_id


def _composition_lane_id() -> str:
    member = {"signal_id": SOURCE, "reasoning_run_id": "rrun_composed",
              "score_inputs": {"C": 70}, "reason_code": "open_signal"}
    refs = composer.composite_evidence(org_id=ORG, deal_id=ENTITY, members=(member,))
    return refs[0].evidence_id


def test_one_fact_routed_through_all_three_lanes_yields_exactly_one_evidence_id():
    """The K2 gate row. Before this wave these were three different strings.

    They differed by lineage the lanes happened to have to hand — `reasoning_run_id` here, a
    `value_hash` there, a `partition` in the third — and none of that is identity. Rule 11 raises
    confidence only across independence groups derived from source identity, so two ids for one
    observation is a route to confidence RISING on a duplicate, which Law 4 forbids.
    """
    ids = {_legacy_lane_id(), _native_lane_id(), _composition_lane_id()}

    assert len(ids) == 1, f"three lanes still disagree on one fact's identity: {sorted(ids)}"
    assert ids == {evidence_id(org_id=ORG, entity_ref=ENTITY, field=FIELD,
                               source_ref=SOURCE, observed_at=None)}


def test_no_lane_keeps_a_private_evidence_seed():
    """Structural, and deliberately so: the bug was three call sites, not three wrong values.

    A fourth lane added next quarter that mints its own `stable_id("evidence", ...)` re-opens
    exactly this hole, and it would pass every behavioural test above because those only drive
    the three lanes that exist today.
    """
    for module in (composer, legacy_context, native):
        source = inspect.getsource(module)
        assert 'stable_id("evidence"' not in source, (
            f"{module.__name__} mints an evidence id outside build_evidence_ref")
        assert "build_evidence_ref" in source


def test_the_identity_survives_the_value_changing_and_moves_when_the_source_does():
    """An id that moves with the value is a version, not an identity.

    That was the legacy and native seeds' `value_hash`: re-reading a fact that had changed
    produced a brand new id, so "have we already said this?" — the question suppression is built
    on — could never be answered yes.
    """
    first = build_evidence_ref(org_id=ORG, entity_ref=ENTITY, field=FIELD, value="open",
                               source_ref=SOURCE, observed_at=OBSERVED)
    moved = build_evidence_ref(org_id=ORG, entity_ref=ENTITY, field=FIELD, value="closed",
                               source_ref=SOURCE, observed_at=OBSERVED)
    other_source = build_evidence_ref(org_id=ORG, entity_ref=ENTITY, field=FIELD, value="open",
                                      source_ref="sig_2", observed_at=OBSERVED)
    other_org = build_evidence_ref(org_id="org_other", entity_ref=ENTITY, field=FIELD,
                                   value="open", source_ref=SOURCE, observed_at=OBSERVED)
    later = build_evidence_ref(org_id=ORG, entity_ref=ENTITY, field=FIELD, value="open",
                               source_ref=SOURCE, observed_at=OBSERVED + timedelta(minutes=1))

    assert first.evidence_id == moved.evidence_id
    assert len({first.evidence_id, other_source.evidence_id,
                other_org.evidence_id, later.evidence_id}) == 4


def test_a_neighbour_reading_is_not_the_same_fact_as_the_root_reading():
    """Dropping `partition` from the seed must not collapse two genuinely different claims.

    It does not, because the neighbour reading is a claim about a different ENTITY — the 1-hop
    neighbourhood — and `build_evidence_ref` says so through `entity_ref` rather than through a
    sixth seed component the other two lanes would have to know to reproduce.
    """
    root = build_evidence_ref(org_id=ORG, entity_ref=ENTITY, field=FIELD, value="open",
                              source_ref=SOURCE, observed_at=OBSERVED)
    neighbour = build_evidence_ref(org_id=ORG, entity_ref=ENTITY, field=FIELD, value="open",
                                   source_ref=SOURCE, observed_at=OBSERVED,
                                   context_scope="neighbor")

    assert root.evidence_id != neighbour.evidence_id
    assert neighbour.evidence_id == evidence_id(
        org_id=ORG, entity_ref=neighborhood_ref(ENTITY), field=FIELD,
        source_ref=SOURCE, observed_at=OBSERVED)
    assert neighborhood_ref(neighborhood_ref(ENTITY)) == neighborhood_ref(ENTITY)


def test_an_unobserved_fact_is_not_a_fact_observed_at_the_epoch():
    assert observed_at_key(None) == UNOBSERVED
    assert observed_at_key("  ") == UNOBSERVED
    assert observed_at_key(datetime(1970, 1, 1, tzinfo=timezone.utc)) != UNOBSERVED


def test_two_spellings_of_one_instant_are_one_identity():
    """`...Z`, `...+00:00` and a naive datetime all mean the same moment to every writer here."""
    assert observed_at_key("2026-09-05T12:00:00Z") == observed_at_key("2026-09-05T12:00:00+00:00")
    assert observed_at_key(datetime(2026, 9, 5, 12)) == observed_at_key(
        datetime(2026, 9, 5, 12, tzinfo=timezone.utc))
    assert observed_at_key(datetime(2026, 9, 5, 17, 30,
                                    tzinfo=timezone(timedelta(hours=5, minutes=30)))) == (
        observed_at_key(datetime(2026, 9, 5, 12, tzinfo=timezone.utc)))


def test_the_seed_version_is_inside_the_hash():
    """So a v2 id can never collide with the pre-0117 id it replaces — which is what makes
    `reasoning_evidence_id_map` unambiguous in exactly the cases it exists for."""
    from genios_engine.platform.canonical import stable_id

    expected = stable_id("evidence", {
        "seed_version": EVIDENCE_SEED_VERSION, "org_id": ORG, "entity_ref": ENTITY,
        "field": FIELD, "source_ref": SOURCE, "observed_at_key": observed_at_key(OBSERVED)})

    assert evidence_id(org_id=ORG, entity_ref=ENTITY, field=FIELD, source_ref=SOURCE,
                       observed_at=OBSERVED) == expected


def test_the_builder_refuses_an_identity_it_cannot_form():
    with pytest.raises(ValueError):
        build_evidence_ref(org_id="", entity_ref=ENTITY, field=FIELD, value=1)
    with pytest.raises(ValueError):
        build_evidence_ref(org_id=ORG, entity_ref="", field=FIELD, value=1)
    with pytest.raises(ValueError):
        build_evidence_ref(org_id=ORG, entity_ref=ENTITY, field=FIELD, value=1,
                           context_scope="sideways")


def test_the_canonical_id_is_recoverable_from_a_stored_ref():
    """This is what makes the historic migration COMPLETE rather than best-effort: every seed
    component can be read back off a payload that was written years ago."""
    ref = build_evidence_ref(org_id=ORG, entity_ref=ENTITY, field=FIELD, value="open",
                             source_ref=SOURCE, observed_at=OBSERVED, context_scope="neighbor")
    stored = decanonicalize(json.loads(json.dumps(canonicalize(ref))))

    assert canonical_evidence_id_for(org_id=ORG, root_entity_id=ENTITY,
                                     ref=stored) == ref.evidence_id
    assert canonical_evidence_id_for(org_id=ORG, root_entity_id=ENTITY,
                                     ref=ref) == ref.evidence_id


# ── S1 · Finding as THE per-unit emission ────────────────────────────────────────────────

def _result(reasoner_id: str, *findings: Finding, evidence_ids: tuple[str, ...] = ()
            ) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1.0.0",
                          status=ResultStatus.COMPLETED, findings=findings,
                          evidence_ids=evidence_ids)


def test_every_finding_on_a_real_run_has_a_resolvable_unit_ref():
    """The K2 100% row, driven through the orchestrator rather than a hand-built result list.

    `emissions()` membership-CHECKS every pair, so a finding whose unit cannot be resolved does
    not produce a wrong answer here — it raises. The assertion is therefore that the run happened
    at all, plus that the emission count equals the finding count with nothing quietly dropped.
    """
    from genios_engine.contracts.reasoning import ExecutionMode, ReasoningRequest
    from genios_engine.packs.capabilities import DEAL_COOLING_V1
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.reasoners import default_registry

    from .test_store_replay import NOW as RUN_TIME, deal_cooling_context

    execution = ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id=ORG, capability=DEAL_COOLING_V1, context=deal_cooling_context(),
        evaluation_time=RUN_TIME, trigger_kind="email.received", trigger_ref="event_1",
        mode=ExecutionMode.LIVE, config_snapshot_id=None))
    results = list(execution.ordered_results)
    total_findings = sum(len(result.findings) for result in results)

    observed = emissions(results)

    assert total_findings > 0, "a run with no findings cannot prove a 100% unit_ref rate"
    assert len(observed) == total_findings
    assert all(item.unit_ref for item in observed)
    assert {item.unit_ref for item in observed} <= {item.reasoner_id for item in results}
    # And every evidence id any unit leaned on resolves to at least one unit.
    by_evidence = unit_refs_by_evidence(results)
    cited = {identifier for result in results
             for finding in result.findings for identifier in finding.evidence_ids}
    cited |= {identifier for result in results for identifier in result.evidence_ids}
    assert set(by_evidence) == cited
    assert all(refs for refs in by_evidence.values())


def test_a_unit_ref_that_names_a_unit_which_did_not_emit_the_finding_is_refused():
    mine = Finding(finding_id="f_1", kind="deal_cooling", matched=True)
    theirs = Finding(finding_id="f_2", kind="deal_warming", matched=True)
    result = _result("core.timeline", mine)

    assert unit_ref(result, mine) == "core.timeline"
    with pytest.raises(ValueError, match="was not emitted by"):
        unit_ref(result, theirs)


def test_the_emission_carries_the_magnitude_when_the_finding_measured_one():
    """Globe's third column. A predicate finding has no magnitude and must not be given a 0 —
    "measured nothing" and "found nothing" are different claims."""
    measured = Finding(finding_id="f_drop", kind="engagement_drop", matched=True,
                       value_bp=-2_500, evidence_ids=("ev_1",))
    predicate = Finding(finding_id="f_holds", kind="constraint_holds", matched=True,
                        evidence_ids=("ev_1",))
    observed = emissions([_result("core.impact", measured, predicate)])

    assert {item.finding_id: item.value_bp for item in observed} == {
        "f_drop": -2_500, "f_holds": None}
    assert [item.finding_id for item in observed] == ["f_drop", "f_holds"]


def test_two_units_that_read_one_fact_both_appear_on_it():
    """Which is the whole reason the column is a list. A digest that named only the last unit to
    touch a fact would answer "who saw this" with a coin flip."""
    a = _result("core.timeline", Finding(finding_id="f_a", kind="slip", evidence_ids=("ev_1",)))
    b = _result("core.risk", Finding(finding_id="f_b", kind="exposure",
                                     evidence_ids=("ev_1", "ev_2")))

    assert unit_refs_by_evidence([b, a]) == {
        "ev_1": ("core.risk", "core.timeline"), "ev_2": ("core.risk",)}


def test_emission_order_does_not_depend_on_execution_order():
    """It feeds a content-addressed stamp; a hash that moved because a unit ran in a different
    position would be a false tamper alarm, not a signal."""
    a = _result("core.timeline", Finding(finding_id="f_a", kind="slip"))
    b = _result("core.risk", Finding(finding_id="f_b", kind="exposure"))

    assert [item.finding_id for item in emissions([a, b])] == (
        [item.finding_id for item in emissions([b, a])])


# ── S3's pure half: the digest shape ─────────────────────────────────────────────────────

def test_the_permanent_row_is_bounded_at_120_characters():
    row = digest_row(EvidenceRef("ev_long", "deal.notes", "x" * 5_000))

    assert len(row["rendered_text"]) == RENDERED_TEXT_CAP
    assert row["rendered_text"].endswith("…")
    assert len(rendered_text("f", "short")) <= RENDERED_TEXT_CAP


def test_the_rendered_claim_is_re_readable_a_year_later():
    row = digest_row(EvidenceRef("ev_renewal", "deal.renewal_date", "2027-03-03"))

    assert row["rendered_text"] == "deal.renewal_date=2027-03-03"


def test_the_digest_survives_a_canonical_round_trip_through_the_database():
    """The whole S3 verification story rests on this: digests re-derived from a payload that has
    been through JSONB must equal the ones minted from the in-memory contract, or the
    payload-lives cross-check would fire constantly and be switched off."""
    payload = {"evidence": [
        EvidenceRef("ev_a", "deal.status", "open", source_ref_id="crm_1", occurred_at=OBSERVED),
        EvidenceRef("ev_b", "derived.engagement", 4_000)]}
    stored = decanonicalize(json.loads(json.dumps(canonicalize(payload))))

    assert digests_for_payload(payload) == digests_for_payload(stored)
    assert [row["evidence_id"] for row in digests_for_payload(payload)] == ["ev_a", "ev_b"]


def test_the_set_hash_is_bound_to_the_payload_it_was_minted_from():
    """So a verified-looking digest set cannot be transplanted onto another snapshot."""
    rows = digests_for_payload({"evidence": [EvidenceRef("ev_a", "deal.status", "open")]})

    assert digest_set_hash(payload_hash="a" * 64, rows=rows) != digest_set_hash(
        payload_hash="b" * 64, rows=rows)


def test_one_edited_character_moves_the_row_hash():
    row = digest_row(EvidenceRef("ev_a", "deal.status", "open"))
    tampered = {**row, "rendered_text": "deal.status=closed"}

    assert value_digest("open") != value_digest("closed")
    assert digest_set_hash(payload_hash="a" * 64, rows=[row]) == digest_set_hash(
        payload_hash="a" * 64, rows=[row])
    assert digest_row(EvidenceRef("ev_a", "deal.status", "closed"))["digest_hash"] != (
        row["digest_hash"])
    assert tampered["digest_hash"] == row["digest_hash"], (
        "the row hash is stored, not recomputed — which is why the store re-derives it on read")


def test_a_payload_with_two_rows_for_one_evidence_id_is_refused():
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        digests_for_payload({"evidence": [
            {"evidence_id": "ev_a", "field": "deal.status", "value": "open"},
            {"evidence_id": "ev_a", "field": "deal.status", "value": "closed"}]})
