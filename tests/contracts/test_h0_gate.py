"""GATE H0 · the independent verification pass over the Layer 2 v2 contracts.

`tests/contracts/test_l2_contracts.py` is X0's own suite: it proves each of the nine types
refuses its own invariant violations and that `validate_situation` rejects a
`model_construct`-bypassed object for each of V-1..V-8. This file is the SECOND pair of eyes,
and it deliberately does not repeat any of that. It asks the four questions X0's suite could
not ask about itself:

1. **The gate is written for objects that skipped a constructor — so what shape do those
   actually arrive in?** X0's bypass fixtures pass Python-native values (`is_causal=True`,
   `known=False`, `direction=TrendDirection.DECLINING`). A row rehydrated out of
   `context_situations` jsonb does not: psycopg hands back `1` for a jsonb `1` and the plain
   string `"declining"` for a direction. Three laws read those values with `is`/`.value` and
   were wrong on every one of them — V-7 ADMITTED a causal claim, V-3 ADMITTED an interpolated
   point, and V-5 raised `AttributeError` out of a function whose contract is to return a
   decision. The table below is the wire form of every flag the gate branches on.

2. **Park versus reject versus downgrade.** L1 and L2 both number their rules V-1 and V-5, and
   the two layers give those ids OPPOSITE actions: L1's V-1 parks and its V-5 downgrades-and-
   emits, while doc 08 gives all eight L2 laws REJECT. Getting a failure action backwards does
   not fail loudly — it silently changes what reaches Layer 3 — so the two tables are asserted
   against each other in one place, together with the structural fact that makes the L2 side
   unable to drift: there is no park and no downgrade to drift INTO.

3. **Does `contracts/` import anything above itself at RUNTIME?** `test_layer_topology.py`
   answers this by parsing import statements. That is the right check and it is not the whole
   check: a deferred import inside a function body is a real edge that no top-of-file AST walk
   sees. This asks the interpreter instead.

4. **Do the seventeen Layer 2 placeholders SKIP, with a reason that names the wave?** A gate
   command that dies on "file or directory not found" is the same red as a broken gate. This
   runs the placeholder tree and reads the reasons back.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from genios_engine.contracts.analytic import (Anomaly, AnomalyDirection, CohortBand,
                                              CohortPosition, CorrelationStrength,
                                              MetricCorrelation, MetricPoint, MetricUnit, Trend,
                                              TrendDirection)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.publication import (NON_BLOCKING_RULES, PARKING_RULES,
                                                 PublicationOutcome, PublicationRule)
from genios_engine.contracts.quality import AbsenceType, MissingFact
from genios_engine.contracts.situation import (LAW_ACTIONS, BusinessSituationObject,
                                               ConfidenceVector, ImportanceAttribution,
                                               ImportanceBasis, L2Law, LawAction,
                                               SituationDecision, SituationOutcome,
                                               validate_situation)
from genios_engine.contracts.visibility import Visibility

_ROOT = Path(__file__).resolve().parents[2]
#: Where the Layer 2 placeholders live. One tree, so the count below is read rather than typed.
_PLACEHOLDER_ROOT = _ROOT / "tests" / "context"

#: The same frozen instant `tests/context/conftest.py` uses. Restated rather than imported
#: because that module is the context tree's fixture home and this file is in `tests/contracts/`;
#: nothing here depends on the two being equal, only on neither being a clock.
EVAL_TIME = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)

_QUOTE = "Finance confirmed the renewal lands on the 30th."
_SPAN = EvidenceSpan(source_ref="prepared_content:evt_h0", quote=_QUOTE,
                     start_offset=0, end_offset=len(_QUOTE), verified=True)


def _point(**overrides: Any) -> MetricPoint:
    """A metric point as a jsonb row rehydrates one — `model_construct`, so the wire values
    below reach the gate exactly as psycopg hands them over."""
    base: dict[str, Any] = dict(subject_node_id="node_acc_42", metric="account.reply_count",
                                value_bp=42, unit=MetricUnit.COUNT,
                                currency=None, observed_at=EVAL_TIME, known=True,
                                coverage_ready=True)
    base.update(overrides)
    return MetricPoint.model_construct(**base)


def _trend(**overrides: Any) -> Trend:
    base: dict[str, Any] = dict(
        metric="account.reply_count", direction=TrendDirection.DECLINING, relative_slope_bp=-1_200,
        streak_periods=6, point_count=6, coverage_ratio_bp=10_000, trend_confidence_bp=6_400,
        evidence_points=(_point(value_bp=60), _point(value_bp=44), _point(value_bp=21),
                         _point(value_bp=12)))
    base.update(overrides)
    return Trend.model_construct(**base)


def _correlation(**overrides: Any) -> MetricCorrelation:
    base: dict[str, Any] = dict(
        metric_a="account.reply_count", metric_b="account.meeting_count",
        cohort_id="all_active_accounts", rho_bp=6_200, strength=CorrelationStrength.MODERATE,
        n=24, is_causal=False)
    base.update(overrides)
    return MetricCorrelation.model_construct(**base)


def _cohort(**overrides: Any) -> CohortPosition:
    base: dict[str, Any] = dict(
        metric="account.reply_count", cohort_id="accounts_by_arr_quartile:q4", population_size=37,
        percentile_bp=800, band=CohortBand.D1, p25_bp=12, p50_bp=40, p75_bp=95,
        computed_at=EVAL_TIME)
    base.update(overrides)
    return CohortPosition.model_construct(**base)


#: A situation that is legal in every lane the gate reads, so a rejection in the tables below is
#: attributable to the one field the row changed and to nothing else.
_CLEAN = BusinessSituationObject(
    org_id="org_7173", trace_id="trace_h0", visibility=Visibility(), id="sit_h0",
    type="renewal_at_risk", state="active", signal_ids=("sig_h0",), evidence=(_SPAN,),
    coverage_ready=True,
    confidence=ConfidenceVector(evidence_bp=6_400, overall_bp=6_400, composed_from=("evidence",)),
    importance=ImportanceAttribution(basis=ImportanceBasis.COMPOSED, score_bp=7_400,
                                     base_bp=7_000, version="blg18.v1",
                                     components={"base_bp": 7_000, "trend_bp": 400}))


def bypassed(**overrides: Any) -> BusinessSituationObject:
    """A situation that did NOT go through its constructor, carrying the overridden lanes.

    Built field-by-field off `_CLEAN` rather than by re-validating, because pydantic re-runs a
    nested model's validators when it is assigned through the real constructor — which means a
    situation built the normal way can never carry an illegal sub-object, and a test that built
    one that way would be testing the constructor a second time instead of the gate.
    """
    fields = {name: getattr(_CLEAN, name) for name in BusinessSituationObject.model_fields}
    fields.update(overrides)
    return BusinessSituationObject.model_construct(**fields)


# ================================================== 1 · the shapes a jsonb row hands back

#: `(id, build, expected laws)`. Every row is a value that `context_situations`' jsonb columns
#: really produce, run through the gate. The controls matter as much as the failures: a rule
#: rewritten from `is True` to truthiness must still ADMIT the honest shapes, or V-3 starts
#: rejecting every legitimately measured point that arrived as a jsonb `1`.
REHYDRATED = [
    ("v7-int-one", lambda: bypassed(correlations=(_correlation(is_causal=1),)), [L2Law.V7]),
    ("v7-string-true", lambda: bypassed(correlations=(_correlation(is_causal="true"),)),
     [L2Law.V7]),
    ("v7-python-true", lambda: bypassed(correlations=(_correlation(is_causal=True),)), [L2Law.V7]),
    ("v7-int-zero-admits", lambda: bypassed(correlations=(_correlation(is_causal=0),)), []),
    ("v7-false-admits", lambda: bypassed(correlations=(_correlation(is_causal=False),)), []),
    ("v3-int-zero-with-a-value",
     lambda: bypassed(trends=(_trend(evidence_points=(_point(known=0, value_bp=4_200),)),)),
     [L2Law.V3]),
    ("v3-null-known-with-a-value",
     lambda: bypassed(trends=(_trend(evidence_points=(_point(known=None, value_bp=4_200),)),)),
     [L2Law.V3]),
    ("v3-int-one-with-a-value-admits",
     lambda: bypassed(trends=(_trend(evidence_points=(_point(known=1, value_bp=4_200),)),)), []),
    ("v3-honest-gap-admits",
     lambda: bypassed(trends=(_trend(evidence_points=(_point(known=0, value_bp=None),)),)), []),
    ("v5-string-direction-on-two-points",
     lambda: bypassed(trends=(_trend(direction="declining", point_count=2),)), [L2Law.V5]),
    ("v5-string-direction-on-six-points-admits",
     lambda: bypassed(trends=(_trend(direction="rising", relative_slope_bp=1_200),)), []),
    ("v5-string-refusal-on-two-points-admits",
     lambda: bypassed(trends=(_trend(direction="insufficient_coverage", point_count=2),)), []),
]


@pytest.mark.parametrize("build,expected", [(row[1], row[2]) for row in REHYDRATED],
                         ids=[row[0] for row in REHYDRATED])
def test_the_gate_reads_the_wire_form_of_every_flag_it_branches_on(build, expected):
    """The gate exists for objects that skipped a constructor. This is what those look like.

    A jsonb `1` is not `True` under `is`, and a jsonb `"declining"` has no `.value`. Reading
    them as X0's first cut did admitted a causal claim past V-7 and a fabricated observation
    past V-3 — the two laws whose stated purpose is that no downstream layer can receive those
    — and crashed V-5 instead of returning a decision.
    """
    decision = validate_situation(build())
    assert [failure.law for failure in decision.failures] == expected
    if expected:
        assert decision.outcome is SituationOutcome.REJECT
        assert decision.situation is None, "a rejected situation must not be reachable"
        assert all(failure.detail for failure in decision.failures)
    else:
        assert decision.outcome is SituationOutcome.ADMIT
        assert decision.situation is not None


#: Every lane whose enum reaches the gate as a bare string when a row is rehydrated by hand.
#: The assertion is not about the verdict — it is that the gate RETURNS one. A gate that raises
#: leaves the caller's rejection-ledger row unwritten, and the failure surfaces as a crash in
#: the layer above rather than as a situation that broke a law.
RAW_STRING_LANES = [
    ("trend-direction", lambda: bypassed(trends=(_trend(direction="flat"),))),
    ("trend-refusal", lambda: bypassed(trends=(_trend(direction="insufficient_history"),))),
    ("trend-nonsense", lambda: bypassed(trends=(_trend(direction="sideways"),))),
    ("point-unit", lambda: bypassed(trends=(_trend(evidence_points=(_point(unit="count"),)),))),
    ("cohort-band", lambda: bypassed(cohort_positions=(_cohort(band="D1"),))),
    ("correlation-strength",
     lambda: bypassed(correlations=(_correlation(strength="moderate"),))),
    ("absence-type", lambda: bypassed(missing_facts=(MissingFact.model_construct(
        subject_node_id="node_991", expected_fact="contract.owner_node_id",
        absence_type="genuinely_absent", coverage_ready=True, coverage_basis=("gmail",)),))),
    ("anomaly-direction", lambda: bypassed(anomalies=(Anomaly.model_construct(
        metric="account.reply_count", current_bp=12, baseline_bp=60, mad_bp=8, deviation_bp=48,
        z_like_bp=60_000, direction="below", periods_used=9),))),
]


@pytest.mark.parametrize("build", [row[1] for row in RAW_STRING_LANES],
                         ids=[row[0] for row in RAW_STRING_LANES])
def test_the_gate_returns_a_decision_rather_than_raising_on_a_rehydrated_row(build):
    decision = validate_situation(build())
    assert isinstance(decision, SituationDecision)
    assert decision.outcome in (SituationOutcome.ADMIT, SituationOutcome.REJECT)


# ================================================== 2 · park versus reject versus downgrade

def test_layer_one_and_layer_two_give_the_same_rule_ids_opposite_actions():
    """L1's V-1 PARKS and its V-5 DOWNGRADES; L2's V-1 and V-5 both REJECT.

    Both layers number their rules from V-1 and doc 08's L2 table is uniform where L1's is not.
    An L2 validator that parked where the doc says reject would leave a situation in a
    reviewable limbo Layer 3 never reads; one that downgraded would publish a contested claim
    with a caveat nobody reads. Asserted against both tables in one place so the difference is
    a fact somebody has to edit rather than a comment somebody has to notice.
    """
    assert PARKING_RULES == frozenset({PublicationRule.V1})
    assert NON_BLOCKING_RULES == frozenset({PublicationRule.V5})
    assert LAW_ACTIONS[L2Law.V1] is LawAction.REJECT
    assert LAW_ACTIONS[L2Law.V5] is LawAction.REJECT
    assert set(LAW_ACTIONS) == set(L2Law) and len(L2Law) == 8
    assert set(LAW_ACTIONS.values()) == {LawAction.REJECT}


def test_the_layer_two_gate_has_no_park_and_no_downgrade_to_drift_into():
    """The structural half. L1's `PublicationOutcome` has three members and its decision carries
    a `parked` record and a `confidence_downgrade_bp`; L2's has two and carries neither, so a
    later edit cannot quietly turn a reject into a park without adding the machinery first."""
    assert {member.value for member in LawAction} == {"reject"}
    assert {member.value for member in SituationOutcome} == {"admit", "reject"}
    assert "park" in {member.value for member in PublicationOutcome}
    assert set(SituationDecision.model_fields) == {"outcome", "failures", "situation"}


@pytest.mark.parametrize("law,build", [
    (L2Law.V1, lambda: bypassed(cohort_positions=(_cohort(cohort_id=""),))),
    (L2Law.V5, lambda: bypassed(trends=(_trend(point_count=2),))),
], ids=["V-1-does-not-park", "V-5-does-not-downgrade"])
def test_the_two_laws_whose_l1_namesakes_do_something_else_still_reject(law, build):
    """The behavioural half: the object is DROPPED, not parked and not emitted-with-a-caveat."""
    decision = validate_situation(build())
    assert decision.outcome is SituationOutcome.REJECT
    assert decision.admitted is False
    assert decision.situation is None
    assert [failure.action for failure in decision.failures] == [LawAction.REJECT]
    assert [failure.law for failure in decision.failures] == [law]


# ============================================== 3 · contracts/ imports nothing above itself

def test_contracts_pull_in_no_upper_package_at_runtime():
    """Ask the interpreter, not the AST.

    `test_layer_topology.py` walks import statements, which is the right ratchet and misses one
    real edge: an import inside a function body executes and is invisible at the top of the
    file. A fresh interpreter that imports every module in `contracts/` and then reads
    `sys.modules` cannot miss it. Run out of process so the packages this test session already
    imported for other reasons are not mistaken for contracts' own dependencies.
    """
    probe = (
        "import importlib, json, pkgutil, sys\n"
        "import genios_engine.contracts as c\n"
        "for m in pkgutil.iter_modules(c.__path__):\n"
        "    importlib.import_module('genios_engine.contracts.' + m.name)\n"
        "loaded = [k.split('.') for k in sys.modules if k.startswith('genios_engine.')]\n"
        "print(json.dumps(sorted({parts[1] for parts in loaded if len(parts) > 1})))\n")
    result = subprocess.run([sys.executable, "-c", probe], cwd=_ROOT, capture_output=True,
                            text=True, timeout=180)
    assert result.returncode == 0, result.stderr
    pulled = set(json.loads(result.stdout.strip().splitlines()[-1]))
    assert pulled <= {"contracts", "platform"}, (
        f"importing contracts/ pulled in {sorted(pulled - {'contracts', 'platform'})} — the "
        "boundary vocabulary may depend on platform and stdlib only, or every layer that "
        "imports a contract inherits the layer above it")


# ==================================================== 4 · the Layer 2 placeholders SKIP

#: Doc 09 states its gates as COMMANDS. A command whose path does not exist dies with pytest's
#: usage error, which is the same red as a genuinely broken gate — so the tree carries one
#: placeholder per pending gate. `l2_pending` must SKIP each of them with a reason that names
#: the wave (X0-X8) and the gate (H0-H8), or "17 skipped" is a number nobody can act on.
_SKIP_REASON = re.compile(r"(H[0-8]) pending — (X[0-8]) has not landed \((.+)\)")


def test_every_layer_two_placeholder_skips_with_its_wave_and_gate_named():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/context", "-q", "-rs", "-p", "no:cacheprovider",
         "-p", "no:randomly"],
        cwd=_ROOT, capture_output=True, text=True, timeout=600,
        env={**os.environ, "PYTEST_ADDOPTS": ""})
    assert result.returncode == 0, f"the placeholder tree is not green:\n{result.stdout[-4000:]}"
    reasons = [_SKIP_REASON.search(line) for line in result.stdout.splitlines()
               if line.startswith("SKIPPED")]
    #: `all(reasons)` and NOT `reasons and all(reasons)`. An empty list is the state this tree
    #: reaches when the LAST placeholder is retired, and the original conjunction turned that
    #: into a failure — so the final wave of a layer would have had to weaken this assertion to
    #: land, which is exactly the pressure that produces a weakened gate. What must hold is that
    #: every placeholder that EXISTS skips with a well-formed reason, and the count check below
    #: is what makes "none exist" mean "none were declared" rather than "none ran".
    assert all(reasons), (
        "every placeholder must skip with a reason naming its gate, its wave and the module "
        f"that wave builds:\n{result.stdout[-4000:]}")
    printed = result.stdout.lower().replace("errors summary", "")
    assert "error" not in printed, result.stdout[-4000:]
    #: One placeholder per pending gate, and no pending gate is H0 — H0 is THIS wave, and a
    #: placeholder for it would be the wave declaring itself unbuilt.
    gates = {match.group(1) for match in reasons}
    assert "H0" not in gates
    assert gates <= {"H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8"}
    waves = {match.group(2) for match in reasons}
    assert "X0" not in waves
    #: EVERY declared placeholder skipped, and nothing else did. The count is read off the tree
    #: rather than written here as a literal: waves land one component at a time, and a number in
    #: this file would have to be edited by each of them — including two landing in the same wave,
    #: which is how two correct edits produce one wrong total. What must not happen silently is a
    #: placeholder DISAPPEARING, and `RETIRED_PLACEHOLDERS` below is what catches that.
    declared = [path for path in _PLACEHOLDER_ROOT.rglob("test_*.py")
                if "l2_pending(" in path.read_text()]
    assert len(reasons) == len(declared), (
        f"{len(declared)} placeholders declare `l2_pending`, {len(reasons)} skipped with a "
        "well-formed reason")


#: A placeholder is allowed to disappear ONLY by being replaced with the real thing: the module
#: its skip reason named, and a test file that drives it. Deleting one to make a gate quiet would
#: otherwise look exactly like a wave landing, which is the failure this mapping exists to catch.
#: A wave that retires a placeholder adds its row here.
RETIRED_PLACEHOLDERS = {
    # X1 · L2.4.1 — the metric history store. `tests/context/analytic/test_history.py` kept the
    # gate command's path and now holds the store's WIRING assertions; the behaviour moved to:
    "genios_engine/context/analytic/history.py": "tests/context/analytic/test_metric_history.py",
    # X1 · L2.4.2 — the sampling policy. `test_sampler.py` likewise kept the gate command's path
    # and holds the WIRING (the sampler is called from the sweep, unconditionally, with the
    # sweep's one instant); BLG-07's decision table, the honest gap, determinism, the point
    # budget and the backfill are proven in:
    "genios_engine/context/analytic/sampler.py": "tests/context/analytic/test_metric_sampler.py",
    # X2 · L2.4.3 — the trend computer. Doc 04's six ordered steps and, decisively, the two
    # REFUSALS (too little history, too many holes) that are the product:
    "genios_engine/context/analytic/trend.py": "tests/context/analytic/test_trend.py",
    # X2 · L2.4.4 — declared cohorts and the population floor. Law 3 (cohorts are declared, never
    # clustered) is greppable and Law 2 (five members or a refusal) is unconstructible otherwise:
    "genios_engine/context/analytic/cohort.py": "tests/context/analytic/test_cohort.py",
    # X3 · L2.4.5 — the comparator. Nearest-rank against a DECLARED cohort, every position
    # carrying `cohort_id` and `population_size`, and a population under the floor refusing:
    "genios_engine/context/analytic/comparator.py": "tests/context/analytic/test_comparator.py",
    # X3 · L2.4.6 — the peer baseline, whose whole product is the DISCLOSURE bound: a published
    # ladder from which no individual member's reading can be recovered:
    "genios_engine/context/analytic/peer_baseline.py": "tests/context/analytic/test_peer_baseline.py",
    # X4 · L2.4.7 — the correlator. The n<20 refusal and `is_causal` unsettable are the product;
    # a coefficient computed over zero-filled gaps is the defect:
    "genios_engine/context/analytic/correlator.py": "tests/context/analytic/test_correlator.py",
    # X4 · L2.4.8 — the anomaly detector. MAD rather than a standard deviation an outlier can
    # inflate enough to hide inside, and an unsaturated ratio on an extreme reading:
    "genios_engine/context/analytic/anomaly.py": "tests/context/analytic/test_anomaly.py",
    # X7 · L2.2.7 — the point-in-time graph read. `tests/context/test_point_in_time.py` kept the
    # gate command's path and holds the whole temporal suite; the reader itself lives in the
    # store the rest of L2 already reads:
    "genios_engine/context/graph_store.py": "tests/context/test_point_in_time.py",
    # X7 · L2.2.6 — the authority view. `test_authority.py` kept the gate command's path and
    # holds doc 01's four ACCEPTANCE lines; the ranking, the currency window, the founder
    # bottleneck and the routes are proven in:
    "genios_engine/context/authority_view.py": "tests/context/test_authority_view.py",
    # X7 · L2.3.8 — BLG-05, the dependency correlator. `test_dependency_correlation.py` kept the
    # gate command's path and holds H7's own rows; the 56-row traversal suite is:
    "genios_engine/context/correlation_dependency.py": "tests/context/test_dependency_chains.py",
    # X5 · L2.7.4 — BLG-18, situation importance. `tests/context/test_situation_importance.py`
    # kept the gate command's path and is now H5 itself — the distribution, the per-modifier fire
    # table, the wiring ratchets and the real-Postgres sweep. The composer's own unit suite (the
    # six modifiers, the record, the readers, the supply guard) is:
    "genios_engine/context/importance.py": "tests/context/test_importance.py",
    # X7 · L2.3.4 — BLG-06, cross-timeline. The dormant condition, its parse refusal and the
    # two-span satisfaction:
    "genios_engine/context/correlation_timeline.py": "tests/context/test_cross_timeline.py",
    # X6 · L2.5.5-U1 — BLG-15, typed absence. `tests/context/quality/test_typed_absence.py` kept
    # the gate command's path and IS the H6 row "0 negative inferences drawn from UNKNOWABLE
    # facts": the cascade, its order, the licence that cannot be set, and the drain that writes
    # the rows. The downstream half — the two predicates that read a missing fact as a licence to
    # say "there isn't one" — is `tests/context/quality/test_negative_inference.py`:
    "genios_engine/context/quality/missing.py": "tests/context/quality/test_typed_absence.py",
    # X6 · L-5 — the coverage epoch. `tests/context/test_coverage_epoch.py` kept the gate
    # command's path and holds doc 13's four acceptance lines plus the window semantics ("no
    # trend may cross an epoch boundary without saying so"):
    "genios_engine/context/quality/epoch.py": "tests/context/test_coverage_epoch.py",
    # X6 · L-4 — the drain loop guards. `tests/context/test_convergence.py` kept the gate
    # command's path and holds both of H6's loop rows: `MAX_PASSES` with the state hash that
    # decides what "converged" means (and the scores it refuses to hash, because they move with
    # the clock), and the CI-enforced acyclicity of the derivation graph. The guard itself is two
    # functions in `context/runner.py`; the CI half is the script:
    "scripts/derivation_dag_check.py": "tests/context/test_convergence.py",
    # X6 · E-10 — the gap-reason classifier over `metric_history`. Org-wide silence versus a
    # broken connector versus a real decline, and the correction that keeps a shutdown out of a
    # trend fit — H6's row "DECLINING trends across an org-wide silence window: 0":
    "genios_engine/context/analytic/gap_reason.py": "tests/context/analytic/test_gap_reason.py",
    # X6 · L2.6 — the declarative pattern registry that replaces anchor-type detection.
    # `tests/context/patterns/test_pattern_registry.py` kept the gate command's path and IS H6's
    # first and third rows: ">= 6 patterns registered" and "0 patterns activated while exceeding
    # their expected fire rate 10x", plus the registration-time refusals that stop a pattern
    # nobody implemented from failing silently. The evaluator, the six seed patterns, the
    # candidate builder, the scorer and the real request path are proven beside it in
    # `test_matcher.py`, `test_seed_patterns.py`, `test_candidate.py`, `test_scorer.py` and
    # `test_pattern_path.py`; the declaration and both fire-rate guards live in:
    "genios_engine/context/patterns/registry.py": "tests/context/patterns/test_pattern_registry.py",
    # X6 · L2.7.7-U1 — M-4, resolution detection. `tests/context/lifecycle/test_resolution.py`
    # kept the gate command's path and IS H6's resolution half: doc 07's ACCEPTANCE rows, the
    # golden set's two numbers (false positives below 2%, >= 8 Hinglish fixtures) and the drain
    # reaching the detector on real PostgreSQL. The units behind it — the speaker-authority
    # table, the gate's named refusals, ALG-08 on the quote, the two floors and the claim
    # ledger — are pinned one at a time in `tests/context/lifecycle/test_lifecycle_units.py`,
    # and the fixtures themselves are data at `tests/golden/l2/m4_resolution.json`:
    "genios_engine/context/lifecycle/resolution.py":
        "tests/context/lifecycle/test_resolution.py",
}


@pytest.mark.parametrize("module,test_file", sorted(RETIRED_PLACEHOLDERS.items()))
def test_a_retired_placeholder_left_a_real_module_and_real_tests_behind(module, test_file):
    built = _ROOT / module
    tests = _ROOT / test_file
    assert built.is_file(), f"{module} was declared built and does not exist"
    assert tests.is_file(), f"{test_file} was declared to replace a placeholder and does not exist"
    body = tests.read_text()
    assert "l2_pending(" not in body, f"{test_file} is still a placeholder"
    assert body.count("def test_") >= 3, f"{test_file} does not drive {module}"
