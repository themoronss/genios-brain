"""H2 · L2.4.4 — the cohort builder (BLG-09) and M-9 authoring. The gate for
`context/analytic/cohort.py`.

**Gate H2** (`02-Layer-2-Plan/09-Build-Order-and-Acceptance.md`):

    pytest tests/context/analytic/test_trend.py tests/context/analytic/test_cohort.py -q

Doc 04's acceptance list is five rows and every one of them is here, in its order: a predicate
evaluates identically twice; a node that fails once STAYS and failing twice removes it with
`left_at` set; a cohort of four returns `insufficient_population` rather than a percentile; an
unregistered fact name raises at DEFINITION time; and no code path builds SQL from a predicate.

THE TWO TESTS THAT MATTER MOST ARE NOT IN THAT LIST.

`test_the_sweep_builds_cohorts_and_membership` drives `context/runner.process_pending` — the
function every sync and upload route calls — against a real Postgres and asserts that cohort
definitions and membership rows exist afterwards. Layer 1 shipped six units that were built,
green and called by nothing on a real request path; each was found only by adversarial review.
Every other test in this file constructs the cohort module itself and would pass in a build where
the call in `runner.py` had been deleted.

`test_one_tenants_numbers_never_reach_another_tenants_position` is the isolation law. A cohort is
the one construct in this engine whose purpose is to let one subject be read against others, so it
is the one place a tenant boundary could be crossed by a missing `where`. It builds two orgs that
share a `node_id` — `graph_nodes` is keyed `(node_id, version)` with no org in the key, so that is
constructible — gives them different readings, and asserts the position is computed entirely from
one of them and reveals nothing of the other.
"""

from __future__ import annotations

import ast
import inspect
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.contracts.analytic import (MIN_COHORT_POPULATION, CohortBand,
                                              CohortPosition, expressible_divisions)
from genios_engine.context.analytic.cohort import (COHORT_DEFINITION_TABLE,
                                                   COHORT_MEMBERSHIP_TABLE, MAX_COHORTS_PER_ORG,
                                                   MEMBERSHIP_RETENTION_MONTHS,
                                                   MIN_QUARTILE_POPULATION, MISSES_BEFORE_LEAVING,
                                                   PROPOSAL_SAMPLES, SYSTEM_AUTHOR, CohortEventKind,
                                                   CohortRefusal, CohortRefusalReason,
                                                   FactKind, PredicateError, ProposalRefused,
                                                   ProposalRefusalReason, QuartileFamily,
                                                   approve_proposal, default_cohorts,
                                                   define_cohort, evaluate,
                                                   load_node_facts,
                                                   membership_changes, normalise_fact,
                                                   numeric_values, parse_predicate, percentile_bp,
                                                   position_from_values, position_in_cohort,
                                                   predicate_fingerprint, propose_cohort,
                                                   prune_membership, quartile_cohorts,
                                                   refresh_cohorts_for_drain, refresh_membership,
                                                   save_definitions)
from genios_engine.platform.canonical import canonical_dumps

UTC = timezone.utc
_ENGINE = Path(__file__).resolve().parents[3] / "genios_engine"
_COHORT_SOURCE = (_ENGINE / "context" / "analytic" / "cohort.py").read_text()

#: Every instant in this file is a parameter. Nothing here reads a clock.
AT = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)

GROWTH_MID_ARR = {"all": [
    {"fact": "account.arr_minor_units", "op": "between", "value": [1_000_000, 5_000_000]},
    {"fact": "account.plan", "op": "eq", "value": "growth"},
    {"fact": "account.onboarded_at", "op": "within_days", "value": 180},
]}


def _account(arr: int, plan: str = "growth", onboarded_days_ago: int = 30,
             **extra) -> dict[str, object]:
    return {"node.type": "company", "account.arr_minor_units": arr, "account.plan": plan,
            # `node.tenure_days` is computed by `load_node_facts` from the node row and
            # `eval_time`; a hermetic world has to state it, and stating it is also what makes the
            # tenure quartile family testable without a database.
            "node.tenure_days": onboarded_days_ago,
            "account.onboarded_at": (AT - timedelta(days=onboarded_days_ago)).isoformat(),
            **extra}


def _population(n: int, *, first: int = 1_000_000, step: int = 100_000) -> dict[str, dict]:
    """`n` accounts on a strictly increasing ARR ladder — a population quartiles can separate."""
    return {f"node_acct_{i:02d}": _account(first + step * i, onboarded_days_ago=30 + i)
            for i in range(n)}


# =================================================================================================
# DOC 04 ROW 1 — A PREDICATE EVALUATES IDENTICALLY TWICE
# =================================================================================================

def test_a_predicate_tree_evaluates_identically_twice() -> None:
    """Reproducibility is the whole point of a measuring instrument. Same tree, same facts, same
    instant — same answer, and the same BYTES for the stored predicate and its content address."""
    predicate = parse_predicate(GROWTH_MID_ARR)
    nodes = _population(12)
    first = {node_id: evaluate(predicate, facts, eval_time=AT) for node_id, facts in nodes.items()}
    second = {node_id: evaluate(predicate, facts, eval_time=AT) for node_id, facts in nodes.items()}

    assert first == second and any(first.values())
    assert canonical_dumps(predicate.as_json()) == canonical_dumps(
        parse_predicate(GROWTH_MID_ARR).as_json())
    assert predicate_fingerprint(predicate) == predicate_fingerprint(parse_predicate(GROWTH_MID_ARR))


def test_the_same_cohort_authored_twice_is_one_cohort_not_two() -> None:
    """Content-addressed ids. Approving the same predicate again must not mint a second row —
    that is how a definitions table grows without a single new customer."""
    kwargs = dict(org_id="org_a", name="Growth, mid ARR", node_type="company",
                  predicate=GROWTH_MID_ARR, created_by="user_priya", eval_time=AT)
    assert define_cohort(**kwargs).cohort_id == define_cohort(**kwargs).cohort_id
    other = define_cohort(**{**kwargs, "org_id": "org_b"})
    assert other.cohort_id != define_cohort(**kwargs).cohort_id, (
        "two tenants writing the same predicate must not share a definition row")


def test_evaluation_is_total_over_whatever_a_fact_holds() -> None:
    """A parsed predicate NEVER raises on a node. A predicate that threw halfway through a refresh
    would leave a cohort's membership describing a population that never existed."""
    predicate = parse_predicate(GROWTH_MID_ARR)
    for junk in ({}, {"account.arr_minor_units": None}, {"account.arr_minor_units": "n/a"},
                 {"account.arr_minor_units": {"nested": 1}, "account.plan": ["growth"]},
                 {"account.onboarded_at": "not-a-date"}, {"account.plan": True}):
        assert evaluate(predicate, junk, eval_time=AT) is False


