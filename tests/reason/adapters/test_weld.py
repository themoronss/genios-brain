"""THE WELD, END TO END — an ExpertisePackage becomes a decision that quotes the corpus.

This is the J1 gate as a test: the shipped corpus, the real Layer 4 kernel, and a real
`ReasoningDecision`. Nothing here is a stub — if the weld stopped reaching Layer 4, every
assertion in this file would go red before anybody read a receipt.
"""

from __future__ import annotations

import json

import pytest

from genios_engine.contracts.domain_expertise import require_weld_receipt
from genios_engine.contracts.reasoning import ExecutionMode
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason.adapters.expertise import ADAPTER_VERSION, expertise_capability_manifest
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.decision_maker import RULE_CONFLICT_REASON, WELD_KEY
from genios_engine.reason.domain_shadow import _rejected_candidates
from genios_engine.reason.engine import NodeContext

from .conftest import CLOSING_PLAY, DEAL_FACTS, DEAL_OBSERVATIONS, NOW, URGENCY_RULE

pytestmark = pytest.mark.unit


def _manifest(compiled, **kwargs):
    return expertise_capability_manifest(
        compiled.package, root_entity_type="company",
        situation=compiled.situation, context=compiled.context, **kwargs)


def _decide(compiled):
    """The real kernel, over the real manifest. `reason_native_capability` is the same entry
    `domain_shadow` calls on the live pass."""
    manifest = _manifest(compiled)
    context = NodeContext(
        node_id="node_1", node_type="company",
        facts={path: {"value": value, "confidence": 900, "authority_rank": 3}
               for path, value in DEAL_FACTS.items()},
        obs=[{"kind": kind, "occurred_at": NOW} for kind in DEAL_OBSERVATIONS])
    execution = reason_native_capability(
        org_id="org_weld", context=context, capability=manifest, evaluation_time=NOW,
        graph_version=1, config_snapshot_id=None, mode=ExecutionMode.SHADOW)
    return manifest, execution.decision


# =================================================================================================
# J1 · a blocking rule eliminates a candidate, and the elimination names the rule
# =================================================================================================

def test_a_blocking_corpus_rule_eliminates_a_candidate_and_names_itself(deal_with_absence):
    _, decision = _decide(deal_with_absence)
    eliminated = {candidate.play_id: candidate.candidate_id for candidate in decision.candidates
                  if candidate.disposition.value == "eliminated"}
    assert CLOSING_PLAY in eliminated, "the blocking rule reached no candidate"

    applied = {record["rule_id"]: record for record in decision.constraints_applied}
    urgency = applied[URGENCY_RULE]
    assert urgency["severity"] == "blocking"
    assert urgency["outcome"] == "fired"
    assert urgency["eliminated_candidate_ids"] == (eliminated[CLOSING_PLAY],)
    # And the elimination carries the authored words, not a paraphrase of them.
    assert urgency["statement"].startswith("A closing recommendation MUST rest on a date")


def test_the_eliminated_candidate_would_otherwise_have_won(deal_with_absence):
    """Doctrine that only removes options nobody wanted is not enforcement. On this fixture the
    play the rule eliminates carries the HIGHEST utility in the field."""
    _, decision = _decide(deal_with_absence)
    eliminated = next(candidate for candidate in decision.candidates
                      if candidate.play_id == CLOSING_PLAY)
    best_survivor = max(candidate.utility_bp for candidate in decision.candidates
                        if candidate.disposition.value == "eligible")
    assert eliminated.utility_bp >= best_survivor


def test_the_rejection_reaches_alternatives_rejected_with_its_quote(deal_with_absence):
    """`signals.rejected_candidates` is what the API renders as `alternatives_rejected`, and the
    compiled lane never wrote it. This is the exact payload `domain_shadow` now stores."""
    _, decision = _decide(deal_with_absence)
    selected = next((c for c in decision.candidates
                     if c.candidate_id == decision.selected_candidate_id), None)
    rejected = _rejected_candidates(decision, selected)
    named = [row for row in rejected if row["eliminated_by"]]
    assert len(named) == 1
    assert named[0]["play_id"] == CLOSING_PLAY
    assert named[0]["eliminated_by"][0]["rule_id"] == URGENCY_RULE
    assert "buyer" in named[0]["eliminated_by"][0]["statement"].lower()
    # It has to survive the driver's JSON encoder, which is not the canonical one.
    assert json.loads(json.dumps(rejected)) == rejected


# =================================================================================================
# J1 · a decision carries a heuristic citation, quoted
# =================================================================================================

def test_the_decision_carries_heuristic_citations_that_are_byte_identical(deal_with_absence):
    manifest, decision = _decide(deal_with_absence)
    assert decision.citations, "the decision carries no citation"
    assert all(item["artifact_class"] == "heuristic" for item in decision.citations)
    # `ReasoningDecision` re-runs V-1 on construction, so reaching this line already proves
    # byte-identity; asserting the payload matches the manifest's proves it was not re-derived.
    assert [dict(item) for item in decision.citations] == [
        dict(item) for item in manifest.metadata[WELD_KEY]["citations"]]


