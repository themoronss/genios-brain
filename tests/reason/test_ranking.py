"""Wave Z3 · the ears — doc 04 E1 and E4, and gate K1.

Three layers computed a number this layer had never read. `importance_bp` appeared exactly once
anywhere under `reason/` — a column in a SQL select — while `ranking_weights` gave importance the
largest share of a utility it was not part of. At the same time the authored corpus priority was
handed to `core.priority` as config for every compiled candidate and `score_candidate` returned it
verbatim, so the weighted formula had never once decided anything: **every ranked candidate on the
compiled lane scored 9000, all 4,480 of them.** That measurement is in
`test_the_formula_finally_decides` below and it is the whole reason this wave exists.

Nothing here is an example check. G7 and H5 both taught the same lesson — a green suite full of
examples cannot see a constant — so the gate rows are measured over a POPULATION driven through
the production path: a real `ExpertisePackage` compiled from the shipped corpus, welded into a
`CapabilityManifest` by the real adapter, executed by the real orchestrator and registry.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from genios_engine.context.situation_bso import (
    L1Signals,
    build_business_situation,
    build_context_slice,
    gather_evidence_and_signals,
)
from genios_engine.contracts.reasoning import (
    RANKING_WEIGHTS_V1,
    RANKING_WEIGHTS_V2,
    RANKING_WEIGHTS_V2_SCALE,
    RANKING_WEIGHTS_V2_VERSION,
    CapabilityManifest,
    ContextSnapshot,
    DecisionOutcome,
    ExecutionMode,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
    require_do_nothing,
)
from genios_engine.packs.capabilities.deal_cooling import DEAL_COOLING_V1
from genios_engine.packs.compiler import DomainCompiler, InMemoryRuntimeBrains
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.decision_maker import (
    IMPORTANCE_ABSENT_REASON,
    IMPORTANCE_COMPONENT,
    PRIORITY_OVERRIDE_COMPONENT,
    SITUATION_IMPORTANCE_KEY,
    DecisionMaker,
    build_candidate_objects,
    build_candidates,
    do_nothing_record,
    effective_weights,
    rank_candidates,
    ranking_model_is_v2,
    score_candidate,
    situation_importance,
    synthesize_candidates,
)
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.protocols import OrchestrationError
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.store import ReasoningStore

from ..test_reasoning_audit_replay import (
    CONFIG_SNAPSHOT_ID,
    NOW as AUDIT_NOW,
    _context,
    _persisted_bundle,
)
from .adapters.conftest import NOW

REPO = Path(__file__).resolve().parents[2]


# ═════════════════════════════════════════════════════════════════════════════════════════════
# The population. One compiler, many situations — the same two calls `domain_shadow` makes.
# ═════════════════════════════════════════════════════════════════════════════════════════════

BASE_FACTS = {"deal.status": "open", "thread.ball_in_court": "them"}
OBSERVATIONS = ("proposal_sent", "verbal_yes")


@pytest.fixture(scope="module")
def compiler() -> DomainCompiler:
    return DomainCompiler(catalog=ExpertBrainCatalog(default_authoring_root()),
                          runtime_brains=InMemoryRuntimeBrains(), publisher=None,
                          require_admission=False)


def fact_profile(index: int) -> dict:
    """Eight profiles: money, dated obligations and engagement, in every combination.

    The point is not the facts, it is that a population whose situations differ only in importance
    would prove importance moves the score and prove nothing about whether the rest of the formula
    still does.
    """
    facts = dict(BASE_FACTS)
    if index & 1:
        facts["deal.value"] = 50_000 + index * 12_500
    if index & 2:
        facts["commitment.due_at"] = f"2026-08-{10 + (index % 18):02d}T09:00:00+00:00"
    if index & 4:
        facts["derived.momentum"] = 0.15 + (index % 7) / 100
        facts["thread.last_inbound"] = f"2026-07-{1 + (index % 27):02d}T09:00:00+00:00"
    return facts


def compiled_run(compiler, importance_bp, facts, situation_id, *,
                 ranking_v2: bool, roster_v2: bool = True):
    """L2 situation -> L3 package -> L4 manifest -> a real ReasoningDecision.

    `importance_bp=None` means Layer 1 published no scored signal, which is the state
    `importance_base` answers with `DEFAULT_IMPORTANCE_BP` and a declared fallback — the honesty
    guard's input, and not a special case invented here.
    """
    from genios_engine.reason.engine import NodeContext

    row = {"situation_id": situation_id, "situation_type": "deal", "domain": "sales",
           "status": "active", "correlation_id": None, "confidence_overall": 82,
           "coverage": 70, "first_seen_at": NOW, "last_seen_at": NOW,
           "anchor_node_id": "node_1", "anchor_name": "Fixture", "anchor_type": "company"}
    signal_ids, evidence = gather_evidence_and_signals(None, "org_k1", None, situation_id)
    l1 = (L1Signals(signal_ids=("qs_1",), scored_signal_ids=("qs_1",),
                    importance_bp=importance_bp, importance_version="alg17@1",
                    signal_count=1, scored_count=1)
          if importance_bp is not None else None)
    situation = build_business_situation(
        org_id="org_k1", situation=row, signal_ids=signal_ids, evidence=evidence,
        trace_id="tr", l1=l1)
    context = build_context_slice(
        org_id="org_k1", situation=row,
        facts={path: {"value": value} for path, value in facts.items()},
        observations=[{"kind": kind} for kind in OBSERVATIONS],
        neighbor=(4, set(), {}), graph_version=1, eval_time=NOW, trace_id="tr")
    manifest = expertise_capability_manifest(
        compiler.compile(situation, context), root_entity_type="company",
        situation=situation, context=context, roster_v2=roster_v2, ranking_v2=ranking_v2)
    node = NodeContext(
        node_id="node_1", node_type="company",
        facts={name: {"value": value} for name, value in facts.items()},
        obs=[{"kind": "proposal_sent", "occurred_at": "2026-07-01T09:00:00+00:00"}],
        edge_count=4, neighbor_obs=set(), neighbor_facts={})
    return manifest, reason_native_capability(
        org_id="org_k1", context=node, capability=manifest, evaluation_time=NOW,
        graph_version=1, config_snapshot_id=None, mode=ExecutionMode.SHADOW)


def population(compiler, *, ranking_v2: bool, roster_v2: bool = True,
               importances: int = 40, profiles: int = 8):
    runs = []
    for index in range(importances):
        importance_bp = 500 + index * 235
        for profile in range(profiles):
            runs.append((importance_bp, profile) + compiled_run(
                compiler, importance_bp, fact_profile(profile), f"sit_{index}_{profile}",
                ranking_v2=ranking_v2, roster_v2=roster_v2))
    return runs


@pytest.fixture(scope="module")
def v2_population(compiler):
    """320 situations — 40 Layer-1 importance scores across 8 fact profiles."""
    return population(compiler, ranking_v2=True)


@pytest.fixture(scope="module")
def v1_population(compiler):
    """The same 320 situations with the switch off: what the engine does today."""
    return population(compiler, ranking_v2=False)


def _ranked(runs):
    return [candidate for _imp, _p, _m, execution in runs
            for candidate in execution.candidates if candidate.rank_position is not None]


def _selected(runs):
    return [(imp, profile, next((c for c in execution.candidates if c.rank_position == 1), None),
             execution.decision)
            for imp, profile, _m, execution in runs]


# ═════════════════════════════════════════════════════════════════════════════════════════════
# GATE K1 — measured, never exemplified
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_formula_finally_decides(v1_population, v2_population, capsys):
    """K1 row 1: >= 50 distinct `final_utility_bp` per day. Today: one, for everything.

    The v1 half is not a control, it is the DEFECT, measured: with the switch off every ranked
    candidate in a 320-situation population carries the identical utility, because the authored
    corpus priority replaced the formula on all of them.
    """
    before = {candidate.utility_bp for candidate in _ranked(v1_population)}
    after = {candidate.utility_bp for candidate in _ranked(v2_population)}
    with capsys.disabled():
        print(f"\nK1 · distinct final_utility_bp over {len(_ranked(v1_population))} ranked "
              f"candidates: before={len(before)} (values {sorted(before)}) after={len(after)}")

    assert len(before) == 1, "the defect this wave exists to end has changed shape"
    assert len(after) >= 50


def test_two_situations_of_one_type_with_different_importance_rank_differently(v2_population):
    """K1 row 2, demonstrated the way the gate words it — SAME type, DIFFERENT importance.

    Every situation in this population is a `deal`, so nothing but Layer 2's importance separates
    two runs of one fact profile. That the utilities are strictly ordered by importance is the
    three-layer supply chain delivering for the first time.
    """
    by_profile: dict[int, list[tuple[int, int]]] = {}
    for importance_bp, profile, selected, _decision in _selected(v2_population):
        assert selected is not None
        by_profile.setdefault(profile, []).append((importance_bp, selected.utility_bp))

    for profile, rows in by_profile.items():
        rows.sort()
        utilities = [utility for _importance, utility in rows]
        assert len(set(utilities)) == len(rows), f"profile {profile} ranks {len(rows)} " \
                                                 "importances onto fewer utilities"
        assert utilities == sorted(utilities), "more important ranked lower"


def test_the_divergence_is_recorded_on_every_decision(v1_population, v2_population):
    """K1 row 3: 100%, on BOTH shapes. Doc 08 retires the 70/30 weight against this data."""
    for runs in (v1_population, v2_population):
        for candidate in _ranked(runs):
            assert candidate.formula_utility_bp is not None
            assert candidate.utility_divergence_bp is not None

    # ...and on v2 the override is recorded as a number of its own, so the divergence is
    # decomposable rather than merely computable.
    for candidate in _ranked(v2_population):
        override = candidate.score_components.get(PRIORITY_OVERRIDE_COMPONENT)
        assert override is not None
        assert candidate.utility_bp == min(10_000, (candidate.formula_utility_bp * 7
                                                    + override * 3) // 10)


def test_do_nothing_is_computed_on_the_pilot(v2_population, capsys):
    """K1 row 6: >= 80% `computed`. Doc 04 E4 conditions it on the roster being awake — so is the
    number, and the roster-asleep case is measured in its own test rather than averaged in."""
    sources = Counter()
    for _imp, _profile, _winner, decision in _selected(v2_population):
        if decision.outcome != DecisionOutcome.DECISION:
            continue
        require_do_nothing(decision.do_nothing)          # the typed shape, on every one
        sources[decision.do_nothing["source"]] += 1
    total = sum(sources.values())
    with capsys.disabled():
        print(f"K1 · do_nothing over {total} published decisions: {dict(sources)}")

    assert total >= 300
    assert sources["computed"] * 100 >= total * 80


def test_the_run_replays_byte_for_byte(compiler):
    """K1 row 7. Two runs of one situation, and the audit bundle's own verifier."""
    _m1, first = compiled_run(compiler, 8_100, fact_profile(3), "sit_replay", ranking_v2=True)
    _m2, second = compiled_run(compiler, 8_100, fact_profile(3), "sit_replay", ranking_v2=True)

    assert first.decision.semantic_hash == second.decision.semantic_hash
    assert ([c.candidate_id for c in first.candidates]
            == [c.candidate_id for c in second.candidates])

    manifest = replace(first.request.capability,
                       metadata={**dict(first.request.capability.metadata),
                                 "context_selector": {"max_edges": 25}})
    request = replace(first.request, capability=manifest,
                      request_id=None, policy_snapshot_id=None)
    execution = ReasoningOrchestrator(default_registry()).execute(request)
    ReasoningStore.__new__(ReasoningStore).verify_replay_bundle(
        _persisted_bundle(execution), org_id="org_k1")


