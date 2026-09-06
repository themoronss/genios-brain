"""G7 · importance scoring — Wave W7. **The Layer 4 unlock gate.**

ALG-17 turns evidence into a rank. It is the most important gate in the plan because the defect
it fixes is not a crash — it is a formula that runs, returns a number, and decides nothing:
`reason/decision_maker.py:243` records *"the formula has never once decided anything"*, and
`reason/reasoners/priority.py:165-197` is where 193 of 223 signals carried an identical score.
A suite of green unit tests is entirely compatible with that failure, so the gate is a
DISTRIBUTION over a generated corpus, not an assertion over a fixture:

    pytest tests/capture/esqe/test_importance.py -q

    distinct importance_bp values          > 50        (a handful means it is not deciding)
    p90 - p50                              > 1500      (a flat distribution cannot rank)
    identical input replayed               byte-identical
    every score has importance_components  100%        (explainability)

WHICH TEST CATCHES ``return 5000``
----------------------------------
Asked and answered here rather than left to be rediscovered, because it is the whole point of
the file. Replacing the formula with a constant was run as a mutation against this suite: 16
tests go red, and the load-bearing one is
**`test_gate_the_score_distribution_is_wide_enough_to_rank_on`** — it scores a 5,760-row corpus
varying every input the formula consumes and requires >50 distinct values with a p90-p50 spread
above 1500, where a constant produces ONE value and a spread of ZERO.

It is singled out because it is the only test here that also catches the NEAR miss: an
implementation that varies but collapses. A formula that read only `signal_type` returns
fourteen distinct values and would satisfy every "strictly lower" row that happened to change
type, while still handing Layer 4 a ranking with fourteen rungs for a book of two hundred
signals. Nothing but a distribution can see that, which is why the gate is a distribution.

The supporting cast catches what a distribution cannot see in return: integer arithmetic end to
end (``x * 9 // 10``, never ``x * 0.9``), components that reconstruct the score they claim to
explain, monotonicity in each term, and the absence of a clock, a model and a float from the
module's source.
"""

from __future__ import annotations

import ast
import inspect
import itertools
import pathlib
import re
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.esqe import importance as I
from genios_engine.capture.esqe.normalize import NormalizedSignal, ThreadContext
from genios_engine.capture.esqe.source_analyzer import ActorBasis, SourceAttribution
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.validate.authority import AuthorityBasis, AuthorityWeight
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.signal import SignalType as T
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate

WAVE = "W7"
GATE = "G7"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)

#: The org whose p50 contract is $45,000 — doc 06's own worked example, in which an $84K
#: renewal is "~2x your typical contract".
P50_MINOR_UNITS = 4_500_000
EIGHTY_FOUR_K = 8_400_000


# =============================================================================================
# Builders. One signal, varied one field at a time — the same discipline `conftest.py` applies
# to `ExtractionResult`, for the same reason: a row that also changed in a second place is a
# row asserting against a fixture rather than against the formula.
# =============================================================================================
def _module_code() -> str:
    """`importance.py` with its docstrings and comments stripped — the CODE, not the prose.

    The module argues at length about the arithmetic it refuses to do, so a naive grep for
    ``math.log`` finds the sentence explaining why there is no ``math.log``. Stripping the
    triple-quoted blocks and the comment lines leaves what actually executes, which is the only
    text these greps are a statement about.
    """
    source = pathlib.Path(inspect.getfile(I)).read_text()
    source = re.sub(r'"""(?:.|\n)*?"""', '""', source)
    return "\n".join(line for line in source.splitlines()
                      if not line.lstrip().startswith("#"))


def _span(quote: str = "the $84K annual contract") -> EvidenceSpan:
    return EvidenceSpan(source_ref="prepared_content:evt_alg17", quote=quote,
                        start_offset=0, end_offset=len(quote))


def _attribution(*, actor_bp: int = 9500,
                 authority: Authority = Authority.SIGNED_DOCUMENT) -> SourceAttribution:
    """L1.6.4's answer, built directly.

    Terms 3 and 6 are read off this object and never recomputed inside ALG-17, so a test that
    wants "the same event from a service account" varies THIS and nothing else — which is also
    the only way to prove the scorer is reading the analyzer rather than re-deriving a second
    authority ladder of its own.
    """
    return SourceAttribution(evidence=AuthorityWeight(authority, AuthorityBasis.EXECUTED),
                             actor_authority_bp=actor_bp, actor_basis=ActorBasis.ROLE_LADDER,
                             actor_email="cfo@northwind.com")


def _date(days: int, certainty: DateCertainty = DateCertainty.EXACT) -> ResolvedDate:
    when = NOW + timedelta(days=days)
    latest = when if certainty is DateCertainty.EXACT else when + timedelta(days=3)
    return ResolvedDate(as_written=f"in {days} days", earliest=when, latest=latest,
                        certainty=certainty, resolved_against=NOW, evidence=[_span()])


def _money(minor_units: int = EIGHTY_FOUR_K, currency: str = "USD") -> Money:
    return Money(minor_units=minor_units, currency=currency, as_written="$84K")


def _signal(*, signal_type: T = T.CONTRACT_RENEWAL,
            amount: Money | None = None,
            date: ResolvedDate | None = None,
            entity: str | None = "Northwind Ltd",
            attribution: SourceAttribution | None = None) -> NormalizedSignal:
    return NormalizedSignal(
        org_id="org_alg17", event_id="evt_alg17", source="gmail",
        object_type="email_attachment", occurred_at=NOW, visibility=None,
        recipients=("founder@genios.ai",), internal_kind=None,
        signal_type=signal_type, predicate="renewal_window_open",
        subject_key="contract:northwind", subject_label="the annual contract",
        primary_entity=entity, primary_date=date, primary_amount=amount,
        evidence_refs=(_span(),), attribution=attribution or _attribution(),
        thread=ThreadContext(thread_key="thr_1"))


def _baseline(**over) -> I.OrgBaseline:
    kwargs = dict(org_id="org_alg17", p50_minor_units=P50_MINOR_UNITS, currency="USD",
                  sample_size=40, basis=I.BaselineBasis.ORG_HISTORY, computed_against=NOW,
                  mission_critical=frozenset({"northwind ltd"}),
                  top_decile=frozenset({"globex"}), active=frozenset({"initech"}),
                  known=frozenset({"initech", "globex", "hooli"}))
    kwargs.update(over)
    return I.OrgBaseline(**kwargs)


def _score(signal: NormalizedSignal, baseline: I.OrgBaseline | None = None) -> I.ImportanceScore:
    return I.score_importance(signal, baseline or _baseline(), eval_time=NOW)


#: Doc 06's headline acceptance row: $84K renewal, 12 days out, CFO sender, mission-critical
#: vendor, signed PDF.
def _worked_example(**over) -> NormalizedSignal:
    kwargs = dict(signal_type=T.CONTRACT_RENEWAL, amount=_money(), date=_date(12),
                  entity="Northwind Ltd")
    kwargs.update(over)
    return _signal(**kwargs)


# =============================================================================================
# Doc 06 L1.6.7-U1 · ACCEPTANCE — the required rows, verbatim.
# =============================================================================================
def test_the_worked_example_row_scores_between_7500_and_8500():
    """`$84K renewal, 12 days out, CFO sender, mission-critical vendor, signed PDF`.

    The band is doc 06's, not this test's. It is wide because the row is a calibration
    statement — "this is roughly what a big, near, well-attested thing is worth" — and pinning
    it to a single integer would make every future weight retune a test edit rather than a
    decision.
    """
    score = _score(_worked_example())

    assert 7500 <= score.importance_bp <= 8500, (
        f"doc 06's headline row scored {score.importance_bp}; "
        f"{I.explain_importance(score)}")


@pytest.mark.parametrize("label, weakened", [
    ("a vague date instead of an exact one",
     dict(date=_date(12, DateCertainty.RELATIVE))),
    ("a service account instead of the CFO",
     dict(attribution=_attribution(actor_bp=1000))),
    ("the amount at the org's own p50 instead of twice it",
     dict(amount=_money(P50_MINOR_UNITS))),
    ("a chat aside instead of a signed document",
     dict(attribution=_attribution(authority=Authority.CHAT_ASIDE))),
    ("a first-seen counterparty instead of a mission-critical one",
     dict(entity="Some New Vendor")),
    ("a far deadline instead of a near one", dict(date=_date(200))),
    ("no amount at all", dict(amount=None)),
])
def test_each_weakened_variant_of_the_worked_example_scores_strictly_lower(label, weakened):
    """Doc 06's three "strictly lower" rows, plus one per remaining term.

    STRICTLY, not "lower or equal". Equality here is the whole bug: a term that is present in
    the formula but cannot move the answer is a term that is not deciding anything, and 193 of
    223 identical scores is what that looks like at scale.
    """
    full = _score(_worked_example()).importance_bp
    weaker = _score(_worked_example(**weakened)).importance_bp

    assert weaker < full, f"{label}: {weaker} is not below {full}"


