"""H8 · the Layer 2 v2 pilot report — the pattern path beside anchor-based detection, and the
three claims that are the point of the whole layer.

    python scripts/l2_shadow_diff.py --org <pilot> --days 7 --database-url postgresql://…

    | metric                                                   | gate  |
    |----------------------------------------------------------|-------|
    | situations produced by both paths                        | 100%  |
    | a DECLINING trend on a real account, series citable       | >= 1  |
    | a cohort position on a real account, population named     | >= 1  |
    | a pattern-matched situation with per-condition evidence   | >= 1  |
    | founder-visible regressions                               | 0     |

THE THREE MIDDLE ROWS ARE NOT COUNTS. Doc 09 says of them: *"they are the first time GeniOS can
say 'this is getting worse', 'this is unlike its peers', and 'these five facts hold together' —
each with the numbers behind it."* A row that counts 1 without being able to show the numbers has
not met that bar, so this report RESOLVES each claim against the rows it was computed from and
prints the receipt:

  * a DECLINING trend counts only when its own `series` pointer — `(subject_node_id, metric,
    first_period, last_period, periods)`, which is `metric_history`'s primary key minus the
    ambient tenant — resolves to exactly the points it claims, and the points are printed;
  * a cohort position counts only when its `cohort_id` resolves to a NAMED population in
    `cohort_definitions` whose membership can be enumerated at the window's end, and the name,
    the size, the ladder and the member ids are printed;
  * a pattern fire counts only when its per-condition evidence is present AND every condition
    carries a recoverable `ref`, and each condition is printed with what was expected, what was
    observed and which object satisfied it;
  * and the patterns that did NOT fire are printed beside them, each with the condition that
    stopped it, off `pattern_runs.top_failure_*`. Doc 06's SECOND failure mode is a pattern that
    never fires, and a fire count of zero cannot on its own tell "this tenant has no such
    situation" from "condition 4 reads a field this tenant spells differently" — the two look
    identical and want opposite responses. Printed, never scored: a silent pattern is a legitimate
    answer about a tenant, and failing H8 over one would fail it over a customer who simply has no
    renewal at risk this week.

A trend whose series has been pruned away, a position on a cohort nobody named, a fire whose
evidence array is empty — each of those is a claim GeniOS cannot back, and this report scores it
zero rather than one.

WHAT "BOTH PATHS" MEANS HERE, EXACTLY. Both paths exist in this tree and neither is hypothetical:

  * the OLD path is anchor-based detection — `context/situations.refresh_situations` derives one
    situation per row of `context_correlations` and its type from `anchor_type`. It is what a
    founder sees today and it writes `context_situations`.
  * the NEW path is the L2.6 pattern registry — `context/patterns.evaluate_org` matches declared
    subgraph patterns and writes `pattern_fires` / `pattern_runs`. Doc 06 keeps it beside the
    anchor path rather than replacing it: *"keep anchor-based detection running alongside. Compare
    fire sets on a pilot for 7 days before switching."* This report is that comparison.

So "situations produced by both paths = 100%" is read as: **every LIVE situation the anchor path
produced in the window has a pattern fire on the same anchor node in the same window.** It is a
loss check, not an agreement check — the question doc 06 makes it is "may the anchor path be
deleted yet", and any share below 100% answers no and names the situations that would disappear.
The assumption is recorded as **A-28** in `docs/plans/L2_MISSING_UNIT_SPECS.md` §3.

ACTIVATION IS REPORTED FIRST, AND IT IS A PRECONDITION. `l2_v2_activation` (migration 0106) holds
two switches. `patterns` is a real gate: with it off, `context/runner.process_pending` does not run
the shadow pass at all and `pattern_fires` is empty, so every number below would be a diff of the
anchor path against nothing. `analytic` is a declaration — the analytic stratum runs for every
tenant — and it is what says this window is a pilot window rather than a week somebody happened to
look at. A tenant missing either is reported as NOT MEASURED, never as a passing set of zeros.

WHAT THIS CANNOT MEASURE WITHOUT A REAL TENANT. Everything below runs against whatever database it
is pointed at, and every row is honestly computed — but the gate's subject is SEVEN DAYS OF ONE
REAL TENANT'S TRAFFIC, and there is no pilot tenant connected to this repo. Layer 1's equivalent
(G10) is open for the same reason and says so in `docs/plans/L1_V2_BUILD_RECORD.md` §5.1. The
rows that a seeded org can only DEMONSTRATE — not measure — are named in `NEEDS_REAL_TENANT` and
printed under NOT MEASURED at the foot of every report, together with the command to run when a
tenant exists. A seeded fixture is not a week of real mail and this report never calls it one.

READ-ONLY, AT THE SERVER — `set transaction read only` is the first statement of the transaction
(`scripts/_gate.py`) — and the target is named explicitly through `scripts/_db.py`, which has no
fallback to the application's configured database. This script runs against a LIVE PILOT TENANT.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from genios_engine.contracts.analytic import MIN_COHORT_POPULATION      # noqa: E402
from genios_engine.platform.l2_activation import (SWITCHES,             # noqa: E402
                                                  SWITCH_ANALYTIC, SWITCH_PATTERNS)
from scripts._db import add_database_argument, resolve_database_url     # noqa: E402
from scripts._gate import parse_since, read_only_connection, sql        # noqa: E402

BP = 10_000

#: The situation statuses a founder can still be shown. `resolved` and `archived` are situations
#: the product has deliberately stopped surfacing, and counting them in the loss check would fail
#: the gate over work the anchor path had already finished. `partial` is included because doc 07's
#: own lifecycle says three of five commitments discharged is neither closed nor untouched, and
#: `A-18` records that `active_situations` drops it — a bug this report must not inherit.
LIVE_SITUATION_STATUSES = ("active", "partial")

#: `graph_facts.field` prefixes, spelled here rather than imported so this read-only report takes
#: no import-time dependency on the analytic package it is auditing. `test_l2_shadow_diff` pins
#: each one against the module that writes it.
TREND_FIELD_PREFIX = "derived.trend."
COHORT_FIELD_PREFIX = "derived.cohort_position."

#: The direction that makes row 2 a claim. Written by `analytic/trend.trend_fact_value` as
#: `TrendDirection.DECLINING.value`.
DECLINING = "declining"

#: How many receipts of each kind are PRINTED. Every one is counted; printing all of them turns a
#: gate report into a data dump on a real tenant. The JSON output carries the same cap.
MAX_RECEIPTS = 3

#: How many members of a cohort are named in its receipt. The population SIZE is the claim; the
#: ids are there so a reader can check it, and a full membership list on a 4,000-account cohort is
#: not a receipt anybody reads.
MAX_MEMBERS_NAMED = 10

#: How many lost situations / regressed cards are listed. A breach needs its subjects named, but
#: a tenant with 900 anchor situations and no pattern coverage would otherwise print 900 lines.
MAX_BREACH_EXAMPLES = 20

#: The rows a seeded org can DEMONSTRATE but not MEASURE, and why. Printed under NOT MEASURED at
#: the foot of every report so a green run against a fixture cannot be read as a pilot result.
NEEDS_REAL_TENANT = (
    ("situations_produced_by_both",
     "the loss check is only meaningful over a real correlation set; a seeded org proves the "
     "arithmetic, not that the six shipped patterns cover a customer's situations"),
    ("declining_trend_series_citable",
     "a DECLINING trend needs six real periods of one account's history — 18 months of it after "
     "sampler.backfill_history_for_drain, which needs a real event ledger to reconstruct from"),
    ("cohort_position_population_named",
     f"a named position needs a real cohort of at least {MIN_COHORT_POPULATION} of the tenant's "
     "own accounts, built by the cohort pass from their graph"),
    ("pattern_evidence_per_condition",
     "a fire is a statement about a real subgraph; a seeded slice proves the evaluator runs, not "
     "that a pattern fires on a customer"),
    ("founder_visible_regressions",
     "a regression is a card a founder is actually looking at; there are no live cards on a "
     "seeded org"),
)

#: The command to run when a pilot tenant exists, printed with the NOT MEASURED block. Kept as one
#: string so the report, the build record and this module cannot disagree about it.
PILOT_COMMAND = ("GENIOS_TARGET_DATABASE_URL=<pilot db> "
                 "python scripts/l2_shadow_diff.py --org <pilot> --days 7")


def _json(value: Any, fallback: Any) -> Any:
    """`jsonb` arrives as a dict from psycopg and as text from some drivers. Both are read."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return fallback
    return fallback


