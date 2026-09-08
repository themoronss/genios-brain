"""THE DOCTRINE TEST, and the wiring that makes the voice real.

    pytest tests/reason/test_bundle_doctrine.py -q

    WITH EVERY R-SITE FORCE-FAILED, A FULL REPLAY MUST PRODUCE BYTE-IDENTICAL DecisionObjects.
    If that ever fails, THE MODEL HAS ACQUIRED DECISION AUTHORITY AND THE WAVE IS REVERTED.

That is doc 01 C5's acceptance row and doc 08's K4 addendum, and it is the property that lets a
founder trust a narrated card: the prose can be excellent, plain, or missing, and the company does
the same thing either way. It is proved here three ways, because there are three places the
property could be lost —

  1. **at the object.** A bundle attached to a decision must not move its hash. `reasoning_bundle`
     is excluded from `to_semantic_dict` unconditionally, so the exclusion is checked on the real
     canonical bytes and not on a field list.
  2. **at the replay.** A real execution, persisted to a real store, replayed with no model, with a
     model, and with every R-site force-failed — the same `decision_hash` and the same
     `ReplayComparison` all three times.
  3. **at the seam.** `reason/bundle` must have no way to reach a model except through the gate,
     which is what makes 1 and 2 hold for every FUTURE R-site too. Read structurally, from the AST.

The second half of this file is the other thing L1, L2 and L3 each got wrong once: a unit that is
never reached from a real path. The narration pass is called by `reason/runner.run_all` — THE
production entry — and the narrative it writes is read by `GET /v1/insights`. Both are pinned
structurally, so a refactor that quietly unwires either turns this red.
"""

from __future__ import annotations

import ast
import inspect
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.reasoning import ExecutionMode, ReasoningRequest
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.platform.canonical import canonicalize, semantic_hash
from genios_engine.platform.l4_activation import FEATURE_BUNDLE
from genios_engine.reason import runner as RUNNER
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.bundle import RSiteGate, force_failed, narrate, sweep
from genios_engine.reason.bundle import gate as GATE_MODULE
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.bundle.store import BundleStore
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.replay import replay_persisted
from genios_engine.reason.store import ReasoningStore

from .test_llm_policy import FakeLLM, FakeResult
from .test_store_replay import NOW, deal_cooling_context

TTL_HOURS = 43_800


# ── a real execution, not a fixture-shaped one ───────────────────────────────────────────────

def _execute(org_id: str, *, config_snapshot_id: str | None = None):
    return ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id=org_id, capability=DEAL_COOLING_V1, context=deal_cooling_context(org_id),
        evaluation_time=NOW, trigger_kind="email.received", trigger_ref="event_1",
        mode=ExecutionMode.LIVE, config_snapshot_id=config_snapshot_id))


def _published_execution(engine, org_id: str):
    """An execution bound to a REAL `config_snapshots` row.

    `signals_linked_run_requires_config` refuses a signal whose run has no config, and
    `ReasoningStore` refuses a run whose config's pack does not match the capability's domain and
    whose id is not the content address of its own effective bytes. Both are preserve-hard
    behaviours; satisfying them here is what makes this an end-to-end test rather than a shape.
    """
    import json as _json_mod

    from genios_engine.packs.snapshot import snapshot_id as _snapshot_id
    effective = {"pack_id": DEAL_COOLING_V1.domain, "version": "1.0.0"}
    snapshot = _snapshot_id(effective)
    with engine.begin() as conn:
        conn.execute(text(
            "insert into config_snapshots (snapshot_id, org_id, pack_id, effective, cause) "
            "values (:s, :o, :p, cast(:e as jsonb), 'test') on conflict do nothing"),
            {"s": snapshot, "o": org_id, "p": DEAL_COOLING_V1.domain,
             "e": _json_mod.dumps(effective)})
    return _execute(org_id, config_snapshot_id=snapshot)


def _engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the doctrine replay needs a real store")
    from genios_engine.platform.db import get_engine
    return get_engine(url)