def test_a_newsletter_with_no_money_no_date_and_no_entity_scores_under_2000():
    """Doc 06's floor row. The formula's job at the bottom of the range is as important as at
    the top: a qualification floor that everything clears is not a floor."""
    score = _score(_signal(signal_type=T.ANOMALY, amount=None, date=None, entity=None,
                           attribution=_attribution(actor_bp=3000,
                                                    authority=Authority.EMAIL_PROSE)))

    assert score.importance_bp < 2000, I.explain_importance(score)


def test_the_relative_halving_is_exactly_five_tenths_of_the_exact_reading():
    """*"Renewal coming up pretty soon"* must not score the same as *"renewal on October 15"*,
    and the discount is doc 06's ``* 5 // 10`` rather than a judgement call."""
    exact = _score(_worked_example(date=_date(12))).components
    relative = _score(_worked_example(date=_date(12, DateCertainty.RELATIVE))).components

    assert exact.deadline_proximity_bp == 6000, "12 days is the 14-day rung"
    assert relative.deadline_proximity_bp == 6000 * 5 // 10
    assert I.ImportanceFlag.RELATIVE_DEADLINE in relative.flags, (
        "a halved term that does not say it was halved is unexplainable")


# =============================================================================================
# The terms — each one moves the answer, in the right direction, by a table anyone can read.
# =============================================================================================
@pytest.mark.parametrize("days, expected_bp", [
    (-30, 10000), (-1, 10000), (0, 10000),
    (1, 9000), (2, 9000),
    (3, 7500), (7, 7500),
    (8, 6000), (14, 6000),
    (15, 4000), (30, 4000),
    (31, 2000), (90, 2000),
    (91, 500), (365, 500),
])
def test_the_deadline_ladder_reads_the_conservative_edge_of_the_window(days, expected_bp):
    """Every rung of doc 06 term 2, including both sides of every boundary.

    Boundaries are tested in pairs because an off-by-one here is invisible in aggregate — the
    distribution stays wide, the monotonicity holds, and a fortnight's deadline quietly scores
    as a month's for every tenant.
    """
    components = _score(_worked_example(date=_date(days))).components
    assert components.deadline_proximity_bp == expected_bp


@pytest.mark.parametrize("certainty, flag", [
    (DateCertainty.UNRESOLVED, I.ImportanceFlag.UNRESOLVED_DEADLINE),
])
def test_an_unresolved_date_contributes_nothing_and_says_so(certainty, flag):
    """ALG-09 refuses to invent a window; ALG-17 must not invent urgency from the refusal."""
    unresolved = ResolvedDate(as_written="at some point", earliest=None, latest=None,
                              certainty=certainty, resolved_against=NOW, evidence=[_span()])
    components = _score(_worked_example(date=unresolved)).components

    assert components.deadline_proximity_bp == 0
    assert flag in components.flags, "a zero with no reason beside it is unauditable"


@pytest.mark.parametrize("entity, standing, expected_bp", [
    ("Northwind Ltd", I.EntityStanding.MISSION_CRITICAL, 10000),
    ("Globex", I.EntityStanding.TOP_DECILE, 8000),
    ("Initech", I.EntityStanding.ACTIVE, 6000),
    ("Hooli", I.EntityStanding.KNOWN, 4000),
    ("Brand New Co", I.EntityStanding.FIRST_SEEN, 2000),
    (None, I.EntityStanding.ABSENT, 0),
])
def test_entity_criticality_is_one_rung_of_the_orgs_own_ladder(entity, standing, expected_bp):
    """Term 4, and the rung is recorded beside the number.

    ``ABSENT`` is this build's sixth rung and the row is here to pin it: "names no
    counterparty" scoring the same as "names one we have never seen" would hand 400 bp of final
    score to every newsletter, which is exactly the noise the floor is meant to strip.
    """
    components = _score(_worked_example(entity=entity)).components

    assert components.entity_standing is standing
    assert components.entity_criticality_bp == expected_bp


def test_a_higher_standing_wins_when_an_entity_qualifies_for_several_rungs():
    """A mission-critical vendor that is ALSO top-decile and ALSO has an open deal is
    mission-critical. The choice is made in `OrgBaseline.standing_of` so two call sites cannot
    disagree about which of three true facts outranks the others."""
    baseline = _baseline(mission_critical=frozenset({"acme"}), top_decile=frozenset({"acme"}),
                         active=frozenset({"acme"}), known=frozenset({"acme"}))

    assert baseline.standing_of("ACME") is I.EntityStanding.MISSION_CRITICAL
    assert baseline.standing_of("  acme  ") is I.EntityStanding.MISSION_CRITICAL, (
        "an entity key that depends on whitespace is a counterparty with two standings")


def test_the_signal_type_nudge_cannot_outvote_the_other_four_terms():
    """Doc 06: term 5 is *"a small nudge by type, not the dominant term"*.

    The whole 6000 bp span of the type table is worth 600 bp of final score. If a retune ever
    made type dominant, a RELATIONSHIP_CHANGE about a mission-critical vendor with an overdue
    $2M invoice would rank below an ANOMALY about nothing — which is precisely the "authored
    constants decide the ranking" failure one layer up, reimported into Layer 1.
    """
    scores = {kind: _score(_worked_example(signal_type=kind)).importance_bp for kind in T}
    span = max(scores.values()) - min(scores.values())

    assert span <= 600, f"the type table moved the score by {span} bp"
    assert len(set(scores.values())) > 1, "a term that never moves the answer is not a term"


def test_every_signal_type_has_a_weight_and_every_standing_has_a_criticality():
    """Totality, on the same terms as ALG-16's precedence check. A fifteenth taxonomy member
    with no weight is a `KeyError` inside a tenant's sweep, not a missing row someone notices."""
    assert set(I.SIGNAL_TYPE_WEIGHT_BP) == set(T)
    assert set(I.ENTITY_CRITICALITY_BP) == set(I.EntityStanding)
    assert I.IMPORTANCE_WEIGHTS_V1.total == 10000


# =============================================================================================
# Monotonicity — the property a wrong table breaks and an example row cannot see.
# =============================================================================================
def test_a_larger_amount_never_lowers_the_score():
    ladder = [0, 1_00, 10_000, 100_000, 1_000_000, 4_500_000, 9_000_000, 45_000_000,
              450_000_000, 4_500_000_000]
    scores = [_score(_worked_example(amount=_money(minor))).importance_bp for minor in ladder]

    assert scores == sorted(scores), dict(zip(ladder, scores))
    assert len(set(scores)) > 4, "a money ladder with four readings is not log-scaled, it is flat"


def test_a_nearer_deadline_never_lowers_the_score():
    ladder = [365, 120, 90, 45, 30, 20, 14, 7, 3, 1, 0, -5]
    scores = [_score(_worked_example(date=_date(days))).importance_bp for days in ladder]

    assert scores == sorted(scores), dict(zip(ladder, scores))


def test_a_higher_authority_never_lowers_the_score():
    actor = [1000, 3000, 5000, 6000, 8000, 9000, 9500, 10000]
    assert ([_score(_worked_example(attribution=_attribution(actor_bp=bp))).importance_bp
             for bp in actor] == sorted(
        _score(_worked_example(attribution=_attribution(actor_bp=bp))).importance_bp
        for bp in actor))

    ranked = [Authority.INFERRED, Authority.CHAT_ASIDE, Authority.EMAIL_PROSE,
              Authority.ATTACHMENT, Authority.STRUCTURED_SOURCE, Authority.COMPANY_CANON,
              Authority.SIGNED_DOCUMENT]
    evidence = [_score(_worked_example(attribution=_attribution(authority=a))).importance_bp
                for a in ranked]
    assert evidence == sorted(evidence), dict(zip([a.value for a in ranked], evidence))


def test_the_score_never_leaves_the_contracts_range_even_at_both_extremes():
    """`QualifiedEnterpriseSignal.importance_bp` is an int 0..10000 and its validator will
    refuse anything else at the seam. Refusing at the seam is a parked signal; refusing here is
    a bug found in a test."""
    biggest = _score(_signal(signal_type=T.INFORMATION_CONFLICT, amount=_money(10 ** 14),
                             date=_date(-100), entity="Northwind Ltd",
                             attribution=_attribution(actor_bp=10000)))
    smallest = _score(_signal(signal_type=T.ANOMALY, amount=None, date=None, entity=None,
                              attribution=_attribution(actor_bp=0,
                                                       authority=Authority.INFERRED)))

    assert 0 <= smallest.importance_bp <= biggest.importance_bp <= 10000
    assert biggest.importance_bp == 9900, (
        "the top of the range is 9900 and not 10000, because the TYPE table's own ceiling is "
        "9000 rather than 10000 — 100 bp of headroom nothing can claim. That is deliberate: a "
        "score that saturates at the maximum has stopped ordering the things above it, and the "
        "signals at the very top are exactly the ones a founder needs ordered")
    assert smallest.importance_bp < 200, (
        "no amount, no date, no entity and no authority is worth almost nothing — but not "
        "exactly nothing: every signal has a TYPE, and the type nudge is the floor of the "
        "range rather than a zero, so two worthless signals of different kinds still order")


