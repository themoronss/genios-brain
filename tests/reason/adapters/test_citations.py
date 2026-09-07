"""CLG-08 · the citation binder. The expert's own words, or a named reason they did not travel."""

from __future__ import annotations

import pytest

from genios_engine.contracts.domain_expertise import (
    MAX_CITATIONS,
    citation_statement_hash,
    require_citation,
    require_framing_block,
)
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
from genios_engine.reason.adapters import citations as cb
from genios_engine.reason.adapters.rule_compiler import RuleVerdict, compile_package_rules

from .conftest import URGENCY_RULE, code_identifiers

pytestmark = pytest.mark.unit


def _bind(compiled):
    rules = compile_package_rules(compiled.package, compiled.adapter)
    return cb.bind_citations(compiled.package, rules.verdicts), rules


# =================================================================================================
# SELECTION — deterministic tag intersection, no embeddings anywhere in this layer (MAP B)
# =================================================================================================

def test_no_similarity_machinery_exists_in_this_layer():
    """MAP B: *"embeddings: none"*. Retrieval here is registry lookup and set arithmetic; the
    check is structural because a similarity call would pass every behavioural test that does not
    happen to exercise it."""
    names = code_identifiers(cb)
    for forbidden in ("embed", "cosine", "similar", "vector", "faiss", "numpy", "sklearn"):
        offenders = sorted(name for name in names if forbidden in name)
        assert not offenders, f"{forbidden}: {offenders} in the citation binder"


def test_a_heuristic_reaches_the_decision_quoted(deal_with_absence):
    binding, _ = _bind(deal_with_absence)
    assert binding.citations, "no heuristic was cited on a route carrying 26 of them"
    for citation in binding.citations:
        assert citation["artifact_class"] == "heuristic"
        assert citation["statement_hash"] == citation_statement_hash(citation["statement"])
        assert citation["source_ref"].startswith("expert:")


def test_a_cited_statement_is_byte_identical_to_the_authored_artifact(deal_with_absence):
    """V-1 proves a citation matches its OWN hash. This proves the hash was taken over what the
    corpus actually says — the half a contract cannot check, because it has no corpus."""
    catalog = ExpertBrainCatalog(default_authoring_root())
    binding, _ = _bind(deal_with_absence)
    domain = catalog.domain("sales")
    for citation in binding.citations:
        authored = domain.artifacts[citation["artifact_id"]].content["heuristic"]["statement"]
        assert citation["statement"] == authored


def test_a_paraphrase_cannot_be_constructed(deal_with_absence):
    binding, _ = _bind(deal_with_absence)
    citation = dict(binding.citations[0])
    citation["statement"] = citation["statement"].replace("the", "a", 1)
    with pytest.raises(ValueError):
        require_citation(citation)
    # Even a whitespace-only edit is refused: the hash is over the authored BYTES.
    stripped = dict(binding.citations[0])
    stripped["statement"] = " " + stripped["statement"]
    with pytest.raises(ValueError):
        require_citation(stripped)


def test_a_heuristic_from_a_capability_this_situation_never_routed_is_refused():
    binding = cb.bind_citations(_package([_heuristic("h1", owner="other.cap")]), ())
    assert binding.citations == ()
    assert binding.refusals == {"capability_not_routed": 1}


def test_a_heuristic_that_shares_no_tag_with_the_situation_is_refused():
    package = _package([_heuristic("h1", objects=("obj.z",))], objects=("obj.a",))
    binding = cb.bind_citations(package, ())
    assert binding.citations == ()
    assert binding.refusals == {"no_tag_overlap": 1}


def test_capability_match_alone_is_not_enough_for_a_claim_but_is_for_a_lens():
    """The two bars, and why they differ: a citation is quoted as a reason and must prove it is
    about this situation; a framing block is input material for a renderer and never a claim."""
    package = _package([_heuristic("h1", objects=()), _model("m1", objects=())],
                       objects=("obj.a",))
    binding = cb.bind_citations(package, ())
    assert binding.citations == ()
    assert [item["artifact_id"] for item in binding.framing_blocks] == ["m1"]


# =================================================================================================
# THE CAP — five, ranked, truncation receipted
# =================================================================================================