@pytest.fixture(scope="module")
def engine():
    return _engine()


@pytest.fixture
def org(engine, request):
    org_id = f"org_z4_{abs(hash(request.node.name)) % 10 ** 9}"
    with engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, :o) "
                          "on conflict (id) do nothing"), {"o": org_id})
    yield org_id
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org_id})


def _narrating_gate(org_id: str, *, client=None) -> RSiteGate:
    return RSiteGate(org_id=org_id, client=client, activated=frozenset({FEATURE_BUNDLE}),
                     budget=NarrativeBudget(org_id=org_id))


def _good_generation(execution) -> FakeLLM:
    """A model that answers the shape R-2 asks for. Its content does not matter to this file — what
    matters is that a SUCCESSFUL consult moves nothing either."""
    return FakeLLM(FakeResult(parsed={
        "headline": "Deal cooling on an open deal",
        "situation_summary": "The deal is open and the engagement reading has fallen.",
        "why_it_matters": "The engine holds this at {confidence_pct} percent confidence.",
        "root_cause": "The reasoning units report a cooling deal on the recorded evidence.",
        "recommendation_rationale": "Recommended: the play the engine ranked first here.",
        "expected_effect": "Acting addresses the cooling; doing nothing leaves it where it is.",
    }))


# ═════════════════════════════════════════════════════════════════════════════════════════════
# 1 · AT THE OBJECT — a narrative cannot move the decision it narrates
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_attaching_a_bundle_changes_no_byte_of_the_decision(org):
    """Not "the id is stable" — the canonical BYTES are identical, which is what a stored
    `decision_hash` is compared against on replay."""
    from genios_engine.reason.bundle import build_catalogue, build_grounding, template_bundle
    execution = _execute(org)
    decision = execution.decision
    before_bytes = canonicalize(decision.to_semantic_dict())
    before_id, before_hash = decision.decision_id, decision.semantic_hash

    catalogue = build_catalogue(decision, execution.ordered_results, eval_time=NOW)
    grounding = build_grounding(decision, execution.ordered_results, request=execution.request)
    if decision.action_id is None:
        pytest.skip("this capability did not commit to an action on this context")
    narrated = decision.with_bundle(template_bundle(
        decision, catalogue=catalogue, grounding=grounding,
        evidence_refs=grounding.evidence_refs or ("ev_status",)))

    assert narrated.reasoning_bundle is not None
    assert canonicalize(narrated.to_semantic_dict()) == before_bytes
    assert (narrated.decision_id, narrated.semantic_hash) == (before_id, before_hash)


def test_the_bundle_is_excluded_from_the_hash_unconditionally_and_not_merely_when_empty(org):
    """A correctness requirement, not hash hygiene: the bundle names `decision_id`, and
    `decision_id` is the content address of that dict. A bundle inside it could never be attached."""
    execution = _execute(org)
    assert "reasoning_bundle" not in execution.decision.to_semantic_dict()