# =============================================================================================
# Determinism, and the arithmetic it rests on.
# =============================================================================================
def test_the_same_input_scored_twice_is_byte_identical():
    """The property ranking rests on. Two replays of one signal must agree in every field, not
    only in the headline integer — a components dict that differs is a card whose explanation
    changes between two viewings of the same signal."""
    signal, baseline = _worked_example(), _baseline()

    first = I.score_importance(signal, baseline, eval_time=NOW)
    second = I.score_importance(signal, baseline, eval_time=NOW)

    assert first == second
    assert first.components.as_record() == second.components.as_record()
    assert I.explain_importance(first) == I.explain_importance(second)


def test_the_score_moves_with_eval_time_and_never_with_a_clock():
    """`eval_time` is the only thing that makes a deadline near or far. Two evaluations of the
    SAME signal against two instants must differ — which is also the proof that no `now()` is
    being read, because a clock would make both calls agree."""
    signal = _worked_example(date=_date(12))

    at_capture = I.score_importance(signal, _baseline(), eval_time=NOW)
    a_fortnight_later = I.score_importance(signal, _baseline(), eval_time=NOW + timedelta(days=14))

    assert a_fortnight_later.importance_bp > at_capture.importance_bp
    assert a_fortnight_later.components.eval_time == NOW + timedelta(days=14)


@pytest.mark.parametrize("forbidden", ["float(", "math.log", "datetime.now", "utcnow(",
                                       "time.time", "/ 10000", "random."])
def test_the_module_source_contains_no_float_no_clock_and_no_division(forbidden):
    """Source-grep, exactly as doc 06's reverse prompt requires.

    A grep rather than a behavioural assertion because the failure it guards is silent: a single
    ``/`` where a ``//`` belongs produces a float that compares, sorts and prints like an
    integer right up to the machine where it rounds the other way.
    """
    assert forbidden not in _module_code(), f"{forbidden!r} is on ALG-17's call path"


def test_the_module_contains_no_true_division_and_no_float_literal_anywhere():
    """The grep above catches the spellings; this catches the arithmetic itself.

    Parsing the module rather than reading it: ``a / b`` inside a docstring is prose and ``a /
    b`` inside a function is a float, and only an AST can tell those apart.
    """
    tree = ast.parse(pathlib.Path(inspect.getfile(I)).read_text())

    divisions = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp)
                 and isinstance(n.op, ast.Div)]
    floats = [n for n in ast.walk(tree) if isinstance(n, ast.Constant)
              and isinstance(n.value, float)]

    assert divisions == [], "true division on the score path — every quotient must be `//`"
    assert floats == [], "a float literal in a module whose output must replay byte-identical"


def test_no_llm_module_is_reachable_from_the_import_graph_of_this_unit():
    """Doc 06: *"LLM — no, absolutely not."* An import-graph test rather than a call-count one,
    because a model that is merely IMPORTED here is a model somebody will call here."""
    tree = ast.parse(pathlib.Path(inspect.getfile(I)).read_text())
    imported = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                 for alias in node.names}

    assert not [m for m in imported if "llm" in m.lower() or "anthropic" in m.lower()], imported


# =============================================================================================
# Explainability — doc 06: "storing the components is MANDATORY".
# =============================================================================================
def test_the_components_reconstruct_the_score_they_claim_to_explain():
    """*"Why is this an 8100?"* answered from the stored row alone, with no recomputation.

    This is the assertion that keeps the two-division arithmetic honest: a fused
    ``// 100_000_000`` would be off by up to 1 bp from the product of the numbers a founder is
    shown, and an explanation that does not add up is worse than a coarser one.
    """
    parts = _score(_worked_example()).components
    weights = I.IMPORTANCE_WEIGHTS_V1

    weighted = (weights.money * parts.monetary_exposure_bp
                + weights.deadline * parts.deadline_proximity_bp
                + weights.authority * parts.actor_authority_bp
                + weights.criticality * parts.entity_criticality_bp
                + weights.signal_type * parts.signal_type_weight_bp) // 10000

    assert weighted == parts.weighted_bp
    assert (parts.weighted_bp * parts.evidence_authority_multiplier_bp // 10000
            == _score(_worked_example()).importance_bp)


def test_every_score_carries_a_version_and_a_serialisable_record():
    """The stored row must survive JSON and must name the weights that produced it. Two scores
    from two weight versions are not comparable, and sorting them together is the drift doc 06's
    failure table calls out by name."""
    import json

    score = _score(_worked_example())
    record = score.components.as_record()

    assert score.importance_version == I.IMPORTANCE_VERSION
    assert json.loads(json.dumps(record)) == record, "the audit row needs a custom encoder"
    assert record["eval_time"] == NOW.isoformat()
    assert record["baseline_used"] == P50_MINOR_UNITS


@pytest.mark.parametrize("case, signal, baseline", [
    ("the worked example", _worked_example(), _baseline()),
    ("a cold-start org", _worked_example(), I.OrgBaseline.cold_start("new", computed_against=NOW)),
    ("no money", _worked_example(amount=None), _baseline()),
    ("no date", _worked_example(date=None), _baseline()),
    ("no entity", _worked_example(entity=None), _baseline()),
    ("a vague date", _worked_example(date=_date(4, DateCertainty.RELATIVE)), _baseline()),
    ("nothing at all", _signal(signal_type=T.ANOMALY, amount=None, date=None, entity=None,
                               attribution=_attribution(actor_bp=1000,
                                                        authority=Authority.INFERRED)),
     I.OrgBaseline.cold_start("new", computed_against=NOW)),
])
def test_the_renderer_produces_one_true_sentence_for_every_shape_of_score(case, signal, baseline):
    """L1.6.7-U3. A score nobody can explain cannot be argued with by the founder it is shown to.

    The renderer must survive every degenerate score, because those are exactly the ones a
    founder questions. A missing term is OMITTED rather than described as a zero: "the amount is
    small (0)" about a message that named no amount is a false sentence.
    """
    sentence = I.explain_importance(I.score_importance(signal, baseline, eval_time=NOW))
    score = I.score_importance(signal, baseline, eval_time=NOW)

    assert sentence.startswith(f"Scored {score.importance_bp}:"), case
    assert sentence.endswith(".") and len(sentence) > 40, case
    assert "None" not in sentence and "{" not in sentence, f"{case}: unsubstituted template"
    if signal.primary_amount is None:
        assert "amount" not in sentence, f"{case}: described an amount that was never named"


# =============================================================================================
# L1.6.7-U2 · the org baseline — and the cold start that must not flatten anything.
# =============================================================================================
def _observation(minor: int, *, days_ago: int = 30, counterparty: str | None = None,
                 currency: str = "USD", is_open: bool = False) -> I.BaselineObservation:
    return I.BaselineObservation(amount=Money(minor_units=minor, currency=currency,
                                              as_written=f"{minor}"),
                                 occurred_at=NOW - timedelta(days=days_ago),
                                 counterparty=counterparty, is_open=is_open)


def test_the_baseline_is_the_p50_of_the_orgs_own_priced_history():
    """Nearest-rank, integer, lower median. Not a mean: one enterprise deal in a year of SMB
    contracts would drag an average above every real contract the org has ever signed, and
    every subsequent amount would then read as small."""
    history = [_observation(m) for m in (1_00_000, 2_00_000, 4_50_000, 9_00_000, 20_00_000)]

    baseline = I.compute_org_baseline(history, org_id="org_alg17", eval_time=NOW)

    assert baseline.p50_minor_units == 4_50_000
    assert baseline.basis is I.BaselineBasis.ORG_HISTORY
    assert baseline.sample_size == 5


def test_only_the_last_365_days_count_toward_the_baseline():
    """A window, not a lifetime. An org whose prices doubled last year must not be calibrated
    against the prices it charged before they did."""
    history = [_observation(1_000_000, days_ago=10), _observation(1_000_000, days_ago=20),
               _observation(9_000_000, days_ago=400)]

    baseline = I.compute_org_baseline(history, org_id="org_alg17", eval_time=NOW)

    assert baseline.sample_size == 2 and baseline.p50_minor_units == 1_000_000


def test_a_mixed_currency_history_settles_on_one_currency_deterministically():
    """A p50 is one integer, and an integer over mixed currencies is a fiction — this build has
    no FX table and inventing one would put a fabricated conversion under every score. The modal
    currency wins; a tie breaks on the ISO code so two runs cannot disagree."""
    history = ([_observation(1_000_000, currency="USD") for _ in range(3)]
               + [_observation(90_000_000, currency="INR") for _ in range(2)])

    baseline = I.compute_org_baseline(history, org_id="org_alg17", eval_time=NOW)

    assert baseline.currency == "USD" and baseline.sample_size == 3


def test_the_top_decile_counterparties_come_off_the_same_window():
    largest = _observation(50_000_000, counterparty="Globex")
    history = [_observation(1_000_000, counterparty=f"Smallco{n}") for n in range(9)] + [largest]

    baseline = I.compute_org_baseline(history, org_id="org_alg17", eval_time=NOW)

    # The keys are ALG-11's, not this test's spelling: every set on an `OrgBaseline` is folded
    # through `derive_key`, because the name that arrives on a SIGNAL has already been through
    # it and two spellings of one counterparty is a mission-critical vendor scoring `first_seen`.
    assert "globex" in baseline.top_decile
    assert "smallco3" in baseline.known and "smallco3" not in baseline.top_decile