def test_the_cap_holds_and_the_truncation_is_counted():
    package = _package([_heuristic(f"h{i}", objects=("obj.a",)) for i in range(9)],
                       objects=("obj.a",))
    binding = cb.bind_citations(package, ())
    assert len(binding.citations) == MAX_CITATIONS
    assert binding.citations_truncated == 9 - MAX_CITATIONS
    assert binding.refusals["over_citation_cap"] == 9 - MAX_CITATIONS
    assert binding.by_class["heuristic"]["cited"] == MAX_CITATIONS


def test_rank_is_overlap_then_recency_then_id_and_never_id_first():
    package = _package([
        _heuristic("h_zzz", objects=("obj.a", "obj.b"), updated="2026-01-01"),
        _heuristic("h_aaa", objects=("obj.a",), updated="2026-09-01"),
        _heuristic("h_mmm", objects=("obj.a",), updated="2026-01-01"),
    ], objects=("obj.a", "obj.b"))
    binding = cb.bind_citations(package, ())
    assert [item["artifact_id"] for item in binding.citations] == ["h_zzz", "h_aaa", "h_mmm"]


def test_the_binding_is_reproducible(deal_with_absence):
    first, _ = _bind(deal_with_absence)
    second, _ = _bind(deal_with_absence)
    assert [dict(c) for c in first.citations] == [dict(c) for c in second.citations]
    assert [dict(f) for f in first.framing_blocks] == [dict(f) for f in second.framing_blocks]


# =================================================================================================
# FRAMING — input material, never a new claim
# =================================================================================================

def test_models_and_frameworks_become_framing_blocks(deal_with_absence):
    binding, _ = _bind(deal_with_absence)
    assert binding.framing_blocks
    for block in binding.framing_blocks:
        assert block["artifact_class"] in ("mental_model", "decision_framework")
        assert block["statement_hash"] == citation_statement_hash(block["statement"])


def test_a_heuristic_may_not_be_smuggled_in_as_framing(deal_with_absence):
    """The contract's rule, asserted from the producer side: a heuristic is a claim, and a claim
    belongs in citations where it is quoted and capped."""
    binding, _ = _bind(deal_with_absence)
    smuggled = dict(binding.citations[0])
    with pytest.raises(ValueError):
        require_framing_block(smuggled)


def test_the_framing_cap_holds_and_is_counted():
    package = _package([_model(f"m{i}") for i in range(7)])
    binding = cb.bind_citations(package, ())
    assert len(binding.framing_blocks) == cb.MAX_FRAMING_BLOCKS
    assert binding.framing_truncated == 7 - cb.MAX_FRAMING_BLOCKS
    assert binding.refusals["over_framing_cap"] == 7 - cb.MAX_FRAMING_BLOCKS


# =================================================================================================
# CLASS ROUTING — every class accounted for, none of them twice
# =================================================================================================

def test_a_rule_is_not_cited_because_it_already_travels_as_a_constraint(deal_with_absence):
    binding, rules = _bind(deal_with_absence)
    assert rules.fired, "no rule fired on this fixture"
    assert not any(item["artifact_class"] == "rule" for item in binding.citations)
    assert binding.by_class["rule"]["consumed_as_compiled_constraint"] >= len(rules.verdicts)
    assert binding.by_class["rule"]["fired"] == len(rules.fired)


def test_a_playbook_is_not_cited_because_it_already_travels_as_a_play(deal_with_absence):
    binding, _ = _bind(deal_with_absence)
    assert binding.by_class["playbook"] == {"consumed_as_play": binding.by_class["playbook"][
        "consumed_as_play"]}
    assert not any(item["artifact_class"] == "playbook" for item in binding.citations)


# =================================================================================================
# CONTRADICTIONS — surfaced, never resolved silently
# =================================================================================================

def test_a_claim_that_denies_doctrine_which_fired_does_not_travel_beside_it():
    fired = RuleVerdict(rule_id="x.rule.a.b", severity="blocking", outcome="fired",
                        statement="Doctrine.", statement_hash=citation_statement_hash("Doctrine."),
                        source_ref="expert:artifact:x.rule.a.b", owner_capability="x.cap.one")
    package = _package([
        _heuristic("h1", objects=("obj.a",), contradicts=("x.rule.a.b",)),
        _rule_record("x.rule.a.b"),
    ], objects=("obj.a",))
    binding = cb.bind_citations(package, (fired,))
    assert binding.citations == ()
    assert binding.refusals["contradicts_fired_rule"] == 1
    # Dropped, but NOT hidden: the tension is named.
    assert binding.conflicts == ()          # the heuristic is no longer active, so no pair stands
    assert not binding.abstain