# ═════════════════════════════════════════════════════════════════════════════════════════════
# 2 · AT THE REPLAY — the property doc 01 C5 actually names
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_with_every_r_site_force_failed_a_full_replay_is_byte_identical(engine, org):
    """THE DOCTRINE TEST.

    A real execution, persisted to a real store, replayed three ways: with no model at all, with a
    model that answers well, and with every R-site refused. The decision has to come back
    byte-identical every time — and the third run has to be visibly a force-fail rather than a run
    that happened to have no client, or the test proves nothing about the switch.
    """
    execution = _execute(org)
    store = ReasoningStore(engine=engine)
    bundle_store = BundleStore(engine)
    persisted = persist_execution(store=store, execution=execution,
                                  context_payload_ttl_hours=TTL_HOURS)
    run_id = persisted["run"]["run_id"]
    orchestrator = ReasoningOrchestrator(default_registry())

    def _replayed():
        replayed, comparison = replay_persisted(
            store=store, org_id=org, run_id=run_id, orchestrator=orchestrator)
        assert comparison.matches, comparison.differences
        return canonicalize(replayed.decision.to_semantic_dict()), replayed.decision.semantic_hash

    baseline = _replayed()

    # (a) narrated with no model configured — the deployment state of every tenant today
    narrate(execution.decision, execution.ordered_results,
            gate=_narrating_gate(org), eval_time=NOW, request=execution.request,
            store=bundle_store, run_id=run_id)
    assert _replayed() == baseline

    # (b) narrated by a model that answered
    narrate(execution.decision, execution.ordered_results,
            gate=_narrating_gate(org, client=_good_generation(execution)), eval_time=NOW,
            request=execution.request, store=bundle_store, run_id=run_id)
    assert _replayed() == baseline

    # (c) every R-site force-failed
    with force_failed():
        outcome = narrate(execution.decision, execution.ordered_results,
                          gate=_narrating_gate(org, client=_good_generation(execution)),
                          eval_time=NOW, request=execution.request, store=bundle_store,
                          run_id=run_id)
    assert _replayed() == baseline
    if outcome is not None:
        assert outcome.consult.outcome == "force_failed", (
            "the force-fail run did not actually go through the switch, so it proved nothing")


def test_a_force_failed_run_still_produces_a_card(engine, org):
    """The other half of the acceptance row: "decisions byte-identical AND every card still renders
    (template prose)". A doctrine that produced silence instead of plainer prose would be a
    different, worse product."""
    execution = _execute(org)
    if execution.decision.action_id is None:
        pytest.skip("this capability did not commit to an action on this context")
    with force_failed():
        narration = narrate(execution.decision, execution.ordered_results,
                            gate=_narrating_gate(org, client=_good_generation(execution)),
                            eval_time=NOW, request=execution.request)
    assert narration is not None and narration.is_fallback
    rendered = narration.bundle.render()
    assert all(rendered[name] for name in
               ("headline", "situation_summary", "why_it_matters", "root_cause",
                "recommendation_rationale", "expected_effect"))


def test_the_narrative_is_cached_on_the_decision_and_never_regenerated(engine, org):
    """Doc 11 guard 2 and loop L-2: the same decision re-surfaced tomorrow reads exactly as it read
    today, and costs nothing to re-read."""
    execution = _execute(org)
    if execution.decision.action_id is None:
        pytest.skip("this capability did not commit to an action on this context")
    bundle_store = BundleStore(engine)
    llm = _good_generation(execution)
    first = narrate(execution.decision, execution.ordered_results,
                    gate=_narrating_gate(org, client=llm), eval_time=NOW,
                    request=execution.request, store=bundle_store)
    calls_after_first = len(llm.calls)
    second = narrate(execution.decision, execution.ordered_results,
                     gate=_narrating_gate(org, client=llm), eval_time=NOW,
                     request=execution.request, store=bundle_store)
    assert second is not None and second.cached
    assert len(llm.calls) == calls_after_first, "a cached decision paid for a second generation"
    assert second.bundle.bundle_hash == first.bundle.bundle_hash


# ═════════════════════════════════════════════════════════════════════════════════════════════
# 3 · AT THE SEAM — no R-site can reach a model except through the gate
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_no_module_in_the_bundle_package_calls_a_model_except_the_gate():
    """Read from the AST, so it holds for the R-sites this wave did not build. "No R-site may call
    a model directly" is doc 01 C5's first sentence, and it is the reason the doctrine test above
    can be trusted to keep holding."""
    import genios_engine.reason.bundle as package
    from pathlib import Path
    offenders = []
    for path in sorted(Path(package.__file__).parent.glob("*.py")):
        if path.name in {"gate.py", "sweep.py"}:
            continue                       # the gate IS the caller; the sweep only RESOLVES one
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "call":
                offenders.append(f"{path.name}: a bare .call( — only the gate may consult a model")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""])
                for name in names:
                    if "llm" in name.lower() or "anthropic" in name.lower():
                        offenders.append(f"{path.name}: imports {name}")
    assert not offenders, "\n".join(offenders)