def test_the_compiled_lane_could_not_be_replayed_before_this_wave(compiler):
    """The hole `audit._output` and `store.verify_replay_bundle` were carrying.

    `ReasoningDecision.to_semantic_dict` folds `citations` and `constraints_applied` into the
    decision hash when they are carried, and the weld gives both to every compiled decision — but
    `decision_core` never persisted them and the rebuild never read them, so from the day Layer 3
    landed, EVERY compiled bundle failed `contract decision hash integrity mismatch`. A whole
    lane's replay guarantee was gone and no test was watching. This pins the round trip for all
    five conditional fields at once.
    """
    _manifest, execution = compiled_run(compiler, 8_100, fact_profile(3), "sit_weld",
                                        ranking_v2=False)
    assert execution.decision.citations and execution.decision.constraints_applied

    manifest = replace(execution.request.capability,
                       metadata={**dict(execution.request.capability.metadata),
                                 "context_selector": {"max_edges": 25}})
    rerun = ReasoningOrchestrator(default_registry()).execute(
        replace(execution.request, capability=manifest,
                request_id=None, policy_snapshot_id=None))

    ReasoningStore.__new__(ReasoningStore).verify_replay_bundle(
        _persisted_bundle(rerun), org_id="org_k1")


# ═════════════════════════════════════════════════════════════════════════════════════════════
# E1a · importance as the sixth component, and the honesty guard
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_carrier_reaches_the_manifest_from_a_real_situation(compiler):
    manifest, _execution = compiled_run(compiler, 7_400, BASE_FACTS, "sit_carrier",
                                        ranking_v2=True)

    assert manifest.ranking_weights == dict(RANKING_WEIGHTS_V2)
    assert manifest.ranking_weights_version == RANKING_WEIGHTS_V2_VERSION
    carrier = manifest.metadata[SITUATION_IMPORTANCE_KEY]
    assert carrier["importance_bp"] == 7_400
    assert carrier["source"] == "l1_qualified_signals"
    assert carrier["fallback"] is False