def test_two_rules_that_both_fired_and_contradict_each_other_make_layer_4_abstain():
    """Doc 03: *"both fire; the contradiction surfaces as a named conflict — L4 abstains rather
    than picking silently"*. The `contradicts` field is authored on the artifact, so the conflict
    is the corpus's own statement rather than this module's inference."""
    verdicts = tuple(
        RuleVerdict(rule_id=rid, severity="blocking", outcome="fired", statement="Doctrine.",
                    statement_hash=citation_statement_hash("Doctrine."),
                    source_ref=f"expert:artifact:{rid}", owner_capability="x.cap.one")
        for rid in ("x.rule.a.one", "x.rule.a.two"))
    package = _package([
        _rule_record("x.rule.a.one", contradicts=("x.rule.a.two",)),
        _rule_record("x.rule.a.two"),
    ])
    binding = cb.bind_citations(package, verdicts)
    assert binding.abstain
    assert binding.conflicts == ({"left": "x.rule.a.one", "left_role": "fired_rule",
                                  "right": "x.rule.a.two", "right_role": "fired_rule",
                                  "declared_by": "x.rule.a.one"},)


def test_a_conflict_is_named_once_however_many_sides_declare_it():
    verdicts = tuple(
        RuleVerdict(rule_id=rid, severity="warning", outcome="fired", statement="Doctrine.",
                    statement_hash=citation_statement_hash("Doctrine."),
                    source_ref=f"expert:artifact:{rid}", owner_capability="x.cap.one")
        for rid in ("x.rule.a.one", "x.rule.a.two"))
    package = _package([
        _rule_record("x.rule.a.one", contradicts=("x.rule.a.two",)),
        _rule_record("x.rule.a.two", contradicts=("x.rule.a.one",)),
    ])
    assert len(cb.bind_citations(package, verdicts).conflicts) == 1


def test_the_corpus_actually_authors_a_heuristic_that_contradicts_a_shipped_rule():
    """The conflict detector reads an authored field, and this proves the field is authored — so
    the branch is data-reachable rather than fixture-only."""
    catalog = ExpertBrainCatalog(default_authoring_root())
    domain = catalog.domain("admin")
    heuristic = domain.artifacts["admin.heu.approval_coordination.slow_approvals_teach_workarounds"]
    assert "admin.rule.commitment_tracking.no_chase_while_we_hold_the_ball" in cb.contradicts_of(
        {"definition": heuristic.content})


def test_the_urgency_rule_is_a_real_blocking_rule_in_the_shipped_corpus():
    catalog = ExpertBrainCatalog(default_authoring_root())
    rule = catalog.domain("sales").artifacts[URGENCY_RULE].content["rule"]
    assert rule["severity"] == "blocking"
    assert rule["enforced_by"] == "L4_constraint"


# =================================================================================================
# helpers — the only hand-built packages in this file, and only where the corpus cannot say it yet
# =================================================================================================

class _Package:
    def __init__(self, records, objects=()) -> None:
        self.expert_rules = tuple(records)
        self.capabilities = ({"id": "x.cap.one", "definition": {}},)
        self.objects = tuple({"id": object_id} for object_id in objects)
        self.metadata = {"matched_situation_ids": ("x.sit.one",), "domain_ids": ("x",),
                         "required_object_ids": tuple(objects), "optional_object_ids": ()}
        self.pattern_id = None
        self.matched_conditions = ()


def _package(records, objects=("obj.a",)) -> _Package:
    return _Package(records, objects)


def _heuristic(artifact_id, *, owner="x.cap.one", objects=("obj.a",), updated="2026-01-01",
               contradicts=()):
    heuristic = {"statement": f"Claim of {artifact_id}.", "why": "because"}
    if contradicts:
        heuristic["contradicts"] = list(contradicts)
    return {"id": artifact_id, "kind": "artifact", "version": "1.0.0", "definition": {
        "identity": {"id": artifact_id, "kind": "heuristic", "owner_capability": owner,
                     "domain": "x", "scope": "capability"},
        "heuristic": heuristic, "objects_used": list(objects),
        "metadata": {"last_updated": updated}}}


