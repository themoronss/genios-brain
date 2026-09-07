"""L3.1-U1 · the five analytic predicate kinds, and the refusals they must not answer.

Doc 01's acceptance row is *"a situation YAML with a `trend` predicate matches only when the BSO
carries a qualifying trend; `UNKNOWABLE` never satisfies `absence`; `INSUFFICIENT_HISTORY` yields
UNKNOWN, receipted."* The last word is the one that costs work: an abstention nobody can count is
indistinguishable from a rule that quietly did not fire, so every UNKNOWN here is asserted with
the receipt it carries.
"""
from __future__ import annotations

import pytest

from l3_inputs import (anomaly_fact, build_situation, build_slice, cohort_fact,
                       trend_fact)

from genios_engine.context.quality.inference import ABSENT_FIELDS_KEY
from genios_engine.packs.compiler import DomainCompiler, ExpertBrainCatalog, InMemoryRuntimeBrains
from genios_engine.packs.compiler.context_adapter import (ANOMALY_FACT_PREFIX,
                                                          COHORT_POSITION_FACT_PREFIX,
                                                          PREDICATE_KINDS,
                                                          TREND_FACT_PREFIX,
                                                          UNRESOLVED_CONFLICT, ContextAdapter,
                                                          PredicateState)


def _verdict(condition, *, facts=None, neighbor_facts=None, metadata=None,
             situation_metadata=None, missing_fields=()):
    adapter = ContextAdapter(
        build_situation(metadata=situation_metadata),
        build_slice(facts=facts, neighbor_facts=neighbor_facts, metadata=metadata,
                    missing_fields=missing_fields))
    return adapter.evaluate(condition)


def _assert_unknown(verdict, *receipts):
    assert verdict.state is PredicateState.UNKNOWN
    assert verdict.missing == receipts, verdict.missing


# =================================================================================================
# The vocabulary is the producers' own
# =================================================================================================

def test_the_fact_prefixes_are_the_ones_layer_2_actually_writes():
    """The three prefixes are SPELLED in `context_adapter`, not imported (see the constant's own
    note). A copy with no pin is a copy that drifts, and the drift is silent: a predicate reading
    `derived.trends.` finds nothing, answers UNKNOWN for ever, and looks exactly like a tenant
    with no history."""
    from genios_engine.context.analytic.anomaly import ANOMALY_FACT_PREFIX as owner_anomaly
    from genios_engine.context.analytic.comparator import POSITION_FACT_PREFIX as owner_cohort
    from genios_engine.context.analytic.trend import TREND_FACT_PREFIX as owner_trend
    from genios_engine.context.importance import UNRESOLVED_RESOLUTION as owner_conflict

    assert TREND_FACT_PREFIX == owner_trend
    assert COHORT_POSITION_FACT_PREFIX == owner_cohort
    assert ANOMALY_FACT_PREFIX == owner_anomaly
    assert UNRESOLVED_CONFLICT == owner_conflict


def test_all_five_kinds_are_declared_and_dispatched():
    """J3's row is "5 new predicate kinds evaluable". Counted here, and each one is driven by its
    own test below — a set with five strings in it proves nothing on its own."""
    assert PREDICATE_KINDS == {"trend", "cohort", "anomaly", "absence", "conflict"}


def test_an_unrecognised_kind_is_refused_by_name_not_answered_by_the_path_tail():
    """A typo must not fall through into the `path:` evaluator, where it would be answered by a
    different question entirely and the author would never learn."""
    _assert_unknown(_verdict({"kind": "trendy", "metric": "engagement"}),
                    "unsupported_predicate_kind:trendy")


# =================================================================================================
# trend
# =================================================================================================

def test_a_trend_predicate_matches_only_a_qualifying_trend():
    facts = {f"{TREND_FACT_PREFIX}engagement": {"value": trend_fact(confidence_bp=7_000)}}
    condition = {"kind": "trend", "metric": "engagement", "direction": "DECLINING",
                 "min_confidence_bp": 5_000}
    assert _verdict(condition, facts=facts).state is PredicateState.TRUE


def test_a_trend_in_the_other_direction_is_false():
    facts = {f"{TREND_FACT_PREFIX}engagement": {"value": trend_fact(direction="rising")}}
    condition = {"kind": "trend", "metric": "engagement", "direction": "DECLINING"}
    assert _verdict(condition, facts=facts).state is PredicateState.FALSE