def test_the_gate_checks_activation_before_it_checks_anything_else():
    """Step order is the policy. A gate that checked the budget first would spend a query on a
    tenant that is not on the pilot; one that built a prompt first would spend the work."""
    source = inspect.getsource(GATE_MODULE.RSiteGate.consult)
    order = [marker for marker in
             ("self._activated", "force_fail_r_sites()", "precondition", "cached", "self._client",
              "build_prompt(None)", "self._budget.check", "self._client.call")
             if marker in source]
    assert order == ["self._activated", "force_fail_r_sites()", "precondition", "cached",
                     "self._client", "build_prompt(None)", "self._budget.check",
                     "self._client.call"]
    assert source.index("self._activated") < source.index("self._client.call")


def test_the_doctrine_switch_is_readable_from_the_environment():
    """So the property can be checked against a running deployment and not only in a unit test."""
    assert GATE_MODULE.FORCE_FAIL_ENV == "GENIOS_L4_FORCE_FAIL_R_SITES"
    assert not GATE_MODULE.force_fail_r_sites()
    with force_failed():
        assert GATE_MODULE.force_fail_r_sites()


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE REAL PATH — L1 shipped six unreached units, L2 five, L3 two. Not this time.
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_production_entry_calls_the_narration_pass():
    """`run_all` is THE production entry — every caller in `api/routes.py` enters through it."""
    source = inspect.getsource(RUNNER.run_all)
    assert "narrate_published" in source, (
        "reason/runner.run_all no longer narrates what it published — the voice is unwired")
    assert "from genios_engine.reason.bundle import narrate_published" in source


def test_the_narration_runs_after_publication_and_not_before():
    """Doc 05 §7 and doc 11 guard 5: a slow model may never delay a decision. Positional, because
    the guarantee IS the position — moving the call above the pack loop would put a model on the
    critical path without changing a single behaviour a unit test could see."""
    source = inspect.getsource(RUNNER.run_all)
    assert source.index("for pid in pack_ids") < source.index("narrate_published")
    assert source.index("narrate_published") < source.index('return {"nodes"')


def test_the_narration_pass_cannot_fail_the_sweep():
    source = inspect.getsource(RUNNER.run_all)
    tail = source[source.index("narrate_published"):]
    assert "except Exception" in tail, (
        "a narrative that failed must be a plainer card, never a failed sweep")


def test_the_sweep_is_gated_on_the_tenants_own_switch(engine, org):
    """No row, no consult, no spend — and one query to find that out."""
    class Store:
        def __init__(self, eng):
            self.engine = eng
    tally = sweep.narrate_published(store=Store(engine), org_id=org, eval_time=NOW)
    assert tally["narrated"] == 0
    assert "bundle_not_activated" in tally["skipped"]


def test_the_card_feed_reads_the_narrative_it_wrote():
    """The founder-bar surface. A narrative nobody can see is the same defect as no narrative."""
    from genios_engine.api import intelligence_routes as IR
    source = inspect.getsource(IR.list_insights)
    assert "_card_narratives" in source and '"reasoning"' in source
    helper = inspect.getsource(IR._card_narratives)
    assert "bundles_for_cards" in helper
    assert "except Exception" in helper, (
        "a missing narrative must never be a failed feed")


def test_the_narrative_tables_are_erased_with_the_account():
    from genios_engine.api import account_routes as ACC
    assert "l4_reasoning_bundles" in ACC._ORG_SCOPED_TABLES
    assert "l4_r_site_calls" in ACC._ORG_SCOPED_TABLES
    assert (ACC._ORG_SCOPED_TABLES.index("l4_reasoning_bundles")
            < ACC._ORG_SCOPED_TABLES.index("reasoning_runs")), (
        "the narrative points at a run; the deletion order in that list is load-bearing")