def test_an_unactivated_tenant_reaches_the_same_manifest_bytes(compiler):
    """The switch may not move a capability that is not switched on: the version is a content
    address and the audit rows already written against it have to stay verifiable."""
    off, _ = compiled_run(compiler, 7_400, BASE_FACTS, "sit_off", ranking_v2=False)
    on, _ = compiled_run(compiler, 7_400, BASE_FACTS, "sit_on", ranking_v2=True)

    assert off.ranking_weights == dict(RANKING_WEIGHTS_V1)
    assert SITUATION_IMPORTANCE_KEY not in off.metadata
    assert off.capability_snapshot_id != on.capability_snapshot_id


def test_importance_enters_the_utility_and_nothing_else_moved(compiler):
    low, _ = compiled_run(compiler, 1_000, BASE_FACTS, "sit_low", ranking_v2=True)
    high, _ = compiled_run(compiler, 9_000, BASE_FACTS, "sit_high", ranking_v2=True)
    _m, low_run = compiled_run(compiler, 1_000, BASE_FACTS, "sit_low", ranking_v2=True)
    _m2, high_run = compiled_run(compiler, 9_000, BASE_FACTS, "sit_high", ranking_v2=True)

    low_selected = next(c for c in low_run.candidates if c.rank_position == 1)
    high_selected = next(c for c in high_run.candidates if c.rank_position == 1)

    assert low_selected.play_id == high_selected.play_id
    assert low_selected.score_components[IMPORTANCE_COMPONENT] == 1_000
    assert high_selected.score_components[IMPORTANCE_COMPONENT] == 9_000
    assert high_selected.utility_bp > low_selected.utility_bp
    del low, high


