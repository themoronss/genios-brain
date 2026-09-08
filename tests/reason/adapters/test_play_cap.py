"""CLG-07 · the selection-aware play cap, and the receipts the four unlocked classes now carry.

The defect is measured on the shipped corpus rather than described: the `deal` route compiles 21
playbooks, the cap keeps 16, and under the old rule-id sort the five cut were four situation-fit
plays plus one other — while five `icp_definition` plays survived because "i" sorts before "n".
"""

from __future__ import annotations

import pytest

from genios_engine.reason.adapters.expertise import MAX_PLAYS, expertise_capability_manifest

pytestmark = pytest.mark.unit

#: A play whose playbook declares one of the situations that fired. Alphabetically it sorts near
#: the END of the routed set, so under the old cap it was cut.
FIT_BUT_LATE = "sales.pb.value_proposition.quantified_value_narrative"

#: A play whose playbook declares NO situation at all. Alphabetically it sorts early, so under the
#: old cap it survived — ahead of four plays that named the situation.
UNFIT_BUT_EARLY = "sales.pb.icp_definition.tri_cohort_analysis"


def _manifest(compiled):
    return expertise_capability_manifest(
        compiled.package, root_entity_type="company",
        situation=compiled.situation, context=compiled.context)


def test_the_route_actually_exceeds_the_cap(deal_with_absence):
    """Without this the rest of the file proves nothing: a cap that never bites cannot be shown to
    select badly."""
    playbooks = [record for record in deal_with_absence.package.expert_rules
                 if (record["definition"].get("identity") or {}).get("kind") == "playbook"
                 and record["definition"].get("steps")]
    assert len(playbooks) > MAX_PLAYS, f"only {len(playbooks)} step-bearing playbooks routed"


def test_situation_fit_beats_alphabetical(deal_with_absence):
    """The acceptance row: *"a situation-fit play beats an alphabetically-earlier generic play"*."""
    play_ids = {play.play_id for play in _manifest(deal_with_absence).plays}
    assert FIT_BUT_LATE in play_ids
    assert UNFIT_BUT_EARLY not in play_ids
    assert UNFIT_BUT_EARLY < FIT_BUT_LATE, "the fixture no longer demonstrates the inversion"


def test_every_cut_play_declared_no_matching_situation(deal_with_absence):
    manifest = _manifest(deal_with_absence)
    matched = set(deal_with_absence.package.metadata["matched_situation_ids"])
    by_id = {record["id"]: record for record in deal_with_absence.package.expert_rules}
    for play_id in manifest.metadata["play_receipt"]["plays_truncated"]:
        declared = (by_id[play_id]["definition"].get("when_to_use") or {}).get("situations") or ()
        assert not (set(declared) & matched), f"{play_id} was cut despite declaring the situation"


def test_the_cap_still_holds_and_the_truncation_is_still_receipted(deal_with_absence):
    """The cap is legitimate; only the selection was not. Nothing about the receipt weakens."""
    manifest = _manifest(deal_with_absence)
    receipt = manifest.metadata["play_receipt"]
    assert len(manifest.plays) == MAX_PLAYS
    assert receipt["plays_emitted"] == MAX_PLAYS
    assert receipt["plays_truncated"]
    assert receipt["truncation_reason"]
    for play_id in receipt["plays_truncated"]:
        assert receipt["skipped_rule_ids"][play_id] == f"over_play_cap_{MAX_PLAYS}"
    assert receipt["generic_fallback_used"] is False


def test_the_ranking_is_byte_stable(deal_with_absence):
    """Law 2 at the play cap: the sort must not depend on anything that varies between runs."""
    first = [play.play_id for play in _manifest(deal_with_absence).plays]
    second = [play.play_id for play in _manifest(deal_with_absence).plays]
    assert first == second


def test_the_rank_inputs_are_reported_not_implied(deal_with_absence):
    receipt = _manifest(deal_with_absence).metadata["play_receipt"]
    assert receipt["plays_situation_fit"] > 0
    # The corpus declares no per-play priority today. Reported as a number so the constant term is
    # a measurement rather than something to rediscover.
    assert receipt["plays_with_authored_priority"] == 0
    assert "situation_fit" in receipt["selection"]


# =================================================================================================
# THE RECEIPT THAT USED TO SAY NOBODY READ THESE
# =================================================================================================

def test_no_artifact_class_with_a_consumer_is_still_reported_unsupported(deal_with_absence):
    """J1's second row. `no_steps_artifact_unsupported` was the play converter's honest answer
    when it was the only consumer; it is now a false statement about rules, heuristics, models and
    frameworks, so it must not appear for any of them."""
    manifest = _manifest(deal_with_absence)
    skipped = manifest.metadata["play_receipt"]["skipped_rule_ids"]
    by_id = {record["id"]: record for record in deal_with_absence.package.expert_rules}
    unlocked = {"rule", "heuristic", "mental_model", "decision_framework"}
    offenders = [rule_id for rule_id, reason in skipped.items()
                 if reason == "no_steps_artifact_unsupported"
                 and (by_id.get(rule_id, {}).get("definition", {}).get("identity") or {}
                      ).get("kind") in unlocked]
    assert not offenders, offenders