def test_a_ratio_fact_is_normalised_through_decimal_never_a_float() -> None:
    """`derived.py` writes engagement as `repr(round(v, 4))`. It arrives as 0.8333 and is compared
    as 8333 basis points — through `Decimal`, so a boundary is decided by the decimal a human
    wrote and not by a binary expansion."""
    assert normalise_fact(FactKind.RATIO, 0.8333) == 8333
    assert normalise_fact(FactKind.RATIO, "0.5") == 5000
    assert normalise_fact(FactKind.NUMBER, 4_200_000) == 4_200_000
    assert normalise_fact(FactKind.NUMBER, "not a number") is None

    hot = parse_predicate({"all": [{"fact": "derived.engagement", "op": "gte", "value": 8000}]})
    assert evaluate(hot, {"derived.engagement": 0.8333}, eval_time=AT) is True
    assert evaluate(hot, {"derived.engagement": 0.79}, eval_time=AT) is False


def test_within_days_is_backward_looking_only() -> None:
    """"Churned in the last year" must not collect next quarter's renewal."""
    predicate = parse_predicate(
        {"all": [{"fact": "account.churned_at", "op": "within_days", "value": 365}]})
    assert evaluate(predicate, {"account.churned_at": (AT - timedelta(days=200)).isoformat()},
                    eval_time=AT) is True
    assert evaluate(predicate, {"account.churned_at": (AT - timedelta(days=400)).isoformat()},
                    eval_time=AT) is False
    assert evaluate(predicate, {"account.churned_at": (AT + timedelta(days=10)).isoformat()},
                    eval_time=AT) is False


def test_the_combinators_do_what_they_say() -> None:
    facts = _account(2_000_000, plan="growth")
    cases = (
        ({"any": [{"fact": "account.plan", "op": "eq", "value": "enterprise"},
                  {"fact": "account.plan", "op": "eq", "value": "growth"}]}, True),
        ({"none": [{"fact": "account.plan", "op": "eq", "value": "growth"}]}, False),
        ({"none": [{"fact": "account.plan", "op": "eq", "value": "free"}]}, True),
        ({"all": [{"fact": "account.industry", "op": "missing"}]}, True),
        ({"all": [{"fact": "account.arr_minor_units", "op": "exists"}]}, True),
        ({"all": [{"fact": "account.plan", "op": "in", "value": ["growth", "scale"]}]}, True),
    )
    for raw, expected in cases:
        assert evaluate(parse_predicate(raw), facts, eval_time=AT) is expected, raw


# =================================================================================================
# DOC 04 ROW 4 — AN UNREGISTERED FACT RAISES AT DEFINITION TIME
# =================================================================================================

def test_an_unregistered_fact_name_raises_at_definition_time() -> None:
    """Doc 04 failure 3: a reference to a missing fact is a SILENT EMPTY COHORT, and an empty
    cohort reads exactly like a true answer about a business with no such accounts."""
    with pytest.raises(PredicateError) as raised:
        parse_predicate({"all": [{"fact": "account.arr", "op": "gt", "value": 10}]})
    assert "not a registered cohort fact" in str(raised.value)

    with pytest.raises(PredicateError):
        define_cohort(org_id="org_a", name="typo", node_type="company",
                      predicate={"all": [{"fact": "acount.plan", "op": "eq", "value": "growth"}]},
                      created_by="user_priya", eval_time=AT)


def test_definition_time_refusals_are_table_driven() -> None:
    """Everything that cannot be evaluated honestly is refused while somebody is still looking at
    what they wrote — never at evaluation, where the symptom is an empty cohort."""
    cases = {
        "a float threshold": {"all": [{"fact": "account.arr_minor_units", "op": "gt",
                                       "value": 1_000_000.5}]},
        "an operator the kind cannot answer": {
            "all": [{"fact": "account.onboarded_at", "op": "gt", "value": 5}]},
        "a text fact compared numerically": {
            "all": [{"fact": "account.plan", "op": "gt", "value": 3}]},
        "an unknown operator": {"all": [{"fact": "account.plan", "op": "like", "value": "gro"}]},
        "an empty group": {"all": []},
        "an inverted between": {"all": [{"fact": "account.arr_minor_units", "op": "between",
                                         "value": [50, 10]}]},
        "a value on a nullary operator": {"all": [{"fact": "account.plan", "op": "exists",
                                                   "value": "growth"}]},
        "a missing value": {"all": [{"fact": "account.plan", "op": "eq"}]},
        "a combinator with two keys": {"all": [{"fact": "account.plan", "op": "exists"}],
                                       "any": [{"fact": "account.plan", "op": "missing"}]},
    }
    for label, raw in cases.items():
        with pytest.raises(PredicateError):
            parse_predicate(raw)
            pytest.fail(f"{label} was accepted")


def test_a_predicate_about_the_wrong_node_type_is_refused_at_definition_time() -> None:
    """`account.plan` never appears on a person, so a person cohort declared over it matches
    nobody — which is indistinguishable from a true answer once it is stored."""
    with pytest.raises(PredicateError) as raised:
        define_cohort(org_id="org_a", name="People on growth", node_type="person",
                      predicate={"all": [{"fact": "account.plan", "op": "eq", "value": "growth"}]},
                      created_by="user_priya", eval_time=AT)
    assert "empty cohort" in str(raised.value)


# =================================================================================================
# DOC 04 ROW 3 — A COHORT OF FOUR IS A REFUSAL, NOT A WEAK POSITION
# =================================================================================================

def test_a_cohort_below_the_floor_is_refused_not_weakened() -> None:
    """Law 2. With four members every percentile is 2500/5000/7500/10000 — the number describes
    the arithmetic, not the business, and "bottom quartile" becomes a sentence about one person."""
    values = {f"node_{i}": 10 * i for i in range(MIN_COHORT_POPULATION - 1)}
    outcome = position_from_values(metric="engagement.touch_count_28d", cohort_id="coh_small",
                                   values=values, subject_node_id="node_0", eval_time=AT)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.INSUFFICIENT_POPULATION
    assert outcome.population_size == MIN_COHORT_POPULATION - 1
    assert outcome.is_position is False

    # and the contract makes the weak position unconstructible even by hand
    with pytest.raises(ValueError):
        CohortPosition(metric="m", cohort_id="coh_small", population_size=4, percentile_bp=2500,
                       band=CohortBand.Q2, p25_bp=0, p50_bp=10, p75_bp=20, computed_at=AT)


def test_a_cohort_at_the_floor_is_a_position() -> None:
    """CHANGED, and the old assertion was the defect written down as a test.

    It asserted `band is CohortBand.D3` for the WORST member of a five-member cohort. That was
    never a judgement — it was arithmetic nobody had checked. Nearest rank counts the subject, so
    the smallest percentile a population of n can produce is `10000 // n`; at n=5 that is 2000,
    and D1 `[0, 1000)` and D2 `[1000, 2000)` are empty sets. "Bottom of five" was therefore
    published as "third decile", which reads as below average and not alarming. `CohortPosition`
    now narrows the scheme to the finest its population can express (`expressible_divisions`), so
    the same member comes back Q1 — the bottom QUARTILE, a band five members can actually fill.
    The percentile is unchanged at 2000: the number was always right, only its label lied.
    """
    values = {f"node_{i}": 10 * i for i in range(MIN_COHORT_POPULATION)}
    position = position_from_values(metric="engagement.touch_count_28d", cohort_id="coh_floor",
                                    values=values, subject_node_id="node_0", eval_time=AT)
    assert isinstance(position, CohortPosition)
    assert position.population_size == MIN_COHORT_POPULATION
    assert position.percentile_bp == 2000 and position.band is CohortBand.Q1
    # and the band it was given is one this population can reach at all
    assert position.band.divisions == expressible_divisions(MIN_COHORT_POPULATION, requested=10)


