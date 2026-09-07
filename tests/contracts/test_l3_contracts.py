"""J0 · Wave Y0 — the Layer 3 contracts every later wave writes through.

WHAT THIS FILE IS DEFENDING. Layer 3's compiler is built, its corpus is 1,394 authored files, and
446 of the 712 knowledge artifacts in it have no runtime reader at all: `reason/adapters/expertise.py`
consumes `organization_rules` and nothing else, so every rule, heuristic, mental model and decision
framework is retrieved, hashed and dropped. Wave Y0 does not fix that — Y1 does — but Y0 decides the
SHAPES Y1 has to fill, and a shape that cannot be validated is a shape that ships empty. So each test
below is one of doc 05's five validators, or one of the two properties the activation table exists to
have.

THE FIVE VALIDATORS, and where each lives:

  V-1  a citation's statement is BYTE-IDENTICAL to the artifact's authored text
       -> `citation_statement_hash` on both sides; a paraphrase is a ValueError, not a warning
  V-2  a compiled constraint carries a severity in {blocking, warning} and a PARSEABLE tree
       -> `require_compiled_constraint` + `require_predicate_tree`
  V-3  a weld receipt exists whenever expert rules do — consumption is always accounted for
  V-4  the additions are optional-with-defaults; an OLD-SHAPED PACKAGE STILL CONSTRUCTS
  V-5  no float anywhere

THE ONE GRAMMAR. `compiled_constraints` predicates are the SAME whitelisted operator tree as L2
cohorts. `test_the_predicate_tree_is_literally_l2s_grammar_not_a_second_one` proves it by feeding a
tree through `cohort.parse_predicate` -> `cohort.predicate_json` and handing the output straight to
the contract, which is the round trip Y1's rule compiler must perform. The contract cannot import
cohort (`test_layer_topology` holds `contracts/` to platform and stdlib), so this test is where the
two halves are pinned to each other.

The Postgres cases need GENIOS_TEST_DATABASE_URL, like every other real-DB file in this suite.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.domain_expertise import (
    CITATION_CLASSES,
    CONSTRAINT_OUTCOMES,
    CONSTRAINT_SEVERITIES,
    EXPERTISE_PACKAGE_VERSION,
    EXPERTISE_PACKAGE_VERSION_V1,
    FRAMING_CLASSES,
    MAX_CITATIONS,
    MAX_PREDICATE_DEPTH,
    PREDICATE_GRAMMAR,
    WELD_RECEIPT_COUNTERS,
    BrainKind,
    ExpertiseEvidence,
    ExpertisePackage,
    citation_statement_hash,
    require_citation,
    require_compiled_constraint,
    require_constraint_application,
    require_framing_block,
    require_predicate_tree,
    require_weld_receipt,
)
from genios_engine.contracts.reasoning import (
    CandidateDisposition,
    DecisionCandidate,
    DecisionOutcome,
    ReasoningDecision,
)
from genios_engine.platform import l3_activation as ACT
from genios_engine.platform.canonical import canonicalize

ORG = "org_scratch_tests"                        # seeded by tests/conftest.py; satisfies the FK
NOW = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)

#: A real sentence out of the Sales corpus's heuristics, kept as the authored bytes so the V-1 tests
#: are about a quote somebody wrote rather than about the string "x".
AUTHORED = "Warmth is close to uncorrelated with intent.\n"


# ── fixtures: the smallest package and decision the contracts accept ─────────────────────────

def _evidence(**kw) -> ExpertiseEvidence:
    return ExpertiseEvidence(brain=kw.get("brain", BrainKind.EXPERT),
                             source_ref=kw.get("source_ref", "expert:heuristic:h1"),
                             source_version="1.0.0", content_hash="a" * 64,
                             confidence_bp=8000, visibility={"scope": "org"})


def _package(**overrides) -> ExpertisePackage:
    body = dict(org_id="org_y0", trace_id="trace_y0", visibility={"scope": "org"}, id="exp_y0",
                situation_id="sit_y0", brain_snapshot_id="snap_y0",
                capabilities=({"id": "cap.admin.approval"},), objects=({"id": "obj.approval"},),
                expert_rules=({"id": "rule.urgency"},), organization_rules=(),
                behavior_patterns=(), adaptive_preferences=(), confidence_bp=7000,
                evidence=(_evidence(),))
    body.update(overrides)
    return ExpertisePackage(**body)


def _citation(**overrides) -> dict:
    record = {"artifact_id": "heuristic.warmth_vs_intent", "artifact_class": "heuristic",
              "statement": AUTHORED, "statement_hash": citation_statement_hash(AUTHORED),
              "source_ref": "expert:heuristic:warmth_vs_intent"}
    record.update(overrides)
    return record


def _tree() -> dict:
    """A REAL L2 cohort predicate — the facts are registered ones and the operators are theirs.
    `test_the_predicate_tree_is_literally_l2s_grammar_not_a_second_one` runs this exact tree through
    `cohort.parse_predicate`, so the fixture cannot drift into a shape only this contract accepts."""
    return {"all": [{"fact": "deal.value", "op": "gt", "value": 500000},
                    {"fact": "thread.ball_in_court", "op": "exists"}]}


def _constraint(**overrides) -> dict:
    record = {"rule_id": "urgency_must_belong_to_the_buyer", "severity": "blocking",
              "predicate_grammar": PREDICATE_GRAMMAR, "predicate_tree": _tree(),
              "source_ref": "expert:rule:urgency_must_belong_to_the_buyer"}
    record.update(overrides)
    return record


def _receipt(**overrides) -> dict:
    record = {key: 0 for key in WELD_RECEIPT_COUNTERS}
    record.update(overrides)
    return record


# =============================================================================================
# V-1 · citations are QUOTED, never paraphrased
# =============================================================================================

def test_v1_a_citation_carrying_the_authored_text_is_accepted():
    assert require_citation(_citation())["statement"] == AUTHORED


def test_v1_a_paraphrased_citation_is_a_validation_error_not_a_warning():
    """THE defect this validator exists for. The binder copies the digest of the ARTIFACT's authored
    text onto the citation; if it then writes its own words in `statement`, the two disagree. There
    is no path here that logs and continues — a paraphrase reaching a card is the expert voice being
    invented, which is exactly what E5's audit trail is supposed to make impossible."""
    paraphrase = _citation(statement="Warmth doesn't really predict intent.")
    paraphrase["statement_hash"] = citation_statement_hash(AUTHORED)
    with pytest.raises(ValueError, match="never paraphrased"):
        require_citation(paraphrase)