def test_each_unlocked_class_names_its_own_consumer(deal_with_absence):
    manifest = _manifest(deal_with_absence)
    skipped = manifest.metadata["play_receipt"]["skipped_rule_ids"]
    by_id = {record["id"]: record for record in deal_with_absence.package.expert_rules}
    expected = {"rule": "consumed_as_compiled_constraint",
                "heuristic": "consumed_as_citation",
                "mental_model": "consumed_as_framing_block",
                "decision_framework": "consumed_as_framing_block"}
    seen = set()
    for rule_id, reason in skipped.items():
        klass = (by_id.get(rule_id, {}).get("definition", {}).get("identity") or {}).get("kind")
        if klass in expected:
            assert reason == expected[klass], f"{rule_id}: {reason}"
            seen.add(klass)
    assert seen == set(expected), sorted(set(expected) - seen)


# =================================================================================================
# THE FOUR RANK TERMS, ISOLATED — each one decides on its own, in doc 03's order
# =================================================================================================

class _Package:
    """Only what `_plays` reads. Hand-built here and nowhere else in this directory, because the
    point of these four tests is to hold three of the four rank terms CONSTANT while one varies —
    which the shipped corpus, having authored no per-play priority at all, cannot do."""

    def __init__(self, plays, capabilities, situations=("x.sit.one",)) -> None:
        self.expert_rules = tuple(plays)
        self.capabilities = tuple(capabilities)
        self.adaptive_preferences = ()
        self.metadata = {"matched_situation_ids": tuple(situations)}


def _capability(capability_id, updated):
    return {"id": capability_id, "kind": "capability", "version": "1.0.0",
            "definition": {"metadata": {"last_updated": updated}}}


def _playbook(artifact_id, *, owner, situations=(), priority_bp=None):
    metadata = {"last_updated": "2026-01-01"}
    if priority_bp is not None:
        metadata["priority_bp"] = priority_bp
    return {"id": artifact_id, "kind": "artifact", "version": "1.0.0", "definition": {
        "identity": {"id": artifact_id, "kind": "playbook", "owner_capability": owner,
                     "domain": "x", "scope": "capability"},
        "when_to_use": {"situations": list(situations)},
        "steps": [{"order": 1, "name": "do a thing"}],
        "metadata": metadata}}


def _order(package):
    from genios_engine.reason.adapters.expertise import _plays
    plays, _, _defs = _plays(package)
    return [play.play_id for play in plays]


def test_term_one_situation_fit_outranks_every_other_term():
    """A fit play wins even when it is alphabetically last AND owned by the stalest capability —
    otherwise "situation fit first" is a comment rather than a rank."""
    package = _Package(
        [_playbook("x.pb.a.alpha", owner="x.cap.fresh"),
         _playbook("x.pb.z.zulu", owner="x.cap.stale", situations=("x.sit.one",))],
        [_capability("x.cap.fresh", "2026-09-01"), _capability("x.cap.stale", "2020-01-01")])
    assert _order(package) == ["x.pb.z.zulu", "x.pb.a.alpha"]


def test_term_two_capability_recency_decides_between_two_equally_fit_plays():
    """A re-stamped capability is a maintained one. With fit equal, the newer stamp wins even
    though its play sorts later by id."""
    package = _Package(
        [_playbook("x.pb.a.alpha", owner="x.cap.stale"),
         _playbook("x.pb.z.zulu", owner="x.cap.fresh")],
        [_capability("x.cap.stale", "2020-01-01"), _capability("x.cap.fresh", "2026-09-01")],
        situations=())
    assert _order(package) == ["x.pb.z.zulu", "x.pb.a.alpha"]


def test_term_three_authored_priority_decides_inside_one_capability():
    """The term the shipped corpus does not use yet. It exists because an author who wants to
    order two plays within one capability has nowhere else to say so."""
    package = _Package(
        [_playbook("x.pb.a.alpha", owner="x.cap.one"),
         _playbook("x.pb.z.zulu", owner="x.cap.one", priority_bp=9_000)],
        [_capability("x.cap.one", "2026-01-01")], situations=())
    assert _order(package) == ["x.pb.z.zulu", "x.pb.a.alpha"]


def test_term_four_the_rule_id_breaks_a_genuine_tie_and_only_that():
    """Where a deterministic tie-break belongs: LAST. With every authored signal equal, the id
    orders the pair — which is exactly what it used to do with every authored signal ignored."""
    package = _Package(
        [_playbook("x.pb.z.zulu", owner="x.cap.one"),
         _playbook("x.pb.a.alpha", owner="x.cap.one")],
        [_capability("x.cap.one", "2026-01-01")], situations=())
    assert _order(package) == ["x.pb.a.alpha", "x.pb.z.zulu"]


def test_an_undated_capability_sorts_behind_a_dated_one():
    package = _Package(
        [_playbook("x.pb.a.alpha", owner="x.cap.undated"),
         _playbook("x.pb.z.zulu", owner="x.cap.dated")],
        [{"id": "x.cap.undated", "definition": {}}, _capability("x.cap.dated", "2020-01-01")],
        situations=())
    assert _order(package) == ["x.pb.z.zulu", "x.pb.a.alpha"]