def test_a_population_that_is_mostly_unknown_is_refused_for_coverage() -> None:
    """Half a cohort with no reading is not a peer group with a gap; it is a different cohort."""
    values = {f"node_{i}": 10 * i for i in range(6)}
    outcome = position_from_values(metric="deal.value_minor_units", cohort_id="coh_thin",
                                   values=values, subject_node_id="node_0", eval_time=AT,
                                   unknown=8)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.INSUFFICIENT_COVERAGE


def test_a_subject_with_no_reading_is_refused_by_name() -> None:
    outcome = position_from_values(metric="deal.value_minor_units", cohort_id="coh",
                                   values={f"node_{i}": i for i in range(8)},
                                   subject_node_id="node_absent", eval_time=AT)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.SUBJECT_VALUE_UNKNOWN


# =================================================================================================
# THE BAND ALWAYS CONTAINS THE PERCENTILE
# =================================================================================================

@pytest.mark.parametrize("size", [5, 6, 7, 10, 11, 20, 37, 100])
@pytest.mark.parametrize("divisions", [4, 10])
def test_the_band_always_contains_the_percentile(size: int, divisions: int) -> None:
    """Doc 04's coherence rule, over every member of several populations rather than one example.

    A card that prints "bottom decile" beside a median is not a tuning difference — it is the one
    failure `CohortBand.contains` exists to make unconstructible, and this is the sweep that
    proves the position builder never hands it a pair that disagrees.
    """
    values = {f"node_{i:03d}": i * 7 for i in range(size)}
    for node_id in values:
        position = position_from_values(metric="engagement.touch_count_28d", cohort_id="coh_band",
                                        values=values, subject_node_id=node_id, eval_time=AT,
                                        divisions=divisions)
        assert isinstance(position, CohortPosition)
        assert position.band.contains(position.percentile_bp)
        # CHANGED: was `== divisions`, which asserted that a REQUESTED scheme is published
        # verbatim however small the population. It is not, and it must not be: at n <= 10 a
        # requested decile scheme has empty bands at the bottom (n=5 can only ever produce
        # 2000, 4000, 6000, 8000, 10000), so publishing "D3" for the worst of five was a label
        # with nothing in it. The published scheme is the finest the population can EXPRESS.
        assert position.band.divisions == expressible_divisions(size, requested=divisions)
        assert position.p25_bp <= position.p50_bp <= position.p75_bp


def test_the_percentile_is_nearest_rank_and_integer() -> None:
    """Doc 04 L2.4.5 step 3: `rank = count(v <= value); percentile_bp = rank * 10000 // n`."""
    population = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert percentile_bp(population, 10) == 1000
    assert percentile_bp(population, 100) == 10_000
    assert percentile_bp(population, 55) == 5000
    assert all(isinstance(percentile_bp(population, v), int) for v in population)


def test_a_position_replayed_is_byte_identical() -> None:
    """Same population, same subject, same instant -> the same bytes. A comparison engine whose
    output moves between two identical runs cannot be argued with."""
    values = {f"node_{i:02d}": (i * 13) % 47 for i in range(24)}
    first = position_from_values(metric="engagement.touch_count_28d", cohort_id="coh_replay",
                                 values=values, subject_node_id="node_07", eval_time=AT)
    second = position_from_values(metric="engagement.touch_count_28d", cohort_id="coh_replay",
                                  values=dict(reversed(list(values.items()))),
                                  subject_node_id="node_07", eval_time=AT)
    assert isinstance(first, CohortPosition)
    assert first.model_dump_json() == second.model_dump_json()


# =================================================================================================
# U2 — QUARTILE COHORTS, BALANCED BY CONSTRUCTION OR REFUSED
# =================================================================================================

def test_a_quartile_family_is_four_balanced_cohorts() -> None:
    values = numeric_values(_population(24), "account.arr_minor_units")
    family = quartile_cohorts(org_id="org_a", fact="account.arr_minor_units", node_type="company",
                              values=values, eval_time=AT)
    assert isinstance(family, QuartileFamily)
    assert len(family.definitions) == 4
    assert family.boundaries_bp[0] < family.boundaries_bp[1] < family.boundaries_bp[2]
    assert all(d.created_by == SYSTEM_AUTHOR for d in family.definitions)

    # every member lands in exactly one slot, and every slot clears the population floor
    per_slot = [0, 0, 0, 0]
    for value in values.values():
        hits = [i for i, d in enumerate(family.definitions)
                if evaluate(d.predicate, {"account.arr_minor_units": value}, eval_time=AT)]
        assert len(hits) == 1, f"{value} matched {len(hits)} quartiles"
        per_slot[hits[0]] += 1
    assert all(count >= MIN_COHORT_POPULATION for count in per_slot), per_slot


def test_a_quartile_family_below_the_population_floor_is_refused() -> None:
    values = numeric_values(_population(MIN_QUARTILE_POPULATION - 1), "account.arr_minor_units")
    outcome = quartile_cohorts(org_id="org_a", fact="account.arr_minor_units", node_type="company",
                               values=values, eval_time=AT)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.INSUFFICIENT_POPULATION


def test_a_concentrated_population_is_refused_rather_than_cut() -> None:
    """Every account paying the same amount has quartile boundaries that all collapse onto one
    number: one cohort holds everybody and three hold nobody. Four definition rows that can never
    produce a position is worse than none."""
    values = {f"node_{i:02d}": 2_000_000 for i in range(30)}
    outcome = quartile_cohorts(org_id="org_a", fact="account.arr_minor_units", node_type="company",
                               values=values, eval_time=AT)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.DEGENERATE_DISTRIBUTION


def test_a_fact_nobody_registered_as_quartilable_is_refused() -> None:
    with pytest.raises(PredicateError):
        quartile_cohorts(org_id="org_a", fact="account.plan", node_type="company",
                         values={"n": 1}, eval_time=AT)


def test_the_shipped_defaults_exist_before_anybody_authors_anything() -> None:
    """Doc 04 ships five families so value exists on day one. What cannot be cut is REFUSED with
    a reason, not shipped empty — "nobody writes ARR" is the honest answer to "where are my ARR
    cohorts?" and an operator who cannot see it concludes the generator is broken."""
    accounts = _population(24)
    for i, facts in enumerate(accounts.values()):
        facts["deal.stage"] = ("proposing", "negotiating", "won")[i % 3]
    shipped = default_cohorts(org_id="org_a", facts_by_type={"company": accounts}, eval_time=AT)

    names = {d.name for d in shipped.definitions}
    assert "All active accounts" in names
    assert sum(1 for n in names if n.startswith("account.arr_minor_units")) == 4
    assert sum(1 for n in names if n.startswith("node.tenure_days")) == 4
    assert sum(1 for n in names if n.startswith("Deals in stage")) == 3
    assert len(shipped.definitions) <= MAX_COHORTS_PER_ORG
    # `deal.value` is written by nobody in this graph — refused for population, never invented.
    assert any(r.metric == "deal.value" for r in shipped.refusals)
    assert all(isinstance(r, CohortRefusal) for r in shipped.refusals)