def test_v1_the_statement_is_not_stripped_because_a_strip_is_the_smallest_paraphrase():
    """`require_text` strips. The authored bytes end in a newline, and a validator that quietly
    trimmed it would hash a different string than the catalog holds and fail V-1 for a reason nobody
    reading the two strings could see."""
    assert AUTHORED.endswith("\n")
    kept = require_citation(_citation())["statement"]
    assert kept == AUTHORED and kept.endswith("\n")
    with pytest.raises(ValueError, match="never paraphrased"):
        require_citation(_citation(statement=AUTHORED.strip()))


def test_v1_a_quote_and_its_fingerprint_travel_together_or_not_at_all():
    naked = _citation()
    naked.pop("statement_hash")
    with pytest.raises(ValueError, match="missing 'statement_hash'"):
        require_citation(naked)
    hash_only = _citation()
    hash_only.pop("statement")
    with pytest.raises(ValueError, match="missing 'statement'"):
        require_citation(hash_only)


def test_v1_both_sides_of_the_check_call_the_same_function():
    """The catalog-side digest is DEFINED as this function's output, not as "a hash". A binder that
    hashed the whole YAML file, or a normalised statement, would be comparing two different things
    and would prove nothing while looking like it proved something."""
    assert citation_statement_hash(AUTHORED) == hashlib.sha256(
        AUTHORED.encode("utf-8")).hexdigest()


def test_v1_an_unknown_artifact_class_is_refused():
    with pytest.raises(ValueError, match="artifact_class"):
        require_citation(_citation(artifact_class="anecdote"))
    assert set(CITATION_CLASSES) == {"decision_framework", "heuristic", "mental_model",
                                     "playbook", "rule"}


def test_v1_a_framing_block_carrying_prose_quotes_it_under_the_same_check():
    """Framing blocks are input material, never new claims — so if one carries prose it is quoted."""
    block = {"artifact_id": "model.expected_value", "artifact_class": "mental_model",
             "source_ref": "expert:mental_model:expected_value",
             "statement": AUTHORED, "statement_hash": citation_statement_hash("something else")}
    with pytest.raises(ValueError, match="never paraphrased"):
        require_framing_block(block)
    assert set(FRAMING_CLASSES) == {"decision_framework", "mental_model"}


def test_v1_an_optional_quote_still_cannot_travel_without_its_fingerprint():
    """`statement` is REQUIRED on a citation, so the pairing rule only bites where quoting is
    optional — framing blocks and constraint applications. Those are exactly the places a quote is
    most likely to be added later, by hand, without the hash: a card saying "eliminated because
    <sentence>" is an expert claim whether or not the field was mandatory."""
    for optional in (require_framing_block, require_constraint_application):
        base = ({"artifact_id": "model.expected_value", "artifact_class": "mental_model",
                 "source_ref": "expert:mental_model:expected_value"}
                if optional is require_framing_block
                else {"rule_id": "r1", "severity": "warning", "outcome": "fired"})
        with pytest.raises(ValueError, match="unverifiable quote"):
            optional(dict(base, statement=AUTHORED))
        with pytest.raises(ValueError, match="nothing to fingerprint"):
            optional(dict(base, statement_hash=citation_statement_hash(AUTHORED)))
        assert optional(dict(base, statement=AUTHORED,
                             statement_hash=citation_statement_hash(AUTHORED)))["statement"] \
            == AUTHORED