def test_semantic_hash_is_the_cache_key_and_not_the_store_hash(engine, org):
    """The two decision hashes are different numbers and the bug is silent both ways: keyed on the
    store's, a decision that had not moved would regenerate every sweep; joined on the contract's,
    a card would never find its prose."""
    execution = _execute(org)
    if execution.decision.action_id is None:
        pytest.skip("this capability did not commit to an action on this context")
    persisted = persist_execution(store=ReasoningStore(engine=engine), execution=execution,
                                  context_payload_ttl_hours=TTL_HOURS)
    store_hash = persisted["output"]["decision_hash"]
    contract_hash = execution.decision.semantic_hash
    assert store_hash != contract_hash, (
        "these two became the same number, which would make the distinction untestable")
    bundle_store = BundleStore(engine)
    narrate(execution.decision, execution.ordered_results, gate=_narrating_gate(org),
            eval_time=NOW, request=execution.request, store=bundle_store,
            run_id=persisted["run"]["run_id"], store_decision_hash=store_hash)
    with engine.connect() as conn:
        row = conn.execute(text(
            "select decision_hash, store_decision_hash from l4_reasoning_bundles "
            "where org_id=:o"), {"o": org}).first()
    assert row.decision_hash == contract_hash
    assert row.store_decision_hash == store_hash
    assert bundle_store.get(org_id=org, decision_hash=contract_hash) is not None
    assert semantic_hash and datetime and timedelta and timezone      # imports are load-bearing


# ═════════════════════════════════════════════════════════════════════════════════════════════
# END TO END: a published signal -> the sweep -> a narrative -> the card feed's read
# ═════════════════════════════════════════════════════════════════════════════════════════════

def _publish(engine, org_id: str, execution, persisted) -> tuple[str, str]:
    """A signal and a card the way the compiled lane writes them, so the sweep's worklist read and
    the feed's join are exercised against the REAL rows and their six foreign keys."""
    run = persisted["run"]
    output = persisted["output"]
    signal_id, card_id = f"sig_{org_id}", f"card_{org_id}"
    with engine.begin() as conn:
        conn.execute(text(
            "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, "
            "rule_version, level, subject_node_id, score, reason_code, eval_time, "
            "config_snapshot_id, reasoning_run_id, reasoning_candidate_id, "
            "reasoning_decision_hash, authority_expires_at, capability_id, status) "
            "values (:s, :o, 'sales', '1.0.0', 'deal_cooling', 1, 'prescriptive', 'deal_1', 70, "
            "'deal_cooling', :t, :cfg, :run, :cand, :dh, :exp, :cap, 'open')"),
            {"s": signal_id, "o": org_id, "t": NOW, "cfg": run["config_snapshot_id"],
             "run": run["run_id"], "cand": output["selected_candidate_id"],
             "dh": output["decision_hash"], "exp": NOW + timedelta(days=7),
             "cap": execution.decision.capability_id})
        conn.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, expires_at) values (:c, :s, :o, 'prescriptive', 'high', "
            "'Deal cooling', 'The deal has gone quiet', 70, :exp)"),
            {"c": card_id, "s": signal_id, "o": org_id, "exp": NOW + timedelta(days=7)})
    return signal_id, card_id