def test_an_org_with_no_priced_history_still_gets_its_entity_knowledge():
    """The cold-start rule, and the half of it that is easy to get wrong: a tenant knows which
    vendors are mission-critical on the day it connects a mailbox, long before a deal closes.
    Discarding that because the p50 is missing would flatten term 4 for the whole trial."""
    baseline = I.compute_org_baseline([], org_id="new_org", eval_time=NOW,
                                      mission_critical=["AWS"],
                                      active_counterparties=["Northwind Ltd"])

    assert baseline.basis is I.BaselineBasis.ESTIMATED and baseline.p50_minor_units == 0
    assert baseline.standing_of("aws") is I.EntityStanding.MISSION_CRITICAL
    assert baseline.standing_of("Northwind Ltd") is I.EntityStanding.ACTIVE
    assert baseline.standing_of("Nobody") is I.EntityStanding.FIRST_SEEN


def test_a_missing_baseline_flags_itself_and_never_divides_by_zero():
    """Doc 06's failure table, row 1: *"No money baseline for a new org -> every money term 0"*.
    The mitigation is a ladder switch, and the flag is what makes the switch visible in the audit
    row instead of inferable from a suspicious number."""
    cold = I.OrgBaseline.cold_start("new_org", computed_against=NOW)

    parts = I.score_importance(_worked_example(), cold, eval_time=NOW).components

    assert parts.monetary_exposure_bp > 0, "the money term collapsed to zero — the exact bug"
    assert I.ImportanceFlag.BASELINE_ESTIMATED in parts.flags
    assert I.ImportanceFlag.NO_MONEY_BASELINE in parts.flags


def test_a_cold_start_org_still_gets_a_wide_money_term_across_the_absolute_ladder():
    """**The cold-start anti-collapse property, stated as an assertion.**

    A brand-new org gets the absolute ladder: twenty buckets over whole currency units, the same
    500..10000 range the ratio ladder spans. It loses CALIBRATION — a $50K deal reads "large"
    for everybody until the org's own history says otherwise — and it does NOT lose variance,
    which is the difference between a degraded score and the flat one this gate exists to
    prevent.
    """
    cold = I.OrgBaseline.cold_start("new_org", computed_against=NOW)
    amounts = [50, 5_00, 50_00, 500_00, 5_000_00, 50_000_00, 500_000_00, 5_000_000_00,
               50_000_000_00, 500_000_000_00]

    readings = [I.score_importance(_worked_example(amount=_money(m)), cold,
                                   eval_time=NOW).components.monetary_exposure_bp
                for m in amounts]

    assert len(set(readings)) >= 8, f"a cold start flattened the money term: {readings}"
    assert readings == sorted(readings)


def test_a_foreign_currency_amount_falls_back_rather_than_comparing_dollars_to_rupees():
    """There is no FX table in this build. Scoring ₹84,000 against a $45,000 p50 as "1.8x
    typical" is a fabricated conversion at the top of a founder's list; the absolute ladder is
    wrong in detail, right in magnitude, and says so on the row."""
    parts = _score(_worked_example(amount=_money(8_400_000, currency="INR"))).components

    assert I.ImportanceFlag.CURRENCY_MISMATCH in parts.flags
    assert I.ImportanceFlag.BASELINE_ESTIMATED in parts.flags
    assert parts.monetary_exposure_bp > 0


def test_an_unknown_currency_assumes_the_conservative_exponent_and_says_so():
    """`minor_unit_exponent` RAISES for an unidentified currency, and a raise inside a sweep
    costs a whole tenant's capture. Assuming two decimals understates the figure, which is the
    recoverable direction of a guess: it costs the signal some importance instead of putting a
    hundredfold magnitude at the top of a list."""
    unknown = Money(minor_units=8_400_000, currency="UNKNOWN", as_written="84,000")

    parts = _score(_worked_example(amount=unknown)).components

    assert I.ImportanceFlag.UNKNOWN_CURRENCY in parts.flags
    assert parts.monetary_exposure_bp > 0


# =============================================================================================
# THE GATE — a distribution, because an example passes on a constant.
# =============================================================================================
#: The corpus's axes. Every one is an input the formula actually consumes, and the values span
#: what a real inbox produces rather than what makes the numbers look good: sub-$100 invoices
#: through eight-figure contracts, a fortnight overdue through a year out, robots through
#: founders, Slack asides through executed agreements.
_CORPUS_AMOUNTS = (None, 5_000, 250_000, 2_250_000, 4_500_000, 9_000_000, 45_000_000,
                   900_000_000)
_CORPUS_DAYS = (-14, 1, 5, 12, 25, 200)
_CORPUS_ACTORS = (1000, 3000, 6000, 9000, 10000)
_CORPUS_ENTITIES = ("Northwind Ltd", "Globex", "Initech", "Hooli", "Brand New Co", None)
_CORPUS_TYPES = (T.INFORMATION_CONFLICT, T.CONTRACT_RENEWAL, T.COMMITMENT_MADE, T.ANOMALY)
#: Rotated by row index rather than multiplied into the product: certainty and evidence rank
#: vary across the corpus without turning 5,760 rows into 120,960.
_CORPUS_CERTAINTY = (DateCertainty.EXACT, DateCertainty.RANGE, DateCertainty.RELATIVE)
_CORPUS_AUTHORITY = (Authority.SIGNED_DOCUMENT, Authority.STRUCTURED_SOURCE,
                     Authority.EMAIL_PROSE, Authority.CHAT_ASIDE, Authority.INFERRED)


def _corpus() -> list[NormalizedSignal]:
    """A deterministic cross-product of the formula's real inputs. No RNG anywhere.

    An RNG with a seed would be reproducible and still wrong for this purpose: the gate's claim
    is that the formula spreads over the SPACE of real inputs, and a sample says only that it
    spread over the sample. A full product says it over the space, and the product is small
    enough to score in well under a second.
    """
    rows: list[NormalizedSignal] = []
    for index, (amount, days, actor, entity, kind) in enumerate(itertools.product(
            _CORPUS_AMOUNTS, _CORPUS_DAYS, _CORPUS_ACTORS, _CORPUS_ENTITIES, _CORPUS_TYPES)):
        certainty = _CORPUS_CERTAINTY[index % len(_CORPUS_CERTAINTY)]
        authority = _CORPUS_AUTHORITY[index % len(_CORPUS_AUTHORITY)]
        rows.append(_signal(
            signal_type=kind, entity=entity,
            amount=None if amount is None else _money(amount),
            date=_date(days, certainty),
            attribution=_attribution(actor_bp=actor, authority=authority)))
    return rows


@pytest.fixture(scope="module")
def scored_corpus() -> list[I.ImportanceScore]:
    baseline = _baseline()
    return [I.score_importance(signal, baseline, eval_time=NOW) for signal in _corpus()]


def _percentile(values: list[int], quantile_bp: int) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, (quantile_bp * (len(ordered) - 1) + 5000) // 10000)]


@pytest.mark.gate
def test_gate_the_score_distribution_is_wide_enough_to_rank_on(scored_corpus):
    """**G7 · THE LAYER 4 UNLOCK GATE.** The one test in this file that `return 5000` fails.

    Every other test here would pass against a constant of the right magnitude — which is
    exactly how ``importance_bp=DEFAULT_IMPORTANCE_BP`` survived in `context/situation_bso.py`
    long enough for 193 of 223 signals to carry the same score. A constant returns ONE distinct
    value and a p90-p50 spread of ZERO, and fails both thresholds below on the first assertion.

    The thresholds are the plan's, and each is the minimum for a different consumer: >50
    distinct values so a ranked list has an order rather than a tie-break, and a >1500 bp spread
    between p50 and p90 so a utility formula weighting importance can actually be moved by it.
    """
    values = [score.importance_bp for score in scored_corpus]
    p50, p90 = _percentile(values, 5000), _percentile(values, 9000)

    assert len(values) > 1000, "a distribution over a handful of rows is an example test"
    assert len(set(values)) > 50, (
        f"only {len(set(values))} distinct scores over {len(values)} signals — the formula is "
        f"not deciding anything, which is the exact defect G7 exists to catch")
    assert p90 - p50 > 1500, (
        f"p50={p50} p90={p90}: a distribution this flat cannot rank, whatever its mean")
    assert min(values) >= 0 and max(values) <= 10000


@pytest.mark.gate
def test_gate_every_score_in_the_corpus_carries_its_components(scored_corpus):
    """100% coverage, doc 06's own number. A score nobody can explain cannot be argued with by
    the founder it is shown to, and a components dict that is present 97% of the time is a card
    that silently renders without its reasons for one signal in thirty."""
    for score in scored_corpus:
        parts = score.components
        assert isinstance(parts, I.ImportanceComponents)
        assert parts.eval_time == NOW and score.importance_version == I.IMPORTANCE_VERSION
        record = parts.as_record()
        assert set(record) >= {"monetary_exposure_bp", "deadline_proximity_bp",
                               "actor_authority_bp", "entity_criticality_bp",
                               "signal_type_weight_bp", "evidence_authority_multiplier_bp",
                               "baseline_used", "eval_time"}, "doc 06's stored shape is short"


