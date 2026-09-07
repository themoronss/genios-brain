"""E-10 · WHY a series has a hole — org-wide silence, a broken source, or a real decline.

> *"Zero emails during Diwali week and zero emails because the Gmail token expired look
> identical in `metric_history`: both are `known=False`. And a gap read as a decline is a false
> churn signal — on a real account, delivered with a confident receipt."*
> — doc 13, E-10, "the subtlest failure in Layer 2, and the one most likely to reach a customer"

Three causes, three OPPOSITE meanings, and until this module they were one shape:

| reason | what happened | what it licenses |
|---|---|---|
| `ORG_INACTIVE` | the whole org was quiet — every source, same window | nothing. **Exclude the period from the fit.** |
| `COVERAGE_BROKEN` | this source stopped reporting while the others carried on | nothing. Mark UNKNOWABLE, degrade confidence. |
| `GENUINELY_ZERO` | sources healthy, org active, **this** subject quiet | **this is the product.** Feed the trend. |

**No model, no calendar, no configuration.** The whole classification is arithmetic over event
counts this system already stores. A holiday calendar was the obvious alternative and doc 13
refuses it in as many words: org-wide silence is *measurable from the data itself*, which works
for any org in any country with nothing to set up — and configuration is the thing most likely to
be missing on the tenant where it matters. A model here would be worse still: it would put a
generated sentence between a founder and the claim "your best customer is churning".

**Why zero-filling is not an option and exclusion is.** Zero-filling a holiday MANUFACTURES the
decline this module exists to prevent, and it improves the coverage ratio that would otherwise
have revealed the hole. Excluding the period removes it from the arithmetic entirely, which is
the only treatment that leaves both the slope and the coverage honest.

---

## The vocabulary is SHARED with typed absence (L2.5.5), not parallel to it

`GapReason` and `contracts.quality.AbsenceType` are the same idea at two grains: an absence type
answers *"is this expected fact missing, and what kind of missing"* about ONE fact; a gap reason
answers *"why does this PERIOD of this series have no usable reading"*. Two vocabularies for one
idea is how a downstream reader ends up asking the same question twice and getting two answers,
so the mapping is declared here as data (`ABSENCE_TYPE_BY_REASON`) rather than left implicit:

* `COVERAGE_BROKEN` -> `UNKNOWABLE` — doc 13 says the words. Licenses nothing.
* `GENUINELY_ZERO`  -> `GENUINELY_ABSENT` — "a source could have carried it and none did". It is
  the only reason that licenses a negative inference, and `NEGATIVE_INFERENCE_TYPES` is the one
  place that says so.
* `ORG_INACTIVE`    -> `NOT_EXPECTED` — the period is not one in which a reading was expected of
  anybody. Not `UNKNOWABLE`: the sources were fine and we could see perfectly well; there was
  simply nothing to see, from anyone. Calling it unknowable would be a complaint about our own
  coverage on a week when our coverage was complete.

`test_gap_reason.py` asserts that map is total and that exactly one reason licenses an inference,
so the two vocabularies cannot drift apart without a test failing.

---

## WHERE IT IS CONSUMED — the part that makes it a feature rather than a function

`trend.compute_trend` already refuses with `INSUFFICIENT_COVERAGE`, and the coverage floor is
what a gap trips — but a refusal is not the answer to a holiday. The answer is a trend computed
over the periods that were real. So `refresh_gap_corrected_trends` runs on the drain, immediately
after `refresh_trend_facts` and BEFORE the situation-importance composer that reads
`derived.trend.*`, and it recomputes — through `trend.compute_trend` itself, over a corrected
series — every trend whose window contains an excluded period. It writes back through
`trend._write_trend_fact`, the same version-keyed upsert on the same `fv_trend_*` row: there is
ONE trend algorithm and ONE trend fact per (node, metric), and this module changes only the
SERIES it is computed over. On an org with no silence in its window the pass costs one grouped
query and writes nothing at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

from genios_engine.context.analytic.history import (MetricDefinition, MetricGrain, MetricRegistry,
                                                    next_period, period_start)
from genios_engine.contracts.analytic import DIRECTIONAL, NON_ANSWERS, MetricPoint
from genios_engine.contracts.quality import NEGATIVE_INFERENCE_TYPES, AbsenceType
from genios_engine.contracts.validators import require_aware, require_identifier

# =================================================================================================
# THE THREE ANSWERS
# =================================================================================================


class GapReason(str, Enum):
    """Doc 13 E-10's three causes. Exactly one applies to any (org, period) pair.

    A `str` enum for the same reason every other enum in this layer is one: the value is written
    into a JSON fact body that L3 and a card renderer both read, and a bare `Enum` serialises as
    its `repr` the first time somebody forgets `.value`.
    """

    #: The whole org was quiet — no source carried anything in this period. Not a decline about
    #: anyone. The period is removed from the fit; see `trend_ready_series`.
    ORG_INACTIVE = "org_inactive"
    #: A source that had been reporting stopped, while the org's other sources carried on. We
    #: cannot see this period; it is not evidence that nothing happened in it.
    COVERAGE_BROKEN = "coverage_broken"
    #: Sources healthy, org active, and this reading is still what it is. THE REAL SIGNAL — the
    #: only reason that feeds a trend and the only one that licenses a negative inference.
    GENUINELY_ZERO = "genuinely_zero"


#: The bridge to L2.5.5's typed absence. Declared as DATA and asserted total by the test suite,
#: so `GapReason` and `AbsenceType` are one vocabulary at two grains rather than two vocabularies
#: for one idea. See the module docstring for why `ORG_INACTIVE` is `NOT_EXPECTED` and not
#: `UNKNOWABLE`.
ABSENCE_TYPE_BY_REASON: Mapping[GapReason, AbsenceType] = {
    GapReason.ORG_INACTIVE: AbsenceType.NOT_EXPECTED,
    GapReason.COVERAGE_BROKEN: AbsenceType.UNKNOWABLE,
    GapReason.GENUINELY_ZERO: AbsenceType.GENUINELY_ABSENT,
}

#: The reasons whose periods do NOT belong in a trend fit. Kept as a set rather than as an `if`
#: at the one site that needs it, so "which periods are excluded" has an answer a reader can see
#: without tracing control flow — the same discipline `NEGATIVE_INFERENCE_TYPES` keeps next door.
NON_MEASURING_REASONS: frozenset[GapReason] = frozenset(
    {GapReason.ORG_INACTIVE, GapReason.COVERAGE_BROKEN})

#: How much of the surrounding window a source must have reported in before its silence counts as
#: BROKEN rather than as a source that simply has not started yet. In basis points, compared with
#: `>=`, so a source live in exactly half the other periods qualifies.
#:
#: The floor exists for one failure mode: a connector added mid-window has no history, so every
#: earlier period would read as "this source reported nothing" and the whole year would be
#: retro-classified `COVERAGE_BROKEN` the day a tenant connects Calendar. A source with no
#: baseline can therefore never trigger the verdict.
BASELINE_LIVE_FLOOR_BP = 5_000

#: How many (node, metric) pairs one sweep may re-examine. The same ceiling and the same reason as
#: `trend.MAX_TREND_FACTS_PER_SWEEP`: the write is a version-keyed upsert and is bounded by
#: construction, but the READ is one dense series each. Deterministic tail — pairs are ordered, so
#: the same sweep truncates at the same place and the next one covers what this one did.
MAX_GAP_CORRECTED_PAIRS_PER_SWEEP = 2_000

#: How many period reasons are copied into a fact body as its receipt. The trend window is twelve
#: periods, so this is never reached in practice; it is here so that a caller passing a longer
#: window cannot turn a `graph_facts` row into an unbounded document.
MAX_RECEIPT_PERIODS = 24


# =================================================================================================
# THE EVIDENCE — event counts per period per source, and nothing else
# =================================================================================================

@dataclass(frozen=True, slots=True)
class PeriodActivity:
    """What every source carried in one period. The whole input to the classification.

    `events_by_source` holds ONLY sources that carried something: a source with no events in the
    period is absent from the mapping, which is the same absence-is-no-row discipline
    `metric_history` keeps. `sources_reporting` and `total_events` are derived rather than stored
    so the two can never disagree.
    """

    period_start: datetime
    events_by_source: Mapping[str, int]

    @property
    def total_events(self) -> int:
        """Doc 13's `org_activity` — total events across ALL sources in the period."""
        return sum(self.events_by_source.values())

    @property
    def sources_reporting(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, n in self.events_by_source.items() if n > 0))