def test_a_fallback_importance_is_absent_rather_than_five_thousand(compiler):
    """The guard. `importance_base` publishes the neutral midpoint for a situation Layer 1 never
    scored and DECLARES that it did; reading the integer alone would rank a whole unscored tenant
    on a constant, which is the "every card scores 50" defect rebuilt out of new parts."""
    manifest, execution = compiled_run(compiler, None, BASE_FACTS, "sit_unscored",
                                       ranking_v2=True)

    assert manifest.metadata[SITUATION_IMPORTANCE_KEY]["importance_bp"] == 5_000
    assert manifest.metadata[SITUATION_IMPORTANCE_KEY]["fallback"] is True
    assert f"{IMPORTANCE_ABSENT_REASON}:default" in execution.decision.uncertainty
    for candidate in execution.candidates:
        assert IMPORTANCE_COMPONENT not in candidate.score_components


def test_an_absent_carrier_names_itself_rather_than_passing_silently():
    request = _v2_request()
    decision = DecisionMaker().decide(
        request, [_completed("core.confidence", confidence_bp=9_000)],
        terminal=None, uncertainty=(), degraded=False).decision

    assert f"{IMPORTANCE_ABSENT_REASON}:not_supplied" in decision.uncertainty


def test_a_carrier_that_cannot_state_basis_points_is_a_deployment_fault():
    for broken in ({"importance_bp": "8100", "fallback": False},
                   {"importance_bp": 20_000, "fallback": False},
                   {"importance_bp": True, "fallback": False},
                   {"fallback": False}):
        with pytest.raises(OrchestrationError, match="integer basis points"):
            situation_importance(_v2_request(importance=broken))


def test_an_unstated_provenance_reads_as_not_measured():
    """`fallback` is checked for the literal False, so a carrier that omitted it — or carried
    None, or 0 — cannot pass as a measurement."""
    for stated in (None, 0, "", "no"):
        value, reason = situation_importance(
            _v2_request(importance={"importance_bp": 8_100, "fallback": stated,
                                    "source": "l1_qualified_signals"}))
        assert value is None and reason.startswith(IMPORTANCE_ABSENT_REASON)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# E1a · the reweigh
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_remaining_five_are_reweighed_to_exactly_ten_thousand():
    present = {name: 5_000 for name in RANKING_WEIGHTS_V2 if name != IMPORTANCE_COMPONENT}

    weights = effective_weights(dict(RANKING_WEIGHTS_V2), present)

    assert sum(weights.values()) == RANKING_WEIGHTS_V2_SCALE
    assert IMPORTANCE_COMPONENT not in weights
    assert weights == {"impact": 2_667, "urgency": 2_667, "success": 2_000,
                       "effort": 1_333, "risk": 1_333}