def test_the_sweep_narrates_what_the_lane_just_published_and_the_feed_can_read_it(engine, org):
    """The whole path, on real rows: an activated tenant, a published signal, the worklist read,
    the verified replay, the narration, the stored prose, and the join a card surface makes."""
    from genios_engine.platform import l4_activation as ACT
    from genios_engine.reason.bundle import bundles_for_cards

    execution = _published_execution(engine, org)
    if execution.decision.action_id is None:
        pytest.skip("this capability did not commit to an action on this context")
    persisted = persist_execution(store=ReasoningStore(engine=engine), execution=execution,
                                  context_payload_ttl_hours=TTL_HOURS)
    _signal_id, card_id = _publish(engine, org, execution, persisted)
    ACT.activate(engine, org, feature=FEATURE_BUNDLE, by="tests")

    class Store:
        def __init__(self, eng):
            self.engine = eng

    tally = sweep.narrate_published(store=Store(engine), org_id=org, eval_time=NOW,
                                    llm=_good_generation(execution))
    assert tally["considered"] == 1, tally
    assert tally["narrated"] == 1, tally

    narratives = bundles_for_cards(engine, org_id=org, card_ids=[card_id])
    assert card_id in narratives, "the narrative never reached the surface that renders it"
    card = narratives[card_id]
    for section in ("headline", "situation_summary", "why_it_matters", "root_cause",
                    "recommendation_rationale", "expected_effect"):
        assert card[section], section
    assert card["generation"], "a card must always be able to say how its prose was produced"
    assert "{" not in card["why_it_matters"]

    # ... and a second sweep finds nothing left to do, which is what stops loop L-2 from paying
    # for the same decision every drain.
    assert sweep.narrate_published(store=Store(engine), org_id=org, eval_time=NOW,
                                   llm=_good_generation(execution))["considered"] == 0


def test_a_tenant_switched_off_mid_pilot_stops_narrating(engine, org):
    from genios_engine.platform import l4_activation as ACT

    execution = _published_execution(engine, org)
    persisted = persist_execution(store=ReasoningStore(engine=engine), execution=execution,
                                  context_payload_ttl_hours=TTL_HOURS)
    _publish(engine, org, execution, persisted)
    ACT.activate(engine, org, feature=FEATURE_BUNDLE, by="tests")
    ACT.deactivate(engine, org, feature=FEATURE_BUNDLE, by="tests")

    class Store:
        def __init__(self, eng):
            self.engine = eng
    tally = sweep.narrate_published(store=Store(engine), org_id=org, eval_time=NOW)
    assert tally["narrated"] == 0 and "bundle_not_activated" in tally["skipped"]


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE THREE PLACES A BAD NARRATIVE COULD STILL REACH A CARD
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_a_stored_narrative_is_refused_for_a_decision_that_chose_something_else(engine, org):
    """Doc 09 case 2 has one route the constructor cannot close: a bundle that is internally
    perfect, arriving from the CACHE, for a decision whose action has moved. The read checks."""
    execution = _published_execution(engine, org)
    if execution.decision.action_id is None:
        pytest.skip("this capability did not commit to an action on this context")
    bundle_store = BundleStore(engine)
    narrate(execution.decision, execution.ordered_results, gate=_narrating_gate(org),
            eval_time=NOW, request=execution.request, store=bundle_store)
    key = execution.decision.semantic_hash
    assert bundle_store.get(org_id=org, decision_hash=key,
                            expect_action_id=execution.decision.action_id) is not None
    assert bundle_store.get(org_id=org, decision_hash=key,
                            expect_action_id="some_other_play") is None, (
        "a cached narrative was handed to a decision that committed to a different action")


def test_a_generation_the_gauntlet_refuses_never_becomes_a_bundle(engine, org):
    """The constructor holds V-3's ids, V-4, V-5 and V-7; V-1, V-2 and V-6 need the SITUATION and
    are the gauntlet's alone. This generation is one the constructor would happily accept — no
    digits, no placeholders, every cap met — and it names a company that does not exist."""
    execution = _published_execution(engine, org)
    if execution.decision.action_id is None:
        pytest.skip("this capability did not commit to an action on this context")
    invented = FakeLLM(FakeResult(parsed={
        "headline": "Deal cooling on an open deal",
        "situation_summary": "The deal is open and the engagement reading has fallen away.",
        "why_it_matters": "Contoso Holdings has been evaluating the same category all quarter.",
        "root_cause": "The reasoning units report a cooling deal on the recorded evidence.",
        "recommendation_rationale": "Recommended: the play the engine ranked first here.",
        "expected_effect": "Acting addresses the cooling; doing nothing leaves it where it is.",
    }), FakeResult(parsed={
        "headline": "Deal cooling on an open deal",
        "situation_summary": "The deal is open and the engagement reading has fallen away.",
        "why_it_matters": "Contoso Holdings has been evaluating the same category all quarter.",
        "root_cause": "The reasoning units report a cooling deal on the recorded evidence.",
        "recommendation_rationale": "Recommended: the play the engine ranked first here.",
        "expected_effect": "Acting addresses the cooling; doing nothing leaves it where it is.",
    }))
    narration = narrate(execution.decision, execution.ordered_results,
                        gate=_narrating_gate(org, client=invented), eval_time=NOW,
                        request=execution.request)
    assert narration is not None
    assert narration.is_fallback, "an invented entity reached a customer's card"
    assert "Contoso" not in "".join(str(v) for v in narration.bundle.render().values())
    assert narration.gauntlet is not None and not narration.gauntlet.passed
    assert "V-6" in {check.check for check in narration.gauntlet.failures}