@dataclass(frozen=True, slots=True)
class GapVerdict:
    """One period's reason, with the arithmetic that produced it.

    Doctrine 3 — no claim without a receipt. "We excluded your holiday week" is a claim about a
    customer's data that changes what a card says, so the counts it rests on travel with it:
    `org_events` is what made `ORG_INACTIVE` true or false, and `silent_sources` names exactly
    which connector went dark while the others carried on.
    """

    period_start: datetime
    reason: GapReason
    org_events: int
    #: Sources that reported in this period. Sorted, so two sweeps hash the same.
    reporting_sources: tuple[str, ...] = ()
    #: Sources with a live baseline that reported NOTHING in this period. Empty unless the reason
    #: is `COVERAGE_BROKEN` — it is the evidence FOR that verdict.
    silent_sources: tuple[str, ...] = ()
    #: Sources that carried events in at least `BASELINE_LIVE_FLOOR_BP` of the OTHER periods of
    #: the window. The population `silent_sources` is drawn from.
    baseline_live_sources: tuple[str, ...] = ()

    @property
    def absence_type(self) -> AbsenceType:
        """The L2.5.5 type this reason IS. One vocabulary, two grains — see the module docstring."""
        return ABSENCE_TYPE_BY_REASON[self.reason]

    @property
    def licenses_negative_inference(self) -> bool:
        """Read through `NEGATIVE_INFERENCE_TYPES` rather than compared with a member here, so
        widening the licence stays a one-line edit in `contracts/quality.py` and never becomes a
        second condition somebody forgets to update."""
        return self.absence_type in NEGATIVE_INFERENCE_TYPES

    @property
    def feeds_trend(self) -> bool:
        """Doc 13: *"Only `GENUINELY_ZERO` may contribute to a trend."*"""
        return self.reason not in NON_MEASURING_REASONS