def _model(artifact_id, *, owner="x.cap.one", objects=()):
    return {"id": artifact_id, "kind": "artifact", "version": "1.0.0", "definition": {
        "identity": {"id": artifact_id, "kind": "mental_model", "owner_capability": owner,
                     "domain": "x", "scope": "capability"},
        "purpose": {"statement": f"Lens of {artifact_id}."}, "objects_used": list(objects),
        "metadata": {"last_updated": "2026-01-01"}}}


def _rule_record(artifact_id, *, contradicts=()):
    rule = {"statement": "Doctrine.", "severity": "blocking", "enforced_by": "L4_constraint",
            "when": [{"path": "deal.status", "op": "=", "value": "open"}]}
    if contradicts:
        rule["contradicts"] = list(contradicts)
    return {"id": artifact_id, "kind": "artifact", "version": "1.0.0", "definition": {
        "identity": {"id": artifact_id, "kind": "rule", "owner_capability": "x.cap.one",
                     "domain": "x", "scope": "capability"},
        "rule": rule, "metadata": {"last_updated": "2026-01-01"}}}


def test_a_tension_between_two_cited_claims_is_named_but_does_not_abstain():
    """The common case, and the one the corpus authors 143 times: two heuristics that disagree.

    Both travel — *"real expertise contains genuine tensions and hiding them makes the brain read
    more confident than the profession is"* — and the tension is named. Abstention is reserved for
    two RULES, because a rule is doctrine that binds and a heuristic is a claim that informs;
    deferring every decision whose sources disagree would defer most of them.
    """
    package = _package([
        _heuristic("h_one", objects=("obj.a",), contradicts=("h_two",)),
        _heuristic("h_two", objects=("obj.a",)),
    ], objects=("obj.a",))
    binding = cb.bind_citations(package, ())
    assert {item["artifact_id"] for item in binding.citations} == {"h_one", "h_two"}
    assert binding.conflicts == ({"left": "h_one", "left_role": "citation",
                                 "right": "h_two", "right_role": "citation",
                                 "declared_by": "h_one"},)
    assert not binding.abstain


def test_a_tension_between_doctrine_and_framing_does_not_abstain_either():
    fired = RuleVerdict(rule_id="x.rule.a.b", severity="blocking", outcome="fired",
                        statement="Doctrine.", statement_hash=citation_statement_hash("Doctrine."),
                        source_ref="expert:artifact:x.rule.a.b", owner_capability="x.cap.one")
    model = _model("m1")
    model["definition"]["mental_model"] = {"contradicts": ["x.rule.a.b"]}
    binding = cb.bind_citations(_package([model, _rule_record("x.rule.a.b")]), (fired,))
    assert [item["artifact_id"] for item in binding.framing_blocks] == ["m1"]
    roles = {binding.conflicts[0]["left_role"], binding.conflicts[0]["right_role"]}
    assert roles == {"framing_block", "fired_rule"}
    assert not binding.abstain


def test_the_corpus_authors_mutual_tensions_between_heuristics():
    """The named-conflict branch is reachable from shipped data, not only from a fixture."""
    catalog = ExpertBrainCatalog(default_authoring_root())
    artifacts = catalog.domain("sales").artifacts
    left = "sales.heu.follow_up.the_thread_you_answered_is_not_the_loop_you_closed"
    right = "sales.heu.follow_up.silence_is_an_answer_about_timing__not_value"
    assert right in cb.contradicts_of({"definition": artifacts[left].content})
    assert left in cb.contradicts_of({"definition": artifacts[right].content})


def test_a_statement_is_hashed_exactly_as_authored_whitespace_included():
    """V-1's `_verbatim` refuses to strip, and a producer that strips would compute a hash over
    text the artifact does not contain. YAML block scalars end in a newline, so this is the shape
    a folded `purpose.statement` actually has — not a hypothetical."""
    package = _package([_heuristic("h1", objects=("obj.a",))], objects=("obj.a",))
    authored = "Silence is an answer about timing.\n"
    package.expert_rules[0]["definition"]["heuristic"]["statement"] = authored
    citation = cb.bind_citations(package, ()).citations[0]
    assert citation["statement"] == authored
    assert citation["statement_hash"] == citation_statement_hash(authored)
    assert citation["statement_hash"] != citation_statement_hash(authored.strip())