def _iso(value: Any) -> str | None:
    """Every instant this report prints, normalised to UTC.

    Postgres hands back a timestamptz in the SESSION's time zone, so an operator in Asia/Kolkata
    and one in UTC read the same series as `2026-03-01T05:30:00+05:30` and `2026-03-01T00:00:00Z`
    — the same instant, two strings, and two gate reports that cannot be diffed against each other
    even though the header says UTC. The window line already says UTC; this makes the receipts
    agree with it.
    """
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat()
    return str(value) if value else None


def _instant(value: Any) -> datetime | None:
    """An ISO string out of a JSONB body back into an aware datetime, or `None`.

    `None` on anything unparseable rather than a raise: a malformed pointer is a receipt that does
    not resolve, which this report scores as "not citable" and prints — never a crash that stops
    the other four rows from being measured.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ── the receipts ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SeriesReceipt:
    """A DECLINING trend and the points it was computed from, read back out of `metric_history`.

    `citable` is the whole content of doc 09's "series citable". The trend fact stores a POINTER
    to its series rather than a copy of it (`trend.trend_fact_value`: "the evidence values are
    deliberately not copied in"), which is the right shape and also the thing that can rot — a
    retention pass, a re-keyed metric or a node that was merged away leaves a fact claiming a
    decline whose series nobody can read. That is a claim without a receipt, and it scores zero.
    """

    subject_node_id: str
    metric: str
    claimed_periods: int
    trend_confidence_bp: int
    relative_slope_bp: int
    streak_periods: int
    first_period: str | None
    last_period: str | None
    points: tuple[tuple[str, int, str, bool | None], ...]   # (observed_at, value_bp, unit, cov)
    changepoint_at: str | None = None

    @property
    def citable(self) -> bool:
        """The pointer resolves to exactly the series it claims. `>= 2` because a "decline" drawn
        from one point is not a direction, and the equality because a pointer that resolves to
        FEWER points than it claims is describing a series that no longer exists."""
        return len(self.points) >= 2 and len(self.points) == self.claimed_periods

    def as_dict(self) -> dict[str, Any]:
        return {"subject_node_id": self.subject_node_id, "metric": self.metric,
                "claimed_periods": self.claimed_periods, "points_resolved": len(self.points),
                "trend_confidence_bp": self.trend_confidence_bp,
                "relative_slope_bp": self.relative_slope_bp,
                "streak_periods": self.streak_periods,
                "first_period": self.first_period, "last_period": self.last_period,
                "changepoint_at": self.changepoint_at, "citable": self.citable,
                "series": [{"observed_at": at, "value_bp": v, "unit": u, "coverage_ready": c}
                           for at, v, u, c in self.points]}


@dataclass(frozen=True)
class CohortReceipt:
    """A cohort position and the POPULATION it was cut from, named.

    "Population named" is not "population_size is an integer". A percentile with a number beside it
    and no way to find out who the peers were is the shape doc 04 refuses everywhere else in the
    analytic stratum: the position must resolve to a cohort somebody DEFINED (`cohort_definitions.
    name`, and `created_by` says whether that was a human or `system:default`) and whose members
    can still be enumerated at the window's end.
    """

    subject_node_id: str
    metric: str
    cohort_id: str
    cohort_name: str | None
    node_type: str | None
    created_by: str | None
    population_size: int
    members_enumerated: int
    member_ids: tuple[str, ...]
    percentile_bp: int | None
    band: str | None
    ladder: tuple[int | None, int | None, int | None]
    #: Why the ladder is absent, verbatim from the fact body. `comparator.position_fact_value`
    #: WITHHELDS the distribution below `MIN_BASELINE_POPULATION` and states the reason in the
    #: row, because "a reader that found no `p25_bp` could not tell 'this cohort is too small to
    #: describe' from 'an older writer wrote this row'". A report that printed three `None`s and
    #: not the sentence re-opened exactly that ambiguity at the gate.
    distribution_withheld: str | None = None

    @property
    def named(self) -> bool:
        """A definition with a name, a population the comparator's own floor allows to be
        described (`contracts/analytic.MIN_COHORT_POPULATION`), and members we can still point at.
        """
        return (bool(self.cohort_name)
                and self.population_size >= MIN_COHORT_POPULATION
                and self.members_enumerated > 0)

    def as_dict(self) -> dict[str, Any]:
        return {"subject_node_id": self.subject_node_id, "metric": self.metric,
                "cohort_id": self.cohort_id, "cohort_name": self.cohort_name,
                "node_type": self.node_type, "created_by": self.created_by,
                "population_size": self.population_size,
                "members_enumerated": self.members_enumerated,
                "member_ids": list(self.member_ids), "percentile_bp": self.percentile_bp,
                "band": self.band,
                "p25_bp": self.ladder[0], "p50_bp": self.ladder[1], "p75_bp": self.ladder[2],
                "distribution_withheld": self.distribution_withheld,
                "named": self.named}


@dataclass(frozen=True)
class PatternReceipt:
    """A pattern fire and WHY each of its conditions held.

    `matcher._evidenced` already treats a satisfied condition with no recoverable object as a
    FAILURE, so a fire that reaches the log should carry one evidence entry per satisfied
    condition. `evidenced` re-checks it at the read end anyway: this report's job is to show the
    receipt, and a fire whose evidence array was written empty by an older writer, or whose entries
    carry no `ref`, is exactly the claim it must refuse to count.
    """

    pattern_id: str
    pattern_version: int
    anchor_node_id: str
    anchor_node_type: str
    situation_type: str
    match_strength_bp: int
    activated: bool
    evaluated_at: str | None
    conditions: tuple[Mapping[str, Any], ...]

    @property
    def evidenced(self) -> bool:
        return bool(self.conditions) and all(str(c.get("ref") or "").strip()
                                             for c in self.conditions)

    def as_dict(self) -> dict[str, Any]:
        return {"pattern_id": self.pattern_id, "pattern_version": self.pattern_version,
                "anchor_node_id": self.anchor_node_id, "anchor_node_type": self.anchor_node_type,
                "situation_type": self.situation_type,
                "match_strength_bp": self.match_strength_bp, "activated": self.activated,
                "evaluated_at": self.evaluated_at, "evidenced": self.evidenced,
                "conditions": [dict(c) for c in self.conditions]}


@dataclass(frozen=True)
class SilentPattern:
    """A pattern that was EVALUATED in the window and matched nothing, and which condition stopped
    it. The other half of doc 09's per-condition-evidence row.

    `PatternReceipt` prints the conditions that HELD, because a fire only carries the satisfied
    ones — `matcher.MatchResult.evidence` is one entry per required condition of a match that
    happened. The conditions that did NOT hold are on the other side of the ledger, in
    `pattern_runs.top_failure_*`, which `store.record_evaluation` writes for every pattern
    including the silent ones. Doc 06's second failure mode is "a pattern that never fires", and a
    report that only printed successes could not tell "this tenant has no such situation" from
    "condition 4 reads a field this tenant spells differently" — the two look identical in a fire
    count of zero and want opposite responses.

    Not a gate row: a silent pattern is a legitimate answer, and failing H8 over one would fail it
    over a tenant who simply has no renewal at risk this week. It is printed, never scored.
    """

    pattern_id: str
    pattern_version: int
    anchors_considered: int
    top_failure_index: int | None
    top_failure_reason: str | None
    top_failure_field: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"pattern_id": self.pattern_id, "pattern_version": self.pattern_version,
                "anchors_considered": self.anchors_considered,
                "top_failure_index": self.top_failure_index,
                "top_failure_reason": self.top_failure_reason,
                "top_failure_field": self.top_failure_field}


@dataclass(frozen=True)
class Activation:
    """Whether this tenant is actually on the pilot, from the table that decides it."""

    analytic_live: bool = False
    patterns_live: bool = False
    analytic_enabled_at: datetime | None = None
    patterns_enabled_at: datetime | None = None
    analytic_disabled_at: datetime | None = None
    patterns_disabled_at: datetime | None = None
    enabled_by: str = ""
    notes: str = ""
    present: bool = False

    @property
    def live(self) -> bool:
        """BOTH switches. `patterns` off means the new path never ran; `analytic` off means nobody
        declared this window a pilot window. Either way the report has not measured a pilot."""
        return self.analytic_live and self.patterns_live

    def as_dict(self) -> dict[str, Any]:
        return {"present": self.present, "live": self.live,
                "enabled_by": self.enabled_by, "notes": self.notes,
                SWITCH_ANALYTIC: {"live": self.analytic_live,
                                  "enabled_at": _iso(self.analytic_enabled_at),
                                  "disabled_at": _iso(self.analytic_disabled_at)},
                SWITCH_PATTERNS: {"live": self.patterns_live,
                                  "enabled_at": _iso(self.patterns_enabled_at),
                                  "disabled_at": _iso(self.patterns_disabled_at)}}


@dataclass(frozen=True)
class ShadowDiff:
    org_id: str
    since: datetime
    until: datetime
    activation: Activation
    #: Live anchor-path situations produced in the window: (situation_id, anchor_node_id, type).
    anchor_situations: tuple[tuple[str, str, str], ...]
    #: Anchors the pattern path fired on in the window.
    pattern_anchors: frozenset[str]
    #: Pattern evaluation runs recorded in the window — the denominator that says the new path RAN.
    pattern_runs: int
    trends: tuple[SeriesReceipt, ...]
    cohorts: tuple[CohortReceipt, ...]
    patterns: tuple[PatternReceipt, ...]
    #: Evaluated in the window, matched nothing, and what stopped each one. Printed, never scored.
    silent: tuple[SilentPattern, ...]
    regressions: tuple[tuple[str, str, str], ...]     # (card_id, situation_id, anchor_node_id)
    caveats: tuple[str, ...] = field(default_factory=tuple)
    #: Live in the window but written by neither path — `periodic.py` and the readings that
    #: follow it insert straight into `context_situations` with a synthetic correlation id. Named
    #: in every report, counted in none: see `read_direct_writer_situations`.
    direct_writer_situations: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)

    # ── row 1 ────────────────────────────────────────────────────────────────────────────────
    @property
    def covered_situations(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(s for s in self.anchor_situations if s[1] in self.pattern_anchors)

    @property
    def lost_situations(self) -> tuple[tuple[str, str, str], ...]:
        """The situations that DISAPPEAR the day the anchor path is deleted. The breach, named."""
        return tuple(s for s in self.anchor_situations if s[1] not in self.pattern_anchors)

    @property
    def both_bp(self) -> int:
        """Share of anchor-path situations the pattern path also produced, in basis points.

        ZERO when the anchor path produced nothing, not 10000: a window with no anchor situations
        has not been compared, and a full percentage on an empty denominator is how "neither path
        ran here" reads as "the two agree completely".
        """
        total = len(self.anchor_situations)
        return 0 if total == 0 else len(self.covered_situations) * BP // total

    # ── rows 2, 3, 4 ─────────────────────────────────────────────────────────────────────────
    @property
    def citable_trends(self) -> tuple[SeriesReceipt, ...]:
        return tuple(t for t in self.trends if t.citable)

    @property
    def named_cohorts(self) -> tuple[CohortReceipt, ...]:
        return tuple(c for c in self.cohorts if c.named)

    @property
    def evidenced_patterns(self) -> tuple[PatternReceipt, ...]:
        return tuple(p for p in self.patterns if p.evidenced)

    @property
    def checks(self) -> tuple[tuple[str, str, str, bool], ...]:
        """(key, observed, gate, passed) for each of doc 09's five H8 lines."""
        total = len(self.anchor_situations)
        return (
            ("situations_produced_by_both",
             (f"{len(self.covered_situations)}/{total} ({self.both_bp} bp)" if total else
              "the anchor path produced no live situation in this window"),
             "100%", total > 0 and self.both_bp == BP),
            ("declining_trend_series_citable",
             f"{len(self.citable_trends)} citable of {len(self.trends)} declining",
             ">= 1", len(self.citable_trends) >= 1),
            ("cohort_position_population_named",
             f"{len(self.named_cohorts)} named of {len(self.cohorts)} positions",
             ">= 1", len(self.named_cohorts) >= 1),
            ("pattern_evidence_per_condition",
             f"{len(self.evidenced_patterns)} evidenced of {len(self.patterns)} fires",
             ">= 1", len(self.evidenced_patterns) >= 1),
            ("founder_visible_regressions", str(len(self.regressions)), "0",
             not self.regressions),
        )

    @property
    def passed(self) -> bool:
        """Activation is a PRECONDITION, not a metric: a tenant that is not on the pilot has not
        been measured, and a set of zeros from an inactive tenant must never read as a pass."""
        return self.activation.live and all(ok for _, _, _, ok in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": "H8", "org_id": self.org_id,
            "window": {"since": self.since.isoformat(), "until": self.until.isoformat()},
            "activation": self.activation.as_dict(),
            "anchor_situations": len(self.anchor_situations),
            "direct_writer_situations": [
                {"situation_id": s, "anchor_node_id": a, "situation_type": t}
                for s, a, t in self.direct_writer_situations[:MAX_BREACH_EXAMPLES]],
            "direct_writer_situation_count": len(self.direct_writer_situations),
            "pattern_runs": self.pattern_runs,
            "pattern_anchors": len(self.pattern_anchors),
            "lost_situations": [{"situation_id": s, "anchor_node_id": a, "situation_type": t}
                                for s, a, t in self.lost_situations[:MAX_BREACH_EXAMPLES]],
            "trend_receipts": [t.as_dict() for t in self.trends[:MAX_RECEIPTS]],
            "cohort_receipts": [c.as_dict() for c in self.cohorts[:MAX_RECEIPTS]],
            "pattern_receipts": [p.as_dict() for p in self.patterns[:MAX_RECEIPTS]],
            "silent_patterns": [p.as_dict() for p in self.silent],
            "founder_visible_regressions": [
                {"card_id": c, "situation_id": s, "anchor_node_id": a}
                for c, s, a in self.regressions[:MAX_BREACH_EXAMPLES]],
            "checks": [{"key": k, "observed": o, "gate": g, "passed": p}
                       for k, o, g, p in self.checks],
            "caveats": list(self.caveats),
            "not_measured": [{"key": k, "why": w} for k, w in NEEDS_REAL_TENANT],
            "pilot_command": PILOT_COMMAND,
            "passed": self.passed,
        }


# ── reads ────────────────────────────────────────────────────────────────────────────────────

def read_activation(conn, *, org_id: str) -> Activation:
    """`l2_v2_activation`, read directly rather than through `platform/l2_activation`.

    Direct because that module's gate reads are fail-CLOSED by design — an unreadable table
    answers "off" — and a gate report must distinguish "this tenant is not on the pilot" from "the
    activation table could not be read". Here an error propagates and the run fails loudly.
    """
    row = conn.execute(sql(
        "select analytic_enabled_at, analytic_disabled_at, patterns_enabled_at, "
        "       patterns_disabled_at, enabled_by, coalesce(notes,'') as notes "
        "from l2_v2_activation where org_id = :org"), {"org": org_id}).first()
    if row is None:
        return Activation()
    return Activation(
        present=True,
        analytic_live=row.analytic_enabled_at is not None and row.analytic_disabled_at is None,
        patterns_live=row.patterns_enabled_at is not None and row.patterns_disabled_at is None,
        analytic_enabled_at=row.analytic_enabled_at,
        analytic_disabled_at=row.analytic_disabled_at,
        patterns_enabled_at=row.patterns_enabled_at,
        patterns_disabled_at=row.patterns_disabled_at,
        enabled_by=str(row.enabled_by or ""), notes=str(row.notes or ""))


#: The anchor path is `context/situations.refresh_situations`, and this module's own header
#: defines it as "one situation per row of `context_correlations`". That join is the definition,
#: not an optimisation — see `read_anchor_situations`.
_ANCHOR_PATH_WINDOW = (
    "from context_situations s "
    "{join} context_correlations c on c.org_id = s.org_id "
    "  and c.correlation_id = s.correlation_id "
    "where s.org_id = :org and s.computed_at >= :since and s.computed_at <= :until "
    "and s.status = any(:statuses) {extra} order by s.situation_id")


def read_anchor_situations(conn, *, org_id: str, since: datetime, until: datetime
                           ) -> tuple[tuple[str, str, str], ...]:
    """The OLD path's output for the window: live situations `refresh_situations` computed.

    Bounded on `computed_at` rather than on `last_seen_at`, and the difference matters. The
    situation set is REBUILT from graph state on every sweep, so `computed_at` is "the anchor path
    produced this in the window" — which is the thing being compared. `last_seen_at` is when the
    tenant's own evidence last moved, so a window keyed on it would drop a live situation the
    anchor path produced all week about a relationship that has gone quiet, which is exactly the
    kind of situation the pattern path is most likely to miss.

    THE JOIN TO `context_correlations` IS THE DEFINITION OF THE PATH, and it used to be absent.
    `context_situations` is not one producer's table: `periodic.py`, `support_situations.py`,
    `document_register.py` and the readings that follow them write their rows DIRECTLY, with a
    synthetic correlation id and no `context_correlations` row, because their subject is a window
    or a computed anchor rather than a group of correlated events. This module's own header names
    the old path as "`context/situations.refresh_situations` derives one situation per row of
    `context_correlations`", and A-28 records that the row being scored is that path's loss —
    so counting a period aggregate the anchor path never produced attributes another producer's
    output to it, and then scores the pattern path for failing to reproduce something no pattern
    can anchor on (`patterns/store.evaluate_org` only ever walks `registry.anchor_types()`, and no
    pattern anchors on the tenant node `periodic.py` mints).

    This was invisible until the sweep clock was bound. The direct writers were called with the
    WALL clock while the rest of the drain ran at `sweep_at`, so their `computed_at` landed outside
    every historical window and they fell out of this read by accident. Binding them to `sweep_at`
    (the correct fix — one clock per sweep) put them in, and the mis-attribution surfaced as a
    gate that no tenant could ever pass: a real org gets one period situation per domain per week,
    forever, and none of them is reachable by the pattern path. `situations.active_situations`
    already carries the same distinction, in the opposite direction, for the same reason.

    NOTHING IS DROPPED SILENTLY: the excluded rows are read by `read_direct_writer_situations`
    and printed under their own heading in every report.
    """
    rows = conn.execute(sql(
        "select s.situation_id, s.anchor_node_id, s.situation_type "
        + _ANCHOR_PATH_WINDOW.format(join="join", extra="")),
        {"org": org_id, "since": since, "until": until,
         "statuses": list(LIVE_SITUATION_STATUSES)}).all()
    return tuple((str(r.situation_id), str(r.anchor_node_id), str(r.situation_type)) for r in rows)


def read_direct_writer_situations(conn, *, org_id: str, since: datetime, until: datetime
                                  ) -> tuple[tuple[str, str, str], ...]:
    """The live situations in the window that NEITHER path produced — the direct writers' rows.

    Printed, never scored, for the same reason a silent pattern is: they are a legitimate answer
    about a tenant rather than a breach, and a report that removed them from the loss check
    without naming them would be hiding the fact that they too disappear if anchor-based detection
    is deleted. They are named here so the reader can see exactly what was set aside and why.
    """
    rows = conn.execute(sql(
        "select s.situation_id, s.anchor_node_id, s.situation_type "
        + _ANCHOR_PATH_WINDOW.format(join="left join",
                                     extra="and c.correlation_id is null")),
        {"org": org_id, "since": since, "until": until,
         "statuses": list(LIVE_SITUATION_STATUSES)}).all()
    return tuple((str(r.situation_id), str(r.anchor_node_id), str(r.situation_type)) for r in rows)


def read_pattern_anchors(conn, *, org_id: str, since: datetime,
                         until: datetime) -> frozenset[str]:
    """Every anchor the NEW path fired on in the window."""
    return frozenset(str(r[0]) for r in conn.execute(sql(
        "select distinct anchor_node_id from pattern_fires where org_id = :org "
        "and evaluated_at >= :since and evaluated_at <= :until"),
        {"org": org_id, "since": since, "until": until}))


def count_pattern_runs(conn, *, org_id: str, since: datetime, until: datetime) -> int:
    """How many pattern evaluations were RECORDED in the window — the denominator that separates
    "the new path found nothing" from "the new path never ran". `record_evaluation` writes a run
    row for every pattern including the silent ones, which is the only reason this number exists.
    """
    return int(conn.execute(sql(
        "select count(*) from pattern_runs where org_id = :org "
        "and evaluated_at >= :since and evaluated_at <= :until"),
        {"org": org_id, "since": since, "until": until}).scalar() or 0)


def read_trend_receipts(conn, *, org_id: str, since: datetime,
                        until: datetime) -> tuple[SeriesReceipt, ...]:
    """Every DECLINING trend fact written in the window, each resolved against its own series.

    The second query is the receipt and it is deliberately not a join: the fact stores a pointer
    keyed on `(subject_node_id, metric, first_period, last_period)`, and reading it back the way a
    reader would is what proves the pointer WORKS rather than that a join can be written.
    """
    receipts: list[SeriesReceipt] = []
    rows = conn.execute(sql(
        "select subject_node_id, field, value from graph_facts "
        "where org_id = :org and field like :prefix and valid_to is null and status = 'active' "
        "and occurred_at >= :since and occurred_at <= :until "
        "order by subject_node_id, field"),
        {"org": org_id, "prefix": TREND_FIELD_PREFIX + "%", "since": since, "until": until}).all()
    for row in rows:
        body = _json(row.value, {})
        if not isinstance(body, dict) or str(body.get("direction", "")).lower() != DECLINING:
            continue
        series = body.get("series") or {}
        metric = str(series.get("metric") or body.get("metric") or "")
        node = str(series.get("subject_node_id") or row.subject_node_id)
        first, last = series.get("first_period"), series.get("last_period")
        points: tuple[tuple[str, int, str, bool | None], ...] = ()
        first_at, last_at = _instant(first), _instant(last)
        if metric and first_at and last_at:
            # PARSED, not passed through. The pointer is stored as ISO TEXT inside the fact body,
            # and handing that text straight to a `timestamptz` comparison leaves the driver to
            # guess the type — which is how a receipt query silently returns nothing on one driver
            # and the whole series on another. A pointer that will not parse resolves to no
            # points, which is exactly what "not citable" means.
            points = tuple(
                (_iso(p.observed_at) or "", int(p.value_bp), str(p.unit), p.coverage_ready)
                for p in conn.execute(sql(
                    "select observed_at, value_bp, unit, coverage_ready from metric_history "
                    "where org_id = :org and subject_node_id = :node and metric = :metric "
                    "and observed_at >= :first and observed_at <= :last order by observed_at"),
                    {"org": org_id, "node": node, "metric": metric,
                     "first": first_at, "last": last_at}).all())
        changepoint = body.get("changepoint") or {}
        receipts.append(SeriesReceipt(
            subject_node_id=node, metric=metric,
            claimed_periods=int(series.get("periods") or 0),
            trend_confidence_bp=int(body.get("trend_confidence_bp") or 0),
            relative_slope_bp=int(body.get("relative_slope_bp") or 0),
            streak_periods=int(body.get("streak_periods") or 0),
            first_period=_iso(first), last_period=_iso(last), points=points,
            changepoint_at=_iso(changepoint.get("at")) if isinstance(changepoint, dict) else None))
    return tuple(receipts)


def read_cohort_receipts(conn, *, org_id: str, since: datetime,
                         until: datetime) -> tuple[CohortReceipt, ...]:
    """Every cohort position written in the window, each resolved against its own population."""
    receipts: list[CohortReceipt] = []
    rows = conn.execute(sql(
        "select subject_node_id, field, value from graph_facts "
        "where org_id = :org and field like :prefix and valid_to is null and status = 'active' "
        "and occurred_at >= :since and occurred_at <= :until "
        "order by subject_node_id, field"),
        {"org": org_id, "prefix": COHORT_FIELD_PREFIX + "%", "since": since,
         "until": until}).all()
    for row in rows:
        body = _json(row.value, {})
        if not isinstance(body, dict) or body.get("refused"):
            # A refusal IS the right answer for a cohort too small to describe, and it is not a
            # position. Counting it would let "we could not compare this" satisfy a gate whose
            # subject is a comparison that was made.
            continue
        cohort_id = str(body.get("cohort_id") or "")
        definition = conn.execute(sql(
            "select name, node_type, created_by from cohort_definitions "
            "where org_id = :org and cohort_id = :cid"),
            {"org": org_id, "cid": cohort_id}).first() if cohort_id else None
        members = [str(r[0]) for r in conn.execute(sql(
            "select node_id from cohort_membership where org_id = :org and cohort_id = :cid "
            "and joined_at <= :at and (left_at is null or left_at > :at) "
            "order by node_id"), {"org": org_id, "cid": cohort_id, "at": until}).all()
        ] if cohort_id else []
        receipts.append(CohortReceipt(
            subject_node_id=str(row.subject_node_id),
            metric=str(body.get("metric") or ""), cohort_id=cohort_id,
            cohort_name=str(definition.name) if definition is not None else None,
            node_type=str(definition.node_type) if definition is not None else None,
            created_by=str(definition.created_by) if definition is not None else None,
            population_size=int(body.get("population_size") or 0),
            members_enumerated=len(members),
            member_ids=tuple(members[:MAX_MEMBERS_NAMED]),
            percentile_bp=(int(body["percentile_bp"])
                           if body.get("percentile_bp") is not None else None),
            band=str(body.get("band")) if body.get("band") is not None else None,
            ladder=(body.get("p25_bp"), body.get("p50_bp"), body.get("p75_bp")),
            distribution_withheld=(str(body["distribution_withheld"])
                                   if body.get("distribution_withheld") else None)))
    return tuple(receipts)


def read_pattern_receipts(conn, *, org_id: str, since: datetime,
                          until: datetime) -> tuple[PatternReceipt, ...]:
    """Every fire in the window with its per-condition evidence, verbatim from the log."""
    rows = conn.execute(sql(
        "select pattern_id, pattern_version, anchor_node_id, anchor_node_type, situation_type, "
        "       match_strength_bp, activated, evidence, evaluated_at from pattern_fires "
        "where org_id = :org and evaluated_at >= :since and evaluated_at <= :until "
        "order by match_strength_bp desc, pattern_id, anchor_node_id"),
        {"org": org_id, "since": since, "until": until}).all()
    receipts: list[PatternReceipt] = []
    for row in rows:
        evidence = _json(row.evidence, [])
        conditions = tuple(c for c in (evidence if isinstance(evidence, list) else [])
                           if isinstance(c, dict))
        receipts.append(PatternReceipt(
            pattern_id=str(row.pattern_id), pattern_version=int(row.pattern_version),
            anchor_node_id=str(row.anchor_node_id),
            anchor_node_type=str(row.anchor_node_type),
            situation_type=str(row.situation_type),
            match_strength_bp=int(row.match_strength_bp), activated=bool(row.activated),
            evaluated_at=_iso(row.evaluated_at), conditions=conditions))
    return tuple(receipts)


def read_silent_patterns(conn, *, org_id: str, since: datetime,
                         until: datetime) -> tuple[SilentPattern, ...]:
    """Every pattern EVALUATED in the window that produced no fire, with the condition that
    stopped it most often. Reads `pattern_runs`, which is the only record a silent pattern leaves.
    """
    rows = conn.execute(sql(
        "select pattern_id, pattern_version, sum(anchors_considered) as anchors, "
        "       sum(fires) as fires, "
        "       min(top_failure_index) as idx, min(top_failure_reason) as reason, "
        "       min(top_failure_field) as field "
        "from pattern_runs where org_id = :org "
        "and evaluated_at >= :since and evaluated_at <= :until "
        "group by pattern_id, pattern_version having sum(fires) = 0 "
        "order by pattern_id"),
        {"org": org_id, "since": since, "until": until}).all()
    return tuple(SilentPattern(
        pattern_id=str(r.pattern_id), pattern_version=int(r.pattern_version),
        anchors_considered=int(r.anchors or 0),
        top_failure_index=None if r.idx is None else int(r.idx),
        top_failure_reason=str(r.reason) if r.reason else None,
        top_failure_field=str(r.field) if r.field else None) for r in rows)


def read_regressions(conn, *, org_id: str, since: datetime,
                     until: datetime) -> tuple[tuple[str, str, str], ...]:
    """The cards that STOP EXISTING the day anchor-based detection is deleted.

    The founder-visible object is the card, and the chain to a Layer 2 situation is
    `cards -> signals.subject_node_id -> context_situations.anchor_node_id` — the only link the
    schema carries between something a founder looks at and something Layer 2 produced. A card
    whose subject has a live anchor-path situation and NO pattern fire in the window is a card the
    switch-over removes; that is the regression, stated as the thing a person loses rather than as
    a count of rows.

    Restricted to LIVE cards (`expires_at` in the future at the window's end) because an expired
    card is not something a founder can see, and counting it would fail the gate over a card that
    had already gone.
    """
    rows = conn.execute(sql(
        "select distinct c.card_id, s2.situation_id, s2.anchor_node_id "
        "from cards c "
        "join signals s on s.signal_id = c.signal_id and s.org_id = c.org_id "
        "join context_situations s2 on s2.org_id = c.org_id "
        "  and s2.anchor_node_id = s.subject_node_id "
        "where c.org_id = :org and (c.expires_at is null or c.expires_at >= :until) "
        "  and s2.status = any(:statuses) "
        "  and s2.computed_at >= :since and s2.computed_at <= :until "
        "  and not exists (select 1 from pattern_fires f where f.org_id = c.org_id "
        "                   and f.anchor_node_id = s2.anchor_node_id "
        "                   and f.evaluated_at >= :since and f.evaluated_at <= :until) "
        "order by c.card_id"),
        {"org": org_id, "since": since, "until": until,
         "statuses": list(LIVE_SITUATION_STATUSES)}).all()
    return tuple((str(r.card_id), str(r.situation_id), str(r.anchor_node_id)) for r in rows)


def build_report(conn, *, org_id: str, since: datetime, until: datetime) -> ShadowDiff:
    activation = read_activation(conn, org_id=org_id)
    anchor_situations = read_anchor_situations(conn, org_id=org_id, since=since, until=until)
    direct_writers = read_direct_writer_situations(conn, org_id=org_id, since=since, until=until)
    pattern_anchors = read_pattern_anchors(conn, org_id=org_id, since=since, until=until)
    runs = count_pattern_runs(conn, org_id=org_id, since=since, until=until)

    caveats: list[str] = []
    if not activation.present:
        caveats.append("this tenant has NO row in l2_v2_activation. Nobody declared it a Layer 2 "
                       "v2 pilot, and the pattern shadow pass therefore never ran on any sweep: "
                       "every number below is the anchor path measured against nothing. "
                       "'Built but not enabled is not done.'")
    else:
        if not activation.patterns_live:
            caveats.append("the `patterns` switch is not live, so context/runner.process_pending "
                           "did not run the L2.6 shadow pass: pattern_fires cannot have grown "
                           "during this window whatever it contains.")
        if not activation.analytic_live:
            caveats.append("the `analytic` switch is not live. It gates no code (the analytic "
                           "stratum is unconditional), but it is what declares this window a "
                           "pilot window — without it these numbers describe a week nobody chose.")
        for switch, off in ((SWITCH_ANALYTIC, activation.analytic_disabled_at),
                            (SWITCH_PATTERNS, activation.patterns_disabled_at)):
            if off is not None and since <= off <= until:
                caveats.append(f"the `{switch}` switch was turned OFF at {off.isoformat()}, "
                               "INSIDE this window: the two paths ran side by side for part of it "
                               "and not all of it.")
        for switch, on in ((SWITCH_ANALYTIC, activation.analytic_enabled_at),
                           (SWITCH_PATTERNS, activation.patterns_enabled_at)):
            if on is not None and on > since:
                caveats.append(f"the `{switch}` switch was turned ON at {on.isoformat()}, AFTER "
                               "this window opened: the window is longer than the pilot.")
    if runs == 0:
        caveats.append("no pattern_runs rows in this window: the pattern registry was never "
                       "evaluated here, so 'situations produced by both paths' is the anchor "
                       "path compared with an empty set rather than with a second path.")
    if not anchor_situations:
        caveats.append("the anchor path produced no live situation in this window, so there is "
                       "nothing to lose and nothing to compare — the first row reports 0, not "
                       "100%, deliberately.")

    return ShadowDiff(
        org_id=org_id, since=since, until=until, activation=activation,
        anchor_situations=anchor_situations, pattern_anchors=pattern_anchors, pattern_runs=runs,
        trends=read_trend_receipts(conn, org_id=org_id, since=since, until=until),
        cohorts=read_cohort_receipts(conn, org_id=org_id, since=since, until=until),
        patterns=read_pattern_receipts(conn, org_id=org_id, since=since, until=until),
        silent=read_silent_patterns(conn, org_id=org_id, since=since, until=until),
        regressions=read_regressions(conn, org_id=org_id, since=since, until=until),
        caveats=tuple(caveats), direct_writer_situations=direct_writers)


# ── rendering: the receipts, not the counts ──────────────────────────────────────────────────

def render(report: ShadowDiff) -> str:
    act = report.activation
    lines = [f"H8 shadow diff — org={report.org_id}",
             f"  window     {report.since:%Y-%m-%d %H:%M} .. {report.until:%Y-%m-%d %H:%M} UTC",
             "  activation " + ("  ".join(
                 f"{s}={'LIVE' if (act.analytic_live if s == SWITCH_ANALYTIC else act.patterns_live) else 'off'}"
                 for s in SWITCHES) + (f"   (by {act.enabled_by})" if act.enabled_by else "")),
             f"  anchor path  {len(report.anchor_situations)} live situations"
             + (f"  (+{len(report.direct_writer_situations)} written by neither path)"
                if report.direct_writer_situations else ""),
             f"  pattern path {report.pattern_runs} runs, "
             f"{len(report.pattern_anchors)} anchors fired, {len(report.patterns)} fires", ""]
    for key, observed, gate, ok in report.checks:
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {key:<34} {observed}   (gate {gate})")

    if report.lost_situations:
        lines += ["", "  situations the anchor path produced and the pattern path did not "
                      "(these disappear on switch-over):"]
        for sid, anchor, stype in report.lost_situations[:MAX_BREACH_EXAMPLES]:
            lines.append(f"    {sid}  anchor={anchor}  type={stype}")
        if len(report.lost_situations) > MAX_BREACH_EXAMPLES:
            lines.append(f"    … and {len(report.lost_situations) - MAX_BREACH_EXAMPLES} more")

    if report.direct_writer_situations:
        lines += ["", "  live situations written by NEITHER path — `periodic.py` and the readings "
                      "that follow it insert directly, with no `context_correlations` row, so "
                      "`refresh_situations` never produced them and no pattern can anchor on "
                      "them (printed, never scored; they disappear with the anchor path too):"]
        for sid, anchor, stype in report.direct_writer_situations[:MAX_BREACH_EXAMPLES]:
            lines.append(f"    {sid}  anchor={anchor}  type={stype}")
        if len(report.direct_writer_situations) > MAX_BREACH_EXAMPLES:
            lines.append("    … and "
                         f"{len(report.direct_writer_situations) - MAX_BREACH_EXAMPLES} more")

    # THE RECEIPTS. Doc 09's three bold rows are claims, and a claim without its numbers is the
    # thing this layer exists to stop producing — so the numbers are printed, not summarised.
    if report.trends:
        lines += ["", "  RECEIPT · 'this is getting worse' — the series each decline was "
                      "computed from:"]
        for trend in report.trends[:MAX_RECEIPTS]:
            mark = "citable" if trend.citable else "NOT CITABLE"
            lines.append(f"    {trend.subject_node_id}  {trend.metric}  [{mark}]  "
                         f"confidence={trend.trend_confidence_bp}bp  "
                         f"slope={trend.relative_slope_bp}bp  streak={trend.streak_periods}")
            for at, value, unit, coverage in trend.points:
                flag = "" if coverage is not False else "   (coverage not ready)"
                lines.append(f"        {at}  {value} {unit}{flag}")
            if not trend.points:
                lines.append(f"        claims {trend.claimed_periods} periods "
                             f"{trend.first_period}..{trend.last_period}; metric_history "
                             "returned NONE — the pointer does not resolve")
            elif not trend.citable:
                lines.append(f"        claims {trend.claimed_periods} periods, "
                             f"{len(trend.points)} resolve")
            if trend.changepoint_at:
                lines.append(f"        changepoint at {trend.changepoint_at}")

    if report.cohorts:
        lines += ["", "  RECEIPT · 'this is unlike its peers' — the population each position was "
                      "cut from:"]
        for cohort in report.cohorts[:MAX_RECEIPTS]:
            mark = "named" if cohort.named else "POPULATION NOT NAMED"
            lines.append(f"    {cohort.subject_node_id}  {cohort.metric}  [{mark}]  "
                         f"percentile={cohort.percentile_bp}bp  band={cohort.band}")
            lines.append(f"        cohort {cohort.cohort_id} "
                         f"\"{cohort.cohort_name or '(no definition row)'}\" "
                         f"({cohort.node_type or '?'}, by {cohort.created_by or '?'})  "
                         f"population={cohort.population_size}  "
                         f"members enumerated={cohort.members_enumerated}")
            p25, p50, p75 = cohort.ladder
            if cohort.distribution_withheld:
                lines.append(f"        ladder WITHHELD — {cohort.distribution_withheld}")
            else:
                lines.append(f"        ladder p25={p25} p50={p50} p75={p75}")
            if cohort.member_ids:
                lines.append("        members: " + ", ".join(cohort.member_ids))

    if report.patterns:
        lines += ["", "  RECEIPT · 'these facts hold together' — the per-condition evidence "
                      "behind each fire:"]
        for pattern in report.patterns[:MAX_RECEIPTS]:
            mark = "evidenced" if pattern.evidenced else "NO PER-CONDITION EVIDENCE"
            lines.append(f"    {pattern.pattern_id}@{pattern.pattern_version}  "
                         f"anchor={pattern.anchor_node_id} ({pattern.anchor_node_type})  "
                         f"type={pattern.situation_type}  "
                         f"strength={pattern.match_strength_bp}bp  "
                         f"{'ACTIVATED' if pattern.activated else 'shadow'}  [{mark}]")
            for condition in pattern.conditions:
                lines.append(
                    f"        #{condition.get('index')} {condition.get('kind')} "
                    f"{condition.get('field_path')} {condition.get('operator')} "
                    f"{condition.get('expected')!r} -> observed {condition.get('observed')!r}  "
                    f"ref={condition.get('ref') or '(NONE)'}")
            if not pattern.conditions:
                lines.append("        (the evidence array is empty — this fire cannot say why)")

    if report.silent:
        lines += ["", "  and the patterns that did NOT fire — the condition that stopped each "
                      "(doc 06's second failure mode; not a gate row):"]
        for quiet in report.silent:
            where = ("nothing to match: no anchor of this pattern's type in the graph"
                     if quiet.anchors_considered == 0 else
                     f"stopped at condition #{quiet.top_failure_index} "
                     f"({quiet.top_failure_reason}) on {quiet.top_failure_field}"
                     if quiet.top_failure_reason else "no failure recorded")
            lines.append(f"    {quiet.pattern_id}@{quiet.pattern_version}  "
                         f"{quiet.anchors_considered} anchors considered, 0 fires — {where}")

    if report.regressions:
        lines += ["", "  founder-visible regressions — cards that stop existing on switch-over:"]
        for card_id, situation_id, anchor in report.regressions[:MAX_BREACH_EXAMPLES]:
            lines.append(f"    card {card_id}  situation {situation_id}  anchor {anchor}")

    for caveat in report.caveats:
        lines += ["", f"  NOTE: {caveat}"]

    lines += ["", "  NOT MEASURED WITHOUT A REAL TENANT AND REAL ELAPSED TIME:"]
    for key, why in NEEDS_REAL_TENANT:
        lines.append(f"    {key:<34} {why}")
    lines += [f"    run then: {PILOT_COMMAND}"]
    lines += ["", f"  VERDICT: {'PASS' if report.passed else 'FAIL'}"]
    return "\n".join(lines)


def parse_instant(value: str) -> datetime:
    """`--as-of`, so the window's end is an ARGUMENT and not a clock.

    Doctrine 4 puts the clock at the process boundary; `main` reads it once when this is absent.
    Naive input is read as UTC rather than refused: every timestamp in this database is stored
    aware in UTC, and an operator typing `2026-09-01T00:00:00` means that instant there.
    """
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--as-of must be an ISO-8601 instant (e.g. 2026-09-01T00:00:00Z); got {value!r}"
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="l2_shadow_diff",
        description="H8 pilot report: the L2.6 pattern path beside anchor-based detection.")
    parser.add_argument("--org", required=True, help="pilot org id")
    parser.add_argument("--days", type=int, default=7, help="window in whole days (default 7)")
    parser.add_argument("--since", type=parse_since, default=None,
                        help="window as 30d/12h/90m; overrides --days when given")
    parser.add_argument("--as-of", type=parse_instant, default=None, dest="as_of",
                        help="end of the window as an ISO instant; default is now, read once here")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    # The target banner goes to STDERR under `--json` and to stdout otherwise. `scripts/_db.py`
    # prints it before returning on purpose — a guard the operator cannot see is a guard they
    # cannot correct — but two human-readable lines ahead of a JSON document make the document
    # unparseable, so a CI step piping this report into `jq` would either lose the guard or lose
    # the report. Both survive on separate streams.
    url = resolve_database_url(args, purpose="H8 L2 v2 shadow diff (read-only)",
                               stream=sys.stderr if args.json else sys.stdout)

    from genios_engine.platform.db import get_engine
    until = args.as_of or datetime.now(timezone.utc)
    window = args.since if args.since is not None else timedelta(days=args.days)
    conn = read_only_connection(get_engine(url))
    try:
        report = build_report(conn, org_id=args.org, since=until - window, until=until)
    finally:
        conn.close()

    print(json.dumps(report.as_dict(), indent=2) if args.json else render(report))
    return 0 if report.passed else 1


if __name__ == "__main__":                              # pragma: no cover - CLI entry
    raise SystemExit(main())