# =================================================================================================
# THE CLASSIFICATION — doc 13's three-line cascade, and the two guards it needs to be usable
# =================================================================================================

def baseline_live_sources(window: Sequence[PeriodActivity], *,
                          period_start: datetime) -> tuple[str, ...]:
    """Sources that were reporting NORMALLY around this period — the population a silence is
    judged against.

    "Normally" is measured over the OTHER periods of the window and never over this one, which is
    the point: a source that went dark in the period under test would otherwise be counted as
    part of its own baseline and could never be found silent.

    Integer basis points throughout. A source live in `k` of `n` other periods qualifies when
    `k * 10000 // n >= BASELINE_LIVE_FLOOR_BP`, and with no other periods at all nothing qualifies
    — a one-period window has no baseline to speak of, and inventing one would classify a brand
    new tenant's first week as a broken connector.
    """
    others = [p for p in window if p.period_start != period_start]
    if not others:
        return ()
    seen: dict[str, int] = {}
    for activity in others:
        for source, count in activity.events_by_source.items():
            if count > 0:
                seen[source] = seen.get(source, 0) + 1
    return tuple(sorted(
        source for source, live in seen.items()
        if live * 10_000 // len(others) >= BASELINE_LIVE_FLOOR_BP))


def classify_period(window: Sequence[PeriodActivity], *, period_start: datetime) -> GapVerdict:
    """Doc 13's cascade, in its order:

    ```
    if org_activity == 0                                          -> ORG_INACTIVE
    elif this source's events == 0 and other sources reported     -> COVERAGE_BROKEN
    else                                                          -> GENUINELY_ZERO
    ```

    **`ORG_INACTIVE` is tested FIRST and that ordering is load-bearing.** On an org with a single
    connected source the two verdicts are arithmetically indistinguishable — the source being
    silent and the org being silent are the same row of data — and `ORG_INACTIVE` is the answer
    that excludes the period rather than the one that blames a connector we have no evidence
    against. With one source there is nothing to compare a silence to, and doc 13's second branch
    requires "other sources reported normally" in as many words.

    A period the window does not contain is `ORG_INACTIVE` with zero events, which is the truthful
    answer for a period in which this org's ledger holds nothing at all.
    """
    at = require_aware(period_start, "period_start")
    activity = next((p for p in window if p.period_start == at), None)
    if activity is None:
        activity = PeriodActivity(period_start=at, events_by_source={})

    if activity.total_events == 0:
        return GapVerdict(period_start=at, reason=GapReason.ORG_INACTIVE, org_events=0,
                          baseline_live_sources=baseline_live_sources(window, period_start=at))

    baseline = baseline_live_sources(window, period_start=at)
    reporting = activity.sources_reporting
    silent = tuple(s for s in baseline if activity.events_by_source.get(s, 0) == 0)
    # `and reporting` is REDUNDANT with the `ORG_INACTIVE` branch above, and it stays. It is the
    # second of two mechanisms holding one invariant — a whole org's silence must never be reported
    # as a broken connector — and the failure it guards against is telling a tenant to reconnect
    # Gmail because they took Christmas off. Doc 13 spells the condition out ("and other sources
    # reported normally"), so the branch says what it means rather than relying on a neighbour.
    if silent and reporting:
        return GapVerdict(period_start=at, reason=GapReason.COVERAGE_BROKEN,
                          org_events=activity.total_events, reporting_sources=reporting,
                          silent_sources=silent, baseline_live_sources=baseline)
    return GapVerdict(period_start=at, reason=GapReason.GENUINELY_ZERO,
                      org_events=activity.total_events, reporting_sources=reporting,
                      baseline_live_sources=baseline)


def classify_window(window: Sequence[PeriodActivity]) -> dict[datetime, GapVerdict]:
    """Every period the event ledger can actually SPEAK TO, classified. Deterministic, clock-free.

    **A period before the ledger's first observed event is not classified at all**, and this guard
    is the difference between a correction and a catastrophe. `source_events` is a live table: raw
    payloads expire, old rows are pruned, and `sampler.backfill_org` deliberately reconstructs
    EIGHTEEN MONTHS of history from an event ledger that may hold far less. Without this rule every
    period older than the ledger reads "no events across all sources" — which is
    arithmetically true and means nothing — every one of them is excluded, and an org whose events
    have aged out has EVERY trend it owns silently retracted. Absence of evidence about the org's
    activity is not evidence that the org was inactive, and this layer refuses that inference
    everywhere else.

    **Trailing silence is still classified, and that asymmetry is the point.** We are watching NOW
    — the drain just ran — so a window whose last three periods are empty is a window in which
    nothing happened, and that is precisely the shutdown this module exists to catch. It is only
    the OLD end of the ledger that is ambiguous.

    A window with no events anywhere therefore classifies NOTHING and corrects NOTHING, which is
    the honest answer for a tenant whose ledger this sweep cannot see.
    """
    observed = [a.period_start for a in window if a.total_events > 0]
    if not observed:
        return {}
    since = min(observed)
    return {activity.period_start: classify_period(window, period_start=activity.period_start)
            for activity in window if activity.period_start >= since}


# =================================================================================================
# THE EVIDENCE READ — one grouped query per sweep, bucketed in Python by the SHARED period function
# =================================================================================================

_ACTIVITY_SQL = (
    "select source, occurred_at from source_events "
    "where org_id = :o and occurred_at >= :since and occurred_at < :until")


def read_period_activity(store, org_id: str, *, since: datetime, until: datetime,
                         grain: MetricGrain) -> tuple[PeriodActivity, ...]:
    """Per-period, per-source event counts across the window. ONE query, whatever the window.

    **Bucketed through `history.period_start`, not through SQL's `date_trunc`.** The sampler's
    periods and these periods have to be the same periods or a "silent week" would be offset from
    the week whose reading it is meant to explain — doc 04 names that class of disagreement
    ("backfill and live sampling disagree on period boundaries -> phantom changepoints") and names
    the one shared boundary function as the mitigation. `date_trunc('week', ...)` also depends on
    the server's `DateStyle` for its week start, which is a second clock nobody declared.

    Every period between `since` and `until` appears in the result, including the ones with no
    events at all — a period missing from the ledger is `ORG_INACTIVE`, and it has to be IN the
    window for `baseline_live_sources` to count it as a period a source failed to report in.
    """
    from sqlalchemy import text

    start = period_start(require_aware(since, "since"), grain)
    end = require_aware(until, "until")
    counts: dict[datetime, dict[str, int]] = {}
    cursor = start
    while cursor <= end:
        counts[cursor] = {}
        cursor = next_period(cursor, grain)

    with store.engine.connect() as conn:
        rows = conn.execute(text(_ACTIVITY_SQL),
                            {"o": org_id, "since": start, "until": end}).all()
    for row in rows:
        occurred = row.occurred_at
        if occurred is None:
            continue
        bucket = period_start(occurred, grain)
        if bucket not in counts:
            continue
        source = str(row.source or "unknown")
        counts[bucket][source] = counts[bucket].get(source, 0) + 1

    return tuple(PeriodActivity(period_start=at, events_by_source=dict(sorted(by_source.items())))
                 for at, by_source in sorted(counts.items()))


# =================================================================================================
# THE CONSUMPTION — a series with the unmeasurable periods taken out of it
# =================================================================================================

def _unknowable(point: MetricPoint) -> MetricPoint:
    """The same period, marked as one we could not see. Never zero-filled.

    `coverage_ready=False` is set deliberately and is the accurate reading for `COVERAGE_BROKEN`:
    the source that carries this metric stopped reporting, so no connected source could have
    carried it for this period. It is the same tri-state `MetricPoint` documents — and it counts
    AGAINST `coverage_ratio_bp` in `compute_trend`, which is exactly doc 13's "degrade
    confidence".
    """
    return MetricPoint(subject_node_id=point.subject_node_id, metric=point.metric, value_bp=None,
                       unit=point.unit, currency=point.currency, observed_at=point.observed_at,
                       known=False, coverage_ready=False)


def trend_ready_series(series: Sequence[MetricPoint],
                       verdicts: Mapping[datetime, GapVerdict]) -> tuple[MetricPoint, ...]:
    """The series `compute_trend` should have been given. Doc 13's two treatments, applied.

    * `ORG_INACTIVE` -> **the point is removed.** Not zeroed, and not marked unknown either:
      marking it unknown would count it against the coverage ratio and refuse the trend, and a
      refusal is not the answer to a public holiday. The period simply is not one in which
      anybody's reading was expected.
    * `COVERAGE_BROKEN` -> the point becomes an honest gap (`known=False`, no value), so it counts
      against coverage and degrades confidence exactly as doc 13 asks.
    * `GENUINELY_ZERO`, and any period with no verdict at all -> untouched.

    **The degradation when everything is excluded.** If dropping the excluded periods would leave
    nothing, every point is marked unknown instead. `compute_trend` refuses an empty series with a
    `ValueError` — correctly, since a trend with no evidence points is a claim with no receipt —
    and the honest output for a window we could not measure at all is `INSUFFICIENT_COVERAGE`, not
    an exception on the sweep and not last sweep's `DECLINING` left standing.
    """
    kept: list[MetricPoint] = []
    for point in series:
        verdict = verdicts.get(point.observed_at)
        if verdict is None or verdict.reason is GapReason.GENUINELY_ZERO:
            kept.append(point)
        elif verdict.reason is GapReason.COVERAGE_BROKEN:
            kept.append(point if not point.known else _unknowable(point))
    if not kept and series:
        return tuple(point if not point.known else _unknowable(point) for point in series)
    return tuple(kept)


def gap_receipt(verdicts: Mapping[datetime, GapVerdict]) -> dict[str, Any]:
    """The receipt copied into the fact body: which periods were excluded, and why.

    Only the periods that CHANGED the answer travel — a body listing twelve `genuinely_zero`
    verdicts is noise a reader has to filter, and the interesting statement is always the
    exclusion. Sorted and capped so the row is bounded and two sweeps produce identical JSON.
    """
    excluded = sorted(at for at, v in verdicts.items() if v.reason is GapReason.ORG_INACTIVE)
    unknowable = sorted(at for at, v in verdicts.items() if v.reason is GapReason.COVERAGE_BROKEN)
    body: dict[str, Any] = {
        "excluded_periods": [at.isoformat() for at in excluded[:MAX_RECEIPT_PERIODS]],
        "unknowable_periods": [at.isoformat() for at in unknowable[:MAX_RECEIPT_PERIODS]],
        "reasons": {at.isoformat(): verdicts[at].reason.value
                    for at in (excluded + unknowable)[:MAX_RECEIPT_PERIODS]},
    }
    silent = sorted({s for v in verdicts.values() for s in v.silent_sources})
    if silent:
        body["silent_sources"] = silent
    return body


# =================================================================================================
# THE SWEEP — where a caller ACTS on the classification
# =================================================================================================

@dataclass(frozen=True, slots=True)
class GapSweep:
    """What one gap-correction pass did, in numbers an operator can act on."""

    #: Periods in the window that no reading may be taken from. Zero means the pass short-circuited
    #: after its single query and wrote nothing at all — the ordinary case.
    excluded_periods: int = 0
    unknowable_periods: int = 0
    pairs_examined: int = 0
    #: `derived.trend.*` facts rewritten because the corrected series gave a different answer.
    facts_corrected: int = 0
    #: How many of those flipped OUT of a directional claim — the false-churn count, and the
    #: number doc 09's H6 row ("DECLINING trends across an org-wide silence window: 0") is about.
    directional_claims_withdrawn: int = 0
    budget_exhausted: bool = False


def _corrected_body(trend, changepoint, verdicts: Mapping[datetime, GapVerdict]) -> dict[str, Any]:
    """`trend.trend_fact_value`'s body plus the gap receipt. Imported, never re-implemented: the
    fact's shape is L3's read contract and a second copy of it here would drift the first time a
    field is added."""
    from genios_engine.context.analytic.trend import trend_fact_value

    body = trend_fact_value(trend, changepoint)
    body["gap_corrected"] = True
    body["gap_reasons"] = gap_receipt(verdicts)
    return body


def _pairs(store, org_id: str, limit: int) -> list[tuple[str, str]]:
    """Every `(node, metric)` this org has history for, ordered, capped — the same population
    `trend._trended_pairs` reads and for the same reason: the sampler's policy already decided
    which series are worth having, and re-deriving that decision here would be a second copy of
    BLG-07 that can disagree with the first."""
    from sqlalchemy import text

    from genios_engine.context.analytic.history import HISTORY_TABLE

    with store.engine.connect() as conn:
        rows = conn.execute(text(
            f"select distinct subject_node_id, metric from {HISTORY_TABLE} where org_id = :o "
            "order by subject_node_id, metric limit :n"), {"o": org_id, "n": limit + 1}).all()
    return [(row[0], row[1]) for row in rows]


def refresh_gap_corrected_trends(store, org_id: str, *, eval_time: datetime,
                                 history: Any = None, registry: MetricRegistry | None = None,
                                 window_periods: int | None = None,
                                 limit: int = MAX_GAP_CORRECTED_PAIRS_PER_SWEEP) -> GapSweep:
    """Recompute every trend whose window contains a period no reading may be taken from.

    Called from `context/runner.process_pending`, AFTER `refresh_trend_facts` and BEFORE
    `refresh_situation_importance` — the composer reads `derived.trend.*` for its modifier 3a, so
    a correction that landed after it would rank this sweep's situations on the uncorrected claim.

    **This pass is a no-op on an ordinary org and that is the design.** It reads the org's event
    ledger for the trend window once; if every period in it is `GENUINELY_ZERO` there is nothing
    to correct and the function returns having written nothing. The cost of the guard on a healthy
    tenant is one grouped query per sweep.

    **It writes the SAME row `refresh_trend_facts` wrote**, through that module's own upsert, so
    there is exactly one `derived.trend.<metric>` fact per (node, metric) and exactly one trend
    algorithm. This module changes the SERIES, never the arithmetic — the alternative, publishing a
    second "corrected trend" fact family, would leave two answers on one node and make every
    downstream reader choose.

    `eval_time` is a parameter with no default and no fallback clock: it is the end of the window,
    the `as_at` horizon of every series read, and the timestamp of every row written.
    """
    # `_write_trend_fact` is private and is imported ON PURPOSE. The alternative is a second copy
    # of one upsert, which is precisely the defect `analytic/publish.py` exists to delete: four
    # modules each held their own copy and each of the four moved `valid_from` on conflict.
    from genios_engine.context.analytic.sampler import resolve_history_store, sampler_registry
    from genios_engine.context.analytic.trend import (TREND_WINDOW_PERIODS, _write_trend_fact,
                                                      _window_start, compute_trend,
                                                      find_changepoint, trend_fact_field,
                                                      trend_fact_value)

    at = require_aware(eval_time, "eval_time")
    require_identifier(org_id, "org_id")
    periods = TREND_WINDOW_PERIODS if window_periods is None else window_periods
    registry = registry or sampler_registry()
    history = history if history is not None else resolve_history_store(store)

    # One activity read per grain the registry actually uses — never one per (node, metric).
    grains = {registry.require(name).grain for name in registry.names}
    verdicts_by_grain: dict[MetricGrain, dict[datetime, GapVerdict]] = {}
    for grain in sorted(grains, key=lambda g: g.value):
        window = read_period_activity(store, org_id,
                                      since=_window_start(at, grain, periods), until=at,
                                      grain=grain)
        verdicts_by_grain[grain] = classify_window(window)

    excluded = sum(1 for v in verdicts_by_grain.values() for x in v.values()
                   if x.reason is GapReason.ORG_INACTIVE)
    unknowable = sum(1 for v in verdicts_by_grain.values() for x in v.values()
                     if x.reason is GapReason.COVERAGE_BROKEN)
    if not excluded and not unknowable:
        return GapSweep()          # nothing unmeasurable in this window: no read, no write

    pairs = _pairs(store, org_id, limit)
    exhausted = len(pairs) > limit
    pairs = pairs[:limit]

    corrections: list[tuple[str, str, dict[str, Any]]] = []
    withdrawn = 0
    for node_id, metric in pairs:
        definition: MetricDefinition | None = registry.get(metric)
        if definition is None:
            continue
        verdicts = verdicts_by_grain.get(definition.grain)
        if not verdicts:
            continue
        series = history.read_series(
            org_id, node_id, metric,
            since=_window_start(at, definition.grain, periods), until=at, as_at=at)
        if not series:
            continue
        corrected = trend_ready_series(series, verdicts)
        if tuple(corrected) == tuple(series):
            continue               # no period in THIS series was excluded
        as_written = compute_trend(series)
        as_corrected = compute_trend(corrected)
        if trend_fact_value(as_corrected) == trend_fact_value(as_written):
            continue               # the exclusion did not change the answer; leave the row alone
        if as_written.direction in DIRECTIONAL and as_corrected.direction not in DIRECTIONAL:
            # THE FALSE-CHURN COUNT. `DIRECTIONAL` rather than `NON_ANSWERS`: a decline that
            # becomes FLAT is a withdrawn claim just as much as one that becomes a refusal, and
            # FLAT is the answer an org-wide silence most often turns a decline into.
            withdrawn += 1
        changepoint = (None if as_corrected.direction in NON_ANSWERS
                       else find_changepoint(corrected))
        corrections.append((node_id, trend_fact_field(metric),
                            _corrected_body(as_corrected, changepoint, verdicts)))

    if corrections:
        with store.engine.begin() as conn:
            for node_id, field_name, body in corrections:
                _write_trend_fact(conn, org_id=org_id, node_id=node_id, field_name=field_name,
                                  value=body, now=at)

    return GapSweep(excluded_periods=excluded, unknowable_periods=unknowable,
                    pairs_examined=len(pairs), facts_corrected=len(corrections),
                    directional_claims_withdrawn=withdrawn, budget_exhausted=exhausted)


__all__ = ["ABSENCE_TYPE_BY_REASON", "BASELINE_LIVE_FLOOR_BP",
           "MAX_GAP_CORRECTED_PAIRS_PER_SWEEP", "MAX_RECEIPT_PERIODS", "NON_MEASURING_REASONS",
           "GapReason", "GapSweep", "GapVerdict", "PeriodActivity", "baseline_live_sources",
           "classify_period", "classify_window", "gap_receipt", "read_period_activity",
           "refresh_gap_corrected_trends", "trend_ready_series"]
