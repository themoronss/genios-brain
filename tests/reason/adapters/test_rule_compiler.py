"""CLG-06 · the rule compiler. Doc 03's five steps, each with the failure it prevents.

Every acceptance row from doc 03 L3.3-U1 is here, and the fixtures are the SHIPPED corpus rather
than an invented rule: `urgency-must-belong-to-the-buyer` is the artifact the plan names, so it is
the artifact the tests drive.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from genios_engine.context.analytic.cohort import PredicateError, parse_predicate
from genios_engine.contracts.domain_expertise import (
    PREDICATE_GRAMMAR,
    citation_statement_hash,
    require_compiled_constraint,
)
from genios_engine.packs.compiler.authoring import default_authoring_root
from genios_engine.reason.adapters import rule_compiler as rc

from .conftest import CLOSING_PLAY, URGENCY_RULE, code_identifiers

pytestmark = pytest.mark.unit


# =================================================================================================
# STEP 1 · PARSE — one grammar, no eval, closed vocabulary
# =================================================================================================

@pytest.mark.parametrize("authored,expected", [
    ({"path": "deal.status", "op": "=", "value": "open"},
     {"fact": "deal.status", "op": "eq", "value": "open"}),
    ({"path": "thread.ball_in_court", "op": "!=", "value": "us"},
     {"fact": "thread.ball_in_court", "op": "ne", "value": "us"}),
    ({"exists": "commitment.due_at"}, {"fact": "commitment.due_at", "op": "exists"}),
    ({"absent": "commitment.due_at"}, {"fact": "commitment.due_at", "op": "missing"}),
    ({"has_obs": "proposal_sent"}, {"fact": "obs.proposal_sent", "op": "exists"}),
    ({"no_obs": "positive_reply"}, {"fact": "obs.positive_reply", "op": "missing"}),
    ({"neighbor_has_obs": "introduction"},
     {"fact": "nbr_obs.introduction", "op": "exists"}),
    ({"neighbor_no_obs": "competitor"}, {"fact": "nbr_obs.competitor", "op": "missing"}),
    ({"fn": "edge_count", "op": "<=", "value": 2},
     {"fact": "edge_count", "op": "lte", "value": 2}),
    ({"fn": "days_since", "path": "thread.last_inbound", "op": "<=", "value": 7},
     {"fact": "thread.last_inbound", "op": "within_days", "value": 7}),
])
def test_every_authored_predicate_form_translates(authored, expected):
    """The corpus's closed `predicate_forms` list, each mapped onto exactly one grammar node."""
    assert rc.translate_condition(authored, rc.l3_fact_registry()) == expected


def test_a_predicate_is_never_a_string_and_never_an_expression():
    """Doc 03's hard rule 1. The way a free expression gets in is as text somebody evaluates
    later, so the compiler never produces text and never imports a way to evaluate it."""
    names = code_identifiers(rc)
    for forbidden in ("eval", "exec", "__import__", "literal_eval"):
        assert forbidden not in names, f"{forbidden} is called by the rule compiler"
    # And it uses the ONE parser rather than a second one.
    assert "genios_engine.context.analytic.cohort" in names
    assert "parse_predicate" in names


def test_the_compiled_tree_is_the_cohort_grammar_and_round_trips():
    tree = rc.compile_predicate([
        {"path": "deal.status", "op": "=", "value": "open"},
        {"has_obs": "proposal_sent"},
        {"absent": "commitment.due_at"},
    ])
    assert set(tree) == {"all"}
    # Parsing the emitted JSON back through the same grammar must succeed and be stable, which is
    # what makes a stored tree replayable years later.
    reparsed = parse_predicate(tree, registry=rc.l3_fact_registry())
    from genios_engine.context.analytic.cohort import predicate_json
    assert predicate_json(reparsed) == tree


def test_a_ratio_threshold_is_scaled_to_basis_points():
    """`derived.engagement < 1` is authored against a decimal ratio; the registered fact is a
    RATIO, normalised to basis points. Storing `1` unscaled would mean `< 0.0001`."""
    tree = rc.compile_predicate([{"path": "derived.engagement", "op": "<", "value": 1}])
    assert tree["all"][0] == {"fact": "derived.engagement", "op": "lt", "value": 10_000}