@pytest.mark.parametrize("absent", [
    ("importance",), ("impact",), ("urgency",), ("success",), ("effort",), ("risk",),
    ("importance", "urgency"), ("effort", "risk"), ("importance", "impact", "success"),
    ("impact", "urgency", "success", "effort"),
])
def test_every_absence_reweighs_to_the_scale_exactly(absent):
    """Floor division alone loses up to one basis point per component, and a weight vector summing
    to 9,998 scales every candidate down by two parts in ten thousand — invisible, and enough to
    reorder a tie."""
    present = {name: 5_000 for name in RANKING_WEIGHTS_V2 if name not in absent}

    weights = effective_weights(dict(RANKING_WEIGHTS_V2), present)

    assert sum(weights.values()) == RANKING_WEIGHTS_V2_SCALE
    assert set(weights) == set(present)
    assert all(isinstance(value, int) for value in weights.values())


def test_the_reweigh_is_a_redistribution_and_not_a_substitution():
    """An absent importance must not be able to move a candidate at all — which is what both a
    zero and a neutral 5,000 would do."""
    without = _utility(_v2_request(), {"impact": 9_000, "urgency": 2_000, "success": 6_000,
                                       "effort": 1_000, "risk": 1_000})
    as_zero = _utility(_v2_request(), {IMPORTANCE_COMPONENT: 0, "impact": 9_000,
                                       "urgency": 2_000, "success": 6_000,
                                       "effort": 1_000, "risk": 1_000})
    as_neutral = _utility(_v2_request(), {IMPORTANCE_COMPONENT: 5_000, "impact": 9_000,
                                          "urgency": 2_000, "success": 6_000,
                                          "effort": 1_000, "risk": 1_000})

    assert without != as_zero
    assert without != as_neutral


def test_a_run_with_no_weighted_component_left_refuses_rather_than_ranking():
    with pytest.raises(OrchestrationError, match="nothing can be ranked"):
        effective_weights(dict(RANKING_WEIGHTS_V2), {})


# ═════════════════════════════════════════════════════════════════════════════════════════════
# E1b · the override becomes a prior
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_override_is_a_seventy_thirty_prior_on_the_new_model():
    request = _v2_request(importance={"importance_bp": 5_000, "fallback": False,
                                      "source": "l1_qualified_signals"})
    components = {IMPORTANCE_COMPONENT: 5_000, "impact": 5_000, "urgency": 5_000,
                  "success": 5_000, "effort": 5_000, "risk": 5_000}

    final = score_candidate(request, components, 9_600)

    assert components["formula_utility"] == 5_000
    assert components[PRIORITY_OVERRIDE_COMPONENT] == 9_600
    assert final == (5_000 * 7 + 9_600 * 3) // 10 == 6_380


def test_the_legacy_five_weight_lane_still_lets_the_override_win():
    """`reason/store.py` re-runs this function against persisted manifests. A capability ranked
    under the five-weight model has to reach the utility it reached then."""
    request = _v1_request()
    components = {"impact": 5_000, "urgency": 5_000, "success": 5_000,
                  "effort": 5_000, "risk": 5_000}

    assert score_candidate(request, components, 9_600) == 9_600
    assert PRIORITY_OVERRIDE_COMPONENT not in components
    assert components["formula_utility"] != 9_600


def test_the_demotion_can_never_round_above_either_input():
    """Floor division, as doc 04 writes it — not `divide_half_up`."""
    request = _v2_request(importance={"importance_bp": 5_000, "fallback": False,
                                      "source": "l1_qualified_signals"})
    for override in range(0, 10_001, 137):
        components = {IMPORTANCE_COMPONENT: 3_333, "impact": 6_001, "urgency": 4_449,
                      "success": 7_777, "effort": 2_221, "risk": 1_113}
        final = score_candidate(request, components, override)
        formula = components["formula_utility"]
        assert min(formula, override) <= final <= max(formula, override)
        assert final == (formula * 7 + override * 3) // 10


def test_the_formula_leads_and_the_corpus_only_pulls():
    """70/30 means a candidate the model hates cannot be dragged to the top by an authored 10000
    the way it used to be."""
    request = _v2_request(importance={"importance_bp": 0, "fallback": False,
                                      "source": "l1_qualified_signals"})
    components = {IMPORTANCE_COMPONENT: 0, "impact": 0, "urgency": 0,
                  "success": 0, "effort": 10_000, "risk": 10_000}

    assert score_candidate(request, components, 10_000) == 3_000        # was 10_000


