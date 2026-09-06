"""L2 · Situation Engine — the object reasoning actually consumes.

A correlation says "these events are about the same thing". A situation says what that
thing IS, in terms an executive would use: an opportunity, a support case, a relationship
— with how sure we are, how current it is, and what we still do not know.

The Reasoning Engine should never wake up and ask for the graph. It should ask for the
active situations. Traversing nodes and edges to rebuild context on every question is not
thinking; it is assembling. Assembling happens here, once.

WHAT A SITUATION IS NOT
It carries no priority, no risk score and no recommendation. Those are decisions, and
decisions belong to the layer that is allowed to have opinions. This layer answers only
"what is true right now, and how sure are we" — the same discipline the correlation
engine and the context graph already keep.

(The architecture notes list Risk Detector and Opportunity Detector inside this stage.
That contradicts their own rule that context never decides, and this codebase already
detects risk in the packs — building it here too would give two layers an opinion about
the same thing and no way to tell which one was wrong. Detection stays downstream.)

CONFIDENCE IS A VECTOR, AND `overall` IS A MINIMUM
Four dimensions describe whether you can TRUST a situation:

    evidence     how much independent material backs it
    freshness    how current that material is
    consistency  whether the sources contradict each other
    identity     whether we are sure WHO it is about

`overall` is the minimum of those, never the average. They are failure modes, not
features, and averaging lets one strong dimension hide a fatal one: perfect evidence
about an entity we cannot identify is not 60% confidence, it is unusable. You are only
as sure as your weakest link.

COVERAGE IS DELIBERATELY OUTSIDE `overall`
Completeness is a different question from correctness. Not knowing a deal's close date
does not make the stage we DO know less true. Folding coverage into overall would make
absence read as doubt — the same mistake as reading absence as negative evidence, which
this codebase already refuses everywhere else. Coverage is reported beside overall so a
reader can tell "we are unsure" apart from "we are missing pieces".

AN UNKNOWN DIMENSION IS EXCLUDED, NOT ZEROED
Evidence with no timestamps tells us nothing about currency — it does not tell us the
situation is stale. Scoring that as zero would turn missing data into bad news. A
dimension with no basis is left out of the minimum and marked, so the score says
"we cannot tell" rather than "it is old".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.domain_spec import spec_for, spec_version
from genios_engine.context.quality.lens import read_coverage_lens
from genios_engine.context.quality.missing import AbsenceSubject, refresh_typed_absences
from genios_engine.platform.ids import new_id

# Lifecycle. `dormant` is not a failure — it is a situation that has gone quiet and
# should stop competing for attention without being forgotten.
STATUS_ACTIVE = "active"
STATUS_DORMANT = "dormant"
STATUS_RESOLVED = "resolved"
STATUS_ARCHIVED = "archived"
# L2.7.7 · SOME THINGS END IN PIECES. Three of five commitments discharged is not a closed
# situation and it is not an untouched one: closing it would drop the other two silently, which
# is the exact failure ("2 obligations vanish") doc 12 case 2 names, and leaving it ACTIVE throws
# away what we just learned. A distinct state is the only shape that keeps both facts.
STATUS_PARTIALLY_RESOLVED = "partial"

# How a resolution was reached — the three behave differently when new evidence arrives.
RESOLVED_BY_FACT = "fact"      # re-derived every refresh; self-correcting
RESOLVED_BY_HUMAN = "human"    # sticks until new evidence, then reopens
# L2.7.7 · SOMEBODY SAID SO. Until this existed a situation could end only two ways — a CRM stage
# moving to closed-won, or a person clicking "handled" — so "all sorted, we signed yesterday"
# landed as fresh activity and made the situation look MORE alive than before anyone said it was
# over. Deliberately re-derived every pass, exactly like RESOLVED_BY_FACT and for the reason this
# module's own lifecycle docstring already gives: the system should not need a human to undo a
# conclusion it drew from data that has since changed. `context/lifecycle/` derives it; nothing
# else in this file may set it.
RESOLVED_BY_STATEMENT = "statement"

DORMANT_AFTER_DAYS = 45        # matches the correlation window: past it, a new
                               # generation opens and this one has genuinely ended
ARCHIVE_AFTER_DAYS = 180       # resolved and long past — out of the working set

# Deal stages that END a situation. Matched case-insensitively on a normalized form so
# "CLOSEDWON", "closed_won" and "Closed Won" all count — a CRM writes all three.
#
# This is the ONE piece of domain vocabulary left in this file, and it is here because it
# is a LIFECYCLE rule (when does a situation stop being live) rather than a statement
# about what sales means. It applies to any domain that produces a `deal.stage` fact.
_TERMINAL_DEAL_STAGES: frozenset[str] = frozenset({"closedwon", "closedlost"})


def situation_type(anchor_type: str, domain: str) -> str:
    """What kind of situation this is, per the domain's registered spec.

    An unregistered domain gets `<domain>_<anchor>` — visibly unmapped rather than
    silently filed as something it is not, and never an error. That is what lets a new
    domain start producing situations before anyone has described it.
    """
    return spec_for(domain).type_for(anchor_type)


def normalize_stage(value) -> str:
    """CRM stage → a comparable token. Strips quotes (values arrive JSON-encoded),
    punctuation and case."""
    raw = str(value or "").strip().strip('"').lower()
    return "".join(ch for ch in raw if ch.isalnum())


# ── the confidence dimensions ────────────────────────────────────────────────────

def evidence_score(*, event_count: int, source_count: int) -> int:
    """How much independent material backs this situation.

    Sources outweigh volume on purpose: twenty emails in one thread are one person's
    account of events, while an email plus a CRM record plus a calendar invite are three
    systems independently agreeing. Corroboration across tools is what makes a situation
    trustworthy, not repetition within one.

    The caps encode that — 60 available for corroboration against 40 for volume — so a
    noisy single-source thread can never outscore genuine cross-tool agreement. An
    earlier split (60 volume / 40 sources) inverted it and made this docstring a lie;
    tests/test_situations.py now pins the ordering.
    """
    volume = min(40, max(0, int(event_count)) * 8)
    corroboration = min(60, max(0, int(source_count)) * 25)
    return max(0, min(100, volume + corroboration))


def freshness_score(*, last_seen_at: datetime | None, now: datetime) -> tuple[int, bool]:
    """How current the evidence is. Returns (score, known).

    `known=False` when nothing is dated. That is NOT staleness — it is an absence of
    information about time, and the caller excludes it from the overall score rather
    than letting missing data masquerade as bad news.
    """
    if last_seen_at is None:
        return 0, False
    age_days = (now - last_seen_at).total_seconds() / 86400.0
    if age_days <= 3:
        return 100, True
    if age_days <= 7:
        return 85, True
    if age_days <= 14:
        return 70, True
    if age_days <= 30:
        return 50, True
    if age_days <= DORMANT_AFTER_DAYS:
        return 30, True
    return 10, True


def consistency_score(*, open_discrepancies: int) -> int:
    """Do the sources contradict each other about this entity?

    A discrepancy is already a recorded product signal (the CRM says closed, Slack says
    the customer is unhappy). One is a real dent in trust; three make the situation
    something a human must look at before anything acts on it.
    """
    return max(0, 100 - min(100, max(0, int(open_discrepancies)) * 34))


def identity_score(*, open_merge_proposals: int) -> int:
    """Are we sure WHO this is about?

    An unresolved duplicate means the evidence may be split across two nodes, so this
    situation is probably missing half its material — or is about the wrong entity
    entirely. Neither is a small doubt, which is why one open proposal costs so much.
    """
    if open_merge_proposals <= 0:
        return 100
    return 40 if open_merge_proposals == 1 else 20


#: THE UNIT OF EVERY SCORE ON `context_situations`. All four confidence dimensions and `coverage`
#: are an int PERCENT, 0..SCORE_MAX — never basis points. Stated as a constant because it was
#: stated NOWHERE, and three direct writers (`periodic.py` and, following it, the support and
#: document readings) picked basis points instead. The seam that punishes that is
#: `situation_bso._bp`, which multiplies the stored number by 100 and clamps at 10000: a coverage
#: honestly capped at 25 (knowledge_gap) or 30 (escalation) arrived at Layer 3 as
#: coverage_bp=10000 — full, records-grade certainty — and `expertise_builder`'s
#: `min(situation.confidence_bp, expert.coverage_bp)` had nothing left to cap. Measured on the
#: eight inferred readings whose entire honesty story IS that cap. `reason/runner.py` also
#: publishes `situation.coverage` to pack rules as a plain fact, where an authored threshold of
#: `>= 60` reads as a percent, so a stored 5000 clears every gate an author can write.
SCORE_MAX = 100

#: The score returned when a domain registers no expectations. Sentinel, not a percentage: it is
#: outside 0..100 on purpose so no consumer can average it into a number and lose the distinction
#: between "nothing is missing" and "we never said what complete means here".
COVERAGE_UNKNOWN = -1


def coverage_is_known(score: int) -> bool:
    """Whether a coverage number means anything. Gates must consult this before trusting it."""
    return score != COVERAGE_UNKNOWN


def coverage_score(*, present_fields: set[str], expected: dict[str, str]) -> tuple[int, list[str]]:
    """How complete the picture is, and the plain-language names of what is missing.

    Reported beside confidence, never inside it: not knowing a close date does not make
    the stage we do know less true.
    """
    # "We expect nothing" is neither 100% covered nor 0% known, and both readings cause harm.
    #
    # Scoring it 0 invents a gap that does not exist and makes every situation in a new domain
    # look broken the day it is added — absence read as negative evidence, which this codebase
    # refuses everywhere else.
    #
    # Scoring it 100 is what let 34 of one org's 73 situations report `missing=[]` and full
    # coverage, and it hands a downstream gate reading "no actionable output when required
    # context is unknown" a green light earned by ignorance.
    #
    # The honest answer is a third state. `coverage_status` carries it so a consumer can tell
    # "complete" from "we never said what complete means here", while the number stays neutral
    # rather than asserting either.
    if not expected:
        return COVERAGE_UNKNOWN, ["coverage unknown — no expectations registered for this domain"]
    missing = [label for f, label in sorted(expected.items()) if f not in present_fields]
    known = len(expected) - len(missing)
    return int(round(100 * known / len(expected))), missing


# ── the sixth axis: how good were the COMPARATIVE inputs? ────────────────────────
#
# L2.5.1-U1. The five axes above ask whether the situation is TRUE. This one asks whether the
# comparisons an importance number leaned on were worth leaning on.
#
# It exists because of what L2.7.4's modifiers can do: importance can be raised +1000 by a cohort
# position computed over 5 members and +1000 by a trend whose own `trend_confidence_bp` is 5000.
# The result is numerically identical to a situation whose modifiers came from a 200-member cohort
# and eight periods of history — same importance, wildly different certainty, and until this axis
# no field carried the difference. Doc 05 states the requirement in one sentence: "A situation
# whose importance leaned on a 5-member cohort should be visibly less certain than one that
# leaned on 200."
#
# WHAT IT IS NOT: it is not a second opinion about the importance number, and it never changes it.
# It describes the inputs. Deciding what to do about a thin comparison is a downstream call.

#: The inputs are read by NAME off whatever the analytic stratum hands over — a `CohortPosition`,
#: a `Trend`, an `AnomalyVerdict`, or the jsonb fact value any of those was stored as. Attributes
#: and mapping keys both, because `trend_fact_value()` and friends round-trip through jsonb and a
#: caller that read the fact back has a dict where the computer had a dataclass. Naming the four
#: fields here rather than importing the three classes also keeps `situations.py` free of a
#: dependency on `context/analytic/`, which is a heavier module than a confidence axis should pull.
ANALYTIC_POPULATION_FIELD = "population_size"        # CohortPosition.population_size
ANALYTIC_TREND_CONFIDENCE_FIELD = "trend_confidence_bp"   # Trend.trend_confidence_bp
ANALYTIC_HISTORY_FIELD = "point_count"               # Trend.point_count
ANALYTIC_ANOMALY_FIELD = "periods_used"              # AnomalyVerdict.periods_used

#: Where each input stops earning more credit. Not invented — each is the number the module that
#: produces the input already treats as "enough":
#:   200   doc 05's own comparison ("a 5-member cohort ... one that leaned on 200"); the FLOOR
#:         for a legal position is `cohort.MIN_COHORT_POPULATION` = 5, which lands near the bottom
#:         of this ramp exactly as it should.
#:   12    `trend.CONFIDENT_POINTS` — the point count that module's own confidence saturates at.
#:   6     `anomaly.BASELINE_PERIODS` — a full baseline; more periods than that are not read.
#: Spelled as literals with the provenance in this comment rather than imported, for the
#: dependency reason above; `tests/context/test_situation_confidence.py` pins them to the source
#: constants so the two cannot drift apart silently.
ANALYTIC_FULL_POPULATION = 200
ANALYTIC_FULL_TREND_CONFIDENCE_BP = 10_000
ANALYTIC_FULL_HISTORY_POINTS = 12
ANALYTIC_FULL_ANOMALY_PERIODS = 6

#: The floor every USED input keeps. A comparison against five peers is thin, not absent, and
#: scoring it 0 would say "this evidence is bad" about a measurement that was legitimately taken
#: — the same mistake `freshness_score` refuses when nothing is dated. Absence has its own answer
#: below, and it is not a number.
ANALYTIC_FLOOR = 10

#: The reason strings, which are the point of the tuple: the score says how thin, this says WHICH
#: input was the thin one. A bare number sends a reader to re-derive four sub-scores by hand.
ANALYTIC_POPULATION = "population"
ANALYTIC_TREND_CONFIDENCE = "trend_confidence"
ANALYTIC_HISTORY_DEPTH = "history_depth"
ANALYTIC_ANOMALY_PERIODS = "anomaly_periods"

#: The reason reported beside the not-applicable sentinel. "No comparison was made" is a different
#: fact from "the comparison was bad", and the string has to say so or a renderer will print
#: "weakest: population" about a situation that never touched a cohort.
ANALYTIC_NONE = "no comparative input"


def _analytic_reading(item, field_name: str) -> int | None:
    """One input's number, off an object or off the jsonb it was stored as.

    Returns None when this item does not carry the field at all — an `AnomalyVerdict` has no
    `point_count` and never will. A None is "this input says nothing about that dimension", not a
    zero: the caller drops it from the minimum instead of scoring it.
    """
    value = item.get(field_name) if hasattr(item, "get") else getattr(item, field_name, None)
    if value is None or isinstance(value, bool):
        # bool is an int in Python and `flagged` sits next to these fields on AnomalyVerdict; a
        # True read as 1 would be a one-period baseline that nobody measured.
        return None
    return int(value)


def _analytic_min(items, field_name: str) -> int | None:
    """The SMALLEST reading of one field across the inputs used, or None if none carries it.

    The minimum and not the mean: the axis is about the thinnest input the importance leaned on,
    and this is also the receipt stored in `inputs` so the number can be re-derived by hand.
    """
    readings = [r for r in (_analytic_reading(i, field_name) for i in items) if r is not None]
    return min(readings) if readings else None


def _analytic_sub_score(value: int, full: int) -> int:
    """One input's thinness on the 0..SCORE_MAX scale the other five axes use.

    Integer division throughout, and a floor rather than a zero — see ANALYTIC_FLOOR. `full` is
    the point of saturation, so anything richer than "enough" reports SCORE_MAX rather than
    accumulating credit a reader would over-read.
    """
    capped = max(0, min(int(value), full))
    return ANALYTIC_FLOOR + capped * (SCORE_MAX - ANALYTIC_FLOOR) // full


def analytic_score(trends=(), cohort_positions=(), anomalies=()) -> tuple[int, str]:
    """The sixth axis: (score, the weakest reason).

    WEAKEST LINK, NOT MEAN — the same rule `score_situation` applies to the other five, for the
    same reason it reports a `weakest` field. Three eight-period trends and one five-member cohort
    is not "mostly solid": the modifier that moved importance may well have been the cohort's, and
    an average would report certainty about the one input that did not have it.

    NO ANALYTIC INPUT IS NOT ZERO. Every situation built before the analytic stratum existed, and
    every situation whose subject has no peers to be compared against, used no comparison at all.
    Scoring that 0 would say their comparative evidence is bad, which is a claim about a
    measurement nobody took, and it would drag a sixth of the vector to the floor for the entire
    back catalogue. The answer is the same not-applicable sentinel `coverage_score` returns for an
    unregistered domain, read through `coverage_is_known()` — outside 0..100 on purpose so no
    consumer can average it back in.

    Each argument is any iterable of items carrying the fields named above, in either an attribute
    or a mapping form; items that carry none of them contribute nothing rather than a zero.
    """
    subs: list[tuple[int, str]] = []

    # The SMALLEST population across the positions used, the LOWEST confidence across the trends,
    # and so on. Not the mean of them and not the one from the "main" input: the question this
    # axis answers is how thin the thinnest thing the importance leaned on was.
    for items, field_name, full, reason in (
            (cohort_positions, ANALYTIC_POPULATION_FIELD, ANALYTIC_FULL_POPULATION,
             ANALYTIC_POPULATION),
            (trends, ANALYTIC_TREND_CONFIDENCE_FIELD, ANALYTIC_FULL_TREND_CONFIDENCE_BP,
             ANALYTIC_TREND_CONFIDENCE),
            (trends, ANALYTIC_HISTORY_FIELD, ANALYTIC_FULL_HISTORY_POINTS,
             ANALYTIC_HISTORY_DEPTH),
            (anomalies, ANALYTIC_ANOMALY_FIELD, ANALYTIC_FULL_ANOMALY_PERIODS,
             ANALYTIC_ANOMALY_PERIODS)):
        thinnest = _analytic_min(items, field_name)
        if thinnest is not None:
            subs.append((_analytic_sub_score(thinnest, full), reason))

    if not subs:
        return COVERAGE_UNKNOWN, ANALYTIC_NONE
    # min() on the pair would tie-break on the reason STRING, which would make the answer depend
    # on alphabetical order. Ties break on the declared order above instead — cohort first,
    # because a thin population is the failure doc 05 names — so the result is reproducible.
    score = min(sub for sub, _ in subs)
    return score, next(reason for sub, reason in subs if sub == score)


def analytic_receipt(trends=(), cohort_positions=(), anomalies=()) -> tuple[int, dict]:
    """The sixth axis AND the three `inputs` keys that explain it, built exactly once.

    TWO CALLERS, ONE CONSTRUCTION. `score_situation` fills these keys for the situations it
    writes; `situation_bso.refresh_situation_importance` fills them for every situation in the
    org once the analytic facts and the composition exist (five other modules write this table
    and none of them calls `score_situation`). A second hand-written copy of the receipt is how
    `analytic_known` ends up disagreeing with `confidence_analytic` on half a tenant's rows —
    two numbers about the same axis, both looking right.
    """
    analytic, weakest = analytic_score(trends, cohort_positions, anomalies)
    return analytic, {
        # Same shape as freshness and coverage: a dimension with no basis is REPORTED as having no
        # basis rather than being scored.
        "analytic_known": coverage_is_known(analytic),
        # WHICH comparative input was the thin one, and the four raw minima it was read from. A
        # reader who disagrees with the axis can re-derive it without re-querying the analytic
        # stratum.
        "analytic_weakest": weakest,
        "analytic_inputs": {
            "smallest_population": _analytic_min(cohort_positions, ANALYTIC_POPULATION_FIELD),
            "lowest_trend_confidence_bp": _analytic_min(trends,
                                                        ANALYTIC_TREND_CONFIDENCE_FIELD),
            "fewest_points": _analytic_min(trends, ANALYTIC_HISTORY_FIELD),
            "fewest_anomaly_periods": _analytic_min(anomalies, ANALYTIC_ANOMALY_FIELD)},
    }



@dataclass(frozen=True, slots=True)
class Confidence:
    overall: int
    evidence: int
    freshness: int
    consistency: int
    identity: int
    coverage: int
    #: L2.5.1-U1's sixth axis. Defaulted because it is the only one that can be genuinely
    #: not-applicable at construction: a caller that used no comparison passes none, and the
    #: sentinel — never a 0 — is what it gets. Read it through `coverage_is_known()`.
    analytic: int = COVERAGE_UNKNOWN
    missing: tuple[str, ...] = ()
    inputs: dict = field(default_factory=dict)


def score_situation(*, event_count: int, source_count: int,
                    last_seen_at: datetime | None, open_discrepancies: int,
                    open_merge_proposals: int, present_fields: set[str],
                    expected_fields: dict[str, str], now: datetime,
                    trends=(), cohort_positions=(), anomalies=()) -> Confidence:
    """The whole confidence vector. Pure — every input explicit, fully replayable.

    The three analytic arguments are the comparisons an importance number LEANED ON — the ones
    whose modifiers actually fired, not every trend the org holds. They default to empty because
    most callers make no comparison at all, and that is a not-applicable axis rather than a bad
    one (see `analytic_score`).
    """
    evidence = evidence_score(event_count=event_count, source_count=source_count)
    freshness, freshness_known = freshness_score(last_seen_at=last_seen_at, now=now)
    consistency = consistency_score(open_discrepancies=open_discrepancies)
    identity = identity_score(open_merge_proposals=open_merge_proposals)
    coverage, missing = coverage_score(present_fields=present_fields,
                                       expected=expected_fields)
    coverage_known = coverage_is_known(coverage)
    analytic, analytic_receipt_keys = analytic_receipt(trends, cohort_positions, anomalies)

    # Minimum, not average — you are only as sure as your weakest link. A dimension with
    # no basis is left OUT rather than scored zero, so "we cannot tell how current this
    # is" never reads as "this is stale".
    trust = [evidence, consistency, identity]
    if freshness_known:
        trust.append(freshness)

    # `analytic` is REPORTED, not composed — beside `overall` where `coverage` already sits, and
    # for the same reason. A five-member cohort does not make the situation less true; it makes
    # the IMPORTANCE that leaned on it less certain, and folding it into `overall` would answer a
    # question about a comparison with a number that reads as doubt about the facts. It would
    # also silently move every existing overall the day a modifier starts firing, which doc 09's
    # must-not-regress item 3 exists to prevent.

    return Confidence(
        overall=min(trust), evidence=evidence, freshness=freshness,
        consistency=consistency, identity=identity, coverage=coverage,
        analytic=analytic, missing=tuple(missing),
        inputs={"event_count": event_count, "source_count": source_count,
                "freshness_known": freshness_known,
                # Same shape as freshness: a dimension with no basis is REPORTED as having no
                # basis rather than being scored, so "we never said what complete means for this
                # domain" cannot be read as "this is fully covered".
                "coverage_known": coverage_known,
                # Same shape once more, plus the receipt — built by `analytic_receipt` so the
                # later pass that re-fills these keys for the whole org cannot construct them
                # differently.
                **analytic_receipt_keys,
                "open_discrepancies": open_discrepancies,
                "open_merge_proposals": open_merge_proposals,
                "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
                # Which domain registry typed this situation. A change here explains a
                # re-typing that would otherwise look like the world changed.
                "domain_spec_version": spec_version(),
                "weakest": "freshness" if freshness_known and freshness == min(trust)
                           else ("evidence" if evidence == min(trust)
                                 else "consistency" if consistency == min(trust)
                                 else "identity")})


# ── lifecycle ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LifecycleDecision:
    status: str
    resolved_by: str | None
    reopened: bool = False


#: What `context/lifecycle/` derives from the stored resolution claims and hands back here. NOT a
#: model output: the ledger is re-read every pass and reduced to one of these three words by
#: deterministic code (`lifecycle/ledger.py`), which is what makes a statement-resolution
#: self-correcting in the same way a fact-resolution already is.
STATEMENT_RESOLVED = "statement_resolved"    # every open obligation is covered by a live claim
STATEMENT_PARTIAL = "statement_partial"      # some are, some are not
STATEMENT_NONE = "statement_none"            # the ledger supports nothing right now


def decide_lifecycle(*, current_status: str | None, resolved_by: str | None,
                     last_seen_at: datetime | None, resolved_at: datetime | None,
                     terminal_by_fact: bool, now: datetime,
                     stated_resolution: str | None = None) -> LifecycleDecision:
    """What state this situation is in. Deterministic, and re-derived on every refresh.

    The three ways a situation ends behave differently on purpose:

      * RESOLVED BY FACT (the CRM stage went to closed-won) is recomputed each time. If
        the stage moves back, the situation un-resolves by itself — the system should not
        need a human to undo a conclusion it drew from data that has since changed.

      * RESOLVED BY A HUMAN sticks until new evidence arrives, then reopens. Someone
        marking a thing handled is a statement about the past, not a promise about the
        future; when the customer writes again, it is open again.

      * RESOLVED BY A STATEMENT (someone wrote "all sorted, we signed yesterday") behaves
        like a fact resolution, deliberately: `stated_resolution` is re-derived from the
        claim ledger on every pass, so a later contradiction un-resolves it with no human
        in the loop. It is the same reasoning as the first bullet, applied to a different
        kind of evidence — which is why it reuses that rule rather than the human one.

    `stated_resolution` DEFAULTS TO None, AND None IS NOT `STATEMENT_NONE`. None means "this
    caller did not re-derive the ledger", and the statement branch is then skipped entirely so
    the situation keeps whatever the ledger last decided. `refresh_situations` below is exactly
    that caller: it rebuilds every situation from graph state and knows nothing about claims, and
    if its silence read as "the ledger supports nothing" it would reopen every
    statement-resolved situation on every drain — a resolution that survives for as long as it
    takes the next sweep to run. `STATEMENT_NONE` is the ledger speaking, and only it un-resolves.

    A FACT STILL BEATS A STATEMENT, and a human's decision still outranks one. Both fall out of
    the order below rather than from a rule of their own: `terminal_by_fact` returns before the
    statement branch is reached, and the branch declines to touch a row a human resolved.
    """
    if terminal_by_fact:
        return LifecycleDecision(STATUS_RESOLVED, RESOLVED_BY_FACT)

    if current_status == STATUS_RESOLVED and resolved_by == RESOLVED_BY_FACT:
        # It was closed because of a fact, and that fact no longer holds.
        return LifecycleDecision(STATUS_ACTIVE, None, reopened=True)

    if stated_resolution is not None and resolved_by != RESOLVED_BY_HUMAN:
        if stated_resolution == STATEMENT_RESOLVED:
            return LifecycleDecision(STATUS_RESOLVED, RESOLVED_BY_STATEMENT)
        if stated_resolution == STATEMENT_PARTIAL:
            # NOT a close: `resolved_at` stays empty (the upsert writes it only for the two
            # terminal states) because nothing has finished. What the state carries is that some
            # of it has, and which — the claims hold the scope.
            return LifecycleDecision(STATUS_PARTIALLY_RESOLVED, RESOLVED_BY_STATEMENT)
        if (stated_resolution == STATEMENT_NONE
                and resolved_by == RESOLVED_BY_STATEMENT
                and current_status in (STATUS_RESOLVED, STATUS_PARTIALLY_RESOLVED,
                                       STATUS_ARCHIVED)):
            # The claim that closed it no longer stands — contradicted, or withdrawn by a
            # re-derivation. Same self-correction as the fact branch above.
            return LifecycleDecision(STATUS_ACTIVE, None, reopened=True)

    # STATUS_PARTIALLY_RESOLVED is held here for the same reason the two terminal states are: a
    # caller that did not re-derive the ledger must not silently discard what the ledger last
    # said. The two rules inside cannot fire for it (a partial has no `resolved_at`, and its
    # `resolved_by` is never `human`), so it comes back unchanged.
    if current_status in (STATUS_RESOLVED, STATUS_ARCHIVED, STATUS_PARTIALLY_RESOLVED):
        if (resolved_by == RESOLVED_BY_HUMAN and last_seen_at is not None
                and resolved_at is not None and last_seen_at > resolved_at):
            return LifecycleDecision(STATUS_ACTIVE, None, reopened=True)
        if (current_status == STATUS_RESOLVED and resolved_at is not None
                and (now - resolved_at) > timedelta(days=ARCHIVE_AFTER_DAYS)):
            return LifecycleDecision(STATUS_ARCHIVED, resolved_by)
        return LifecycleDecision(current_status, resolved_by)

    if last_seen_at is None:
        return LifecycleDecision(STATUS_ACTIVE, None)
    gone_quiet = (now - last_seen_at) > timedelta(days=DORMANT_AFTER_DAYS)
    return LifecycleDecision(STATUS_DORMANT if gone_quiet else STATUS_ACTIVE, None)


# ═══════════════════════════════════════════════════════════════════════════════════
# Persistence — bulk-read the org, score in memory, upsert once per situation. The same
# shape as refresh_attention, for the same reason: one query per concept beats one query
# per row the moment a tenant has real volume.
# ═══════════════════════════════════════════════════════════════════════════════════

def _bulk(conn, sql: str, params: dict) -> list:
    return conn.execute(text(sql), params).fetchall()


def refresh_situations(store, org_id: str, *, eval_time: datetime | None = None) -> int:
    """Rebuild every situation for one org. Returns the number written.

    Idempotent: running it twice changes nothing, because every value is derived from
    graph state plus a stored human decision. A situation you cannot rebuild is a
    situation you cannot trust.
    """
    now = eval_time or datetime.now(timezone.utc)

    with store.engine.connect() as conn:
        correlations = _bulk(conn,
            "select correlation_id, anchor_node_id, anchor_type, domain, generation, "
            "       first_event_at, last_event_at, event_count "
            "from context_correlations where org_id = :o", {"o": org_id})
        if not correlations:
            return 0

        # distinct SOURCES per correlation — corroboration across tools, which is what
        # makes evidence strong, rather than how many emails one thread produced.
        sources: dict[str, int] = {r.correlation_id: int(r.n) for r in _bulk(conn,
            "select m.correlation_id, count(distinct se.source) as n "
            "from context_correlation_members m "
            "join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
            "where m.org_id = :o group by m.correlation_id", {"o": org_id})}

        facts_by_node: dict[str, dict[str, str]] = {}
        for row in _bulk(conn,
                "select subject_node_id, field, value from graph_facts "
                "where org_id = :o and valid_to is null and status = 'active'",
                {"o": org_id}):
            facts_by_node.setdefault(row.subject_node_id, {})[row.field] = row.value

        # Fields the situation's own evidence established, wherever they landed.
        #
        # Checking only the anchor node is wrong and quietly useless: `thread.ball_in_court`
        # and `commitment.due_at` are written to PEOPLE, so a company-anchored opportunity
        # would report "whose turn it is" missing forever — a detector that is always
        # right and never informative, which is the exact failure this module's docstring
        # warns about. Coverage asks what THIS SITUATION knows, not what one node holds.
        fields_by_correlation: dict[str, set[str]] = {}
        for row in _bulk(conn,
                "select distinct m.correlation_id, f.field from context_correlation_members m "
                "join graph_facts f on f.org_id = m.org_id "
                "  and f.created_by_event_id = m.event_id "
                "where m.org_id = :o and f.valid_to is null and f.status = 'active'",
                {"o": org_id}):
            fields_by_correlation.setdefault(row.correlation_id, set()).add(row.field)

        discrepancies: dict[str, int] = {r.subject_node_id: int(r.n) for r in _bulk(conn,
            "select subject_node_id, count(*) as n from discrepancies "
            "where org_id = :o and status = 'open' group by subject_node_id", {"o": org_id})}

        # An open duplicate on EITHER side means we are unsure who this is about.
        proposals: dict[str, int] = {}
        for row in _bulk(conn,
                "select left_node_id, right_node_id from merge_proposals "
                "where org_id = :o and status = 'open'", {"o": org_id}):
            for node in (row.left_node_id, row.right_node_id):
                proposals[node] = proposals.get(node, 0) + 1

        existing = {r.correlation_id: r for r in _bulk(conn,
            "select correlation_id, situation_id, status, resolved_by, resolved_at "
            "from context_situations where org_id = :o", {"o": org_id})}

        # THE IMPORTANCE IS NOT COMPOSED HERE, and the reason is an ORDERING one rather than a
        # layering preference. BLG-18's six modifiers read `derived.trend.*`,
        # `derived.cohort_position.*`, `derived.anomaly.*` and `derived.dependency.blocked_count`,
        # and every one of those facts is written by an analytic pass that `reason/runner` runs
        # AFTER this function. Composing here would read last sweep's facts — and on a tenant's
        # FIRST sweep it would read none at all, so every modifier would be silent and the
        # distribution would come out flat for a reason that has nothing to do with the composer.
        # `situation_bso.refresh_situation_importance` runs behind the analytic block instead, and
        # covers the five other writers of this table as well as this one.

    written = 0
    absence_subjects: list[AbsenceSubject] = []
    with store.engine.begin() as conn:
        for corr in correlations:
            if not corr.event_count:
                continue          # a group with no evidence describes nothing

            stype = situation_type(corr.anchor_type, corr.domain)
            node_facts = facts_by_node.get(corr.anchor_node_id, {})
            expected = spec_for(corr.domain).fields_for(stype)
            present = set(node_facts) | fields_by_correlation.get(corr.correlation_id, set())
            confidence = score_situation(
                event_count=int(corr.event_count),
                source_count=sources.get(corr.correlation_id, 0),
                last_seen_at=corr.last_event_at,
                open_discrepancies=discrepancies.get(corr.anchor_node_id, 0),
                open_merge_proposals=proposals.get(corr.anchor_node_id, 0),
                # The anchor's own facts PLUS whatever this situation's evidence
                # established elsewhere — a deal's stage sits on the deal, but whose turn
                # it is sits on a person.
                present_fields=present,
                # The sixth axis is left at its not-applicable sentinel HERE and filled in by
                # `refresh_situation_importance`, for the ordering reason above: the comparisons
                # it scores are the ones the importance modifiers LEANED ON, and neither those
                # facts nor that composition exist yet at this point in the sweep.
                expected_fields=expected, now=now)

            held = existing.get(corr.correlation_id)
            lifecycle = decide_lifecycle(
                current_status=held.status if held else None,
                resolved_by=held.resolved_by if held else None,
                last_seen_at=corr.last_event_at,
                resolved_at=held.resolved_at if held else None,
                terminal_by_fact=normalize_stage(
                    node_facts.get("deal.stage")) in _TERMINAL_DEAL_STAGES,
                now=now)

            situation_id = held.situation_id if held else new_id("sit")
            conn.execute(text(
                "insert into context_situations (situation_id, org_id, correlation_id, "
                "  anchor_node_id, situation_type, domain, status, resolved_by, "
                "  resolved_at, confidence_overall, confidence_evidence, "
                "  confidence_freshness, confidence_consistency, confidence_identity, "
                "  coverage, missing, inputs, first_seen_at, last_seen_at, computed_at) "
                "values (:sid, :o, :cid, :anode, :stype, :dom, :status, :rby, "
                # Archived counts as resolved for this purpose. Clearing resolved_at on
                # archive would strand the row forever: decide_lifecycle needs that
                # timestamp to tell whether new evidence post-dates the resolution, so a
                # null makes an archived situation permanently unable to reopen — the
                # opposite of what the lifecycle rules say, and invisible in a pure test.
                "  case when :status in ('resolved', 'archived') "
                "       then coalesce(:rat, :now) end, "
                "  :c_all, :c_ev, :c_fr, :c_co, :c_id, :cov, cast(:missing as jsonb), "
                "  cast(:inputs as jsonb), :first, :last, :now) "
                "on conflict (org_id, correlation_id) do update set "
                "  status = excluded.status, resolved_by = excluded.resolved_by, "
                "  resolved_at = excluded.resolved_at, "
                # A reopened situation must not keep the note explaining why it was
                # closed — it would read as the current state of something now open.
                "  resolution_note = case when excluded.status in "
                "       ('resolved', 'archived') then context_situations.resolution_note "
                "       end, "
                "  confidence_overall = excluded.confidence_overall, "
                "  confidence_evidence = excluded.confidence_evidence, "
                "  confidence_freshness = excluded.confidence_freshness, "
                "  confidence_consistency = excluded.confidence_consistency, "
                "  confidence_identity = excluded.confidence_identity, "
                "  coverage = excluded.coverage, missing = excluded.missing, "
                "  inputs = excluded.inputs, last_seen_at = excluded.last_seen_at, "
                "  situation_type = excluded.situation_type, "
                # `importance_bp`, `importance_version`, `importance_components` and
                # `confidence_analytic` are DELIBERATELY ABSENT from this update list. They are
                # written by `situation_bso.refresh_situation_importance`, later in the same
                # sweep; listing them here would blank a situation's ranking on every drain and
                # restore it seconds later, so anything reading the table mid-sweep would see a
                # tenant with no importance at all.
                "  computed_at = excluded.computed_at"),
                {"sid": situation_id, "o": org_id, "cid": corr.correlation_id,
                 "anode": corr.anchor_node_id, "stype": stype, "dom": corr.domain,
                 "status": lifecycle.status, "rby": lifecycle.resolved_by,
                 "rat": held.resolved_at if held else None,
                 "c_all": confidence.overall, "c_ev": confidence.evidence,
                 "c_fr": confidence.freshness, "c_co": confidence.consistency,
                 "c_id": confidence.identity, "cov": confidence.coverage,
                 "missing": json.dumps(list(confidence.missing)),
                 "inputs": json.dumps(confidence.inputs, default=str),
                 "first": corr.first_event_at, "last": corr.last_event_at, "now": now})
            # L2.5.5 · the SAME present/expected pair the coverage number was scored from, kept
            # so the absence classifier reads exactly what `coverage_score` read. Recomputing it
            # in a second pass would be two joins and one more chance for the two to disagree
            # about what this situation holds — and a coverage of 60% beside a `missing` list
            # that names a field the situation actually has is the failure this whole unit is
            # about, pointed the other way.
            absence_subjects.append(AbsenceSubject(
                situation_id=situation_id, subject_node_id=corr.anchor_node_id,
                domain=corr.domain, situation_type=stype,
                present_fields=frozenset(present)))
            written += 1

    # THE TYPED ABSENCES, on the same drain, in their own transaction.
    #
    # After the situation write rather than inside it: an absence is a derived view of a
    # situation that now exists, and a failure to type it must not roll back the situations
    # themselves — a tenant with situations and no absence rows is degraded, a tenant with
    # neither is dark. It is on this path rather than in a pass of its own because
    # `refresh_situations` is where the untyped `missing` list is BORN: `coverage_score` returns
    # plain-language labels, which cannot be joined, cannot be counted by type, carry no coverage
    # basis and cannot record the epoch they were drawn under. The labels stay (a card reads
    # them); the answerable version is written beside them.
    if absence_subjects:
        with store.engine.begin() as conn:
            lens = read_coverage_lens(conn, org_id)
            refresh_typed_absences(conn, org_id, absence_subjects, lens=lens, eval_time=now)
    return written


def resolve_situation(conn, *, org_id: str, situation_id: str, note: str | None = None) -> bool:
    """A human marks a situation handled. Reopens by itself when new evidence arrives —
    see decide_lifecycle."""
    return conn.execute(text(
        "update context_situations set status = 'resolved', resolved_by = 'human', "
        "  resolved_at = now(), resolution_note = :note "
        "where org_id = :o and situation_id = :sid and status <> 'resolved'"),
        {"o": org_id, "sid": situation_id, "note": note}).rowcount > 0


def active_situations(conn, *, org_id: str, domain: str | None = None,
                      limit: int = 100) -> list[dict]:
    """What the Reasoning Engine asks for instead of asking for the graph.

    Ordered by confidence: a situation we are sure about is worth more thought than one
    assembled from a single unverified email. Ordering is NOT prioritisation — which
    situation matters most is a decision, and this layer does not make decisions.

    THE JOIN IS A LEFT JOIN, and it used to be an inner one. Not every situation comes from a
    correlation: `periodic.py` and `support_situations.py` write theirs directly, with a synthetic
    correlation id and no `context_correlations` row, because their subject is a window or a
    computed anchor rather than a group of events. An inner join made every one of them invisible
    to this endpoint while `reason/domain_shadow.py` — which already left-joins — compiled them
    happily, so the API and the reasoner disagreed about what was live. `event_count` coalesces to
    0 for the same reason a missing freshness is excluded rather than zeroed: it is an absence of
    correlation, not a situation with no evidence, and the evidence those rows do have is already
    priced into `confidence_evidence`.

    `PARTIALLY_RESOLVED` IS LIVE, AND IT IS READ HERE (A-18). A situation with three of five
    obligations discharged still has two outstanding, and hiding it would take those two with it —
    a milder version of the exact failure the state was created to prevent, and strictly worse than
    never having detected the partial resolution at all, because before M-4 that row was `active`
    and visible. The addition is safe by construction rather than by judgement: `partial` is a
    status L2.7.7 invented, nothing wrote it before, so including it cannot change what this
    endpoint returns for any situation that predates it. What it changes is that M-4 can no longer
    make a live situation disappear by re-labelling it.
    """
    filters = "and s.domain = :dom " if domain else ""
    params: dict = {"o": org_id, "lim": limit}
    if domain:
        params["dom"] = domain
    rows = conn.execute(text(
        "select s.situation_id, s.situation_type, s.domain, s.status, "
        "       s.confidence_overall, s.confidence_evidence, s.confidence_freshness, "
        "       s.confidence_consistency, s.confidence_identity, s.coverage, s.missing, "
        "       s.first_seen_at, s.last_seen_at, s.anchor_node_id, "
        "       n.display_name as anchor_name, n.node_type as anchor_type, "
        "       coalesce(c.event_count, 0) as event_count "
        "from context_situations s "
        "left join context_correlations c on c.org_id = s.org_id "
        "     and c.correlation_id = s.correlation_id "
        "left join graph_nodes n on n.org_id = s.org_id and n.node_id = s.anchor_node_id "
        "     and n.valid_to is null "
        "where s.org_id = :o and s.status in ('active', 'partial') " + filters +
        "order by s.confidence_overall desc, s.last_seen_at desc nulls last limit :lim"),
        params).mappings().all()
    return [dict(r) for r in rows]