def test_v1_a_heuristic_is_a_claim_and_cannot_masquerade_as_a_framing_block():
    with pytest.raises(ValueError, match="belongs in citations"):
        require_framing_block({"artifact_id": "h1", "artifact_class": "heuristic",
                               "source_ref": "expert:heuristic:h1"})


# =============================================================================================
# V-2 · compiled constraints: a severity, and a PARSEABLE predicate tree
# =============================================================================================

def test_v2_a_compiled_constraint_needs_a_severity_from_the_closed_set():
    assert require_compiled_constraint(_constraint())["severity"] == "blocking"
    assert require_compiled_constraint(_constraint(severity="warning"))["severity"] == "warning"
    assert CONSTRAINT_SEVERITIES == ("blocking", "warning")
    with pytest.raises(ValueError, match="severity must be one of"):
        require_compiled_constraint(_constraint(severity="advisory"))


def test_v2_a_predicate_is_never_a_string_because_that_is_how_eval_gets_in():
    """Doc 03's hard rule 1: no eval(), no free expressions. A free expression enters as text
    somebody means to evaluate later, so text is refused at the type level."""
    with pytest.raises(TypeError, match="never a string"):
        require_compiled_constraint(_constraint(predicate_tree="days_since_last_touch > 14"))


def test_v2_an_operator_is_a_bare_token_never_an_expression():
    with pytest.raises(ValueError, match="operator"):
        require_predicate_tree({"fact": "deal.value", "op": "gt) or 1=1 --", "value": 1}, "tree")


def test_v2_a_condition_carries_exactly_fact_op_value():
    with pytest.raises(ValueError, match="unsupported keys"):
        require_predicate_tree({"fact": "deal.value", "op": "gt", "value": 1,
                                "sql": "drop table orgs"}, "tree")
    with pytest.raises(ValueError, match="needs 'fact' and 'op'"):
        require_predicate_tree({"op": "gt", "value": 1}, "tree")


def test_v2_a_combinator_node_carries_one_key_and_a_non_empty_term_list():
    with pytest.raises(ValueError, match="exactly one key"):
        require_predicate_tree({"all": [{"fact": "f", "op": "exists"}], "any": []}, "tree")
    with pytest.raises(ValueError, match="at least one term"):
        require_predicate_tree({"all": []}, "tree")


def test_v2_the_tree_is_depth_bounded_the_way_the_cohort_grammar_is():
    deep = {"fact": "deal.value", "op": "exists"}
    for _ in range(MAX_PREDICATE_DEPTH + 2):
        deep = {"all": [deep]}
    with pytest.raises(ValueError, match="nests deeper"):
        require_predicate_tree(deep, "tree")


def test_v2_a_constraint_must_name_the_one_grammar_that_produced_it():
    """`predicate_grammar` is not decoration. It is the machine-readable form of "do not invent a
    second grammar": a second one cannot appear without changing a string this contract refuses."""
    with pytest.raises(ValueError, match="second place eval"):
        require_compiled_constraint(_constraint(predicate_grammar="l3.rules.v1"))


def test_the_predicate_tree_is_literally_l2s_grammar_not_a_second_one():
    """THE WELD BETWEEN THE TWO HALVES, and the reason Y1's rule compiler has an entry point rather
    than a parser. `contracts/` may not import `context/` (test_layer_topology), so the operator
    whitelist stays in `cohort.parse_predicate` and the shape check stays here — and this test is
    where they are pinned to each other, by running the exact round trip Y1 must run:

        cohort.parse_predicate(authored_when, registry=...) -> cohort.predicate_json(...) -> here
    """
    from genios_engine.context.analytic import cohort

    emitted = cohort.predicate_json(cohort.parse_predicate(_tree()))
    accepted = require_compiled_constraint(_constraint(predicate_tree=emitted))
    assert accepted["predicate_tree"]["all"][0]["op"] == "gt"
    # The round trip is the identity, and what the contract froze is the same tree canonically.
    assert emitted == _tree()
    assert canonicalize(accepted["predicate_tree"]) == canonicalize(_tree())
    # And the parser really is the strict side. Both of these pass the SHAPE check above and are
    # refused by the grammar — an operator it does not have, and a fact nobody registered — which
    # is why Y1 compiles through `parse_predicate` and does not hand-build a tree.
    with pytest.raises(cohort.PredicateError):
        cohort.parse_predicate({"fact": "deal.value", "op": "regex", "value": "x"})
    with pytest.raises(cohort.PredicateError):
        cohort.parse_predicate({"fact": "buyer_stated_deadline", "op": "exists"})