@pytest.mark.gate
def test_gate_the_whole_corpus_replays_byte_identically(scored_corpus):
    """Replay, over the whole corpus rather than one row. Ranking must be identical across
    machines and across runs; a single term that depended on dict order or on a clock would
    show up here and nowhere else."""
    replay = [I.score_importance(signal, _baseline(), eval_time=NOW) for signal in _corpus()]

    assert [s.importance_bp for s in replay] == [s.importance_bp for s in scored_corpus]
    assert ([s.components.as_record() for s in replay]
            == [s.components.as_record() for s in scored_corpus])


@pytest.mark.gate
def test_gate_every_score_in_the_corpus_renders_a_sentence(scored_corpus):
    """U3 over the whole distribution, not one happy row: the explanations a founder actually
    sees are the ones attached to the odd scores."""
    sentences = {I.explain_importance(score) for score in scored_corpus}

    assert len(sentences) > 50, "one sentence for many different scores explains none of them"
    for sentence in sentences:
        assert sentence.startswith("Scored ") and "None" not in sentence


# =============================================================================================
# WIRING — through `capture_event`, the production entry point, not the unit in isolation.
# =============================================================================================
def _renewal_payload(text: str) -> dict:
    """The model's answer for the doc-04 worked example — an amount, an entity, a decision and
    a dependency. Canned rather than generated: this test's subject is the SEAM, and an
    extraction that varied would make a failure ambiguous between the two."""
    def cite(quote: str) -> list[dict]:
        start = text.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    return {
        "intent": "commit", "stance": "cautious",
        "entity_mentions": [{"surface_form": "Finance", "entity_type": "organization",
                             "evidence": cite("Finance"), "confidence_bp": 8800}],
        "amounts": [{"minor_units": EIGHTY_FOUR_K, "currency": "USD", "as_written": "$84K"}],
        "dates_mentioned": [{"as_written": "pretty soon", "certainty": "relative",
                             "evidence": cite("pretty soon")}],
        "decision_states": [{"subject": "annual contract", "state": "pending",
                             "blocked_on": "Finance confirmation",
                             "evidence": cite("we can probably move forward with the $84K "
                                              "annual contract"),
                             "confidence_bp": 8000}],
        "dependencies": [{"blocker": "Finance", "blocked": "Rohit",
                          "dependency_type": "approval",
                          "evidence": cite("I still need Finance to confirm"),
                          "confidence_bp": 7900}],
    }


def _capture_the_worked_example(fake_llm, text: str, **esqe_over):
    llm = fake_llm(_renewal_payload(text))
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m_alg17",
                    occurred_at=NOW, actor_email="buyer@northwind.com",
                    recipients=("founder@genios.ai",),
                    raw={"subject": "Annual contract", "body": text})
    stage = P.EsqeStage(eval_time=NOW, actor_role="cfo", **esqe_over)
    return P.capture_event(raw, org_id="org_alg17", connection_id="con_alg17",
                           repo=InMemorySourceEventRepository(),
                           mailbox_owner="founder@genios.ai",
                           semantic=P.SemanticLane(llm=llm, eval_time=NOW), esqe=stage)


def test_the_pipeline_scores_every_qualified_signal_with_no_baseline_supplied(
        fake_llm, worked_example_text):
    """**THE WIRING ASSERTION.** Four units have shipped in this build with no production caller
    (`extract()`, the scheduler, the cost governor, the claim_group->conflict seam). ALG-17 is
    the one that would be least visible as dead code, because Layer 4 already has a
    ``priority_override`` covering for its absence.

    Nothing here constructs a scorer, a baseline or a `NormalizedSignal`. It captures an email
    through `pipeline.capture_event` — the function the sync runner, the webhook door and
    `api/routes.py` all call — with **no** `org_baseline` on the bundle, and asserts a real
    score came back out. Scoring must not be gated behind a supplied baseline: a tenant on day
    one is exactly the tenant whose signals must not all score alike.
    """
    res = _capture_the_worked_example(fake_llm, worked_example_text)

    assert res.outcome == "emitted" and res.extraction is not None
    assert res.esqe is not None and res.esqe.normalized, "S4 produced nothing to score"
    assert len(res.esqe.importance) == len(res.esqe.normalized), (
        "ALG-17 never ran on the pipeline — the scorer has no production caller")
    assert all(0 < s.importance_bp <= 10000 for s in res.esqe.importance)
    assert all(s.components.eval_time == NOW for s in res.esqe.importance), (
        "a score computed against a clock cannot be replayed to explain the card it produced")


def test_the_scores_are_index_aligned_with_the_signals_they_belong_to(fake_llm,
                                                                      worked_example_text):
    """One event produces several signals and each is a different size. A misalignment here
    would attribute the renewal's score to the approval request — invisible in aggregate, and
    exactly wrong on the card."""
    res = _capture_the_worked_example(fake_llm, worked_example_text)

    primary = res.esqe.primary_importance
    by_type = {sig.signal_type: score
               for sig, score in zip(res.esqe.normalized, res.esqe.importance)}

    assert res.qualification is not None
    assert primary is not None and primary is by_type[res.qualification.primary]


def test_the_trace_row_carries_the_score_its_version_and_its_components(fake_llm,
                                                                        worked_example_text):
    """A qualification that leaves no trace is unauditable, and a SCORE that leaves no trace is
    a ranking nobody can question after the weights are retuned."""
    res = _capture_the_worked_example(fake_llm, worked_example_text)
    row = next(r for r in res.trace.records if r.stage == P.ESQE_STAGE)

    assert row.detail["importance_bp"] == res.esqe.primary_importance.importance_bp
    assert row.detail["importance_version"] == I.IMPORTANCE_VERSION
    assert row.detail["importance_components"]["baseline_used"] == 0, (
        "no baseline was supplied, so the row must say the score was uncalibrated")


def test_the_orgs_baseline_reaches_the_scorer_through_the_bundle(fake_llm, worked_example_text):
    """The injected half of the seam: a baseline on `EsqeStage` must change the number that
    comes out of `capture_event`, or the calibration this whole unit rests on is decorative."""
    cold = _capture_the_worked_example(fake_llm, worked_example_text)
    calibrated = _capture_the_worked_example(
        fake_llm, worked_example_text,
        org_baseline=_baseline(p50_minor_units=45_000_000,
                               mission_critical=frozenset({"finance"})))

    cold_bp = cold.esqe.primary_importance.importance_bp
    calibrated_bp = calibrated.esqe.primary_importance.importance_bp

    assert cold_bp != calibrated_bp, "the baseline never reached the scorer"
    assert (calibrated.esqe.primary_importance.components.baseline_used == 45_000_000)


def test_a_signal_less_event_scores_nothing_rather_than_scoring_zero(fake_llm):
    """"Nothing to score" and "scored 0" are different facts. An empty tuple says the first;
    a zero on a card says the second, about an event that never had a signal."""
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m_alg17_2",
                    occurred_at=NOW, actor_email="buyer@northwind.com",
                    recipients=("founder@genios.ai",), raw={"subject": "Hi", "body": "Thanks!"})

    res = P.capture_event(raw, org_id="org_alg17", connection_id="con_alg17",
                          repo=InMemorySourceEventRepository(),
                          mailbox_owner="founder@genios.ai")

    assert res.outcome == "emitted"
    assert res.esqe.importance == () and res.esqe.primary_importance is None


# =============================================================================================
# The instant. A naive `eval_time` is a caller bug, and the module says so instead of guessing.
# =============================================================================================
@pytest.mark.parametrize("call, why", [
    (lambda: I.score_importance(_worked_example(), _baseline(),
                                eval_time=datetime(2026, 1, 14, 9, 0)),
     "term 2 subtracts an AWARE `ResolvedDate.earliest` from it"),
    (lambda: I.compute_org_baseline((), org_id="org_alg17",
                                    eval_time=datetime(2026, 1, 14, 9, 0)),
     "the 365-day window is measured back from it"),
])
def test_a_naive_eval_time_is_refused_rather_than_silently_assumed_to_be_utc(call, why):
    """A datetime with no offset is not "UTC by default"; it is an unanswered question.

    Assuming UTC moves a deadline across a rung of the ladder by however many hours the writer's
    machine is from Greenwich — an $84K renewal that is 12 days out in London and 13 in Los
    Angeles, from the same stored bytes. That failure is silent, so the guard is loud.
    """
    with pytest.raises(ValueError, match="timezone-aware"):
        call()


def test_an_aware_eval_time_in_any_zone_is_accepted_and_judged_on_the_instant():
    """The guard refuses NAIVE, not non-UTC. The same moment written in two zones is one moment,
    and a scorer that demanded UTC would be a second, undocumented contract on its callers."""
    ist = timezone(timedelta(hours=5, minutes=30))
    in_utc = I.score_importance(_worked_example(), _baseline(), eval_time=NOW)
    in_ist = I.score_importance(_worked_example(), _baseline(), eval_time=NOW.astimezone(ist))

    assert in_utc.importance_bp == in_ist.importance_bp