def test_a_trend_below_the_authored_confidence_floor_is_false_not_unknown():
    """The direction was answered and the strength was MEASURED. The author set the bar; a known
    number under a known bar is a real negative, and abstaining there would make every threshold
    in the corpus unenforceable."""
    facts = {f"{TREND_FACT_PREFIX}engagement": {"value": trend_fact(confidence_bp=4_900)}}
    condition = {"kind": "trend", "metric": "engagement", "direction": "declining",
                 "min_confidence_bp": 5_000}
    assert _verdict(condition, facts=facts).state is PredicateState.FALSE


@pytest.mark.parametrize("refusal", ["insufficient_history", "insufficient_coverage"])
def test_a_refused_trend_is_unknown_and_says_which_refusal(refusal):
    """THE ROW J3 NAMES. `INSUFFICIENT_HISTORY` is a first-class `TrendDirection` member, not an
    error and not a weak answer — and FALSE here would be the claim "engagement is not declining",
    drawn from the fact that we have not looked long enough."""
    facts = {f"{TREND_FACT_PREFIX}engagement": {"value": trend_fact(direction=refusal)}}
    verdict = _verdict({"kind": "trend", "metric": "engagement", "direction": "declining"},
                       facts=facts)
    _assert_unknown(verdict, f"{TREND_FACT_PREFIX}engagement:{refusal}")


def test_a_trend_nobody_computed_is_unknown_not_false():
    verdict = _verdict({"kind": "trend", "metric": "engagement", "direction": "declining"})
    _assert_unknown(verdict, f"{TREND_FACT_PREFIX}engagement")


def test_a_trend_on_a_neighbour_node_is_read():
    """Where these facts LAND. A situation anchored on a company holds almost no facts of its own;
    engagement is measured on the people correlated onto it. Reading the anchor alone would make
    every trend predicate a rule that never fires."""
    condition = {"kind": "trend", "metric": "engagement", "direction": "declining"}
    verdict = _verdict(condition,
                       neighbor_facts={f"{TREND_FACT_PREFIX}engagement": trend_fact()})
    assert verdict.state is PredicateState.TRUE


def test_a_fractional_confidence_is_refused_rather_than_compared():
    """Integer basis points, enforced where the number is read. A Decimal here is a producer
    defect and it is named, never quietly rounded into a comparison."""
    from decimal import Decimal
    body = trend_fact()
    body["trend_confidence_bp"] = Decimal("7000.5")
    facts = {f"{TREND_FACT_PREFIX}engagement": {"value": body}}
    verdict = _verdict({"kind": "trend", "metric": "engagement", "min_confidence_bp": 5_000},
                       facts=facts)
    _assert_unknown(verdict, f"{TREND_FACT_PREFIX}engagement:trend_confidence_bp")


# =================================================================================================
# cohort
# =================================================================================================

def test_a_cohort_predicate_matches_the_band_the_population_can_express():
    facts = {f"{COHORT_POSITION_FACT_PREFIX}spend_growth": {
        "value": cohort_fact(percentile_bp=500, population=47)}}
    condition = {"kind": "cohort", "metric": "spend_growth", "band": "D1", "min_population": 5}
    assert _verdict(condition, facts=facts).state is PredicateState.TRUE


def test_a_cohort_band_is_recomputed_not_trusted():
    """`importance._expressible_band`'s rule, inherited. A stored `D1` on a population of six is a
    decile claim that cohort's own arithmetic can never produce, and trusting the body would let
    a row written by an older writer smuggle "bottom decile" onto a card."""
    facts = {f"{COHORT_POSITION_FACT_PREFIX}spend_growth": {
        "value": cohort_fact(percentile_bp=500, population=6, band="D1")}}
    # Six members express quartiles at best, so the honest band is Q1 — and the authored D1 is
    # therefore not matched.
    assert _verdict({"kind": "cohort", "metric": "spend_growth", "band": "D1"},
                    facts=facts).state is PredicateState.FALSE
    assert _verdict({"kind": "cohort", "metric": "spend_growth", "band": "Q1"},
                    facts=facts).state is PredicateState.TRUE