def test_a_decision_predating_the_weld_still_constructs(deal_with_absence):
    """The additive migration, from the consumer side: a manifest with no weld produces a decision
    with no citations and no constraints, exactly as before this wave."""
    from dataclasses import replace

    manifest = _manifest(deal_with_absence)
    metadata = {k: v for k, v in manifest.metadata.items() if k != WELD_KEY}
    stripped = replace(manifest, metadata=metadata)
    context = NodeContext(node_id="node_1", node_type="company",
                          facts={p: {"value": v, "confidence": 900, "authority_rank": 3}
                                 for p, v in DEAL_FACTS.items()},
                          obs=[{"kind": k, "occurred_at": NOW} for k in DEAL_OBSERVATIONS])
    execution = reason_native_capability(
        org_id="org_weld", context=context, capability=stripped, evaluation_time=NOW,
        graph_version=1, config_snapshot_id=None, mode=ExecutionMode.SHADOW)
    assert execution.decision.citations == ()
    assert execution.decision.constraints_applied == ()


# =================================================================================================
# J1 · UNKNOWN never passes and never blocks
# =================================================================================================

def test_an_unevaluable_blocking_rule_neither_fires_nor_blocks(deal_without_absence):
    manifest, decision = _decide(deal_without_absence)
    applied = {record["rule_id"]: record for record in decision.constraints_applied}
    urgency = applied[URGENCY_RULE]
    assert urgency["outcome"] == "unevaluable"
    assert urgency["missing"] == ("commitment.due_at",)
    assert "eliminated_candidate_ids" not in urgency
    assert CLOSING_PLAY not in manifest.metadata[WELD_KEY]["blocked_play_ids"]
    assert all(candidate.disposition.value != "eliminated"
               or candidate.play_id != CLOSING_PLAY for candidate in decision.candidates)


def test_the_only_difference_between_the_two_fixtures_is_typed_absence(
        deal_with_absence, deal_without_absence):
    """The UNKNOWN test is only meaningful if the two fixtures differ in one thing. They do: one
    declares `commitment.due_at` GENUINELY_ABSENT and the other declares nothing."""
    fired = {v["rule_id"] for v in _manifest(deal_with_absence).metadata[WELD_KEY][
        "rule_verdicts"] if v["outcome"] == "fired"}
    unknown = {v["rule_id"] for v in _manifest(deal_without_absence).metadata[WELD_KEY][
        "rule_verdicts"] if v["outcome"] == "unevaluable"}
    assert URGENCY_RULE in fired
    assert URGENCY_RULE in unknown


# =================================================================================================
# THE RECEIPT — invariant #6, extended and never replaced
# =================================================================================================

def test_the_weld_receipt_accounts_for_every_artifact(deal_with_absence):
    manifest = _manifest(deal_with_absence)
    weld = manifest.metadata[WELD_KEY]
    receipt = require_weld_receipt(dict(weld["weld_receipt"]))
    assert receipt["rules_compiled"] == len(weld["compiled_constraints"])
    assert receipt["citations_attached"] == len(weld["citations"])
    assert receipt["framing_blocks_attached"] == len(weld["framing_blocks"])
    assert receipt["rules_fired"] + receipt["rules_unevaluable"] <= receipt["rules_compiled"]
    assert receipt["rules_blocking_fired"] >= 1
    # Every refusal is named with an identifier and counted.
    assert receipt["refusals"]
    for refusal in receipt["refusals"]:
        assert refusal["reason"].replace("_", "").isalnum()
        assert refusal["count"] > 0


def test_the_play_receipt_is_extended_not_replaced(deal_with_absence):
    """The pre-existing receipt keys are load-bearing elsewhere; the weld adds to them."""
    receipt = _manifest(deal_with_absence).metadata["play_receipt"]
    for key in ("authored_rules", "plays_emitted", "plays_rescored_by_learning",
                "skipped_rule_ids", "truncation_reason", "generic_fallback_used"):
        assert key in receipt


def test_every_artifact_class_is_accounted_for_somewhere(deal_with_absence):
    """Law 4, as arithmetic: every authored artifact in the package is either consumed by a named
    consumer or refused by a named reason. Nothing is silently dropped."""
    manifest = _manifest(deal_with_absence)
    package = deal_with_absence.package
    classes = {(record["definition"].get("identity") or {}).get("kind")
               for record in package.expert_rules}
    assert classes == {"playbook", "heuristic", "rule", "mental_model", "decision_framework"}
    by_class = manifest.metadata[WELD_KEY]["weld_receipt"]["by_class"]
    for klass in classes:
        assert by_class.get(klass), f"{klass} has no consumer receipt"


# =================================================================================================
# LAW 2 · reproducible, and safe to store
# =================================================================================================

def test_the_weld_is_byte_identical_across_runs(deal_with_absence):
    first = _manifest(deal_with_absence)
    second = _manifest(deal_with_absence)
    assert first.version == second.version
    assert semantic_hash(first.to_semantic_dict()) == semantic_hash(second.to_semantic_dict())