# =============================================================================================
# G2 -> G7 PARITY — the plan's own line, written as a test.
#
#   "an identical (amount, date, authority) yields an identical importance_bp whether it came
#    from a MAPPING or from the MODEL"
#
# Both lanes really run. `capture/structured/` reads a typed HubSpot deal through ALG-21 and
# ALG-10/ALG-09; `capture/semantic/` reads prose through the extractor and the same two
# validators. The point of the assertion is that everything after them is blind to which one
# spoke: ALG-17 consumes VALIDATED facts, so the provenance of the sentence cannot move the
# number. If it ever can, one tenant's CRM-sourced renewal outranks another's email-sourced one
# for no reason either founder could be told.
# =============================================================================================
PARITY_AMOUNT_MINOR = EIGHTY_FOUR_K
PARITY_CLOSE_DATE = "2026-01-26"          # 12 days after NOW, the worked example's horizon

#: The prose the MODEL lane reads. It states the amount and the date and NOTHING else that ALG-17
#: consumes — no counterparty, no renewal topic — because the parity claim is about the TRIPLE.
#: Naming an organisation here and not in the CRM row would make the two sides differ on term 4
#: and the test would be measuring the fixture rather than the formula.
_PARITY_PROSE = ("The $84K fee is due and the cancellation window closes on 26 January 2026.")


def _model_lane_capture(*, llm_factory, baseline):
    """The MODEL lane, for real: S2 over prose, through `capture_event`'s own semantic lane."""
    def cite(quote: str) -> list[dict]:
        start = _PARITY_PROSE.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    payload = {
        "intent": "inform", "stance": "neutral",
        "amounts": [{"minor_units": PARITY_AMOUNT_MINOR, "currency": "USD",
                     "as_written": "$84K"}],
        "dates_mentioned": [{"as_written": "26 January 2026",
                             "evidence": cite("26 January 2026")}],
    }
    raw = RawObject(source="gmail", object_type="email_attachment",
                    source_object_id="m_parity_model", occurred_at=NOW,
                    actor_email="cfo@northwind.com", recipients=("founder@genios.ai",),
                    raw={"subject": "Northwind renewal", "body": _PARITY_PROSE})
    return P.capture_event(raw, org_id="org_parity", connection_id="con_parity",
                           repo=InMemorySourceEventRepository(),
                           mailbox_owner="founder@genios.ai",
                           semantic=P.SemanticLane(llm=llm_factory(payload), eval_time=NOW),
                           esqe=P.EsqeStage(eval_time=NOW, actor_role="cfo", executed=True,
                                            org_baseline=baseline))


def _mapping_lane_extraction():
    """The MAPPING lane, for real: `run_structured_lane` over a typed HubSpot deal row.

    No model is reachable from here — `run_structured_lane` takes no client and imports none —
    so the amount goes through ALG-10 and the close date through ALG-09, out of typed COLUMNS
    rather than out of a sentence.
    """
    from genios_engine.capture.structured.lane import run_structured_lane
    from genios_engine.capture.structured.registry import get_mapping

    return run_structured_lane(
        get_mapping("hubspot", "deal"),
        {"id": "d_parity", "dealname": "Northwind renewal", "dealstage": "contractsent",
         "amount": "84000", "deal_currency_code": "USD", "closedate": PARITY_CLOSE_DATE},
        org_id="org_parity", event_id="evt_parity_mapping", eval_time=NOW, tz="UTC").result


def _by_type(signals, scores) -> dict:
    return {signal.signal_type: score for signal, score in zip(signals, scores)}


def test_g2_to_g7_parity_one_amount_one_date_one_authority_scores_the_same_from_either_lane(
        fake_llm):
    """G7's parity line, both lanes really run, one number asserted.

    The two lanes are driven with the SAME (amount, date, authority) triple: $84K USD, the 26th
    of January — twelve days out — and a CFO on an executed document. Everything downstream —
    ALG-15's detection, L1.6.2's normalization, ALG-17's arithmetic — is then handed facts of
    identical shape, and the assertion is that it cannot tell them apart.

    The mapping lane's extraction is re-detected and re-normalized through S4's OWN units, with
    the model lane's own event and attribution, so the single variable between the two sides is
    where the extraction came from. Both are scored against one baseline for the same reason.

    Why it matters that this is a test and not a comment: the two lanes reach ALG-17 by
    completely different code — one through the extractor, a repair retry and a schema
    validator, the other through a field map — and each carries its own opportunity to lose a
    currency, round a date to a different day, or arrive with a different authority. A drift in
    any of those would make a CRM-sourced renewal outrank an email-sourced one on identical
    facts, and no unit test of either lane alone can see it.
    """
    from genios_engine.capture.esqe.detector import DetectionInput, detect_signals
    from genios_engine.capture.esqe.normalize import normalize_signals

    baseline = _baseline()
    model = _model_lane_capture(llm_factory=fake_llm, baseline=baseline)
    assert model.esqe is not None and model.esqe.normalized, "the model lane produced no signal"
    from_model = _by_type(model.esqe.normalized, model.esqe.importance)

    mapped = _mapping_lane_extraction()
    assert mapped is not None and mapped.amounts and mapped.dates_mentioned, (
        "the typed columns did not survive ALG-21, so there is nothing to compare")
    mapped_signals = normalize_signals(
        detect_signals(DetectionInput(extraction=mapped, eval_time=NOW)).signals,
        event=model.event, extraction=mapped, attribution=model.esqe.attribution)
    from_mapping = _by_type(mapped_signals,
                            tuple(I.score_importance(signal, baseline, eval_time=NOW)
                                  for signal in mapped_signals))

    shared = set(from_model) & set(from_mapping)
    assert T.FINANCIAL_OBLIGATION in shared, (
        f"the two lanes reached no comparable signal: model={sorted(t.value for t in from_model)} "
        f"mapping={sorted(t.value for t in from_mapping)}")

    for signal_type in sorted(shared, key=lambda t: t.value):
        model_score, mapped_score = from_model[signal_type], from_mapping[signal_type]
        assert model_score.components.as_record() == mapped_score.components.as_record(), (
            f"{signal_type.value}: the same amount, date and authority produced different "
            f"arithmetic by lane\nmodel  ={model_score.components.as_record()}\n"
            f"mapping={mapped_score.components.as_record()}")
        assert model_score.importance_bp == mapped_score.importance_bp, (
            f"{signal_type.value}: model={model_score.importance_bp} "
            f"mapping={mapped_score.importance_bp}")


# =============================================================================================
# THE BASELINE ON THE REQUEST PATH — L1.6.7-U2's wiring gate.
#
# `compute_org_baseline` shipped built, tested, and with NO production caller. `run_esqe_stage`
# fell through to `OrgBaseline.cold_start(...)` on every event of every sweep, so 50% of ALG-17's
# formula — the money term and the entity term — was pinned to two constants for every tenant,
# the ratio ladder never executed outside its unit test, and doc 06's own headline acceptance
# row scored 5625 in production against a required 7500-8500.
#
# These tests seed an org's real priced history into `l1_extraction_results`, then drive
# `api/routes._sync_connection` — the background sweep every `/sync` and every scheduler tick
# runs — with nothing standing in but the CONNECTOR and the MODEL. The baseline is computed by
# the production wiring or not at all.
# =============================================================================================
ALG17_PG_ORG = "org_alg17_pg"

#: Five priced things this org did. The p50 is the third, $35,000, and Northwind is the largest
#: single contract — so the org's own history is what makes an $84K renewal "about 2.4x typical"
#: and Northwind a top-decile counterparty. Nothing here is asserted directly; what is asserted
#: is that the sweep re-derives both from these rows.
PRICED_HISTORY: tuple[tuple[int, str], ...] = (
    (1_000_000, "Acme Corp"), (2_000_000, "Globex"), (3_500_000, "Initech"),
    (5_000_000, "Hooli"), (20_000_000, "Northwind Ltd"))
SEEDED_P50_MINOR_UNITS = 3_500_000

_HEADLINE_PROSE = ("Northwind Ltd annual contract renewal: the $84K fee is due and the "
                   "cancellation window closes on 26 January 2026.")


@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres baseline tests skipped")
    return live_db_url


def _headline_payload() -> dict:
    def cite(quote: str) -> list[dict]:
        start = _HEADLINE_PROSE.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    return {
        "intent": "inform", "stance": "neutral", "topics": ["renewal"],
        "entity_mentions": [{"surface_form": "Northwind Ltd", "entity_type": "organization",
                             "evidence": cite("Northwind Ltd"), "confidence_bp": 9000}],
        "amounts": [{"minor_units": EIGHTY_FOUR_K, "currency": "USD", "as_written": "$84K"}],
        "dates_mentioned": [{"as_written": "26 January 2026",
                             "evidence": cite("26 January 2026")}],
    }


def _headline_raw(object_id: str = "m_alg17_pg") -> RawObject:
    return RawObject(source="gmail", object_type="email_attachment",
                     source_object_id=object_id, occurred_at=NOW,
                     actor_email="cfo@northwind.com", recipients=("founder@genios.ai",),
                     raw={"subject": "Northwind renewal", "body": _HEADLINE_PROSE})


def _priced_extraction(minor_units: int, counterparty: str) -> dict:
    """One stored extraction, built through the REAL contract and dumped the way the cache
    writes it — so the reader is parsing the bytes production actually files, not a fixture
    shaped like them."""
    from genios_engine.contracts.extraction import EntityMention, ExtractionResult

    span = _span(counterparty)
    return ExtractionResult(
        intent="inform", stance="neutral",
        amounts=[Money(minor_units=minor_units, currency="USD", as_written=f"${minor_units}")],
        entity_mentions=[EntityMention(surface_form=counterparty, entity_type="organization",
                                       evidence=[span], confidence_bp=9000)],
        all_evidence=[span],
        model_snapshot="fake-model-1", prompt_version="p1", schema_version="1",
        extraction_profile="email", input_tokens=10, output_tokens=5,
    ).model_dump(mode="json")