def test_v2_two_constraints_cannot_disagree_about_the_same_authored_rule():
    with pytest.raises(ValueError, match="duplicate rule_id"):
        _package(schema_version=EXPERTISE_PACKAGE_VERSION,
                 compiled_constraints=(_constraint(), _constraint(severity="warning")),
                 weld_receipt=_receipt(rules_compiled=2))


# =============================================================================================
# V-3 · consumption is always accounted for
# =============================================================================================

def test_v3_a_v2_package_with_expert_rules_and_no_receipt_is_refused():
    """Law 4, made mechanical. A compiled package whose heuristics nobody reads is inventory, not
    intelligence — and the only way to tell the two apart from outside is whether the package says
    what the corpus contributed."""
    with pytest.raises(ValueError, match="inventory, not"):
        _package(schema_version=EXPERTISE_PACKAGE_VERSION)


def test_v3_the_receipt_carries_all_eight_counters_zeros_included():
    assert require_weld_receipt(_receipt())["rules_compiled"] == 0
    for missing in WELD_RECEIPT_COUNTERS:
        partial = _receipt()
        partial.pop(missing)
        with pytest.raises(ValueError, match="unaccounted"):
            require_weld_receipt(partial)


def test_v3_a_receipt_that_does_not_add_up_is_refused():
    with pytest.raises(ValueError, match="does not add up"):
        require_weld_receipt(_receipt(rules_compiled=1, rules_fired=1, rules_unevaluable=1))


def test_v3_the_receipt_must_count_what_the_package_actually_carries():
    """A receipt is a claim about this package, so it is checked against this package. A counter
    that drifts from the content is decoration that reads like evidence."""
    with pytest.raises(ValueError, match="rules compiled but"):
        _package(schema_version=EXPERTISE_PACKAGE_VERSION,
                 compiled_constraints=(_constraint(),), weld_receipt=_receipt(rules_compiled=4))
    with pytest.raises(ValueError, match="citations attached but"):
        _package(schema_version=EXPERTISE_PACKAGE_VERSION, citations=(_citation(),),
                 weld_receipt=_receipt(citations_attached=3))


def test_v3_a_full_v2_package_constructs_and_carries_every_class():
    package = _package(
        schema_version=EXPERTISE_PACKAGE_VERSION,
        compiled_constraints=(_constraint(),),
        citations=(_citation(),),
        framing_blocks=({"artifact_id": "model.expected_value",
                         "artifact_class": "mental_model",
                         "source_ref": "expert:mental_model:expected_value"},),
        pattern_id="pattern.renewal_gap",
        matched_conditions=({"fact": "deal.value", "observed": 640000},),
        weld_receipt=_receipt(rules_compiled=1, rules_fired=1, citations_attached=1,
                              plays_selected=4, plays_over_cap=2,
                              by_class={"heuristic": {"selected": 1, "skipped": 3}},
                              refusals=({"reason": "rule_unevaluable", "count": 2},)))
    assert package.citations[0]["statement"] == AUTHORED
    assert package.compiled_constraints[0]["rule_id"] == "urgency_must_belong_to_the_buyer"
    assert package.pattern_id == "pattern.renewal_gap"
    assert package.weld_receipt["plays_over_cap"] == 2


# =============================================================================================
# V-4 · additive: the old shape still constructs, and still HASHES the same
# =============================================================================================

def test_v4_an_old_shaped_package_still_constructs():
    package = _package(schema_version=EXPERTISE_PACKAGE_VERSION_V1)
    assert package.compiled_constraints == () and package.citations == ()
    assert package.framing_blocks == () and package.matched_conditions == ()
    assert package.weld_receipt == {} and package.pattern_id is None


def test_v4_the_live_compilers_schema_string_is_still_accepted():
    """`packs/compiler/expertise_builder.py` stamps 'expertise-package.v1' literally and every row
    already in `expertise_packages` carries it. A version bump that refused it would take the live
    compiler down in the name of a contract change."""
    assert _package(schema_version="expertise-package.v1").schema_version == \
        EXPERTISE_PACKAGE_VERSION_V1
    assert EXPERTISE_PACKAGE_VERSION == "expertise-package.v2"
    with pytest.raises(ValueError, match="unsupported expertise package schema"):
        _package(schema_version="expertise-package.v3")