def test_a_refused_cohort_is_unknown_and_says_why():
    facts = {f"{COHORT_POSITION_FACT_PREFIX}spend_growth": {
        "value": cohort_fact(refused="insufficient_population", population=3)}}
    verdict = _verdict({"kind": "cohort", "metric": "spend_growth", "band": "D1"}, facts=facts)
    _assert_unknown(verdict,
                    f"{COHORT_POSITION_FACT_PREFIX}spend_growth:insufficient_population")


def test_a_population_too_small_to_express_any_band_is_unknown_not_false():
    """Four accounts have no expressible band at all. FALSE would read as "this account is not at
    the bottom of its peer group", which is a statement about the business drawn from a statement
    about the sample size."""
    facts = {f"{COHORT_POSITION_FACT_PREFIX}spend_growth": {
        "value": cohort_fact(percentile_bp=2_500, population=4)}}
    verdict = _verdict({"kind": "cohort", "metric": "spend_growth", "band": "Q1"}, facts=facts)
    _assert_unknown(verdict,
                    f"{COHORT_POSITION_FACT_PREFIX}spend_growth:population_too_small")


def test_a_population_under_the_authored_floor_is_false():
    facts = {f"{COHORT_POSITION_FACT_PREFIX}spend_growth": {
        "value": cohort_fact(percentile_bp=500, population=6)}}
    assert _verdict({"kind": "cohort", "metric": "spend_growth", "min_population": 20},
                    facts=facts).state is PredicateState.FALSE


def test_a_band_outside_the_contract_vocabulary_is_refused_by_name():
    """There is ONE band vocabulary and it is `CohortBand`'s fourteen labels. A symbolic alias
    would be a second grammar for the same fact, and the day the two disagree the card prints the
    loser."""
    facts = {f"{COHORT_POSITION_FACT_PREFIX}spend_growth": {"value": cohort_fact()}}
    verdict = _verdict({"kind": "cohort", "metric": "spend_growth", "band": "top_decile"},
                       facts=facts)
    _assert_unknown(verdict, "cohort_band:top_decile")


# =================================================================================================
# anomaly
# =================================================================================================

def test_a_flagged_anomaly_is_true_and_an_unflagged_one_is_false():
    flagged = {f"{ANOMALY_FACT_PREFIX}support_tickets": {"value": anomaly_fact(flagged=True)}}
    calm = {f"{ANOMALY_FACT_PREFIX}support_tickets": {"value": anomaly_fact(flagged=False)}}
    condition = {"kind": "anomaly", "metric": "support_tickets"}
    assert _verdict(condition, facts=flagged).state is PredicateState.TRUE
    # MEASURED AND NOT FLAGGED is the one honest FALSE in this family: the detector had a
    # baseline, computed the deviation, and both conjuncts failed.
    assert _verdict(condition, facts=calm).state is PredicateState.FALSE


@pytest.mark.parametrize("refusal", ["insufficient_history", "no_current_reading"])
def test_a_refused_anomaly_verdict_is_unknown(refusal):
    facts = {f"{ANOMALY_FACT_PREFIX}support_tickets": {
        "value": anomaly_fact(flagged=False, refusal=refusal)}}
    verdict = _verdict({"kind": "anomaly", "metric": "support_tickets"}, facts=facts)
    _assert_unknown(verdict, f"{ANOMALY_FACT_PREFIX}support_tickets:{refusal}")


def test_an_anomaly_direction_narrows_the_match():
    facts = {f"{ANOMALY_FACT_PREFIX}support_tickets": {"value": anomaly_fact(direction="above")}}
    assert _verdict({"kind": "anomaly", "metric": "support_tickets", "direction": "above"},
                    facts=facts).state is PredicateState.TRUE
    assert _verdict({"kind": "anomaly", "metric": "support_tickets", "direction": "below"},
                    facts=facts).state is PredicateState.FALSE


# =================================================================================================
# conflict
# =================================================================================================

def _conflict_record(field="contract.value", resolution=UNRESOLVED_CONFLICT):
    return {"conflict_id": "conf_1", "signal_id": "signal_1", "field": field,
            "subject_key": "deal:1", "resolution": resolution, "resolved_value": None,
            "event_ids": ["ev_1", "ev_2"], "claim_count": 2}


def test_an_unresolved_conflict_on_the_named_field_is_true():
    verdict = _verdict({"kind": "conflict", "field": "contract.value"},
                       situation_metadata={"conflicts": [_conflict_record()],
                                           "conflict_ids": ["conf_1"]})
    assert verdict.state is PredicateState.TRUE