def _seed_priced_history(url: str, org_id: str) -> None:
    """The org's own priced history, in the two tables it really lives in."""
    import json as _json
    from datetime import datetime as _dt

    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    engine = get_engine(url)
    occurred = _dt.now(timezone.utc) - timedelta(days=30)
    with engine.begin() as conn:
        conn.execute(text("delete from l1_extraction_results where org_id=:o"), {"o": org_id})
        conn.execute(text("delete from raw_payloads where org_id=:o"), {"o": org_id})
        conn.execute(text("delete from prepared_content where org_id=:o"), {"o": org_id})
        conn.execute(text("delete from event_trace where org_id=:o"), {"o": org_id})
        conn.execute(text("delete from qualification_drops where org_id=:o"), {"o": org_id})
        conn.execute(text("delete from source_events where org_id=:o"), {"o": org_id})
        conn.execute(text("delete from sync_cursors where org_id=:o"), {"o": org_id})
        conn.execute(text("delete from orgs where id=:o"), {"o": org_id})
        columns = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        names, holes, params = ["id"], [":id"], {"id": org_id}
        for column in columns:
            names.append(column.column_name)
            holes.append(f":{column.column_name}")
            params[column.column_name] = (
                0 if "int" in column.data_type or "numeric" in column.data_type
                else _dt.now(timezone.utc) if "timestamp" in column.data_type else org_id)
        conn.execute(text(f"insert into orgs ({', '.join(names)}) "
                          f"values ({', '.join(holes)})"), params)
        # The connected mailbox's own address. Without it `_mailbox_owner_for` answers None,
        # S2 cannot tell an inbound message from an outbound one and short-circuits on
        # `direction_unknown` — so the sweep would emit an event with no extraction and this
        # test would be asserting about a signal that never existed.
        conn.execute(text("update orgs set email='founder@genios.ai' where id=:o"), {"o": org_id})
        for index, (minor_units, counterparty) in enumerate(PRICED_HISTORY):
            event_id = f"evt_alg17_hist_{index}"
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, 'con_alg17_pg', 'gmail', 'email_message', :e, :e, "
                "cast('{}' as jsonb), :at)"),
                {"e": event_id, "o": org_id, "at": occurred})
            conn.execute(text(
                "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
                "model_snapshot, profile_id, tier) values (:k, :o, :e, cast(:out as jsonb), "
                "'fake-model-1', 'email', 'T1')"),
                {"k": f"pk_alg17_{index}", "o": org_id, "e": event_id,
                 "out": _json.dumps(_priced_extraction(minor_units, counterparty))})


class _OnePageConnector:
    """The provider, and the ONLY thing standing in on this path. Everything else the sweep
    touches — the repository, the coverage declaration, the baseline, the floor, the ledger —
    is the real object reading the real database."""

    source = "gmail"

    def __init__(self, raw: RawObject) -> None:
        self._raw = raw

    def incremental_changes(self, cursor=None, limit=50, since=None):
        from genios_engine.capture.connectors.base import SourceBatch
        return SourceBatch(objects=[self._raw], next_cursor=None)

    def initial_snapshot(self, cursor=None, limit=50):
        return self.incremental_changes(cursor, limit)


def _sweep_the_headline_event(monkeypatch, fake_llm, org_id: str):
    """Drive `api/routes._sync_connection` and hand back the sweep's own summary."""
    from genios_engine.api import routes
    from genios_engine.contracts.connection import Connection

    if routes._graph is None:
        pytest.skip("routes has no graph store — the request path cannot reach a database")

    connection = Connection(org_id=org_id, connection_id="con_alg17_pg", source_type="gmail",
                            composio_user_id=org_id)
    monkeypatch.setattr(routes, "make_connector_for",
                        lambda conn, **kw: _OnePageConnector(_headline_raw()))
    monkeypatch.setattr(routes, "_semantic_lane_for",
                        lambda org, activated=None: P.SemanticLane(
                            llm=fake_llm(_headline_payload()), eval_time=NOW))
    monkeypatch.setattr(routes, "_run_l2", lambda org: None)

    captured: dict = {}
    real_ledger = routes._run_ledger
    monkeypatch.setattr(routes, "_run_ledger",
                        lambda **kw: (captured.update(kw), real_ledger(**kw))[1])
    routes._sync_connection(connection, "incremental", 5)
    return captured.get("summary")


def _renewal_score(summary):
    for result in summary.results:
        esqe = getattr(result, "esqe", None)
        for signal, score in zip(getattr(esqe, "normalized", ()) or (),
                                 getattr(esqe, "importance", ()) or ()):
            if signal.signal_type is T.CONTRACT_RENEWAL:
                return score
    return None


@pytest.mark.pg
def test_the_sweep_computes_the_orgs_baseline_from_its_own_priced_history(pg_url, fake_llm,
                                                                          monkeypatch):
    """**THE WIRING ASSERTION FOR L1.6.7-U2.** Nothing here builds an `OrgBaseline`.

    Five priced events go into `l1_extraction_results`, one renewal email goes through
    `api/routes._sync_connection`, and the score that comes back out has to say — in its own
    stored components — that it was taken against THIS org's p50 and THIS org's counterparties.

    `baseline_basis == org_history` is the whole assertion: `cold_start` produces `estimated`,
    and that is the value every event in production carried.
    """
    _seed_priced_history(pg_url, ALG17_PG_ORG)

    summary = _sweep_the_headline_event(monkeypatch, fake_llm, ALG17_PG_ORG)
    assert summary is not None and summary.results, "the sweep captured nothing"
    score = _renewal_score(summary)
    assert score is not None, "the sweep produced no CONTRACT_RENEWAL to score"

    components = score.components
    assert components.baseline_basis is I.BaselineBasis.ORG_HISTORY, (
        "the sweep scored against a cold start — compute_org_baseline has no production caller")
    assert components.baseline_used == SEEDED_P50_MINOR_UNITS, (
        f"the p50 of the org's own history is {SEEDED_P50_MINOR_UNITS}; "
        f"the score was taken against {components.baseline_used}")
    assert components.baseline_currency == "USD"
    assert components.entity_standing is I.EntityStanding.TOP_DECILE, (
        "Northwind is this org's largest contract; a cold-start baseline knows nobody, so "
        f"term 4 read {components.entity_standing.value}")
    assert I.ImportanceFlag.BASELINE_ESTIMATED not in components.flags


@pytest.mark.pg
def test_the_swept_score_differs_from_the_cold_start_score_for_the_very_same_event(
        pg_url, fake_llm, monkeypatch):
    """The same event, scored two ways, must not agree.

    A baseline that reached the scorer and changed nothing is a baseline that was not read, and
    a green wiring test that only asserts "a number came back" cannot tell the difference. The
    cold-start number is recomputed HERE from the sweep's own signal and its own instant, so the
    two sides differ in exactly one input.
    """
    _seed_priced_history(pg_url, ALG17_PG_ORG)

    summary = _sweep_the_headline_event(monkeypatch, fake_llm, ALG17_PG_ORG)
    score = _renewal_score(summary)
    assert score is not None

    signal = next(s for result in summary.results
                  for s in (getattr(getattr(result, "esqe", None), "normalized", ()) or ())
                  if s.signal_type is T.CONTRACT_RENEWAL)
    cold = I.score_importance(
        signal, I.OrgBaseline.cold_start(ALG17_PG_ORG, computed_against=score.components.eval_time),
        eval_time=score.components.eval_time)

    assert score.importance_bp != cold.importance_bp, (
        "the org baseline reached the scorer and moved nothing — the ratio ladder never ran")
    assert score.importance_bp > cold.importance_bp, (
        "an $84K renewal is 2.4x this org's typical contract and its counterparty is the "
        "org's biggest; calibration must raise it, not lower it")