def test_v4_an_old_shaped_package_hashes_exactly_as_it_did_before_this_wave():
    """INVARIANT #10 — package-churn suppression. The literal below was computed from the contract
    at HEAD before wave Y0 touched it. A schema addition that unconditionally widened
    `to_semantic_dict` would re-address every row in `expertise_packages` for knowledge that did not
    change: that is the failure `e1a0c47` stopped, at ~238 kB a situation and 995 MB before the
    design partner's database went read-only. So the new fields are hashed WHEN CARRIED and are
    absent otherwise, and the one deliberate re-address the bump costs is the one Y1 spends when it
    flips the builder to v2."""
    package = _package(schema_version=EXPERTISE_PACKAGE_VERSION_V1)
    assert package.semantic_hash == \
        "7ad5674e57566139453c20f5d3380bf00ee164112dd5ba7a912e78ad635e297d"
    assert set(package.to_semantic_dict()) == {
        "org_id", "schema_version", "visibility", "id", "situation_id", "brain_snapshot_id",
        "capabilities", "objects", "expert_rules", "organization_rules", "behavior_patterns",
        "adaptive_preferences", "confidence_bp", "evidence", "metadata"}


def test_v4_carried_content_does_change_the_address():
    """The other half of the same property: identical addresses for identical knowledge, and a NEW
    address the moment the knowledge is different. A citation that did not move the hash would be
    content the publisher's `on conflict do nothing` silently discarded."""
    bare = _package(schema_version=EXPERTISE_PACKAGE_VERSION, weld_receipt=_receipt())
    with_citation = _package(schema_version=EXPERTISE_PACKAGE_VERSION, citations=(_citation(),),
                             weld_receipt=_receipt(citations_attached=1))
    assert bare.semantic_hash != with_citation.semantic_hash
    assert "citations" in with_citation.to_semantic_dict()


def test_v4_a_v1_package_may_not_smuggle_v2_content():
    """A reader pinned to v1 reads none of these fields. Stamping them onto v1 would ship knowledge
    no v1 consumer looks at, which is precisely the inventory Law 4 forbids — and it would do it
    while the package looked welded."""
    for field, value in (("citations", (_citation(),)),
                         ("compiled_constraints", (_constraint(),)),
                         ("framing_blocks", ({"artifact_id": "m1",
                                              "artifact_class": "mental_model",
                                              "source_ref": "expert:mental_model:m1"},)),
                         ("weld_receipt", _receipt()),
                         ("pattern_id", "pattern.renewal_gap"),
                         ("matched_conditions", ({"fact": "f", "observed": 1},))):
        with pytest.raises(ValueError, match="cannot carry"):
            _package(schema_version=EXPERTISE_PACKAGE_VERSION_V1, **{field: value})


# =============================================================================================
# V-5 · no float anywhere
# =============================================================================================

def test_v5_a_float_is_refused_in_every_new_field():
    from genios_engine.platform.canonical import CanonicalizationError

    with pytest.raises(CanonicalizationError):
        require_predicate_tree({"fact": "deal.value", "op": "gt", "value": 14.5}, "tree")
    with pytest.raises(CanonicalizationError):
        require_citation(_citation(tag_overlap=0.5))
    with pytest.raises(ValueError):
        require_weld_receipt(_receipt(rules_compiled=1.0))


# =============================================================================================
# E-02 · the consumption side — what reached the decision, and what it eliminated
# =============================================================================================