def test_a_run_that_does_not_replay_is_never_narrated(engine, org, monkeypatch):
    """The sweep's whole argument is that the narrative is about a decision the record can PROVE.
    A run whose replay disagrees with what was stored is not one, and narrating it would attach
    prose about the decision this process just computed to the card for the decision that was
    published."""
    from genios_engine.platform import l4_activation as ACT
    from genios_engine.reason import replay as REPLAY

    execution = _published_execution(engine, org)
    persisted = persist_execution(store=ReasoningStore(engine=engine), execution=execution,
                                  context_payload_ttl_hours=TTL_HOURS)
    _publish(engine, org, execution, persisted)
    ACT.activate(engine, org, feature=FEATURE_BUNDLE, by="tests")

    real = REPLAY.replay_persisted

    def _disagreeing(**kwargs):
        replayed, comparison = real(**kwargs)
        from dataclasses import replace as _replace
        return replayed, _replace(comparison, decision_matches=False,
                                  differences=("decision_hash",))

    monkeypatch.setattr(REPLAY, "replay_persisted", _disagreeing)

    class Store:
        def __init__(self, eng):
            self.engine = eng
    tally = sweep.narrate_published(store=Store(engine), org_id=org, eval_time=NOW,
                                    llm=_good_generation(execution))
    assert tally["considered"] == 1 and tally["narrated"] == 0
    assert tally["skipped"].get("replay_mismatch") == 1


def test_the_decider_imports_nothing_that_can_narrate_or_call_a_model():
    """LAW 1, THE HALF THAT HAD NO TEST — `DecisionMaker.decide()` is the sole synthesis
    authority, and doc 08's preserve-hard row for it is *"one decider"*.

    The L4 build record claims this invariant was held "grep + mutation PH1", and the grep is
    true today: `reason/decision_maker.py` imports nothing from `bundle/`, `narration` or
    `llm_sites`. But a grep run once by a gate is not an invariant — it is a measurement whose
    expiry date is the next refactor. Injecting `from genios_engine.reason.bundle import narrate`
    at the top of `decision_maker.py` left the whole suite GREEN, which means the one law the
    doctrine rests on could have been broken by an import completing an otherwise ordinary
    change. `test_no_module_in_the_bundle_package_calls_a_model_except_the_gate` guards the seam
    from the bundle's side; nothing guarded it from the decider's.

    Read from the AST rather than the text so an import inside a function body — the shape a
    refactor actually reaches for when a module-level import would be circular — is caught too.
    """
    from pathlib import Path

    import genios_engine.reason.decision_maker as decider

    forbidden = ("bundle", "narration", "llm_sites", "llm", "anthropic", "critique")
    tree = ast.parse(Path(decider.__file__).read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [f"{'.' * node.level}{node.module or ''}"]
        else:
            continue
        for name in names:
            tail = name.rsplit(".", 1)[-1].lower()
            if any(token == tail or f".{token}" in name.lower() for token in forbidden):
                offenders.append(f"line {node.lineno}: imports {name}")
    assert not offenders, (
        "reason/decision_maker.py may not import the voice or a model client — Law 1 says the "
        "decision is fixed before any narrative exists:\n" + "\n".join(offenders))