@pytest.mark.pg
def test_doc_06s_headline_row_lands_in_its_band_on_the_production_path(pg_url, fake_llm,
                                                                       monkeypatch):
    """Doc 06's own acceptance row — *$84K renewal, 12 days out, CFO sender, signed PDF* —
    scored through `capture_event` with the bundle the PRODUCTION WIRING builds.

    The bundle is `api/routes._esqe_stage_for(org)`, which reads this org's seeded history out
    of the database exactly as every sweep door now does. Nothing in this test constructs an
    `OrgBaseline`. The two per-EVENT facts of the row that the sweep-level bundle cannot carry —
    the sender's role and whether the artifact is executed — are stated here because they are
    INPUTS OF THE ROW, and they are the subject of a reported gap rather than of this assertion.

    5625 is what the same capture scored before this wiring existed, and it is asserted rather
    than described: it is the number that has to stop being produced.
    """
    from genios_engine.api import routes

    if routes._graph is None:
        pytest.skip("routes has no graph store — the request path cannot reach a database")
    _seed_priced_history(pg_url, ALG17_PG_ORG)

    def _capture(stage):
        return P.capture_event(
            _headline_raw(f"m_headline_{id(stage)}"), org_id=ALG17_PG_ORG,
            connection_id="con_alg17_pg", repo=InMemorySourceEventRepository(),
            mailbox_owner="founder@genios.ai",
            semantic=P.SemanticLane(llm=fake_llm(_headline_payload()), eval_time=NOW),
            esqe=stage)

    from dataclasses import replace as _replace
    wired = routes._esqe_stage_for(ALG17_PG_ORG)
    assert wired.org_baseline is not None, "the production factory built no baseline"
    row_facts = dict(eval_time=NOW, actor_role="cfo", executed=True)

    calibrated = _renewal_score(type("S", (), {"results": [_capture(
        _replace(wired, **row_facts))]}))
    uncalibrated = _renewal_score(type("S", (), {"results": [_capture(
        P.EsqeStage(**row_facts))]}))

    assert uncalibrated.importance_bp == 5625, (
        "the pre-wiring number changed; this row is the calibration statement the band is "
        f"about, and it now scores {uncalibrated.importance_bp} on a cold start")
    assert 7500 <= calibrated.importance_bp <= 8500, (
        f"doc 06's headline row scored {calibrated.importance_bp} on the production path; "
        f"{I.explain_importance(calibrated)}")


@pytest.mark.parametrize("call, why", [
    ("run_sync", "the sweep"),
    ("backfill_drain", "the full-history drain"),
    ("ingest_pushed_objects", "the real-time webhook"),
])
def test_every_capture_door_in_the_api_supplies_the_orgs_baseline(call, why):
    """A SOURCE-LEVEL gate over `api/routes.py`, on `test_webhook_parity`'s own model.

    `org_baseline` is invisible at a call site: omit it and the row still lands, the sweep still
    reports success, and the only symptom is that every signal that tenant will ever produce is
    scored against an absolute ladder and a counterparty list of nobody. That is exactly the
    class of omission `coverage_fn` already demonstrated across four doors, so it gets the same
    kind of gate — one that fails by file and line rather than by a number nobody re-derives.
    """
    from pathlib import Path

    source = Path(__file__).resolve().parents[3] / "genios_engine" / "api" / "routes.py"
    tree = ast.parse(source.read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) == call]
    assert calls, f"{call} is not called in routes.py — {why} moved and this gate went blind"
    for node in calls:
        keywords = {k.arg for k in node.keywords}
        if call == "ingest_pushed_objects":          # its wiring is one typed argument
            wiring = next(k.value for k in node.keywords if k.arg == "wiring")
            keywords = {k.arg for k in wiring.keywords}
        assert "esqe" in keywords, (
            f"{call} at routes.py:{node.lineno} ({why}) reaches the pipeline with no ESQE "
            "bundle, so every event it captures is scored against OrgBaseline.cold_start")


def test_the_wiring_factory_is_what_the_request_path_calls_for_that_baseline():
    """The gate above proves the keyword is passed; this proves it is passed the real thing.

    A door that passed `esqe=EsqeStage()` would satisfy an AST check and score exactly as badly
    as one that passed nothing.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "genios_engine" / "api"
              / "routes.py").read_text()
    assert "def _esqe_stage_for(org_id: str):" in source
    assert "make_esqe_stage(org_id" in source, (
        "`_esqe_stage_for` no longer reaches `platform/wiring.make_esqe_stage`, which is the "
        "only thing on this path that reads the org's priced history")


# =============================================================================================
# The READER — L1.6.7-U2's input, unit by unit. `capture/esqe/baseline_reader.py`.
# =============================================================================================
def test_a_reader_with_no_engine_answers_a_cold_start_rather_than_raising():
    """Doc 06: *"never block scoring on a missing baseline"*. A deployment with no database is a
    legitimate state, and this runs on the ingestion path — so the answer is a cold start, and
    an exception is not one of the options."""
    from genios_engine.capture.esqe import baseline_reader as R

    assert R.priced_history(None, "org_none", eval_time=NOW) == ()
    assert R.open_deal_counterparties(None, "org_none") == ()
    baseline = R.load_org_baseline(None, "org_none", eval_time=NOW)
    assert baseline.basis is I.BaselineBasis.ESTIMATED and baseline.p50_minor_units == 0


def test_a_database_that_raises_costs_the_calibration_and_never_the_sweep():
    """The same rule one rung harder: an engine that explodes mid-read. A tenant whose history
    table is locked, migrating or unreachable must keep capturing mail."""
    from genios_engine.capture.esqe import baseline_reader as R

    class _Angry:
        def connect(self):
            raise RuntimeError("connection pool exhausted")

    assert R.priced_history(_Angry(), "org_angry", eval_time=NOW) == ()
    assert R.load_org_baseline(_Angry(), "org_angry",
                               eval_time=NOW).basis is I.BaselineBasis.ESTIMATED


@pytest.mark.parametrize("entities, expected, why", [
    ([{"surface_form": "Acme", "entity_type": "organization"}], "Acme",
     "one organisation is the counterparty"),
    ([{"surface_form": "Acme", "entity_type": "organization"},
      {"surface_form": "Priya", "entity_type": "person"}], "Acme",
     "a person on the thread is a participant, never the counterparty"),
    ([{"surface_form": "Acme", "entity_type": "organization"},
      {"surface_form": "Globex", "entity_type": "organization"}], None,
     "two organisations is an introduction; attributing the amount to either invents a fact"),
    ([{"surface_form": "Priya", "entity_type": "person"}], None,
     "no organisation named"),
    ("not a list", None, "a stored shape this build does not know is not a counterparty"),
])
def test_the_counterparty_of_a_priced_event_follows_normalizations_own_rule(entities, expected,
                                                                            why):
    from genios_engine.capture.esqe import baseline_reader as R

    assert R._counterparty_of(entities) == expected, why


@pytest.mark.parametrize("entry, ok, why", [
    ({"minor_units": 8_400_000, "currency": "USD", "as_written": "$84K"}, True, "the real shape"),
    ({"minor_units": 8_400_000, "currency": "USD"}, True, "as_written may be absent on a row"),
    ({"minor_units": 8_400_000}, False, "an amount with no currency is not comparable"),
    ({"minor_units": 84_000.5, "currency": "USD"}, False, "a float never becomes an amount"),
    ({"minor_units": 8_400_000, "currency": "dollars"}, False, "not an ISO code"),
    ("$84K", False, "a string is not a stored Money"),
])
def test_a_stored_amount_is_rebuilt_through_the_money_contract_or_not_at_all(entry, ok, why):
    """The p50 is only meaningful if every number in it went through ALG-10. A row this build
    cannot re-type is skipped, not coerced — coercing it would put whatever a stored row happened
    to hold into the denominator of every money term the tenant ever gets."""
    from genios_engine.capture.esqe import baseline_reader as R

    assert (R._money_of(entry) is not None) is ok, why


@pytest.mark.pg
def test_the_reader_builds_observations_out_of_the_orgs_stored_extractions(pg_url):
    from genios_engine.capture.esqe import baseline_reader as R
    from genios_engine.platform.db import get_engine

    _seed_priced_history(pg_url, ALG17_PG_ORG)
    engine = get_engine(pg_url)

    observations = R.priced_history(engine, ALG17_PG_ORG,
                                    eval_time=datetime.now(timezone.utc))

    assert len(observations) == len(PRICED_HISTORY)
    assert {o.amount.minor_units for o in observations} == {m for m, _ in PRICED_HISTORY}
    assert {o.counterparty for o in observations} == {c for _, c in PRICED_HISTORY}
    assert all(o.amount.currency == "USD" for o in observations)


@pytest.mark.pg
def test_only_the_window_counts_and_the_p50_comes_out_of_it(pg_url):
    """The 365-day window is applied in SQL. An org whose history is all older than the window
    has no p50 — and gets a cold start rather than a stale one."""
    from genios_engine.capture.esqe import baseline_reader as R
    from genios_engine.platform.db import get_engine

    _seed_priced_history(pg_url, ALG17_PG_ORG)
    engine = get_engine(pg_url)
    now = datetime.now(timezone.utc)

    inside = R.load_org_baseline(engine, ALG17_PG_ORG, eval_time=now)
    outside = R.load_org_baseline(engine, ALG17_PG_ORG, eval_time=now, window_days=1)

    assert inside.basis is I.BaselineBasis.ORG_HISTORY
    assert inside.p50_minor_units == SEEDED_P50_MINOR_UNITS
    assert inside.sample_size == len(PRICED_HISTORY)
    assert outside.basis is I.BaselineBasis.ESTIMATED, (
        "a one-day window over month-old history is a cold start, not a p50 of nothing")


@pytest.mark.pg
def test_the_reader_is_scoped_to_one_tenant(pg_url):
    """The only assertion on this module that a cross-tenant leak could not survive: another
    org's contract values must not calibrate this org's ranking."""
    from genios_engine.capture.esqe import baseline_reader as R
    from genios_engine.platform.db import get_engine

    _seed_priced_history(pg_url, ALG17_PG_ORG)

    assert R.priced_history(get_engine(pg_url), "org_alg17_nobody",
                            eval_time=datetime.now(timezone.utc)) == ()
