"""G7 · THE LAYER 4 UNLOCK GATE — an INDEPENDENT probe, built from a different corpus.

`test_importance.py` is the builder's gate. This file is the auditor's, and it exists because
the failure G7 catches is one a green suite is compatible with: `reason/decision_maker.py:243`
records that "the formula has never once decided anything" while every test around it passed,
and `reason/reasoners/priority.py:165-197` handed 193 of 223 signals one identical score. A
gate that shares a corpus with the implementation it checks shares the implementation's blind
spots, so nothing here reuses a builder helper: its own signal factory, its own axes, its own
percentiles, and a CALIBRATED baseline where the builder's default is cold.

What it measures, and the number the plan requires:

    distinct importance_bp values           > 50        (a handful means it is not deciding)
    p90 - p50                               > 1500      (a flat distribution cannot rank)
    identical input replayed                byte-identical over the WHOLE corpus digest
    every score carries its components      100%
    a brand-new org with no history         does NOT collapse to one score

MUTATION-CHECKED, both ways. `return 5000` in place of the formula body takes this file from
green to red (1 distinct value, spread 0), and so does the NEAR miss — an implementation that
reads only `signal_type`, which varies (11 distinct values here) and passes the spread
threshold while still handing Layer 4 eleven rungs for a book of two hundred signals. The
distinct-value count is the assertion that catches the second one, which is why it is not
folded into the spread check.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.esqe import importance as I
from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.capture.esqe.source_analyzer import ActorBasis, SourceAttribution
from genios_engine.capture.validate.authority import AuthorityBasis, AuthorityWeight
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate
from genios_engine.contracts.visibility import Visibility

GATE = "G7"
EVAL = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)

#: The plan's own thresholds, named so a failure message can quote them.
MIN_DISTINCT = 50
MIN_SPREAD = 1500


# =============================================================================================
# The probe's own factory. Deliberately not `test_importance.py`'s.
# =============================================================================================
def _span(quote: str = "the quoted claim") -> EvidenceSpan:
    return EvidenceSpan(source_ref="prepared_content:pc_probe", quote=quote,
                        start_offset=0, end_offset=len(quote))


def _attribution(actor_bp: int, authority: Authority) -> SourceAttribution:
    return SourceAttribution(
        evidence=AuthorityWeight(authority=authority, basis=AuthorityBasis.SOURCE_OBJECT),
        actor_authority_bp=actor_bp, actor_basis=ActorBasis.ROLE_LADDER,
        actor_email="probe@acme.test")


def _date(days: int | None, certainty: DateCertainty) -> ResolvedDate | None:
    if days is None:
        return None
    if certainty is DateCertainty.UNRESOLVED:
        return ResolvedDate(as_written=f"in {days} days", earliest=None, latest=None,
                            certainty=certainty, resolved_against=EVAL, evidence=[_span()])
    at = EVAL + timedelta(days=days)
    latest = at + timedelta(days=3 if certainty is DateCertainty.RANGE else 0)
    return ResolvedDate(as_written=f"in {days} days", earliest=at, latest=latest,
                        certainty=certainty, resolved_against=EVAL, evidence=[_span()])


def _signal(*, kind, entity, amount, date, attribution) -> NormalizedSignal:
    return NormalizedSignal(
        org_id="org_probe", event_id="evt_probe", source="gmail", object_type="message",
        occurred_at=EVAL, visibility=Visibility(scope="participants",
                                                principals=["a@acme.test"]),
        recipients=("a@acme.test",), internal_kind=None, signal_type=kind, predicate="probe",
        subject_key="subj", subject_label="Subject", primary_entity=entity,
        primary_date=date, primary_amount=amount, evidence_refs=(_span(),),
        attribution=attribution)


#: A CALIBRATED baseline. The builder's wiring test runs cold on purpose; this one runs warm,
#: so the ratio ladder and all six entity rungs are on the measured path rather than only the
#: absolute fallback. A formula that spread only when uncalibrated would pass there and fail
#: for every tenant who has been live a month.
BASELINE = I.OrgBaseline(
    org_id="org_probe", p50_minor_units=4_500_000, currency="USD", sample_size=40,
    basis=I.BaselineBasis.ORG_HISTORY, computed_against=EVAL,
    mission_critical=frozenset({"northwind"}), top_decile=frozenset({"acme"}),
    active=frozenset({"globex"}), known=frozenset({"initech"}))

_AMOUNTS = (None,
            Money(minor_units=25_000, currency="USD", as_written="$250"),
            Money(minor_units=450_000, currency="USD", as_written="$4,500"),
            Money(minor_units=2_250_000, currency="USD", as_written="$22,500"),
            Money(minor_units=4_500_000, currency="USD", as_written="$45,000"),
            Money(minor_units=8_400_000, currency="USD", as_written="$84,000"),
            Money(minor_units=45_000_000, currency="USD", as_written="$450,000"),
            Money(minor_units=900_000_000, currency="USD", as_written="$9,000,000"),
            Money(minor_units=3_100_000, currency="EUR", as_written="EUR 31,000"),
            Money(minor_units=1_200_000, currency="XXX", as_written="12,000 ???"))
#: Overdue, due today, and every rung of the ladder, plus "no date at all".
_DAYS = (None, -30, -1, 0, 1, 5, 10, 21, 60, 200, 900)
_ACTORS = (0, 1500, 3000, 4500, 6000, 7500, 9000, 10000)
#: One entity for each standing the baseline above can return, plus None and a stranger.
_ENTITIES = (None, "Northwind", "Acme", "Globex", "Initech", "Unheard Of Ltd")
_CERTAINTY = tuple(DateCertainty)
_AUTHORITY = tuple(Authority)


def _corpus() -> list[NormalizedSignal]:
    """A full cross-product, no RNG. A seeded sample would be reproducible and still only prove
    the formula spread over the sample; the product proves it over the space."""
    rows = []
    for index, (amount, days, actor, entity, kind) in enumerate(itertools.product(
            _AMOUNTS, _DAYS, _ACTORS, _ENTITIES, SignalType)):
        rows.append(_signal(kind=kind, entity=entity, amount=amount,
                            date=_date(days, _CERTAINTY[index % len(_CERTAINTY)]),
                            attribution=_attribution(actor,
                                                     _AUTHORITY[index % len(_AUTHORITY)])))
    return rows


def _percentile(values, quantile_bp: int) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, (quantile_bp * (len(ordered) - 1) + 5000) // 10000)]


def _digest(scores) -> str:
    """The whole corpus as one hash — scores AND components. A term that depended on dict order
    or on a clock moves this and nothing else."""
    blob = json.dumps([[s.importance_bp, sorted((k, str(v))
                                                for k, v in s.components.as_record().items())]
                       for s in scores], sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@pytest.fixture(scope="module")
def scored():
    return [I.score_importance(s, BASELINE, eval_time=EVAL) for s in _corpus()]


# =============================================================================================
# THE GATE
# =============================================================================================
@pytest.mark.gate
def test_gate_the_distribution_is_wide_enough_for_layer_4_to_rank_on(scored):
    """The load-bearing assertion of the whole wave, over an independently built corpus."""
    values = [s.importance_bp for s in scored]
    p50, p90 = _percentile(values, 5000), _percentile(values, 9000)
    distinct = len(set(values))

    assert len(values) > 10_000, "a distribution over a handful of rows is an example test"
    assert distinct > MIN_DISTINCT, (
        f"only {distinct} distinct scores over {len(values)} signals — the formula is not "
        f"deciding anything, which is the exact defect G7 exists to catch")
    assert p90 - p50 > MIN_SPREAD, (
        f"p50={p50} p90={p90}: a distribution this flat cannot rank, whatever its mean")
    assert 0 <= min(values) and max(values) <= 10_000


@pytest.mark.gate
def test_gate_no_single_score_swallows_the_corpus(scored):
    """The 193-of-223 shape, stated as a share rather than as a count. A formula can clear
    ">50 distinct" and still put four fifths of a book on one number."""
    values = [s.importance_bp for s in scored]
    largest = max(values.count(v) for v in set(values))

    assert largest * 100 // len(values) < 5, (
        f"one score covers {largest * 100 // len(values)}% of the corpus")


@pytest.mark.gate
def test_gate_every_score_carries_components_that_reconstruct_it(scored):
    """100%, and not merely present: the stored terms must reproduce the number they explain,
    or the explanation is decoration."""
    weights = I.IMPORTANCE_WEIGHTS_V1
    for score in scored:
        parts = score.components
        assert isinstance(parts, I.ImportanceComponents)
        weighted = (weights.money * parts.monetary_exposure_bp
                    + weights.deadline * parts.deadline_proximity_bp
                    + weights.authority * parts.actor_authority_bp
                    + weights.criticality * parts.entity_criticality_bp
                    + weights.signal_type * parts.signal_type_weight_bp) // 10_000
        assert weighted == parts.weighted_bp
        assert score.importance_bp == min(
            10_000, max(0, weighted * parts.evidence_authority_multiplier_bp // 10_000))


@pytest.mark.gate
def test_gate_the_whole_corpus_replays_byte_identically(scored):
    replay = [I.score_importance(s, BASELINE, eval_time=EVAL) for s in _corpus()]

    assert _digest(replay) == _digest(scored)


@pytest.mark.gate
def test_gate_a_brand_new_org_with_no_history_does_not_collapse_to_one_score():
    """COLD START — the state EVERY tenant is in on day one, and (until L1.6.7-U2's nightly job
    has a producer) the state every tenant is in on the real capture path, because
    `pipeline.run_esqe_stage` builds `OrgBaseline.cold_start` when no baseline is supplied.

    A formula that ranks only once it is calibrated would hand a tenant's first week one score,
    which is the defect this gate exists to catch arriving a month late instead of never.
    """
    cold = I.OrgBaseline.cold_start("org_day_one", computed_against=EVAL)
    values = [I.score_importance(s, cold, eval_time=EVAL).importance_bp for s in _corpus()]
    p50, p90 = _percentile(values, 5000), _percentile(values, 9000)

    assert len(set(values)) > MIN_DISTINCT, (
        f"a cold-start tenant gets {len(set(values))} distinct scores")
    assert p90 - p50 > MIN_SPREAD, f"cold start p50={p50} p90={p90}"


# =============================================================================================
# The properties a distribution cannot see
# =============================================================================================
def test_no_llm_client_is_reachable_from_the_scorers_import_graph():
    """An IMPORT-GRAPH check, not a grep of the prose. The module argues about models at length,
    so a text search for "anthropic" hits a docstring; what matters is whether a client is
    reachable from `score_importance` at all."""
    root = pathlib.Path(__file__).resolve().parents[3]

    def path_of(mod: str):
        for candidate in (root / (mod.replace(".", "/") + ".py"),
                          root / mod.replace(".", "/") / "__init__.py"):
            if candidate.exists():
                return candidate
        return None

    seen, queue = set(), ["genios_engine.capture.esqe.importance"]
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        seen.add(mod)
        path = path_of(mod)
        if path is None:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                queue += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                queue.append(node.module)

    forbidden = {"anthropic", "openai", "litellm", "httpx", "requests", "urllib.request"}
    assert not (seen & forbidden), f"a network/model client is reachable: {sorted(seen & forbidden)}"
    assert not any("llm" in m.split(".")[-1].lower() for m in seen), sorted(seen)


@pytest.mark.parametrize("module", ["importance", "qualification"])
def test_no_float_arithmetic_anywhere_in_the_score_path(module):
    """The ARITHMETIC, not the literal `float(`. `x / 10000` is a float the moment it runs and
    would make a ranking machine-dependent at the last digit; so would a `0.9` constant, a
    `round()`, or anything out of `math`."""
    source = pathlib.Path(__file__).resolve().parents[3] / "genios_engine/capture/esqe" / f"{module}.py"
    offenders = []
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            offenders.append(f"true division at line {node.lineno}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            offenders.append(f"float literal at line {node.lineno}")
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("float", "round", "pow")):
            offenders.append(f"{node.func.id}() at line {node.lineno}")
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "math"):
            offenders.append(f"math.{node.attr} at line {node.lineno}")

    assert not offenders, "\n".join(offenders)


def test_every_stored_components_record_round_trips_back_into_its_typed_object(scored):
    """`from_record` is the inverse `explain_drop` needs to render a MONTHS-OLD refusal without
    re-scoring it. Asserted over the whole corpus rather than one row, because the fields that
    would break it are the optional-looking ones — `flags`, and the two enums."""
    for score in scored[::37]:                       # every 37th, so the sweep stays fast
        rebuilt = I.ImportanceComponents.from_record(score.components.as_record())

        assert rebuilt == score.components
        assert rebuilt.as_record() == score.components.as_record()


def test_a_record_missing_a_term_is_refused_rather_than_defaulted():
    """A rendered explanation whose `entity_standing` silently became `absent` reads as a fact.
    `ValueError` is the honest answer; a default is a fabricated one."""
    full = I.ImportanceComponents(
        monetary_exposure_bp=1, deadline_proximity_bp=2, actor_authority_bp=3,
        entity_criticality_bp=4, signal_type_weight_bp=5,
        evidence_authority_multiplier_bp=10_000, weighted_bp=6, baseline_used=0,
        baseline_currency="XXX", baseline_basis=I.BaselineBasis.ESTIMATED,
        entity_standing=I.EntityStanding.ABSENT, eval_time=EVAL).as_record()

    for missing in ("entity_standing", "eval_time", "weighted_bp", "baseline_basis"):
        with pytest.raises(ValueError):
            I.ImportanceComponents.from_record({k: v for k, v in full.items() if k != missing})