def test_the_shipped_defaults_are_stable_across_sweeps() -> None:
    """System cohort ids are per-SLOT, not per-predicate. A quartile family whose boundaries moved
    must rewrite four rows, never append four — that is the difference between a definitions table
    that is bounded and one that grows every week nobody signed up."""
    first = default_cohorts(org_id="org_a", facts_by_type={"company": _population(24)},
                            eval_time=AT)
    moved = _population(24, first=9_000_000, step=250_000)
    second = default_cohorts(org_id="org_a", facts_by_type={"company": moved},
                             eval_time=AT + timedelta(days=7))
    assert [d.cohort_id for d in first.definitions] == [d.cohort_id for d in second.definitions]
    assert (canonical_dumps(first.definitions[1].predicate.as_json())
            != canonical_dumps(second.definitions[1].predicate.as_json())), (
        "the boundaries must actually have moved for this test to mean anything")


# =================================================================================================
# M-9 — PREDICATE AUTHORING. THE ONE MODEL SITE, AND IT NEVER FIRES IN A SWEEP.
# =================================================================================================

def _drafter(predicate: dict, name: str = "Churned mid-market logistics"):
    """A stub in the shape of the model site: it is handed the ask and the VOCABULARY, and it
    returns a predicate. It is never handed a member row — see `DraftBrief`."""
    def _draft(ask, brief):
        assert brief.node_type == "company"
        assert "account.arr_minor_units" in {name for name, _kind, _q in brief.facts}
        assert all(op in brief.operators for op in ("between", "within_days"))
        return {"name": name, "predicate": predicate}
    return _draft


def _m9_world() -> dict[str, dict]:
    world = {f"node_acct_{i:02d}": _account(1_000_000 + 200_000 * i, onboarded_days_ago=20 + i)
             for i in range(9)}
    world["node_acct_acme"] = _account(2_400_000, onboarded_days_ago=40)
    for node_id, facts in world.items():
        facts["node.name"] = "Acme Logistics" if node_id.endswith("acme") else node_id.title()
        facts["account.churned_at"] = (AT - timedelta(days=100)).isoformat()
    world["node_acct_08"]["account.churned_at"] = (AT - timedelta(days=900)).isoformat()
    return world


CHURNED_MID = {"all": [
    {"fact": "account.arr_minor_units", "op": "between", "value": [800_000, 3_000_000]},
    {"fact": "account.churned_at", "op": "within_days", "value": 365},
]}


def test_m9_drafts_a_predicate_with_a_population_preview_and_named_samples() -> None:
    """Doc 04's acceptance: a natural-language ask produces a valid predicate tree, a population
    count and five named samples — and every number in that preview is computed HERE, never by
    the model."""
    world = _m9_world()
    proposal = propose_cohort(org_id="org_a", ask="customers like Acme who churned last year",
                              drafter=_drafter(CHURNED_MID), node_type="company",
                              node_facts=world, eval_time=AT,
                              reference_node_id="node_acct_acme")

    assert proposal.predicate_json == CHURNED_MID
    assert proposal.population_size == sum(
        1 for facts in world.values()
        if evaluate(parse_predicate(CHURNED_MID), facts, eval_time=AT))
    assert 0 < proposal.population_size < len(world)
    assert len(proposal.samples) == PROPOSAL_SAMPLES
    assert any(name == "Acme Logistics" for _node_id, name in proposal.samples)
    assert proposal.reference_node_id == "node_acct_acme"


def test_m9_refuses_a_predicate_that_excludes_the_named_reference() -> None:
    """Doc 04 failure 14. If the founder named Acme and the draft excludes it, the draft
    misunderstood the ask — surface that, do NOT store it."""
    excludes_acme = {"all": [
        {"fact": "account.arr_minor_units", "op": "between", "value": [100_000, 900_000]}]}
    with pytest.raises(ProposalRefused) as raised:
        propose_cohort(org_id="org_a", ask="customers like Acme who churned",
                       drafter=_drafter(excludes_acme), node_type="company",
                       node_facts=_m9_world(), eval_time=AT,
                       reference_node_id="node_acct_acme")
    assert raised.value.reason is ProposalRefusalReason.REFERENCE_NODE_EXCLUDED


def test_m9_refuses_an_unregistered_fact_and_an_empty_population() -> None:
    with pytest.raises(ProposalRefused) as unregistered:
        propose_cohort(org_id="org_a", ask="churned logistics accounts",
                       drafter=_drafter({"all": [{"fact": "account.vertical", "op": "eq",
                                                  "value": "logistics"}]}),
                       node_type="company", node_facts=_m9_world(), eval_time=AT)
    assert unregistered.value.reason is ProposalRefusalReason.UNREGISTERED_FACT

    with pytest.raises(ProposalRefused) as empty:
        propose_cohort(org_id="org_a", ask="accounts paying a billion",
                       drafter=_drafter({"all": [{"fact": "account.arr_minor_units", "op": "gt",
                                                  "value": 10 ** 12}]}),
                       node_type="company", node_facts=_m9_world(), eval_time=AT)
    assert empty.value.reason is ProposalRefusalReason.EMPTY_POPULATION


def test_a_broad_draft_is_warned_about_rather_than_refused() -> None:
    """Doc 04 failure 12 is mitigated by the PREVIEW, not by a refusal: "all my accounts" can be
    exactly what was asked for, and the human decides once they can see the number."""
    everything = {"all": [{"fact": "account.arr_minor_units", "op": "exists"}]}
    proposal = propose_cohort(org_id="org_a", ask="all my customers",
                              drafter=_drafter(everything, name="Everyone"),
                              node_type="company", node_facts=_m9_world(), eval_time=AT)
    assert proposal.population_size == len(_m9_world())
    assert proposal.share_bp == 10_000
    assert any("compares everyone against themselves" in w for w in proposal.warnings)


def test_approval_records_the_human_and_refuses_the_model() -> None:
    """`created_by` is the answer to "who decided this?". The model drafted; the person owns it."""
    proposal = propose_cohort(org_id="org_a", ask="churned mid-market",
                              drafter=_drafter(CHURNED_MID), node_type="company",
                              node_facts=_m9_world(), eval_time=AT)
    definition = approve_proposal(proposal, approved_by="user_priya", eval_time=AT)
    assert definition.created_by == "user_priya" and not definition.system_owned
    assert definition.predicate.as_json() == CHURNED_MID

    for impostor in ("system:default", "m9", "claude", "model:haiku"):
        with pytest.raises(ProposalRefused) as raised:
            approve_proposal(proposal, approved_by=impostor, eval_time=AT)
        assert raised.value.reason is ProposalRefusalReason.NOT_A_HUMAN_AUTHOR