def test_the_weld_survives_the_jsonb_round_trip_unchanged(deal_with_absence):
    """The manifest is persisted as `jsonb` and rebuilt by `replay.capability_from_manifest`. A
    weld whose hash moved across that trip would break replay for every stored decision."""
    from genios_engine.reason.canonical import canonical_dumps
    from genios_engine.reason.replay import capability_from_manifest

    manifest = _manifest(deal_with_absence)
    rebuilt = capability_from_manifest(json.loads(canonical_dumps(manifest.to_semantic_dict())))
    assert rebuilt.metadata[WELD_KEY]["weld_receipt"] == manifest.metadata[WELD_KEY][
        "weld_receipt"]
    assert semantic_hash(rebuilt.metadata[WELD_KEY]) == semantic_hash(
        manifest.metadata[WELD_KEY])


def test_a_manifest_without_a_situation_says_so_rather_than_claiming_a_clean_run(
        deal_with_absence):
    manifest = expertise_capability_manifest(deal_with_absence.package,
                                             root_entity_type="company")
    weld = manifest.metadata[WELD_KEY]
    assert weld["bound"] is False
    assert weld["blocked_play_ids"] == ()
    assert weld["weld_receipt"]["rules_fired"] == 0
    assert weld["weld_receipt"]["rules_unevaluable"] == weld["weld_receipt"]["rules_compiled"]
    assert all(v["missing"] == ("situation_slice_not_supplied",)
               for v in weld["rule_verdicts"])


def test_the_adapter_declares_the_version_that_produced_this_shape(deal_with_absence):
    manifest = _manifest(deal_with_absence)
    assert manifest.metadata["adapter_version"] == ADAPTER_VERSION == "2.0.0"
    assert manifest.metadata[WELD_KEY]["adapter_version"] == ADAPTER_VERSION


# =================================================================================================
# ABSTENTION — two rules that both fired and contradict each other
# =================================================================================================

def test_layer_4_abstains_when_two_fired_rules_contradict(deal_with_absence):
    """Doc 03's third failure mode. Driven through the real Decision Maker by welding a conflict
    onto the manifest the corpus produced, because no two SHIPPED rules declare each other in
    tension today — the detector runs on every decision, and this is the branch it would take."""
    from dataclasses import replace

    manifest = _manifest(deal_with_absence)
    weld = dict(manifest.metadata[WELD_KEY])
    verdicts = [dict(v) for v in weld["rule_verdicts"] if v["outcome"] == "fired"][:2]
    assert len(verdicts) == 2, "fixture no longer fires two rules"
    weld["conflicts"] = [{"left": verdicts[0]["rule_id"], "left_role": "fired_rule",
                          "right": verdicts[1]["rule_id"], "right_role": "fired_rule",
                          "declared_by": verdicts[0]["rule_id"]}]
    weld["abstain_on_conflict"] = True
    conflicted = replace(manifest, metadata={**manifest.metadata, WELD_KEY: weld})

    context = NodeContext(node_id="node_1", node_type="company",
                          facts={p: {"value": v, "confidence": 900, "authority_rank": 3}
                                 for p, v in DEAL_FACTS.items()},
                          obs=[{"kind": k, "occurred_at": NOW} for k in DEAL_OBSERVATIONS])
    decision = reason_native_capability(
        org_id="org_weld", context=context, capability=conflicted, evaluation_time=NOW,
        graph_version=1, config_snapshot_id=None, mode=ExecutionMode.SHADOW).decision

    assert decision.outcome.value == "defer"
    assert decision.selected_candidate_id is None
    named = [item for item in decision.uncertainty if item.startswith(RULE_CONFLICT_REASON)]
    assert named == [f"{RULE_CONFLICT_REASON}:{verdicts[0]['rule_id']}|"
                     f"{verdicts[1]['rule_id']}"]
    # The ranked field is KEPT — the human still sees what was considered.
    assert any(c.disposition.value == "eligible" for c in decision.candidates)


def test_without_a_conflict_the_same_fixture_decides(deal_with_absence):
    """The abstention test is only meaningful if the unconflicted run does not abstain."""
    _, decision = _decide(deal_with_absence)
    assert decision.outcome.value == "decision"
    assert not any(item.startswith(RULE_CONFLICT_REASON) for item in decision.uncertainty)


def test_the_receipt_counts_the_plays_the_cap_actually_cut(deal_with_absence):
    """`plays_over_cap` is the number a reader uses to decide whether the cap is costing anything.
    A constant zero would make a silently truncated manifest look complete."""
    manifest = _manifest(deal_with_absence)
    receipt = manifest.metadata[WELD_KEY]["weld_receipt"]
    play_receipt = manifest.metadata["play_receipt"]
    assert receipt["plays_over_cap"] == len(play_receipt["plays_truncated"]) > 0
    assert receipt["plays_selected"] == play_receipt["plays_emitted"] == len(manifest.plays)