def _decision(**overrides) -> ReasoningDecision:
    body = dict(outcome=DecisionOutcome.NO_ACTION, capability_id="c", capability_version="1",
                context_snapshot_id="s", candidates=(), selected_candidate_id=None,
                confidence_bp=5000, uncertainty=(), do_nothing_consequence="nothing",
                expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    body.update(overrides)
    return ReasoningDecision(**body)


def test_e02_an_old_shaped_decision_hashes_exactly_as_it_did_before_this_wave():
    """`decision_hash` is stored in `reasoning_runs` and compared on replay. The literal below was
    computed from `contracts/reasoning.py` at HEAD before this wave: a decision that gained no corpus
    content must address exactly as it did, or every stored decision's replay breaks in exchange for
    two fields that are empty on all of them."""
    assert _decision().semantic_hash == \
        "e97fc85ff16481ee0fdd5547da57709588db7513eb2991f17f8e65599d2f24e2"
    assert "citations" not in _decision().to_semantic_dict()


def test_e02_a_decision_carries_citations_through_from_the_package():
    decision = _decision(citations=(_citation(),))
    assert decision.citations[0]["statement"] == AUTHORED
    assert "citations" in decision.to_semantic_dict()


def test_e02_the_byte_identity_check_is_re_run_at_the_decision_not_trusted():
    """This is the object a card renders from, and the render is where a paraphrase finally becomes
    visible to a customer. Trusting the package would put the only check one hop away from the
    only place it matters."""
    paraphrase = _citation(statement="Warmth doesn't really predict intent.")
    paraphrase["statement_hash"] = citation_statement_hash(AUTHORED)
    with pytest.raises(ValueError, match="never paraphrased"):
        _decision(citations=(paraphrase,))


def test_e02_a_decision_does_not_grow_a_bibliography():
    with pytest.raises(ValueError, match="at most 5 citations"):
        _decision(citations=tuple(_citation(artifact_id=f"h{i}") for i in range(MAX_CITATIONS + 1)))


def test_e02_an_unevaluable_rule_must_name_what_it_did_not_know():
    """CLG-06 step 4. An unevaluable blocking rule must never silently pass OR silently block, and a
    receipt that says "unevaluable" without naming the UNKNOWN predicate is indistinguishable from
    one that guessed. Three outcomes, because the predicate evaluation has three states."""
    assert CONSTRAINT_OUTCOMES == ("fired", "satisfied", "unevaluable")
    with pytest.raises(ValueError, match="outcome must be one of"):
        # "blocked" is the tempting fourth word, and it is the coercion: it merges "the rule fired
        # and the candidate lost" with "we could not tell", which is the distinction the three-state
        # evaluation exists to keep.
        require_constraint_application({"rule_id": "r1", "severity": "blocking",
                                        "outcome": "blocked"})
    with pytest.raises(ValueError, match="indistinguishable from one that guessed"):
        _decision(constraints_applied=({"rule_id": "r1", "severity": "blocking",
                                        "outcome": "unevaluable"},))
    honest = _decision(constraints_applied=({"rule_id": "r1", "severity": "blocking",
                                             "outcome": "unevaluable",
                                             "missing": ("buyer_stated_deadline",)},))
    assert honest.constraints_applied[0]["missing"] == ("buyer_stated_deadline",)


def test_e02_only_a_blocking_rule_that_fired_eliminates_anything():
    with pytest.raises(ValueError, match="only a blocking rule that FIRED"):
        require_constraint_application({"rule_id": "r1", "severity": "warning",
                                        "outcome": "fired",
                                        "eliminated_candidate_ids": ("cand_x",)})


def test_e02_an_elimination_must_name_a_candidate_that_is_actually_eliminated_here():
    """`alternatives_rejected` renders straight onto a card, so a receipt that reads correctly and is
    false is worse than no receipt at all. This is what makes E5's "why not X?" answerable from the
    record instead of from a re-run."""
    kept = DecisionCandidate(play_id="play.chase", play_version="1", utility_bp=6000,
                             confidence_bp=6000, score_components={"fit": 6000},
                             disposition=CandidateDisposition.ELIGIBLE, rank_position=1)
    dropped = DecisionCandidate(play_id="play.pressure", play_version="1", utility_bp=1000,
                                confidence_bp=1000, score_components={"fit": 1000},
                                disposition=CandidateDisposition.ELIMINATED)
    applied = {"rule_id": "urgency_must_belong_to_the_buyer", "severity": "blocking",
               "outcome": "fired", "statement": AUTHORED,
               "statement_hash": citation_statement_hash(AUTHORED)}
    good = _decision(outcome=DecisionOutcome.DECISION, candidates=(kept, dropped),
                     selected_candidate_id=kept.candidate_id,
                     constraints_applied=(dict(applied,
                                               eliminated_candidate_ids=(dropped.candidate_id,)),))
    assert good.constraints_applied[0]["eliminated_candidate_ids"] == (dropped.candidate_id,)
    with pytest.raises(ValueError, match="not an eliminated candidate on this decision"):
        _decision(outcome=DecisionOutcome.DECISION, candidates=(kept, dropped),
                  selected_candidate_id=kept.candidate_id,
                  constraints_applied=(dict(applied,
                                            eliminated_candidate_ids=(kept.candidate_id,)),))


def test_e02_two_records_cannot_disagree_about_what_one_rule_did():
    with pytest.raises(ValueError, match="duplicate rule_id"):
        _decision(constraints_applied=({"rule_id": "r1", "severity": "blocking",
                                        "outcome": "fired"},
                                       {"rule_id": "r1", "severity": "warning",
                                        "outcome": "satisfied"}))


# =============================================================================================
# E-03 · l3_activation — per tenant, per DOMAIN, fail closed, stamped not deleted
# =============================================================================================

def _engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the activation table is not exercised")
    from genios_engine.platform.db import get_engine
    return get_engine(url)


@pytest.fixture
def engine():
    eng = _engine()
    with eng.begin() as c:
        c.execute(text("delete from l3_activation where org_id = :o"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from l3_activation where org_id = :o"), {"o": ORG})


def test_e03_activation_is_never_a_global_boolean_and_this_wave_leaves_the_old_one_alone():
    """Law 5, and the ordering doc 06 prints. `use_domain_compiler` stays exactly as it is until the
    first pilot passes J5 — it is the kill switch for the thing this table turns on, and deleting a
    kill switch in the same change that installs its subject leaves a cutover with no way back."""
    from genios_engine.platform.config import get_settings
    assert get_settings().use_domain_compiler is False
    assert ACT.L3_DOMAINS == ("admin", "customer_support", "sales")
    assert ACT.DOMAIN_ADMIN == "admin"


def test_e03_a_typo_in_a_domain_is_a_refusal_not_a_row_nothing_reads():
    """A free-text domain column plus no validation is a row that reads as an activated tenant right
    up until nothing happens."""
    for call in (lambda: ACT.require_domain("admn"),
                 lambda: ACT.is_l3_activated(None, ORG, "admn"),
                 lambda: ACT.l3_activated_orgs(None, "Admin")):
        with pytest.raises(ValueError, match="unknown Layer 3 domain"):
            call()


def test_e03_every_gate_read_fails_closed():
    """No database, an unreadable table, a query that errors — every one answers "not activated".
    The failure mode is then a tenant that compiles exactly as it does today, which is where every
    tenant already is; the opposite default is an unwatched compile on a tenant nobody chose."""
    class _Exploding:
        def connect(self):
            raise RuntimeError("connection refused")

    assert ACT.is_l3_activated(None, ORG, ACT.DOMAIN_ADMIN) is False
    assert ACT.l3_activated_orgs(None, ACT.DOMAIN_ADMIN) == frozenset()
    assert ACT.activated_domains(None, ORG) == frozenset()
    assert ACT.is_l3_activated(_Exploding(), ORG, ACT.DOMAIN_ADMIN) is False
    assert ACT.l3_activated_orgs(_Exploding(), ACT.DOMAIN_ADMIN) == frozenset()
    assert ACT.activated_domains(_Exploding(), ORG) == frozenset()


def test_e03_the_console_reads_do_not_swallow(engine):
    """An operator asking "what is the state of the pilot" must see the database error rather than
    the word "off" — the opposite contract from the gate reads above, on purpose."""
    class _Exploding:
        def connect(self):
            raise RuntimeError("connection refused")

    with pytest.raises(RuntimeError):
        ACT.get_l3_activation(_Exploding(), ORG, ACT.DOMAIN_ADMIN)
    with pytest.raises(RuntimeError):
        ACT.list_l3_activations(_Exploding())
    assert ACT.get_l3_activation(engine, ORG, ACT.DOMAIN_ADMIN) is None


def test_e03_a_tenant_is_activated_per_domain_not_globally(engine):
    """V1 scope is the Admin corpus while Sales and Customer Support stay compiled, stamped and
    inactive. One row per tenant would make that unexpressible."""
    ACT.activate(engine, ORG, domain=ACT.DOMAIN_ADMIN, by="harsh@genios.ai", notes="pilot",
                 at=NOW)
    assert ACT.is_l3_activated(engine, ORG, ACT.DOMAIN_ADMIN) is True
    assert ACT.is_l3_activated(engine, ORG, ACT.DOMAIN_SALES) is False
    assert ACT.activated_domains(engine, ORG) == frozenset({ACT.DOMAIN_ADMIN})
    assert ORG in ACT.l3_activated_orgs(engine, ACT.DOMAIN_ADMIN)
    assert ORG not in ACT.l3_activated_orgs(engine, ACT.DOMAIN_SALES)


def test_e03_reactivating_a_live_row_keeps_the_original_enabling(engine):
    """"Since when has this tenant been on the pilot" is the question the seven-day J5 report is
    read against; an upsert that refreshed the timestamp would answer with the date of the last
    click. And a second note FILLS IN a blank reason, never overwrites one already there."""
    first = ACT.activate(engine, ORG, domain=ACT.DOMAIN_ADMIN, by="harsh@genios.ai",
                         notes="admin pilot", at=NOW)
    again = ACT.activate(engine, ORG, domain=ACT.DOMAIN_ADMIN, by="someone.else@genios.ai",
                         notes="rewritten", at=NOW.replace(day=8))
    assert again.enabled_at == first.enabled_at
    assert again.enabled_by == "harsh@genios.ai"
    assert again.notes == "admin pilot"


def test_e03_a_deactivation_stamps_the_row_it_does_not_delete_it(engine):
    """J5 reads a SEVEN-DAY window and has to be able to say "the admin corpus was switched off on
    day four". A missing row cannot say that; a stamped one can, and the gate reads filter it out so
    the compiler sees exactly what a delete would have left it."""
    ACT.activate(engine, ORG, domain=ACT.DOMAIN_ADMIN, by="harsh@genios.ai", at=NOW)
    assert ACT.deactivate(engine, ORG, domain=ACT.DOMAIN_ADMIN, by="harsh@genios.ai",
                          at=NOW.replace(day=5)) is True
    assert ACT.deactivate(engine, ORG, domain=ACT.DOMAIN_ADMIN) is False   # already off
    assert ACT.is_l3_activated(engine, ORG, ACT.DOMAIN_ADMIN) is False
    record = ACT.get_l3_activation(engine, ORG, ACT.DOMAIN_ADMIN)
    assert record is not None and record.live is False
    assert record.enabled_at == NOW and record.disabled_at == NOW.replace(day=5)
    assert ORG not in {r.org_id for r in ACT.list_l3_activations(engine)}
    assert ORG in {r.org_id for r in ACT.list_l3_activations(engine, include_disabled=True)}


def test_e03_reviving_a_switched_off_row_starts_a_new_pilot_period(engine):
    """Dating a revived pilot from the first enabling would hand J5 a window containing days the
    compiler did not run."""
    ACT.activate(engine, ORG, domain=ACT.DOMAIN_ADMIN, by="harsh@genios.ai", at=NOW)
    ACT.deactivate(engine, ORG, domain=ACT.DOMAIN_ADMIN, at=NOW.replace(day=5))
    revived = ACT.activate(engine, ORG, domain=ACT.DOMAIN_ADMIN, by="pratap@genios.ai",
                           notes="round two", at=NOW.replace(day=20))
    assert revived.enabled_at == NOW.replace(day=20)
    assert revived.enabled_by == "pratap@genios.ai" and revived.notes == "round two"
    assert revived.live is True and revived.disabled_at is None


def test_e03_the_operator_record_says_what_activation_actually_turned_on(engine):
    """A switch an operator can see is on, without being told what it did, is assumed to have done
    everything — and here the honest answer carries a precondition: activation before Y1's typed
    consumers produces generic output that looks like success."""
    ACT.activate(engine, ORG, domain=ACT.DOMAIN_ADMIN, by="harsh@genios.ai", at=NOW)
    record = ACT.get_l3_activation(engine, ORG, ACT.DOMAIN_ADMIN).as_record()
    assert record["live"] is True and record["domain"] == ACT.DOMAIN_ADMIN
    assert "typed consumers" in record["effect"]
    assert "use_domain_compiler" in record["effect"]


def test_e03_the_table_is_erased_by_reset(engine):
    """DRIVEN THROUGH THE REAL ERASURE, not asserted against the list. Three Layer 2 waves added an
    org-scoped table and forgot `_ORG_SCOPED_TABLES`, and each was caught only in review; the loop
    in `_wipe` runs with no try/except by design, so a name missing there leaks silently rather than
    failing loudly. This row names a person and carries free text about the tenant, so it is theirs
    to have erased."""
    from genios_engine.api import account_routes

    assert "l3_activation" in account_routes._ORG_SCOPED_TABLES
    scratch = "org_l3_contracts_reset"
    with engine.begin() as c:
        required = c.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": scratch}
        for row in required:
            cols.append(row.column_name)
            ph.append(f":{row.column_name}")
            kind = row.data_type
            vals[row.column_name] = ("2026-01-01T00:00:00Z" if ("time" in kind or "date" in kind)
                                     else 0 if ("int" in kind or "numeric" in kind
                                                or "double" in kind)
                                     else False if kind == "boolean"
                                     else "{}" if kind in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                       "on conflict (id) do nothing"), vals)
    try:
        ACT.activate(engine, scratch, domain=ACT.DOMAIN_ADMIN, by="harsh@genios.ai", at=NOW)
        with engine.begin() as c:
            wiped = account_routes._wipe(c, scratch)
        assert wiped["l3_activation"] == 1
        assert ACT.get_l3_activation(engine, scratch, ACT.DOMAIN_ADMIN) is None
    finally:
        with engine.begin() as c:
            c.execute(text("delete from l3_activation where org_id=:o"), {"o": scratch})
            c.execute(text("delete from orgs where id=:o"), {"o": scratch})


def test_e03_the_migration_is_applied_and_shaped_as_the_plan_prints_it(engine):
    with engine.connect() as conn:
        columns = {r.column_name: r.is_nullable for r in conn.execute(text(
            "select column_name, is_nullable from information_schema.columns "
            "where table_name = 'l3_activation'"))}
        primary = [r.column_name for r in conn.execute(text(
            "select a.attname as column_name from pg_index i "
            "join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey) "
            "where i.indrelid = 'l3_activation'::regclass and i.indisprimary order by a.attname"))]
    assert set(columns) >= {"org_id", "domain", "enabled_at", "enabled_by", "notes",
                            "disabled_at", "disabled_by", "updated_at"}
    assert columns["enabled_by"] == "NO" and columns["enabled_at"] == "NO"
    assert columns["disabled_at"] == "YES"          # the reversal is optional; the row is not
    assert primary == ["domain", "org_id"]          # per tenant, per DOMAIN — Law 5