def test_m9_never_fires_inside_a_sweep() -> None:
    """Doc 04 L2.4.4-U4: "T3, on demand only — never in a sweep". Proven off the SOURCE of both
    sides, because this is a failure of ABSENCE: a test that called the sweep and asserted no
    model was used would pass in a build where the drafter had a default."""
    module = ast.parse(_COHORT_SOURCE)
    [sweep_def] = [n for n in module.body
                   if isinstance(n, ast.FunctionDef) and n.name == "refresh_cohorts_for_drain"]
    # The CODE, with the docstring dropped: comments and prose explain why the model is absent,
    # and a test that read them would pass on the explanation rather than on the behaviour.
    body = [n for n in sweep_def.body if not (isinstance(n, ast.Expr)
                                              and isinstance(n.value, ast.Constant))]
    sweep = "\n".join(ast.unparse(n) for n in body)
    for forbidden in ("propose_cohort", "drafter", "llm", "Drafter", "approve_proposal"):
        assert forbidden not in sweep, f"the sweep path names {forbidden}"
    assert "drafter" not in inspect.signature(refresh_cohorts_for_drain).parameters

    runner = (_ENGINE / "context" / "runner.py").read_text()
    assert "refresh_cohorts_for_drain" in runner, "the sweep must reach the cohort pass"
    assert "propose_cohort" not in runner and "llm_predicate_drafter" not in runner


# =================================================================================================
# DOC 04 ROW 5 — NO SQL IS BUILT FROM A PREDICATE, AND NOTHING CLUSTERS
# =================================================================================================

def test_no_statement_interpolates_anything_but_a_table_name() -> None:
    """Doc 04 hard rule 1: NO FREE SQL FROM PREDICATES. The tree is interpreted in Python, and the
    only thing any f-string in this module may carry into SQL is one of three table constants —
    which are module constants, not values from a request."""
    allowed = {"COHORT_DEFINITION_TABLE", "COHORT_MEMBERSHIP_TABLE", "HISTORY_TABLE"}
    tree = ast.parse(_COHORT_SOURCE)
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        literal = "".join(p.value for p in node.values if isinstance(p, ast.Constant))
        if not re.search(r"\b(select|insert|update|delete)\b", literal, re.I):
            continue
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                assert isinstance(part.value, ast.Name) and part.value.id in allowed, (
                    "a statement in cohort.py interpolates something that is not a table "
                    f"constant: {ast.dump(part.value)}")


def test_every_cohort_statement_is_scoped_to_one_tenant() -> None:
    """The isolation law, structurally. A statement that touches either cohort table without an
    `org_id` filter is the whole leak, and it is one forgotten `where` away at all times."""
    for statement in re.findall(r'text\(\s*((?:f?"[^"]*"\s*)+)\)', _COHORT_SOURCE):
        sql = " ".join(re.findall(r'"([^"]*)"', statement))
        if not re.search(r"cohort_membership|cohort_definitions|COHORT_\w+_TABLE|metric_history"
                         r"|HISTORY_TABLE|graph_nodes|graph_facts", sql):
            continue
        if sql.lstrip().lower().startswith("insert"):
            # A write is scoped by the org it WRITES, and by the conflict target it upserts on.
            assert "(org_id," in sql and "values (:o" in sql.replace("  ", " "), sql
            assert "org_id" in sql.split("on conflict", 1)[-1], sql
            continue
        assert "org_id = :o" in sql, sql


def test_nothing_in_the_analytic_tree_clusters() -> None:
    """Law 3, as an import ratchet. "If you find yourself importing sklearn, stop — you are
    building the wrong thing."""
    banned = ("sklearn", "scipy.cluster", "kmeans", "k_means", "dbscan", "agglomerative",
              "hdbscan", "embedding_cluster")
    for path in (_ENGINE / "context" / "analytic").rglob("*.py"):
        source = path.read_text().lower()
        for name in banned:
            assert name not in source, f"{path.name} names {name}"


def test_both_tables_are_named_in_the_tenant_erasure_list() -> None:
    """That loop runs with NO try/except, so a name missing from it does not fail — it leaves a
    deleted tenant's peer-group membership behind, silently, and a name that is WRONG breaks org
    deletion for every tenant."""
    from genios_engine.api import account_routes
    for table in (COHORT_MEMBERSHIP_TABLE, COHORT_DEFINITION_TABLE):
        assert table in account_routes._ORG_SCOPED_TABLES
    order = account_routes._ORG_SCOPED_TABLES
    assert order.index(COHORT_MEMBERSHIP_TABLE) < order.index(COHORT_DEFINITION_TABLE), (
        "membership is deleted before the definition it references")


# =================================================================================================
# REAL POSTGRES — the wiring, the hysteresis, the isolation law, and erasure
# =================================================================================================

def _seed_accounts(store, org: str, *, count: int, at: datetime, prefix: str = "n",
                   plan: str = "growth", first: int = 1_000_000, step: int = 100_000) -> None:
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Cohort tests') "
                          "on conflict (id) do nothing"), {"o": org})
        for i in range(count):
            node_id = f"{prefix}_{i:02d}"
            conn.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name, "
                "  valid_from) values (:n, 1, :o, 'company', :d, :vf) on conflict do nothing"),
                {"n": node_id, "o": org, "d": f"Account {i}", "vf": at - timedelta(days=30 + i)})
            for field, value, kind in (("account.arr_minor_units", first + step * i, "number"),
                                       ("account.plan", f'"{plan}"', "string")):
                raw = value if kind == "string" else str(value)
                conn.execute(text(
                    "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                    "  field, value, value_type, status, occurred_at, valid_from) "
                    "values (:fv, :f, :o, :n, :field, cast(:v as jsonb), :t, 'active', :at, :at) "
                    "on conflict (fact_version_id) do nothing"),
                    {"fv": f"fv_{org}_{node_id}_{field}", "f": f"f_{org}_{node_id}_{field}",
                     "o": org, "n": node_id, "field": field, "v": raw, "t": kind, "at": at})


def _drop_org(store, org: str) -> None:
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    with store.engine.begin() as conn:
        for table in _ORG_SCOPED_TABLES:
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        conn.execute(text("delete from orgs where id=:o"), {"o": org})