def test_a_ratio_threshold_that_is_not_whole_basis_points_is_refused():
    with pytest.raises(rc.RuleCompileError) as exc:
        rc.compile_predicate([{"path": "derived.engagement", "op": "<",
                               "value": "0.000001"}])
    assert exc.value.reason == "rule_ratio_value_not_basis_points"


@pytest.mark.parametrize("authored,reason", [
    ({"path": "not.a.registered.fact", "op": "=", "value": 1}, "rule_fact_unregistered"),
    ({"path": "deal.status", "op": "~=", "value": "open"}, "rule_operator_unsupported"),
    ({"fn": "edge_count", "path": "deal.status", "op": "<=", "value": 1},
     "rule_edge_count_takes_no_path"),
    ({"fn": "hours_since", "path": "thread.last_inbound", "op": "<=", "value": 4},
     "rule_elapsed_predicate_unsupported"),
    ({"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 4},
     "rule_elapsed_predicate_unsupported"),
    ({"neighbor_fact": "deal.status", "op": "=", "value": "open"},
     "rule_neighbor_fact_unsupported"),
    ({"path": "deal.value", "op": ">=", "value": {"baseline": "reply_cadence", "mult": 2}},
     "rule_baseline_threshold_unsupported"),
    ({"something": "else"}, "rule_predicate_form_unsupported"),
])
def test_every_refusal_is_named(authored, reason):
    """Invariant #6. A refusal spelled as prose cannot be counted, and the weld receipt requires
    an identifier."""
    with pytest.raises(rc.RuleCompileError) as exc:
        rc.translate_condition(authored, rc.l3_fact_registry())
    assert exc.value.reason == reason


def test_an_unparseable_rule_is_refused_by_the_grammar_not_by_this_module():
    """A value the fact's own KIND cannot answer is the parser's job to refuse, and the compiler
    reports it as `rule_parse_failed` rather than swallowing it."""
    with pytest.raises(rc.RuleCompileError) as exc:
        rc.compile_predicate([{"path": "deal.value", "op": "=", "value": "not a number"}])
    assert exc.value.reason == "rule_parse_failed"
    with pytest.raises(PredicateError):
        parse_predicate({"fact": "deal.value", "op": "eq", "value": "not a number"},
                        registry=rc.l3_fact_registry())


def test_an_empty_when_is_refused():
    with pytest.raises(rc.RuleCompileError) as exc:
        rc.compile_predicate([])
    assert exc.value.reason == "rule_when_empty"


# =================================================================================================
# THE CORPUS ITSELF — the drift guard doc 03 asks validate.py to carry at authoring time
# =================================================================================================

def _shipped_rules():
    root = Path(default_authoring_root())
    for path in sorted(root.rglob("*.yaml")):
        if "/rules/" not in str(path):
            continue
        document = yaml.safe_load(path.read_text()) or {}
        if (document.get("identity") or {}).get("kind") == "rule":
            yield path, document


def test_every_shipped_l4_rule_compiles():
    """The whole enforceable corpus, parsed. A rule that stops compiling because someone authored
    a fact this registry does not carry fails HERE, at build time, instead of becoming a silent
    `rule_fact_unregistered` on a tenant."""
    registry = rc.l3_fact_registry()
    failures = []
    compiled = 0
    for path, document in _shipped_rules():
        rule = document.get("rule") or {}
        if rule.get("enforced_by") != rc.ENFORCED_BY_L4:
            continue
        try:
            rc.compile_predicate(rule.get("when") or (), registry)
            compiled += 1
        except rc.RuleCompileError as exc:
            failures.append(f"{path.name}: {exc.reason}")
    assert not failures, "\n".join(failures)
    assert compiled >= 31, f"only {compiled} L4_constraint rules compiled"


def test_the_observation_vocabulary_still_covers_the_corpus():
    """`OBSERVATION_KINDS` is a restatement of the corpus's own closed list. If an author adds an
    observation kind, this fails instead of the rule quietly losing its consumer."""
    named = set()
    for _, document in _shipped_rules():
        for condition in (document.get("rule") or {}).get("when") or ():
            if isinstance(condition, dict):
                for key in ("has_obs", "no_obs", "neighbor_has_obs", "neighbor_no_obs"):
                    if condition.get(key):
                        named.add(str(condition[key]))
    assert named, "no observation predicates found — the corpus reader is broken, not the corpus"
    assert named <= set(rc.OBSERVATION_KINDS), sorted(named - set(rc.OBSERVATION_KINDS))


# =================================================================================================
# STEPS 2-5 · BIND, EMIT, UNKNOWN, RECEIPT — over a real compiled package
# =================================================================================================

def test_a_blocking_rule_that_fires_eliminates_the_plays_in_its_own_capability(
        deal_with_absence):
    compiled = rc.compile_package_rules(deal_with_absence.package,
                                        deal_with_absence.adapter)
    verdict = next(v for v in compiled.verdicts if v.rule_id == URGENCY_RULE)
    assert verdict.severity == rc.BLOCKING
    assert verdict.outcome == "fired"
    assert verdict.blocks
    assert verdict.blocked_play_ids == (CLOSING_PLAY,)
    assert compiled.blocked_play_ids == (CLOSING_PLAY,)


def test_a_blocking_rule_may_only_block_a_play_the_manifest_declares(deal_with_absence):
    """Doc 03's fourth failure mode, generalised. A rule naming a play the cap cut would put a
    `core.constraint` row on the decision that no candidate can carry, and `reason/store.py`
    rejects exactly that as "candidate checks differ from immutable reasoner result effects"."""
    compiled = rc.compile_package_rules(deal_with_absence.package, deal_with_absence.adapter,
                                        declared_play_ids=frozenset())
    verdict = next(v for v in compiled.verdicts if v.rule_id == URGENCY_RULE)
    assert verdict.outcome == "fired"          # it still fired
    assert verdict.blocked_play_ids == ()      # it just has nothing here to eliminate
    assert compiled.blocked_play_ids == ()


def test_an_unknown_predicate_neither_fires_nor_blocks_and_names_what_was_missing(
        deal_without_absence):
    """Step 4, and the bug this codebase has spent months avoiding. Without the typed absence,
    `{absent: commitment.due_at}` is UNKNOWN — the fact is expected and not held, and nothing
    licenses the inference that it does not exist."""
    compiled = rc.compile_package_rules(deal_without_absence.package,
                                        deal_without_absence.adapter)
    verdict = next(v for v in compiled.verdicts if v.rule_id == URGENCY_RULE)
    assert verdict.outcome == "unevaluable"
    assert verdict.missing == ("commitment.due_at",)
    assert verdict.blocked_play_ids == ()
    assert not verdict.blocks
    assert CLOSING_PLAY not in compiled.blocked_play_ids


def test_a_warning_rule_that_fires_annotates_and_eliminates_nothing(deal_with_absence):
    compiled = rc.compile_package_rules(deal_with_absence.package, deal_with_absence.adapter)
    warnings = [v for v in compiled.fired if v.severity == rc.WARNING]
    assert warnings, "no warning-severity rule fired on this fixture"
    for verdict in warnings:
        assert verdict.blocked_play_ids == ()
        assert not verdict.blocks


def test_without_a_situation_every_rule_is_unevaluable_and_says_so(deal_with_absence):
    """A package compiled outside the live path must not claim that no rule applied."""
    compiled = rc.compile_package_rules(deal_with_absence.package, adapter=None)
    assert compiled.constraints
    assert len(compiled.unevaluable) == len(compiled.verdicts)
    assert all(v.missing == ("situation_slice_not_supplied",) for v in compiled.verdicts)
    assert compiled.blocked_play_ids == ()


def test_rules_enforced_by_another_layer_are_refused_by_name(deal_with_absence):
    compiled = rc.compile_package_rules(deal_with_absence.package, deal_with_absence.adapter)
    assert compiled.skipped, "this route carries L5_validation rules; none were refused"
    assert set(compiled.skipped.values()) == {"rule_enforced_by_l5_validation"}
    assert compiled.refusals["rule_enforced_by_l5_validation"] == len(compiled.skipped)
    # And no rule is both compiled and refused.
    assert not ({v.rule_id for v in compiled.verdicts} & set(compiled.skipped))


def test_an_advisory_rule_is_not_promoted_to_a_warning():
    """The corpus authors three severities; `core.constraint` expresses two. Mapping `advisory`
    onto `warning` would put a claim on the decision its author did not make."""
    package = _package_with_rule(severity="advisory")
    compiled = rc.compile_package_rules(package, adapter=None)
    assert compiled.constraints == ()
    assert compiled.skipped == {"x.rule.a.b": "rule_severity_advisory_not_a_constraint"}


def test_a_core_scoped_rule_is_refused_rather_than_given_an_invented_blast_radius():
    package = _package_with_rule(scope="core", owner=None)
    compiled = rc.compile_package_rules(package, adapter=None)
    assert compiled.skipped == {"x.rule.a.b": "rule_scope_not_capability"}


def test_the_compiled_constraint_satisfies_the_contract(deal_with_absence):
    compiled = rc.compile_package_rules(deal_with_absence.package, deal_with_absence.adapter)
    constraint = next(c for c in compiled.constraints if c["rule_id"] == URGENCY_RULE)
    assert constraint["predicate_grammar"] == PREDICATE_GRAMMAR
    assert constraint["severity"] == "blocking"
    assert constraint["source_ref"] == f"expert:artifact:{URGENCY_RULE}"
    assert constraint["statement_hash"] == citation_statement_hash(constraint["statement"])
    # Re-validating a frozen record is a no-op; a paraphrased one is refused.
    require_compiled_constraint(dict(constraint))
    with pytest.raises(ValueError):
        require_compiled_constraint({**dict(constraint),
                                     "statement": constraint["statement"] + " (roughly)"})


def test_the_compile_is_reproducible(deal_with_absence):
    """Law 2. Same situation, same snapshot, byte-identical output."""
    first = rc.compile_package_rules(deal_with_absence.package, deal_with_absence.adapter)
    second = rc.compile_package_rules(deal_with_absence.package, deal_with_absence.adapter)
    assert [dict(c) for c in first.constraints] == [dict(c) for c in second.constraints]
    assert [v.as_record() for v in first.verdicts] == [v.as_record() for v in second.verdicts]


# =================================================================================================
# THE DECISION-TIME HALF
# =================================================================================================

class _Candidate:
    def __init__(self, play_id: str, candidate_id: str, disposition: str) -> None:
        self.play_id = play_id
        self.candidate_id = candidate_id
        self.disposition = disposition


def test_a_fired_blocking_rule_names_the_candidate_it_eliminated():
    verdicts = [{"rule_id": "x.rule.a.b", "severity": "blocking", "outcome": "fired",
                 "statement": "A statement.", "statement_hash": citation_statement_hash(
                     "A statement."), "blocked_play_ids": ["p1"]}]
    applied = rc.constraint_applications(
        verdicts, [_Candidate("p1", "cand_1", "eliminated"),
                   _Candidate("p2", "cand_2", "eligible")])
    assert applied[0]["eliminated_candidate_ids"] == ("cand_1",)


def test_a_rule_never_claims_a_candidate_that_survived():
    """The contract refuses a receipt that reads correctly and is false; this is the producer
    side making sure it never builds one."""
    verdicts = [{"rule_id": "x.rule.a.b", "severity": "blocking", "outcome": "fired",
                 "statement": "A statement.", "statement_hash": citation_statement_hash(
                     "A statement."), "blocked_play_ids": ["p1"]}]
    applied = rc.constraint_applications(verdicts, [_Candidate("p1", "cand_1", "eligible")])
    assert "eliminated_candidate_ids" not in applied[0]


def test_an_unevaluable_application_must_name_the_missing_predicate():
    verdicts = [{"rule_id": "x.rule.a.b", "severity": "blocking", "outcome": "unevaluable",
                 "statement": "A statement.", "statement_hash": citation_statement_hash(
                     "A statement."), "missing": ["commitment.due_at"],
                 "blocked_play_ids": []}]
    applied = rc.constraint_applications(verdicts, [])
    assert applied[0]["missing"] == ("commitment.due_at",)


def test_a_warning_application_may_not_eliminate():
    verdicts = [{"rule_id": "x.rule.a.b", "severity": "warning", "outcome": "fired",
                 "statement": "A statement.", "statement_hash": citation_statement_hash(
                     "A statement."), "blocked_play_ids": ["p1"]}]
    applied = rc.constraint_applications(verdicts, [_Candidate("p1", "c1", "eliminated")])
    assert "eliminated_candidate_ids" not in applied[0]


# =================================================================================================
# helpers
# =================================================================================================

class _Package:
    """The smallest thing `compile_package_rules` reads: a list of authored records."""

    def __init__(self, expert_rules) -> None:
        self.expert_rules = tuple(expert_rules)
        self.metadata: dict = {}
        self.capabilities = ()
        self.objects = ()


def _package_with_rule(*, severity: str = "blocking", scope: str = "capability",
                       owner: str | None = "x.cap.one", enforced_by: str = "L4_constraint",
                       when=None) -> _Package:
    identity = {"id": "x.rule.a.b", "kind": "rule", "scope": scope, "domain": "x"}
    if owner:
        identity["owner_capability"] = owner
    return _Package([{
        "id": "x.rule.a.b", "kind": "artifact", "version": "1.0.0",
        "definition": {"identity": identity, "rule": {
            "statement": "A statement.", "severity": severity, "enforced_by": enforced_by,
            "when": when or [{"path": "deal.status", "op": "=", "value": "open"}]}},
    }])


def test_a_rule_statement_is_hashed_exactly_as_authored_whitespace_included():
    """The producer half of V-1. `require_compiled_constraint` compares the statement against its
    own hash, so a compiler that stripped before hashing would fail the contract on any artifact
    whose statement carries surrounding whitespace — and a YAML block scalar always does."""
    package = _package_with_rule()
    authored = "Urgency must belong to the buyer.\n"
    package.expert_rules[0]["definition"]["rule"]["statement"] = authored
    constraint = rc.compile_package_rules(package, adapter=None).constraints[0]
    assert constraint["statement"] == authored
    assert constraint["statement_hash"] == citation_statement_hash(authored)
    assert constraint["statement_hash"] != citation_statement_hash(authored.strip())


def test_a_playbook_with_no_owning_capability_belongs_to_no_blast_radius():
    """Belt and braces, tested at its own level.

    `compile_package_rules` already refuses a rule that does not name an `owner_capability`
    (`rule_scope_not_capability`), so nothing today reaches the scope map with an empty key. This
    is the second half of that pair: if it ever did, an ownerless playbook and an ownerless rule
    would meet under the empty string and the rule would eliminate a play it has no relationship
    with. The map refuses to hold it, so the two cannot meet even if the first check moved.
    """
    orphan = {"id": "x.pb.a.orphan", "kind": "artifact", "version": "1.0.0", "definition": {
        "identity": {"id": "x.pb.a.orphan", "kind": "playbook", "domain": "x", "scope": "core"},
        "steps": [{"order": 1, "name": "do a thing"}]}}
    owned = {"id": "x.pb.a.owned", "kind": "artifact", "version": "1.0.0", "definition": {
        "identity": {"id": "x.pb.a.owned", "kind": "playbook", "domain": "x",
                     "scope": "capability", "owner_capability": "x.cap.one"},
        "steps": [{"order": 1, "name": "do a thing"}]}}
    scopes = rc._plays_by_capability(_Package([orphan, owned]))
    assert scopes == {"x.cap.one": ("x.pb.a.owned",)}
    assert "" not in scopes