def test_a_conflict_layer_1_already_settled_is_not_material():
    """`importance._conflict_term`'s definition, inherited rather than restated: the other two
    resolutions HAVE an answer, and firing on a disagreement we resolved charges the reader for
    our own resolution logic."""
    verdict = _verdict({"kind": "conflict", "field": "contract.value"},
                       situation_metadata={
                           "conflicts": [_conflict_record(resolution="resolved_by_authority")],
                           "conflict_ids": ["conf_1"]})
    assert verdict.state is PredicateState.FALSE


def test_no_conflict_at_all_is_false():
    verdict = _verdict({"kind": "conflict", "field": "contract.value"},
                       situation_metadata={"conflicts": [], "conflict_ids": []})
    assert verdict.state is PredicateState.FALSE


def test_truncated_conflict_records_are_unknown_not_false():
    """`_attach_conflicts` caps the RECORDS at MAX_CONFLICTS while `conflict_ids` keeps pointing
    at all of them. More pointers than records means the disagreement about this field may be one
    that did not travel, and a FALSE would report a contested field as settled."""
    verdict = _verdict({"kind": "conflict", "field": "contract.value"},
                       situation_metadata={
                           "conflicts": [_conflict_record(field="deal.stage")],
                           "conflict_ids": ["conf_1", "conf_2"]})
    _assert_unknown(verdict, "conflict:contract.value:truncated")


def test_a_situation_that_carries_no_conflict_key_is_unknown():
    """Silence is not "nothing is contested". Every BSO this codebase builds writes the key; an
    object that does not is one we were not told about."""
    verdict = _verdict({"kind": "conflict", "field": "contract.value"})
    _assert_unknown(verdict, "conflict:contract.value")


# =================================================================================================
# REACH — the grammar has to be authorable, not merely callable
# =================================================================================================

def test_every_new_kind_routes_a_real_compile(authoring_root):
    """The whole grammar, authored in a situation YAML, loaded by the real catalog, evaluated by
    the real resolver inside a real `DomainCompiler.compile`.

    "A test calls the function" is not a caller. This is the path `reason/domain_shadow` runs on
    live traffic — same catalog loader, same resolver, same adapter — with the only difference
    being that the corpus lives in tmp_path.
    """
    when = ("[{kind: trend, metric: engagement, direction: DECLINING, min_confidence_bp: 5000},"
            " {kind: cohort, metric: spend_growth, band: D1, min_population: 5},"
            " {kind: anomaly, metric: support_tickets},"
            " {kind: absence, fact: decision.scheduled, type: GENUINELY_ABSENT},"
            " {kind: conflict, field: contract.value}]")
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(authoring_root(when=when)),
                              runtime_brains=InMemoryRuntimeBrains(), require_admission=False)
    situation = build_situation(metadata={"conflicts": [_conflict_record()],
                                          "conflict_ids": ["conf_1"]})
    context = build_slice(
        facts={f"{TREND_FACT_PREFIX}engagement": {"value": trend_fact()},
               f"{COHORT_POSITION_FACT_PREFIX}spend_growth": {"value": cohort_fact()},
               f"{ANOMALY_FACT_PREFIX}support_tickets": {"value": anomaly_fact()}},
        metadata={ABSENT_FIELDS_KEY: ["decision.scheduled"]})

    package = compiler.compile(situation, context)

    assert [item["id"] for item in package.capabilities] == [
        "sales.qualification.lead_qualification"]
    assert package.metadata["matched_situation_ids"] == ("sales.sit.anchor",)
    assert package.metadata["unresolved_route_predicates"] == ()


def test_one_refused_analytic_input_abstains_the_whole_route_with_a_receipt(authoring_root):
    """The other half of reach: when one of the five cannot be answered the route does not
    silently fire on the rest, and the reason reaches the package's metadata where an operator
    can read it."""
    when = ("[{kind: trend, metric: engagement, direction: DECLINING},"
            " {kind: anomaly, metric: support_tickets}]")
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(authoring_root(when=when)),
                              runtime_brains=InMemoryRuntimeBrains(), require_admission=False)
    from genios_engine.packs.compiler.errors import SituationContextIncomplete
    with pytest.raises(SituationContextIncomplete) as raised:
        compiler.compile(build_situation(), build_slice(
            facts={f"{ANOMALY_FACT_PREFIX}support_tickets": {"value": anomaly_fact()},
                   f"{TREND_FACT_PREFIX}engagement": {
                       "value": trend_fact(direction="insufficient_history")}}))
    assert "sales.sit.anchor:derived.trend.engagement:insufficient_history" in str(raised.value)