@pytest.mark.pg
def test_the_sweep_builds_cohorts_and_membership(pg_store) -> None:
    """`context/runner.process_pending` — the sweep both API routes call — reaches the cohort pass.

    THIS IS THE TEST THAT MATTERS. Every other test in this file constructs the cohort module
    itself and would pass in a build where the call in `runner.py` had been deleted. It is driven
    with no pending events on purpose: a cohort over `node.tenure_days` or `within_days` changes
    because time passed, so the pass must run on a sweep that drained nothing.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_cohort_wiring"
    _drop_org(pg_store, org)
    _seed_accounts(pg_store, org, count=24, at=AT)
    try:
        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=AT)
        assert out["processed"] == 0, "no events: this sweep drained nothing"
        assert out["cohort_changes"] > 0, (
            "the sweep reached no cohort pass — `refresh_cohorts_for_drain` is not on the real "
            "request path")

        with pg_store.engine.connect() as conn:
            definitions = conn.execute(text(
                f"select cohort_id, name, created_by from {COHORT_DEFINITION_TABLE} "
                "where org_id=:o"), {"o": org}).all()
            members = conn.execute(text(
                f"select count(*) from {COHORT_MEMBERSHIP_TABLE} where org_id=:o and "
                "left_at is null"), {"o": org}).scalar()
        assert len(definitions) >= 5 and members > 0
        assert {d.created_by for d in definitions} == {SYSTEM_AUTHOR}
        assert any(d.name.startswith("account.arr_minor_units") for d in definitions)
        # the tenure family proves `load_node_facts` computed `node.tenure_days` off the real
        # node rows and this sweep's instant — it is stored nowhere and cannot be faked upstream
        assert any(d.name.startswith("node.tenure_days") for d in definitions)

        # A second sweep at the same instant is an OVERWRITE, not a second stint.
        before = members
        again = process_pending(org_id=org, store=pg_store, llm=None,
                                crypto_key=get_settings().crypto_key, eval_time=AT)
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                f"select count(*) from {COHORT_MEMBERSHIP_TABLE} where org_id=:o"),
                {"o": org}).scalar()
            definitions_after = conn.execute(text(
                f"select count(*) from {COHORT_DEFINITION_TABLE} where org_id=:o"),
                {"o": org}).scalar()
        assert rows == before, "two sweeps in one period must not double the membership table"
        assert definitions_after == len(definitions), "a regenerated family must rewrite, not add"
        assert again["cohort_changes"] == 0, "a replayed sweep changes nothing"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_a_node_that_fails_once_stays_and_failing_twice_leaves(pg_store) -> None:
    """Doc 04's hysteresis mitigation, on the real table. Without it membership flaps and every
    sweep emits a join/leave pair for a fact that was briefly missing during a re-derive."""
    org = "org_cohort_hysteresis"
    _drop_org(pg_store, org)
    _seed_accounts(pg_store, org, count=8, at=AT)
    try:
        definition = define_cohort(
            org_id=org, name="Growth plan", node_type="company",
            predicate={"all": [{"fact": "account.plan", "op": "eq", "value": "growth"}]},
            created_by="user_priya", eval_time=AT)
        save_definitions(pg_store.engine, [definition])

        facts = load_node_facts(pg_store.engine, org, node_types=("company",),
                                eval_time=AT)["company"]
        joined = refresh_membership(pg_store, definition, eval_time=AT, node_facts=facts)
        assert len(joined.joined) == 8 and joined.left == ()

        # the fact goes missing on one node: FIRST failure
        leaving = dict(facts)
        leaving["n_03"] = {k: v for k, v in facts["n_03"].items() if k != "account.plan"}
        first = refresh_membership(pg_store, definition, eval_time=AT + timedelta(days=1),
                                   node_facts=leaving)
        assert first.left == (), "one failure must not remove a member"
        with pg_store.engine.connect() as conn:
            row = conn.execute(text(
                f"select left_at, miss_streak from {COHORT_MEMBERSHIP_TABLE} "
                "where org_id=:o and node_id='n_03'"), {"o": org}).first()
        assert row.left_at is None and row.miss_streak == 1

        # a REPLAY of that same evaluation must not advance the streak
        replay = refresh_membership(pg_store, definition, eval_time=AT + timedelta(days=1),
                                    node_facts=leaving)
        assert replay.left == ()
        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                f"select miss_streak from {COHORT_MEMBERSHIP_TABLE} where org_id=:o and "
                "node_id='n_03'"), {"o": org}).scalar() == 1, (
                "a sweep replayed at one instant walked a node closer to leaving")

        # SECOND consecutive failure: it leaves, with left_at set and the row kept
        second = refresh_membership(pg_store, definition, eval_time=AT + timedelta(days=2),
                                    node_facts=leaving)
        assert second.left == ("n_03",) and MISSES_BEFORE_LEAVING == 2
        with pg_store.engine.connect() as conn:
            row = conn.execute(text(
                f"select left_at, joined_at from {COHORT_MEMBERSHIP_TABLE} "
                "where org_id=:o and node_id='n_03'"), {"o": org}).first()
        assert row is not None, "membership is HISTORICAL — the row is closed, never deleted"
        assert row.left_at == AT + timedelta(days=2)

        # and the departure is readable as a change event
        events = membership_changes(pg_store, org, since=AT + timedelta(days=1),
                                    until=AT + timedelta(days=3))
        assert [(e.kind, e.node_id) for e in events] == [(CohortEventKind.LEFT, "n_03")]

        # a node that comes back before the streak reaches two keeps its membership
        recovered = refresh_membership(pg_store, definition, eval_time=AT + timedelta(days=3),
                                       node_facts=facts)
        assert "n_03" in recovered.joined, "a returning node re-joins with a new stint"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_write_budget_caps_one_sweep_and_the_next_one_finishes_the_work(pg_store) -> None:
    """The per-sweep membership budget, and the reason it is safe: membership is STATE, not a
    queue, so work the budget refused is done by the next sweep rather than lost.

    A 50k-node org's first pass would otherwise be a single transaction touching a row per node
    per cohort, which is the write-amplification shape that put this database into read-only once
    already.
    """
    from genios_engine.context.analytic.cohort import WriteBudget

    org = "org_cohort_budget"
    _drop_org(pg_store, org)
    _seed_accounts(pg_store, org, count=8, at=AT)
    try:
        definition = define_cohort(
            org_id=org, name="Growth plan", node_type="company",
            predicate={"all": [{"fact": "account.plan", "op": "eq", "value": "growth"}]},
            created_by="user_priya", eval_time=AT)
        save_definitions(pg_store.engine, [definition])

        capped = refresh_membership(pg_store, definition, eval_time=AT, budget=WriteBudget(3))
        assert len(capped.joined) == 3 and capped.budget_exhausted is True
        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                f"select count(*) from {COHORT_MEMBERSHIP_TABLE} where org_id=:o"),
                {"o": org}).scalar() == 3

        finished = refresh_membership(pg_store, definition, eval_time=AT)
        assert len(finished.joined) == 5 and finished.budget_exhausted is False
        assert finished.population_size == 8
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_one_tenants_numbers_never_reach_another_tenants_position(pg_store) -> None:
    """THE ISOLATION LAW. A cohort spans subjects, and it must never span tenants.

    The adversarial shape is built deliberately: org B is given membership rows and metric history
    rows that name ORG A'S NODE IDS AND ORG A'S COHORT ID. `graph_nodes` will not hold the same
    node twice — its primary key is `(node_id, version)` with no org — but `cohort_membership` and
    `metric_history` are both keyed with `org_id` FIRST, so those rows are perfectly constructible
    and they are exactly what a single forgotten `where org_id = :o` would sweep up. Org B's
    readings are three orders of magnitude away from org A's, so if any statement on this path
    dropped its tenant filter the population, the percentile and all three quartiles would move.
    """
    from genios_engine.contracts.analytic import MetricPoint, MetricUnit
    from genios_engine.context.analytic.history import (MetricGrain, PostgresMetricHistory,
                                                        SampleReason, period_start)

    a, b = "org_cohort_iso_a", "org_cohort_iso_b"
    metric = "engagement.touch_count"   # a name `history.CORE_METRICS` registers
    period = period_start(AT, MetricGrain.MONTH)
    for org in (a, b):
        _drop_org(pg_store, org)
    _seed_accounts(pg_store, a, count=8, at=AT, prefix="shared")
    _seed_accounts(pg_store, b, count=8, at=AT, prefix="tenant_b")
    with pg_store.engine.begin() as conn:
        conn.execute(text("update graph_nodes set display_name = 'SECRET OTHER TENANT' "
                          "where org_id = :o"), {"o": b})
    history = PostgresMetricHistory(pg_store.engine)
    try:
        definitions = {}
        for org, prefix, base in ((a, "shared", 10), (b, "tenant_b", 9_000)):
            history.put(org, [MetricPoint(subject_node_id=f"{prefix}_{i:02d}", metric=metric,
                                          value_bp=base + i, unit=MetricUnit.COUNT,
                                          observed_at=period, known=True, coverage_ready=True)
                              for i in range(8)],
                        reason=SampleReason.SCHEDULED, sampled_at=AT)
            definition = define_cohort(
                org_id=org, name="Growth plan", node_type="company",
                predicate={"all": [{"fact": "account.plan", "op": "eq", "value": "growth"}]},
                created_by="user_priya", eval_time=AT)
            save_definitions(pg_store.engine, [definition])
            refresh_membership(pg_store, definition, eval_time=AT)
            definitions[org] = definition

        # THE TRAP: org B claims org A's cohort id and org A's node ids, with its own numbers.
        with pg_store.engine.begin() as conn:
            for i in range(8):
                conn.execute(text(
                    f"insert into {COHORT_MEMBERSHIP_TABLE} "
                    "  (org_id, cohort_id, node_id, joined_at, miss_streak) "
                    "values (:o, :c, :n, :at, 0) on conflict do nothing"),
                    {"o": b, "c": definitions[a].cohort_id, "n": f"shared_{i:02d}", "at": AT})
            history.put(b, [MetricPoint(subject_node_id=f"shared_{i:02d}", metric=metric,
                                        value_bp=900_000 + i, unit=MetricUnit.COUNT,
                                        observed_at=period, known=True, coverage_ready=True)
                            for i in range(8)],
                        reason=SampleReason.SCHEDULED, sampled_at=AT)

        position = position_in_cohort(pg_store, org_id=a, cohort_id=definitions[a].cohort_id,
                                      metric=metric, subject_node_id="shared_07", eval_time=AT)

        assert isinstance(position, CohortPosition)
        assert position.population_size == 8, "org B's eight rows must not be in the population"
        assert position.p25_bp < 100 and position.p75_bp < 100, (
            "the distribution is org A's, in org A's magnitudes")
        assert position.percentile_bp == 10_000

        rendered = position.model_dump_json()
        for leaked in ("SECRET OTHER TENANT", definitions[b].cohort_id, b, "9000", "900000",
                       "shared_07", "tenant_b"):
            assert leaked not in rendered, f"{leaked!r} reached another tenant's position"

        # one tenant cannot position against another's cohort, even naming it exactly
        across = position_in_cohort(pg_store, org_id=a, cohort_id=definitions[b].cohort_id,
                                    metric=metric, subject_node_id="shared_07", eval_time=AT)
        assert isinstance(across, CohortRefusal)
        assert across.reason is CohortRefusalReason.NO_SUCH_COHORT

        # and the WRITE path is scoped too: org A's refresh leaves org B's rows exactly as they
        # were, including the eight it planted under org A's cohort id.
        refresh_membership(pg_store, definitions[a], eval_time=AT + timedelta(days=1))
        with pg_store.engine.connect() as conn:
            per_org = dict(conn.execute(text(
                f"select org_id, count(*) from {COHORT_MEMBERSHIP_TABLE} "
                "where org_id = any(:orgs) and left_at is null group by org_id"),
                {"orgs": [a, b]}).all())
        assert per_org == {a: 8, b: 16}, (
            "org A's refresh must neither adopt nor close org B's rows")
    finally:
        for org in (a, b):
            _drop_org(pg_store, org)


@pytest.mark.pg
def test_deleting_an_org_erases_its_cohorts(pg_store) -> None:
    """Erasure proven on the real schema, both ways: the /reset loop (the org-scoped list, which
    runs with no try/except) and the org cascade that account deletion relies on."""
    org = "org_cohort_erasure"
    _drop_org(pg_store, org)
    _seed_accounts(pg_store, org, count=6, at=AT)
    try:
        definition = define_cohort(
            org_id=org, name="Growth plan", node_type="company",
            predicate={"all": [{"fact": "account.plan", "op": "eq", "value": "growth"}]},
            created_by="user_priya", eval_time=AT)
        save_definitions(pg_store.engine, [definition])
        refresh_membership(pg_store, definition, eval_time=AT)
        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                f"select count(*) from {COHORT_MEMBERSHIP_TABLE} where org_id=:o"),
                {"o": org}).scalar() == 6

        # delete the ORG — the cascade alone must take both tables with it
        with pg_store.engine.begin() as conn:
            conn.execute(text("delete from graph_facts where org_id=:o"), {"o": org})
            conn.execute(text("delete from graph_nodes where org_id=:o"), {"o": org})
            conn.execute(text("delete from orgs where id=:o"), {"o": org})
        with pg_store.engine.connect() as conn:
            for table in (COHORT_MEMBERSHIP_TABLE, COHORT_DEFINITION_TABLE):
                assert conn.execute(text(f"select count(*) from {table} where org_id=:o"),
                                    {"o": org}).scalar() == 0, f"{table} survived org deletion"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_retention_prunes_closed_stints_and_keeps_open_membership(pg_store) -> None:
    """The append side is bounded on the drain path. OPEN membership is never pruned: a node that
    has been in a cohort for three years is one row, and deleting it would delete the cohort."""
    org = "org_cohort_retention"
    _drop_org(pg_store, org)
    _seed_accounts(pg_store, org, count=6, at=AT)
    try:
        definition = define_cohort(
            org_id=org, name="Growth plan", node_type="company",
            predicate={"all": [{"fact": "account.plan", "op": "eq", "value": "growth"}]},
            created_by="user_priya", eval_time=AT)
        save_definitions(pg_store.engine, [definition])
        refresh_membership(pg_store, definition, eval_time=AT)
        ancient = AT - timedelta(days=30 * (MEMBERSHIP_RETENTION_MONTHS + 2))
        with pg_store.engine.begin() as conn:
            conn.execute(text(
                f"update {COHORT_MEMBERSHIP_TABLE} set left_at = :old "
                "where org_id=:o and node_id in ('n_00','n_01')"), {"o": org, "old": ancient})

        pruned = prune_membership(pg_store, org, eval_time=AT)
        assert pruned == 2
        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                f"select count(*) from {COHORT_MEMBERSHIP_TABLE} where org_id=:o"),
                {"o": org}).scalar() == 4
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_authoring_route_stores_the_human_never_the_model(pg_store) -> None:
    """M-9's real request path: `POST /api/org/{org}/cohorts/propose` then `POST .../cohorts`.

    Driven through the route functions themselves — the same entry points FastAPI calls — with a
    stub in place of the model client, because what is being proven here is the WIRING and the
    ownership rule, not the model's drafting.
    """
    from genios_engine.api import cohort_routes as R
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.auth import AuthCtx

    org = "org_cohort_routes"
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    previous = R._graph
    R._graph = GraphStore(url)
    _drop_org(pg_store, org)
    _seed_accounts(pg_store, org, count=8, at=AT)
    ctx = AuthCtx(org_id=org, actor_id="user_priya")

    class _Result:
        ok = True
        parsed = {"name": "Growth plan accounts",
                  "predicate": {"all": [{"fact": "account.plan", "op": "eq", "value": "growth"}]}}

    class _Model:
        def call(self, prompt: str, *, max_tokens: int = 1024):
            assert "account.plan" in prompt and "Do NOT estimate how many records match" in prompt
            return _Result()

    R.make_llm_client = lambda: _Model()                      # the one model site, stubbed
    try:
        preview = R.propose(org, R.ProposeCohort(ask="accounts on the growth plan",
                                                 node_type="company"), org=org, ctx=ctx)
        assert preview["population_size"] == 8
        assert len(preview["samples"]) == 5 and preview["samples"][0]["name"].startswith("Account")

        stored = R.author_cohort(org, R.AuthorCohort(name=preview["name"],
                                                     node_type="company",
                                                     predicate=preview["predicate"]),
                                 org=org, ctx=ctx)
        assert stored["created_by"] == "user_priya", "the human owns what the model drafted"

        listed = R.list_cohorts(org, org=org)
        assert [c["cohort_id"] for c in listed["cohorts"]] == [stored["cohort_id"]]
        assert listed["cohorts"][0]["population_size"] == 0, (
            "authoring declares a cohort; the sweep populates it")

        # an unregistered fact is a 422 on the request that wrote it, not an empty cohort later
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as bad:
            R.author_cohort(org, R.AuthorCohort(name="typo", node_type="company",
                                                predicate={"all": [{"fact": "account.arr",
                                                                    "op": "gt", "value": 1}]}),
                            org=org, ctx=ctx)
        assert bad.value.status_code == 422

        # the definition ceiling: the one path a client can grow `cohort_definitions` from
        R.MAX_COHORTS_PER_ORG = 1
        with pytest.raises(HTTPException) as capped:
            R.author_cohort(org, R.AuthorCohort(name="one too many", node_type="company",
                                                predicate={"all": [{"fact": "account.plan",
                                                                    "op": "exists"}]}),
                            org=org, ctx=ctx)
        assert capped.value.status_code == 409
        R.MAX_COHORTS_PER_ORG = MAX_COHORTS_PER_ORG

        # a credential with no person cannot author one
        with pytest.raises(HTTPException) as anonymous:
            R.author_cohort(org, R.AuthorCohort(name="x", node_type="company",
                                                predicate={"all": [{"fact": "account.plan",
                                                                    "op": "exists"}]}),
                            org=org, ctx=AuthCtx(org_id=org, actor_id=None))
        assert anonymous.value.status_code == 403
    finally:
        _drop_org(pg_store, org)
        R._graph = previous
        R.MAX_COHORTS_PER_ORG = MAX_COHORTS_PER_ORG


# =================================================================================================
# U3's READER ON THE SURFACE — `membership_changes` had no production caller
# =================================================================================================

@pytest.mark.pg
def test_the_changes_route_reaches_the_membership_reader(pg_store) -> None:
    """`GET /api/org/{org}/cohorts/changes` through the app, on real rows.

    WHAT THIS UNIT IS FOR. Doc 04 L2.4.4-U3 exists to make *"three accounts dropped out of your
    healthy-engagement cohort this month"* sayable. `membership_changes` computed exactly that and
    nothing called it, so the transitions were recorded in the table and invisible in the product
    — the same shape as the six Layer 1 units that shipped green and unreachable.

    Driven through the ROUTER, not through the function: every other assertion about this reader
    constructs it directly and would pass in a build where `main.py` never included the route.
    """
    from fastapi.testclient import TestClient

    from genios_engine.api import cohort_routes as R
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.main import app
    from genios_engine.platform.auth import get_current_org

    org, other = "org_changes_route", "org_changes_route_other"
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    previous = R._graph
    R._graph = GraphStore(url)
    app.dependency_overrides[get_current_org] = lambda: org
    _drop_org(pg_store, org)
    _drop_org(pg_store, other)
    try:
        # Seeded relative to the REAL clock, not to `AT`. This route answers "the last N days"
        # and reads its instant at the request boundary, which is where a clock belongs; a test
        # pinned to a fixed date would be asserting against a window that has long since moved.
        now = datetime.now(timezone.utc)
        joined_at = now - timedelta(days=10)
        left_at = now - timedelta(days=3)
        with pg_store.engine.begin() as conn:
            for tenant in (org, other):
                conn.execute(text("insert into orgs (id, name) values (:o, :o) "
                                  "on conflict (id) do nothing"), {"o": tenant})
                conn.execute(text(
                    "insert into cohort_definitions (cohort_id, org_id, name, node_type, "
                    "  predicate, created_by, created_at) "
                    "values (:c, :o, 'healthy engagement', 'company', "
                    "  cast('{\"all\": []}' as jsonb), 'test', :at) "
                    "on conflict (cohort_id) do nothing"),
                    {"c": f"coh_{tenant}", "o": tenant, "at": joined_at})
            # this tenant: one node still in, three that left inside the window
            for i in range(4):
                conn.execute(text(
                    "insert into cohort_membership (org_id, cohort_id, node_id, joined_at, "
                    "  left_at) values (:o, :c, :n, :j, :l)"),
                    {"o": org, "c": f"coh_{org}", "n": f"node_ch_{i}", "j": joined_at,
                     "l": None if i == 0 else left_at})
            # the OTHER tenant's churn, in the same window
            conn.execute(text(
                "insert into cohort_membership (org_id, cohort_id, node_id, joined_at, left_at) "
                "values (:o, :c, 'node_other_secret', :j, :l)"),
                {"o": other, "c": f"coh_{other}", "j": joined_at, "l": left_at})

        client = TestClient(app)
        response = client.get(f"/api/org/{org}/cohorts/changes", params={"days": 30})
        assert response.status_code == 200, response.text
        body = response.json()

        # THE SENTENCE THE UNIT EXISTS FOR: three left, four joined.
        assert body["left"] == 3, (
            "the route reached no membership reader — the transitions the table recorded are "
            "invisible in the product")
        assert body["joined"] == 4
        assert len(body["events"]) == 7
        assert {e["kind"] for e in body["events"]} == {"joined_cohort", "left_cohort"}

        # ONE TENANT. The other org's churn is in the same window and must not appear.
        assert "node_other_secret" not in response.text
        assert f"coh_{other}" not in response.text
        assert all(e["cohort_id"] == f"coh_{org}" for e in body["events"])

        # A WINDOW THAT EXCLUDES THE CHURN EXCLUDES IT — the reader is not returning everything.
        narrow = client.get(f"/api/org/{org}/cohorts/changes", params={"days": 2}).json()
        assert narrow["left"] == 0 and narrow["joined"] == 0 and narrow["events"] == []

        # REFUSALS, not a silent answer over a table that has been pruned.
        assert client.get(f"/api/org/{org}/cohorts/changes",
                          params={"days": 400}).status_code == 400
        assert client.get(f"/api/org/{org}/cohorts/changes",
                          params={"days": 0}).status_code == 400
        assert client.get(f"/api/org/{other}/cohorts/changes").status_code == 403, (
            "the path org must match the credential")
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        _drop_org(pg_store, org)
        _drop_org(pg_store, other)
        R._graph = previous
