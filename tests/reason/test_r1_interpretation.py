"""R-1 · the ambiguity interpreter: what makes it fire, what it may say, and what it may never do.

THE TWO FAILURES THIS FILE EXISTS TO CATCH, both of which have shipped in this repository before:

  * a site that fires on everything — a cost line wearing an intelligence feature's name;
  * a site that fires on nothing — Layer 2's fifteen dead sales rules, gated on a field 9% of
    records carried, with the suite green throughout.

So the precondition is measured here on a POPULATION with a known answer, not merely asserted on one
happy example. And the doctrine half — a reading can never raise a confidence, never re-enter itself,
and never change a decision when the model is down — is pinned as a property of the shipped code.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
)
from genios_engine.reason import interpretation as I
from genios_engine.reason.evidence import build_evidence_ref
from genios_engine.reason.bundle.gate import force_failed
from genios_engine.reason.llm_sites import (
    OUTCOME_FORCE_FAILED,
    OUTCOME_NOT_ACTIVATED,
    OUTCOME_RAN,
    InMemorySiteCache,
    SiteReceipt,
    make_gate,
)


def gate(client=None, *, activated=frozenset({"bundle"})):
    """The ONE C5 gate (`reason/bundle/gate.RSiteGate`), wired for a test.

    Not a stand-in for it: these sites have no policy of their own, so a test that faked one would
    be testing a gate that does not ship. `activated` is passed explicitly rather than read from a
    database so the hermetic cases stay hermetic.
    """
    return make_gate(org_id="org_1", client=client, activated=activated)

NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
HEDGED = "They are considering moving some workloads to another vendor next quarter."
SETTLED = "The renewal has been signed and countersigned by both parties this morning."


class Client:
    """A model that answers whatever it was constructed with, and counts how often it was asked."""

    model = "claude-sonnet-5"

    def __init__(self, *payloads, ok: bool = True):
        self.payloads = list(payloads)
        self.calls = 0
        self.ok = ok
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400):
        from genios_engine.context.llm.client import LLMResult
        self.calls += 1
        self.prompts.append(prompt)
        payload = self.payloads[min(self.calls - 1, len(self.payloads) - 1)]
        return LLMResult(parsed=payload, raw="", ok=self.ok, model=self.model,
                         input_tokens=900, output_tokens=150)


def reading(classification=I.EVALUATING_ALTERNATIVES, confidence_bp=7000):
    return {"classification": classification, "confidence_bp": confidence_bp}


def request(facts, *, declared=("deal.note",), missing=()):
    spec = ReasonerSpec(reasoner_id="core.risk", version="1.0.0", required_fields=tuple(declared))
    capability = CapabilityManifest(
        capability_id="test.capability", version="1.0.0", domain="test",
        root_entity_type="entity",
        goal=Goal(goal_id="g", statement="Prove the precondition."), reasoners=(spec,),
        plays=(PlayDefinition(play_id="do_it", version="1.0.0", label="Do it", steps=("a",)),),
        policies=(), live_delivery_enabled=False)
    evidence = tuple(
        build_evidence_ref(org_id="org_1", entity_ref="node_1", field=name,
                           value=(record["value"] if isinstance(record, dict) else record),
                           source_ref=f"src:{name}")
        for name, record in facts.items())
    context = ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="node_1", root_entity_type="entity",
        evaluation_time=NOW, selector_version="v1", facts=facts, evidence=evidence,
        missing_fields=tuple(missing))
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="test.trigger")


def fact(value):
    return {"value": value}


# ── the precondition ─────────────────────────────────────────────────────────────────────────

def test_a_hedged_claim_on_a_field_the_plan_reads_is_genuine_ambiguity():
    flags = I.find_ambiguities(request({"deal.note": fact(HEDGED)}))
    assert [(f.field, f.kind) for f in flags] == [("deal.note", I.AMBIGUITY_HEDGED)]
    assert flags[0].span == HEDGED


def test_a_settled_claim_is_not_ambiguous_and_costs_nothing():
    assert I.find_ambiguities(request({"deal.note": fact(SETTLED)})) == ()


def test_a_field_the_plan_does_not_read_is_not_interpreted():
    """Doc 11 guard 7: an UNRESOLVED flag on a fact the plan actually reads, never "just in case"."""
    assert I.find_ambiguities(
        request({"other.note": fact(HEDGED)}, declared=("deal.note",))) == ()


def test_a_typed_absence_is_r5s_case_and_is_refused_here():
    """Doc 09 case 13 — a MISSING fact defers to a human; it is not interpreted into existence."""
    assert I.find_ambiguities(
        request({"deal.note": fact(HEDGED)}, missing=("deal.note",))) == ()


def test_a_number_is_never_ambiguous():
    assert I.find_ambiguities(request({"deal.note": fact(84000)})) == ()


def test_text_outside_the_length_band_is_not_a_stance():
    short = request({"deal.note": fact("maybe")})
    long = request({"deal.note": fact("we might " + "x" * I.MAX_SPAN_CHARS)})
    assert I.find_ambiguities(short) == ()
    assert I.find_ambiguities(long) == ()


def test_an_unresolved_conflict_on_a_read_field_is_ambiguity_even_without_a_hedge():
    conflict = {"value": {"field": "deal.note", "resolution": I.UNRESOLVED_CONFLICT,
                          "claim_count": 2, "conflict_id": "cf_1"}}
    flags = I.find_ambiguities(request(
        {"deal.note": fact(SETTLED), "situation.conflict.deal.note": conflict},
        declared=("deal.note", "situation.conflict.deal.note")))
    assert [(f.field, f.kind) for f in flags] == [("deal.note", I.AMBIGUITY_CONFLICT)]


def test_a_resolved_conflict_is_not_reopened():
    conflict = {"value": {"field": "deal.note", "resolution": "resolved_by_authority",
                          "claim_count": 2, "conflict_id": "cf_1"}}
    assert I.find_ambiguities(request(
        {"deal.note": fact(SETTLED), "situation.conflict.deal.note": conflict},
        declared=("deal.note", "situation.conflict.deal.note"))) == ()


def test_the_flags_are_capped_and_ordered_deterministically():
    facts = {f"deal.note_{index}": fact(HEDGED) for index in range(6)}
    declared = tuple(facts)
    flags = I.find_ambiguities(request(facts, declared=declared))
    assert len(flags) == I.MAX_FLAGS_PER_SITUATION
    assert [f.field for f in flags] == sorted(f.field for f in flags)
    assert flags == I.find_ambiguities(request(facts, declared=declared))


def test_a_conflicted_field_outranks_a_merely_hedged_one_when_the_cap_bites():
    facts = {"a.note": fact(HEDGED), "b.note": fact(HEDGED), "c.note": fact(HEDGED),
             "z.note": fact(HEDGED),
             "situation.conflict.z.note": {"value": {"field": "z.note",
                                                     "resolution": I.UNRESOLVED_CONFLICT,
                                                     "claim_count": 2, "conflict_id": "cf"}}}
    flags = I.find_ambiguities(request(facts, declared=tuple(facts)))
    assert flags[0].field == "z.note" and flags[0].kind == I.AMBIGUITY_CONFLICT


def test_the_plan_narrows_the_read_set_rather_than_the_manifest_widening_it():
    """`plan_read_fields` with a plan reads only the units the plan SCHEDULED."""
    req = request({"deal.note": fact(HEDGED)})

    class Plan:
        steps = ()                       # nothing scheduled: the risk unit was dropped

    assert "deal.note" not in I.plan_read_fields(req, Plan())
    assert "deal.note" in I.plan_read_fields(req)


# ── the fire rate, measured ──────────────────────────────────────────────────────────────────

def test_the_fire_rate_tracks_a_known_population_rather_than_firing_on_everything():
    """The measurement the module is judged on, run on a corpus whose true answer is declared.

    A detector that fired on the settled half would show up as a fire rate far above the planted
    share — the "cost line" failure — and one that missed the hedged half as a recall below 100%,
    which is the dead-rule failure. Both are numbers here, not opinions.
    """
    import importlib.util
    import pathlib
    path = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ambiguity_fire_rate.py"
    spec = importlib.util.spec_from_file_location("ambiguity_fire_rate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    quiet = module.seeded(400, hedged_share=0.05)
    busy = module.seeded(400, hedged_share=0.25)
    assert quiet["detector_recall_pct"] == 100.0 and busy["detector_recall_pct"] == 100.0
    assert quiet["detector_false_positive_pct"] == 0.0
    assert busy["detector_false_positive_pct"] == 0.0
    assert 2.0 <= quiet["fire_rate_per_fact_pct"] <= 9.0
    assert 20.0 <= busy["fire_rate_per_fact_pct"] <= 32.0


# ── what the model may say ───────────────────────────────────────────────────────────────────

def test_a_classification_outside_the_enum_is_refused_not_coerced():
    client = Client(reading("URGENT"), reading("URGENT"))
    result = I.interpret(I.find_ambiguities(request({"deal.note": fact(HEDGED)}))[0],
                         org_id="org_1", gate=gate(client))
    assert result is None
    assert client.calls == 2                       # one retry, then silence — never a third


def test_a_confidence_outside_the_band_is_refused_not_clamped():
    client = Client(reading(confidence_bp=9900))
    assert I.interpret(I.find_ambiguities(request({"deal.note": fact(HEDGED)}))[0],
                       org_id="org_1", gate=gate(client)) is None


def test_not_interpretable_is_an_honest_answer_that_reaches_no_snapshot():
    flag = I.find_ambiguities(request({"deal.note": fact(HEDGED)}))[0]
    client = Client(reading(I.NOT_INTERPRETABLE, 3000))
    result = I.interpret(flag, org_id="org_1", gate=gate(client))
    assert result is not None and not result.is_reading
    req = request({"deal.note": fact(HEDGED)})
    assert I.augment(req, [result]) is req


def test_the_prompt_shows_the_model_one_sentence_and_no_decision():
    """It cannot recommend, rank or prioritise because it is not told there is anything to rank."""
    flag = I.find_ambiguities(request({"deal.note": fact(HEDGED)}))[0]
    client = Client(reading())
    I.interpret(flag, org_id="org_1", gate=gate(client))
    prompt = client.prompts[0]
    assert HEDGED in prompt
    for forbidden in ("candidate", "utility", "score", "recommend", "play"):
        assert forbidden not in prompt.lower()


# ── what a reading may never do ──────────────────────────────────────────────────────────────

def test_a_reading_enters_as_evidence_that_can_never_raise_a_confidence():
    """Rule 11's unstated pool. `decision_maker` skips it BY NAME, and the two strings are pinned
    equal here — a rename that separated them would silently give the model a way to buy certainty."""
    from genios_engine.reason.decision_maker import UNATTRIBUTED_GROUP
    assert I.UNATTRIBUTED_GROUP == UNATTRIBUTED_GROUP

    req = request({"deal.note": fact(HEDGED)})
    flag = I.find_ambiguities(req)[0]
    result = I.interpret(flag, org_id="org_1", gate=gate(Client(reading())))
    augmented = I.augment(req, [result])
    ref = next(item for item in augmented.context.evidence
               if item.field == "interpretation.deal.note")
    assert ref.independence_group == UNATTRIBUTED_GROUP
    assert ref.source_ref_id.startswith("llm_interpretation:")


def test_a_reading_is_never_itself_reinterpreted():
    """Doc 09 loop L-6 — one hop, structurally, for the interpretation AND for the claim it read."""
    req = request({"deal.note": fact(HEDGED)})
    flag = I.find_ambiguities(req)[0]
    result = I.interpret(flag, org_id="org_1", gate=gate(Client(reading())))
    augmented = I.augment(req, [result])
    assert I.find_ambiguities(augmented) == ()


def test_the_namespace_guard_holds_even_for_a_text_shaped_interpretation():
    """The one-hop law, tested where it actually bites.

    Today an `interpretation.*` fact carries a MAPPING, so `_fact_text` would decline it anyway and
    the namespace check reads as belt-and-braces. That is exactly the reason to pin it: the day the
    reading is stored as its span — a one-line change to `Interpretation.as_fact` — the namespace
    check is the only thing standing between R-1 and interpreting its own output forever. This test
    plants that shape deliberately.
    """
    req = request({"deal.note": fact(SETTLED),
                   "interpretation.deal.other": fact(HEDGED)},
                  declared=("deal.note", "interpretation.deal.other"))
    assert I.find_ambiguities(req) == ()


def test_an_interpretation_never_overwrites_a_fact_that_is_already_there():
    req = request({"deal.note": fact(HEDGED),
                   "interpretation.deal.note": fact({"classification": "COMMITMENT_MADE"})},
                  declared=("deal.note", "interpretation.deal.note"))
    flag = I.AmbiguityFlag(field="deal.note", kind=I.AMBIGUITY_HEDGED, span=HEDGED,
                           digest="d" * 64, observed_at="unobserved")
    result = I.Interpretation(flag=flag, classification=I.EVALUATING_ALTERNATIVES,
                              confidence_bp=7000, generation="llm:m@v",
                              receipt=SiteReceipt(
                                  site="R-1", outcome=OUTCOME_RAN, generation="llm:m@v",
                                  cache_key="k"))
    assert I.augment(req, [result]) is req


def test_a_reading_cannot_claim_more_certainty_than_the_ceiling():
    with pytest.raises(ValueError):
        I.Interpretation(
            flag=I.AmbiguityFlag(field="f", kind=I.AMBIGUITY_HEDGED, span=HEDGED,
                                 digest="d", observed_at="unobserved"),
            classification=I.EVALUATING_ALTERNATIVES, confidence_bp=9999,
            generation="llm:m@v",
            receipt=SiteReceipt(
                site="R-1", outcome=OUTCOME_RAN, generation="llm:m@v", cache_key="k"))


# ── the gate, and the doctrine ───────────────────────────────────────────────────────────────

def test_a_tenant_that_is_not_activated_buys_nothing():
    client = Client(reading())
    assert I.interpret(I.find_ambiguities(request({"deal.note": fact(HEDGED)}))[0],
                       org_id="org_1", gate=gate(client, activated=frozenset())) is None
    assert client.calls == 0


def test_no_gate_at_all_is_answered_as_no_model_and_never_as_permission():
    client = Client(reading())
    assert I.interpret(I.find_ambiguities(request({"deal.note": fact(HEDGED)}))[0],
                       org_id="org_1", gate=None) is None
    assert client.calls == 0


def test_one_interpretation_per_claim_version_and_the_second_read_is_free():
    """Doc 09 case 12 — cached by claim hash, so two drains cannot read one claim two ways."""
    cache = InMemorySiteCache()
    flag = I.find_ambiguities(request({"deal.note": fact(HEDGED)}))[0]
    client = Client(reading())
    site_gate = gate(client)
    first = I.interpret(flag, org_id="org_1", gate=site_gate, cache=cache)
    second = I.interpret(flag, org_id="org_1", gate=site_gate, cache=cache)
    assert client.calls == 1
    assert second.receipt.outcome == "cached"
    assert (first.classification, first.confidence_bp) == (second.classification,
                                                           second.confidence_bp)


def test_a_claim_that_changed_is_a_different_claim():
    cache = InMemorySiteCache()
    client = Client(reading())
    site_gate = gate(client)
    for text in (HEDGED, HEDGED.replace("next quarter", "next month")):
        flag = I.find_ambiguities(request({"deal.note": fact(text)}))[0]
        I.interpret(flag, org_id="org_1", gate=site_gate, cache=cache)
    assert client.calls == 2


def test_the_site_is_failable_and_a_forced_failure_changes_nothing():
    """K4's doctrine test in miniature, through the SHIPPED switch.

    `force_failed()` is the bundle group's env switch — the one K4's replay flips — and it turns
    this site off too, because this site goes through the same gate. A separate switch for R-1
    would mean the doctrine test could pass while R-1 kept calling a model.
    """
    req = request({"deal.note": fact(HEDGED)})
    interpreter = I.AmbiguityInterpreter(org_id="org_1", gate=gate(Client(reading())))
    with force_failed():
        assert interpreter(req) is req
        assert interpreter.readings(req) == ()


def test_a_forced_failure_is_recorded_as_a_forced_failure_and_not_as_an_outage():
    from genios_engine.reason.llm_sites import SITE_R1, run_site
    flag = I.find_ambiguities(request({"deal.note": fact(HEDGED)}))[0]
    with force_failed():
        result = run_site(site=SITE_R1, org_id="org_1", seed={"digest": flag.digest},
                          precondition=True, build_prompt=lambda: "p", parse=dict,
                          fallback=dict, gate=gate(Client(reading())))
    assert result.receipt.outcome == OUTCOME_FORCE_FAILED


def test_an_interpretation_moves_the_snapshot_only_when_there_is_one():
    req = request({"deal.note": fact(HEDGED)})
    flag = I.find_ambiguities(req)[0]
    result = I.interpret(flag, org_id="org_1", gate=gate(Client(reading())))
    augmented = I.augment(req, [result])
    assert augmented.context.context_snapshot_id != req.context.context_snapshot_id
    assert augmented.request_id != req.request_id      # derived, never carried
    assert dict(augmented.context.facts)["interpretation.deal.note"]["value"] == {
        "classification": I.EVALUATING_ALTERNATIVES, "confidence_bp": 7000,
        "span": HEDGED, "kind": I.AMBIGUITY_HEDGED, "field": "deal.note"}
    assert augmented.context.metadata["llm_interpretations"] == (
        "interpretation.deal.note:EVALUATING_ALTERNATIVES:7000",)


def _reading_confidence(req):
    """`request()` declares only `core.risk`; these two cases need the unit that owns confidence.

    Added on top of the shared helper rather than inside it: widening the helper would move the
    capability snapshot id of every other case in this file for no reason of their own.
    """
    from dataclasses import replace as _replace
    return ReasoningRequest(
        org_id=req.org_id,
        capability=_replace(req.capability, reasoners=req.capability.reasoners + (
            ReasonerSpec(reasoner_id="core.confidence", version="1.0.0"),)),
        context=req.context, evaluation_time=req.evaluation_time,
        trigger_kind=req.trigger_kind)


def test_the_reading_cannot_move_the_number_the_floor_is_applied_to():
    """The doctrine property the test above only half proved — measured on the REAL unit.

    `test_a_reading_enters_as_evidence_that_can_never_raise_a_confidence` pins two strings equal
    and stops there, because `decision_maker._stated_groups` was the only place the unstated pool
    was excluded. It was not the only place the pool was READ: `core.confidence`'s
    `CoverageCompletenessPlugin` counted distinct independence groups over the whole snapshot and
    folded every unnamed ref INTO `unattributed`, then counted that pool as an origin — so R-1's
    ref bought 2,500 bp of `evidence_coverage_bp` and 250 bp of blended `confidence_bp`.

    Confidence is what `resolve_confidence_floor` is applied to, so that was a model output moving
    the number that decides whether the engine speaks or stays silent: the doctrine's
    "may never PERMIT", through the one R-site that runs before the decision. Both the unit's
    output and the composed decision confidence are checked, because the leak was in the unit and
    the consequence was on the decision.
    """
    from genios_engine.reason.decision_maker import compose_confidence
    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner

    # The snapshot's own evidence NAMES its origin, which is the discriminating case: with an
    # unstated base the pool is already occupied and R-1's ref joins it, so the leak only shows on
    # a picture whose sources were stated — the shape a real connector produces.
    from dataclasses import replace as _replace
    base = request({"deal.note": fact(HEDGED)})
    stated = ContextSnapshot(
        org_id=base.context.org_id, graph_version=base.context.graph_version,
        root_entity_id=base.context.root_entity_id,
        root_entity_type=base.context.root_entity_type,
        evaluation_time=base.context.evaluation_time,
        selector_version=base.context.selector_version, facts=dict(base.context.facts),
        evidence=tuple(_replace(item, independence_group="crm")
                       for item in base.context.evidence))
    req = _reading_confidence(ReasoningRequest(
        org_id=base.org_id, capability=base.capability, context=stated,
        evaluation_time=base.evaluation_time, trigger_kind=base.trigger_kind))
    flag = I.find_ambiguities(req)[0]
    augmented = I.augment(req, [I.interpret(flag, org_id="org_1", gate=gate(Client(reading())))])
    assert augmented is not req, "the interpretation never reached the snapshot"

    unit = ConfidenceReasoner()
    before, after = unit.evaluate(req, {}), unit.evaluate(augmented, {})
    assert after.metrics["independent_evidence_groups"] == \
        before.metrics["independent_evidence_groups"]
    assert after.metrics["evidence_coverage_bp"] == before.metrics["evidence_coverage_bp"]
    assert after.metrics["confidence_bp"] == before.metrics["confidence_bp"], (
        "a model output moved core.confidence — the LLM may not SCORE or PERMIT")
    assert compose_confidence([after], augmented, False).confidence_bp == \
        compose_confidence([before], req, False).confidence_bp


def test_an_unstated_origin_buys_no_coverage_at_all():
    """The general law behind it, stated once so the fix cannot be undone for a non-R-1 reason.

    `unattributed` is one pool and not one witness, whether it arrived from a model, from a
    connector that named no source, or from a ref carrying whitespace. `decision_maker` has always
    said so; this pins `core.confidence` to the same sentence.
    """
    from genios_engine.reason.decision_maker import UNATTRIBUTED_GROUP
    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner
    from dataclasses import replace as _replace

    req = _reading_confidence(request({"deal.note": fact(HEDGED)}))
    unit = ConfidenceReasoner()
    stated = unit.evaluate(req, {}).metrics["independent_evidence_groups"]
    for unstated in (UNATTRIBUTED_GROUP, "", "   ", None):
        widened = _replace(req.context, evidence=req.context.evidence + (
            _replace(req.context.evidence[0], evidence_id="ev_unstated",
                     independence_group=unstated),))
        probe = ReasoningRequest(org_id=req.org_id, capability=req.capability, context=widened,
                                 evaluation_time=req.evaluation_time,
                                 trigger_kind=req.trigger_kind)
        assert unit.evaluate(probe, {}).metrics["independent_evidence_groups"] == stated, \
            f"{unstated!r} bought an origin"