def test_the_dependency_blocked_count_needs_no_new_predicate_kind():
    """The fourth `derived.*` family, and the reason it is NOT a sixth kind.

    `derived.dependency.blocked_count` is one integer about its own subject — no direction, no
    refusal, no population, nothing three-state to model — so the existing `path:`/`op:`/`value:`
    predicate answers it exactly. A `{kind: dependency}` would be a second spelling for a question
    the grammar already asks, and every extra spelling is another thing an author can get wrong.
    Pinned against the field name `correlation_dependency` owns.
    """
    from genios_engine.context.importance import DEPENDENCY_BLOCKED_FIELD

    facts = {DEPENDENCY_BLOCKED_FIELD: {"value": 4}}
    assert _verdict({"path": DEPENDENCY_BLOCKED_FIELD, "op": ">", "value": 3},
                    facts=facts).state is PredicateState.TRUE
    assert _verdict({"path": DEPENDENCY_BLOCKED_FIELD, "op": ">", "value": 9},
                    facts=facts).state is PredicateState.FALSE
    # And the three-state rule holds there too, without any new code: a node nobody measured is
    # UNKNOWN, not "nothing is blocked on this".
    _assert_unknown(_verdict({"path": DEPENDENCY_BLOCKED_FIELD, "op": ">", "value": 3}),
                    DEPENDENCY_BLOCKED_FIELD)


#: A plausible value per predicate key, so a FORM can be turned into a condition without the test
#: knowing which form it is looking at.
_SAMPLE = {
    "exists": "deal.amount", "absent": "deal.amount", "path": "deal.amount",
    "neighbor_fact": "deal.amount", "fact": "deal.amount", "field": "contract.value",
    "has_obs": "reply_received", "no_obs": "reply_received",
    "neighbor_has_obs": "reply_received", "neighbor_no_obs": "reply_received",
    "op": "=", "value": 1, "kind": "trend", "metric": "engagement",
    "direction": "declining", "type": "GENUINELY_ABSENT", "band": "D1",
    "min_confidence_bp": 5_000, "min_population": 5, "min_z_like_bp": 30_000,
    "resolution": UNRESOLVED_CONFLICT, "fn": "edge_count",
}


def test_every_form_the_corpus_validator_admits_is_one_this_adapter_dispatches():
    """THE SEAM BETWEEN THE GRAMMAR AND THE AUTHORING GATE, checked in the direction that can be
    checked from here.

    `Domain Expertise/_tools/validate.py` refuses a predicate whose key set "matches no form the
    engine dispatches on" — a real gate, and the reason it exists is that a form the engine does
    not dispatch returns a non-answer for ever while looking like authored expertise. The list is
    a hand-transcription of this module's dispatch order, and a hand-transcription of a dispatch
    order is a copy that drifts.

    This asserts the dangerous direction: nothing the validator LETS THROUGH is a form this
    adapter answers with `unsupported_predicate`. It passes today, and it keeps passing when the
    corpus wave adds the five `kind:` forms — which is the point. It goes red only if the
    validator starts admitting something the compiler cannot evaluate.
    """
    import importlib.util
    import pathlib

    from genios_engine.packs.compiler.authoring import default_authoring_root

    validator_path = default_authoring_root() / "_tools" / "validate.py"
    spec = importlib.util.spec_from_file_location("_corpus_validate", validator_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for form in module.FORM_KEYS:
        condition = {key: _SAMPLE[key] for key in form}
        if "fn" in form and "path" in form:
            # `days_since` is the only `fn` that takes a path; `edge_count` reads the slice's own
            # edge count and refuses a `path:` beside it (the validator says so too).
            condition["fn"] = "days_since"
        verdict = _verdict(condition)
        refusals = [item for item in verdict.missing
                    if item == "unsupported_predicate"
                    or item.startswith("unsupported_predicate_kind:")]
        assert not refusals, (
            f"the corpus validator admits {sorted(form)} and the adapter cannot dispatch it: "
            f"{verdict}")