# ═════════════════════════════════════════════════════════════════════════════════════════════
# E1 · the five-weight lane is byte-identical to the code that shipped
# ═════════════════════════════════════════════════════════════════════════════════════════════

def _prewave_module():
    source = subprocess.run(
        ["git", "show", "HEAD:genios_engine/reason/decision_maker.py"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout
    path = REPO / "genios_engine" / "reason" / "_prewave_decision_maker.py"
    path.write_text(source)
    try:
        spec = importlib.util.spec_from_file_location(
            "genios_engine.reason._prewave_decision_maker", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        path.unlink(missing_ok=True)
        sys.modules.pop("genios_engine.reason._prewave_decision_maker", None)


def test_the_five_weight_utility_is_what_it_was_at_head():
    """Not "looks the same" — the SHIPPED function, extracted from git and run beside this one."""
    prewave = _prewave_module()
    request = _v1_request()
    seen = set()
    for impact in range(0, 10_001, 911):
        for effort in range(0, 10_001, 1_303):
            components = {"impact": impact, "urgency": (impact + effort) % 10_001,
                          "success": (impact * 3) % 10_001, "effort": effort,
                          "risk": (effort * 7) % 10_001}
            mine = score_candidate(request, dict(components), None)
            theirs = prewave.score_candidate(request, dict(components), None)
            assert mine == theirs
            seen.add(mine)
    assert len(seen) > 20, "the grid did not exercise a range of utilities"


def test_a_five_weight_candidate_still_addresses_to_the_same_bytes():
    prewave = _prewave_module()
    request = _v1_request()

    mine = build_candidate_objects(
        rank_candidates(synthesize_candidates(request, [], 6_400, 9_000)), 7_000, ("ev_1",))
    theirs = build_candidate_objects(
        rank_candidates(prewave.synthesize_candidates(request, [], 6_400, 9_000)),
        7_000, ("ev_1",))

    assert [item.candidate_id for item in mine] == [item.candidate_id for item in theirs]


def test_a_five_weight_decision_still_hashes_to_what_it_hashed_to():
    """`ranking_weights_version` and `do_nothing` are carried on the v2 model only, so a decision
    that predates this wave keeps the exact `decision_hash` stored in `reasoning_runs`."""
    request = ReasoningRequest(
        org_id="org_1", capability=DEAL_COOLING_V1, context=_context(),
        evaluation_time=AUDIT_NOW, trigger_kind="email.received", trigger_ref="event_1",
        config_snapshot_id=CONFIG_SNAPSHOT_ID)
    execution = ReasoningOrchestrator(default_registry()).execute(request)

    assert execution.decision.ranking_weights_version is None
    assert execution.decision.do_nothing == {}
    assert "ranking_weights_version" not in execution.decision.to_semantic_dict()
    assert "do_nothing" not in execution.decision.to_semantic_dict()


def test_a_legacy_decision_envelope_persists_the_bytes_it_always_persisted():
    """`audit._output` grew five conditional keys; a decision that carries none of them must write
    exactly the envelope it wrote before, or a row from last week and a row from today are not the
    same shape and `decision_core` stops being comparable across the cutover.

    Proven against the SHIPPED function, extracted from git and run beside this one — not against
    a hardcoded list of key names, which would agree with whatever the code does.
    """
    from genios_engine.reason.audit import _output

    prewave = _prewave_audit()
    request = ReasoningRequest(
        org_id="org_1", capability=DEAL_COOLING_V1, context=_context(),
        evaluation_time=AUDIT_NOW, trigger_kind="email.received", trigger_ref="event_1",
        config_snapshot_id=CONFIG_SNAPSHOT_ID)
    execution = ReasoningOrchestrator(default_registry()).execute(request)

    assert set(_output(execution)["decision_core"]) == \
        set(prewave._output(execution)["decision_core"])


def _prewave_audit():
    source = subprocess.run(["git", "show", "HEAD:genios_engine/reason/audit.py"],
                            cwd=REPO, capture_output=True, text=True, check=True).stdout
    path = REPO / "genios_engine" / "reason" / "_prewave_audit.py"
    path.write_text(source)
    try:
        spec = importlib.util.spec_from_file_location(
            "genios_engine.reason._prewave_audit", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        path.unlink(missing_ok=True)
        sys.modules.pop("genios_engine.reason._prewave_audit", None)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# E4 · the computed cost of doing nothing
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_price_of_inaction_is_read_from_the_cost_unit():
    request = _v2_request()
    record = do_nothing_record(request, [
        _completed("core.cost", do_nothing_cost_bp=6_400),
        _completed("core.timeline", deadline_hours=36),
    ])

    require_do_nothing(record)
    assert record["source"] == "computed"
    assert record["cost_bp"] == 6_400
    assert record["horizon"] == NOW + timedelta(hours=36)
    assert "6400" in record["statement"] and "36 hours away" in record["statement"]


def test_the_alternative_unit_is_the_documented_fallback_and_only_when_cost_is_silent():
    request = _v2_request()
    both = do_nothing_record(request, [
        _completed("core.cost", do_nothing_cost_bp=6_400),
        _completed("core.alternative", do_nothing_baseline_bp=2_100)])
    alone = do_nothing_record(request, [
        _completed("core.alternative", do_nothing_baseline_bp=2_100)])

    assert both["cost_bp"] == 6_400          # one silence is not two estimates
    assert alone["cost_bp"] == 2_100 and alone["source"] == "computed"


def test_a_unit_that_did_not_complete_publishes_nothing():
    request = _v2_request()
    record = do_nothing_record(request, [
        ReasonerResult("core.cost", "1", ResultStatus.FAILED),
        ReasonerResult("core.alternative", "1", ResultStatus.INSUFFICIENT_CONTEXT)])

    assert record["source"] == "manifest_fallback"
    assert record["statement"] == request.capability.do_nothing_consequence


def test_the_fallback_is_labelled_and_never_disguised(compiler):
    """Doc 04 E4 conditions the 80% on the roster being awake, and it is right to: with the
    six-unit DAG `core.cost` and `core.alternative` never run, and every record says so."""
    sources = Counter()
    for index in range(10):
        _m, execution = compiled_run(compiler, 4_000 + index * 500, fact_profile(index % 8),
                                     f"sit_asleep_{index}", ranking_v2=True, roster_v2=False)
        sources[execution.decision.do_nothing["source"]] += 1
        assert execution.decision.do_nothing["statement"] == \
            execution.request.capability.do_nothing_consequence

    assert sources == Counter({"manifest_fallback": 10})


def test_an_overdue_date_is_stated_as_past_and_not_as_a_negative_number():
    request = _v2_request()
    record = do_nothing_record(request, [
        _completed("core.cost", do_nothing_cost_bp=1_000),
        _completed("core.timeline", deadline_hours=-48)])

    assert record["horizon"] == NOW - timedelta(hours=48)
    assert "passed 48 hours ago" in record["statement"]
    assert "-48" not in record["statement"]


def test_a_situation_with_no_material_date_says_so_rather_than_inventing_one():
    record = do_nothing_record(_v2_request(), [
        _completed("core.cost", do_nothing_cost_bp=1_000)])

    require_do_nothing(record)
    assert record["horizon"] is None
    assert "no material date was measured" in record["statement"]


def test_a_non_completed_result_cannot_price_inaction_even_if_it_carries_a_number():
    """The SECOND of two enforcements, and the reason the first is not enough on its own.

    `ReasonerResult` refuses effects on a non-completed result — "non-completed reasoner results
    cannot carry decision effects or evidence" — so the shape below cannot come off the contract.
    It can come off anything that hands this function result-LIKE rows: a store read, a replay
    fixture, a future unit type. The distinction being enforced is not a formality: `computed`
    means a unit actually produced the number, and a card that says a failed run priced its own
    inaction is precisely the claim `source` exists to make impossible.
    """
    class _ResultLike:
        reasoner_id = "core.cost"
        status = ResultStatus.FAILED
        metrics = {"do_nothing_cost_bp": 9_900}

    record = do_nothing_record(_v2_request(), [_ResultLike()])

    assert record["source"] == "manifest_fallback"
    assert record["cost_bp"] == 0


def test_a_metric_that_is_not_an_integer_is_not_a_price():
    """`True` is an `int` in Python and a boolean is not a basis point; a string is a formatting
    accident somewhere upstream. Both read as "not measured" rather than as 1."""
    for value in (True, "6400", 64.0, None):
        record = do_nothing_record(_v2_request(), [
            _completed("core.alternative", do_nothing_baseline_bp=1_500)])             if value is None else do_nothing_record(_v2_request(), [_stub("core.cost", value)])
        if value is None:
            assert record["cost_bp"] == 1_500
        else:
            assert record["source"] == "manifest_fallback"


def _stub(reasoner_id: str, value):
    class _ResultLike:
        pass
    stub = _ResultLike()
    stub.reasoner_id = reasoner_id
    stub.status = ResultStatus.COMPLETED
    stub.metrics = {"do_nothing_cost_bp": value}
    return stub


def test_the_horizon_reads_the_runs_own_instant_and_never_a_clock():
    later = _v2_request(evaluation_time=NOW + timedelta(days=30))
    record = do_nothing_record(later, [
        _completed("core.cost", do_nothing_cost_bp=1_000),
        _completed("core.timeline", deadline_hours=12)])

    assert record["horizon"] == NOW + timedelta(days=30, hours=12)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# The doctrine, checked structurally
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_ranking_path_contains_no_float_arithmetic():
    """Integer basis points, no float, no round, no statistics — a float would make the decision
    hash machine-dependent and destroy replay."""
    module = ast.parse((REPO / "genios_engine" / "reason" / "decision_maker.py").read_text())
    owned = {"score_candidate", "_weighted_utility", "effective_weights",
             "situation_importance", "do_nothing_record", "_do_nothing_statement",
             "synthesize_candidates", "_component_order", "ranking_model_is_v2"}
    for node in ast.walk(module):
        if not isinstance(node, ast.FunctionDef) or node.name not in owned:
            continue
        for inner in ast.walk(node):
            assert not (isinstance(inner, ast.Constant) and isinstance(inner.value, float)), \
                f"{node.name} carries a float literal"
            assert not isinstance(inner, ast.BinOp) or not isinstance(inner.op, ast.Div), \
                f"{node.name} uses true division"
            if isinstance(inner, ast.Name):
                assert inner.id not in {"round", "float", "statistics", "numpy"}, \
                    f"{node.name} reaches for {inner.id}"


def test_no_reasoning_unit_may_move_importance():
    """Layer 2 owns the number. A unit that could adjust it could raise its own card."""
    from genios_engine.reason.guards import CANDIDATE_COMPONENTS

    assert IMPORTANCE_COMPONENT not in CANDIDATE_COMPONENTS


def test_the_model_version_is_read_off_the_weights_and_never_off_a_database():
    """`store.py` re-runs the ranker against a persisted manifest with a request view that has a
    capability and a context and nothing else."""
    from types import SimpleNamespace

    view = SimpleNamespace(capability=_v2_request().capability)
    assert ranking_model_is_v2(view) is True
    assert ranking_model_is_v2(SimpleNamespace(capability=_v1_request().capability)) is False


def test_the_store_re_runs_this_pipeline_and_still_agrees(compiler):
    """The one entry point `reason/store.py` calls, on the new model."""
    _manifest, execution = compiled_run(compiler, 6_600, fact_profile(5), "sit_agree",
                                        ranking_v2=True)
    whole, _confidence = build_candidates(
        execution.request, list(execution.ordered_results),
        any(item.status in {ResultStatus.FAILED, ResultStatus.INSUFFICIENT_CONTEXT}
            for item in execution.ordered_results
            if item.reasoner_id in _optional_ids(execution.request.capability)))

    assert [item.candidate_id for item in whole] == \
        [item.candidate_id for item in execution.candidates]


def _optional_ids(capability) -> set[str]:
    from genios_engine.contracts.reasoning import FailurePolicy
    return {spec.reasoner_id for spec in capability.reasoners
            if spec.failure_policy == FailurePolicy.OPTIONAL}


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Fixtures for the hermetic half
# ═════════════════════════════════════════════════════════════════════════════════════════════

def _completed(reasoner_id: str, **metrics) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1",
                          status=ResultStatus.COMPLETED, matched=True, metrics=metrics)


def _request(weights, *, importance=None, evaluation_time=None) -> ReasoningRequest:
    metadata = {"situation_type": "deal_cooling"}
    if importance is not None:
        metadata[SITUATION_IMPORTANCE_KEY] = importance
    moment = evaluation_time or NOW
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling", version="1.0.0", domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.confidence", "1"),),
        plays=(PlayDefinition(play_id="restore_momentum", version="1", label="Restore",
                              steps=("Prepare a grounded draft",)),),
        policies=(), ranking_weights=dict(weights), metadata=metadata)
    context = ContextSnapshot(
        org_id="org_1", graph_version=17, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=moment, selector_version="selector.v1",
        facts={"deal.status": "open"})
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=moment, trigger_kind="email.received",
                            config_snapshot_id="cfg_1")


def _v2_request(*, importance=None, evaluation_time=None) -> ReasoningRequest:
    return _request(RANKING_WEIGHTS_V2, importance=importance,
                    evaluation_time=evaluation_time)


def _v1_request() -> ReasoningRequest:
    return _request(RANKING_WEIGHTS_V1)


def _utility(request, components) -> int:
    return score_candidate(request, dict(components), None)
