"""K1 · the ranking-distribution report — **the formula finally decides**, measured.

    python scripts/ranking_distribution.py --org <pilot> --days 7 \
        --database-url postgresql://…

WHAT THIS MEASURES AND WHY A UNIT TEST CANNOT. `reason/decision_maker.py` recorded, in its own
source, that *"the formula has never once decided anything"* — the compiled adapter hands the
authored corpus priority to `core.priority` as config for every candidate, `score_candidate`
returned that override verbatim, and every ranked candidate on the lane carried one identical
utility. Every unit test around it passed, because each one asserted about a single candidate and
a constant is correct on every single candidate. So the gate is a DISTRIBUTION over what the
production path actually persisted:

  | metric                                       | gate      | why                             |
  |----------------------------------------------|-----------|---------------------------------|
  | distinct `final_utility_bp` per day          | >= 50     | one value means it is not ranking|
  | same situation type, different importance    | ranks     | the three-layer supply chain     |
  | `formula_utility` recorded on every candidate| 100%      | the divergence is the instrument |
  | `do_nothing` marked `computed`                | >= 80%    | a consequence nobody can check   |

G7 → H5 → K1 must hold on the SAME pilot in the same fortnight (doc 08). G7 proves Layer 1
supplies importance, H5 proves Layer 2 composes it, and this proves Layer 4 finally decides with
it. Any one of the three passing alone changes nothing a customer can see, so this report prints
the importance coverage it actually observed rather than assuming the layers below fired.

NOTHING IS RECOMPUTED HERE and no scorer is imported. Every number is read off the rows
`reason/audit.py` wrote on the reasoning path — `reasoning_candidates.score_components`,
`reasoning_candidates.final_utility_bp` and `reasoning_run_outputs.decision_core` — because a
report that re-derived the utility would answer "does the formula agree with itself" instead of
"what did the engine store".

READ-ONLY, AT THE SERVER. `set transaction read only` is the first statement of the transaction
(`scripts/_gate.py`), and the target is resolved through `scripts/_db.py`, which has no fallback
to the application's configured database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from genios_engine.contracts.reasoning import (                          # noqa: E402
    FORMULA_UTILITY_COMPONENT,
    RANKING_WEIGHTS_V1_VERSION,
)
from genios_engine.reason.decision_maker import (                        # noqa: E402
    IMPORTANCE_COMPONENT,
    PRIORITY_OVERRIDE_COMPONENT,
)
from scripts._db import add_database_argument, resolve_database_url      # noqa: E402
from scripts._gate import read_only_connection, sql                      # noqa: E402

#: Doc 04's own thresholds. Named so a failure message can quote the gate it failed, and so
#: moving one is a visible edit rather than a changed digit inside a comparison.
MIN_DISTINCT_UTILITIES = 50
MIN_DO_NOTHING_COMPUTED_BP = 8_000
BP_MAX = 10_000

#: How many candidate rows one report reads. A gate on a busy tenant must not become an unbounded
#: scan; the newest rows are the ones the newest model wrote.
DEFAULT_LIMIT = 100_000

_CANDIDATES = (
    "select c.candidate_id, c.run_id, c.final_utility_bp, c.score_components, "
    "       c.disposition, c.rank_position, r.capability_id, r.evaluation_time "
    "from reasoning_candidates c "
    "join reasoning_runs r on r.org_id = c.org_id and r.run_id = c.run_id "
    "where c.org_id = :org and r.evaluation_time >= :since "
    "  and c.disposition = 'eligible' and c.rank_position is not null "
    "order by r.evaluation_time desc, c.candidate_id "
    "limit :lim"
)

_OUTPUTS = (
    "select o.run_id, o.outcome_kind, o.decision_core, r.capability_id, r.evaluation_time "
    "from reasoning_run_outputs o "
    "join reasoning_runs r on r.org_id = o.org_id and r.run_id = o.run_id "
    "where o.org_id = :org and r.evaluation_time >= :since "
    "order by r.evaluation_time desc, o.run_id "
    "limit :lim"
)


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return dict(value) if isinstance(value, dict) else {}


def _day(moment: Any) -> str:
    return moment.date().isoformat() if isinstance(moment, datetime) else str(moment)[:10]


@dataclass(frozen=True)
class RankingDistribution:
    """The K1 verdict for one org over one window."""

    org_id: str
    since: datetime
    until: datetime
    candidates: int
    decisions: int
    #: The gate is worded "per day", and a week's rows pooled into one set would pass on seven
    #: flat days that happened to differ from each other. The WORST day is the verdict.
    per_day: tuple[tuple[str, int], ...]
    distinct_overall: int
    with_formula: int
    with_importance: int
    with_override: int
    #: capability_id -> (distinct importance values, distinct utilities among them). Doc 04's
    #: second row, answered from the rows rather than by assertion.
    ranked_by_importance: tuple[tuple[str, int, int], ...]
    do_nothing_computed: int
    do_nothing_fallback: int
    do_nothing_absent: int
    ranking_versions: tuple[str, ...]
    digest: str
    top_utilities: tuple[tuple[int, int], ...]

    @property
    def worst_day(self) -> tuple[str, int] | None:
        return min(self.per_day, key=lambda row: row[1]) if self.per_day else None

    @property
    def do_nothing_total(self) -> int:
        return self.do_nothing_computed + self.do_nothing_fallback + self.do_nothing_absent

    @property
    def computed_bp(self) -> int:
        total = self.do_nothing_total
        return 0 if total == 0 else self.do_nothing_computed * BP_MAX // total

    @property
    def distinct_passed(self) -> bool:
        worst = self.worst_day
        return worst is not None and worst[1] >= MIN_DISTINCT_UTILITIES

    @property
    def divergence_passed(self) -> bool:
        """100%, not "most". A candidate with no `formula_utility` is one whose divergence cannot
        be computed at all, and doc 08 retires the 70/30 weight against exactly that number."""
        return bool(self.candidates) and self.with_formula == self.candidates

    @property
    def importance_ranking_passed(self) -> bool:
        """At least one capability where two situations of the same type carried DIFFERENT
        importance and reached DIFFERENT utilities. A capability whose situations all scored the
        same importance cannot demonstrate it either way and is not counted against the gate."""
        return any(utilities > 1 for _capability, importances, utilities
                   in self.ranked_by_importance if importances > 1)

    @property
    def do_nothing_passed(self) -> bool:
        return bool(self.do_nothing_total) and self.computed_bp >= MIN_DO_NOTHING_COMPUTED_BP

    @property
    def passed(self) -> bool:
        """A window with no candidate is NOT a pass. Nothing was measured, and a gate that returns
        green for an empty table is how "the model never ran" reads as success."""
        return bool(self.candidates) and self.distinct_passed and self.divergence_passed \
            and self.importance_ranking_passed and self.do_nothing_passed

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": "K1", "org_id": self.org_id,
            "window": {"since": self.since.isoformat(), "until": self.until.isoformat()},
            "candidates": self.candidates, "decisions": self.decisions,
            "distinct_utilities_overall": self.distinct_overall,
            "distinct_utilities_per_day": [{"day": day, "distinct": n} for day, n in self.per_day],
            "min_distinct": MIN_DISTINCT_UTILITIES,
            "with_formula_utility": self.with_formula,
            "with_importance": self.with_importance,
            "with_priority_override": self.with_override,
            "ranked_by_importance": [
                {"capability_id": capability, "distinct_importance": importances,
                 "distinct_utility": utilities}
                for capability, importances, utilities in self.ranked_by_importance],
            "do_nothing": {"computed": self.do_nothing_computed,
                           "manifest_fallback": self.do_nothing_fallback,
                           "absent": self.do_nothing_absent,
                           "computed_bp": self.computed_bp,
                           "min_computed_bp": MIN_DO_NOTHING_COMPUTED_BP},
            "ranking_weights_versions": list(self.ranking_versions),
            "digest": self.digest,
            "top_utilities": [{"final_utility_bp": bp, "count": n}
                              for bp, n in self.top_utilities],
            "checks": {"distinct": self.distinct_passed,
                       "divergence": self.divergence_passed,
                       "importance_ranks": self.importance_ranking_passed,
                       "do_nothing": self.do_nothing_passed},
            "passed": self.passed,
        }


def measure(candidate_rows, output_rows, *, org_id: str, since: datetime,
            until: datetime) -> RankingDistribution:
    """The whole verdict, from rows alone — importable, so the acceptance test does not need a DB."""
    per_day: dict[str, set[int]] = {}
    utilities: dict[int, int] = {}
    by_capability: dict[str, dict[int, set[int]]] = {}
    with_formula = with_importance = with_override = 0
    digest_material: list[tuple[str, int, str]] = []

    for row in candidate_rows:
        components = _json(row["score_components"])
        utility = int(row["final_utility_bp"])
        per_day.setdefault(_day(row["evaluation_time"]), set()).add(utility)
        utilities[utility] = utilities.get(utility, 0) + 1
        if FORMULA_UTILITY_COMPONENT in components:
            with_formula += 1
        if PRIORITY_OVERRIDE_COMPONENT in components:
            with_override += 1
        importance = components.get(IMPORTANCE_COMPONENT)
        if importance is not None:
            with_importance += 1
            by_capability.setdefault(str(row["capability_id"]), {}).setdefault(
                int(importance), set()).add(utility)
        digest_material.append((str(row["candidate_id"]), utility,
                                json.dumps(components, sort_keys=True, default=str)))

    computed = fallback = absent = 0
    versions: set[str] = set()
    decisions = 0
    for row in output_rows:
        if str(row["outcome_kind"]) != "decision":
            continue
        decisions += 1
        core = _json(row["decision_core"])
        version = core.get("ranking_weights_version")
        # A decision that carries no version was ranked under the legacy five, which is
        # exactly what the absence means — see `ReasoningDecision.to_semantic_dict`.
        versions.add(str(version) if version else RANKING_WEIGHTS_V1_VERSION)
        do_nothing = core.get("do_nothing")
        if not isinstance(do_nothing, dict) or "source" not in do_nothing:
            absent += 1
        elif do_nothing["source"] == "computed":
            computed += 1
        else:
            fallback += 1

    ranked = tuple(sorted(
        (capability, len(buckets), len({u for values in buckets.values() for u in values}))
        for capability, buckets in by_capability.items()))
    digest = hashlib.sha256(
        json.dumps(sorted(digest_material), sort_keys=True).encode("utf-8")).hexdigest()
    return RankingDistribution(
        org_id=org_id, since=since, until=until,
        candidates=len(digest_material), decisions=decisions,
        per_day=tuple(sorted((day, len(values)) for day, values in per_day.items())),
        distinct_overall=len(utilities),
        with_formula=with_formula, with_importance=with_importance, with_override=with_override,
        ranked_by_importance=ranked,
        do_nothing_computed=computed, do_nothing_fallback=fallback, do_nothing_absent=absent,
        ranking_versions=tuple(sorted(versions)), digest=digest,
        top_utilities=tuple(sorted(utilities.items(), key=lambda item: (-item[1], item[0]))[:5]))


#: Rendered verdict. Three words, not two — see the comment at the VERDICT line.
NO_DATA_VERDICT = ("NO DATA — no ranked candidate in this window; widen --days (it counts back "
                   "from now, not from the population) or check the org id")


def _verdict(report: "RankingDistribution") -> str:
    if report.passed:
        return "PASS"
    return "FAIL" if report.candidates else NO_DATA_VERDICT


def _render(report: RankingDistribution) -> str:
    lines = [
        f"K1 · ranking distribution — {report.org_id}",
        f"  window            {report.since.isoformat()} .. {report.until.isoformat()}",
        f"  ranked candidates {report.candidates}   decisions {report.decisions}",
        f"  weights           {', '.join(report.ranking_versions) or '(none)'}",
        "",
        f"  distinct final_utility_bp, worst day   {report.worst_day or '(no rows)'}"
        f"   gate >= {MIN_DISTINCT_UTILITIES}   {'PASS' if report.distinct_passed else 'FAIL'}",
        f"  formula_utility recorded               {report.with_formula}/{report.candidates}"
        f"   gate 100%   {'PASS' if report.divergence_passed else 'FAIL'}",
        f"  importance carried                     {report.with_importance}/{report.candidates}",
        f"  override carried (demoted to a prior)  {report.with_override}/{report.candidates}",
        f"  same type, different importance ranks  "
        f"{'PASS' if report.importance_ranking_passed else 'FAIL'}",
        f"  do_nothing computed                    {report.computed_bp} bp of "
        f"{report.do_nothing_total}   gate >= {MIN_DO_NOTHING_COMPUTED_BP} bp   "
        f"{'PASS' if report.do_nothing_passed else 'FAIL'}",
        "",
        f"  top utilities     {list(report.top_utilities)}",
        f"  digest            {report.digest}",
        # FAIL and NO DATA are both "not a pass" — `passed` is False either way and nothing here
        # changes that. But a reader who cannot tell them apart mistrusts the gate once and then
        # ignores it, and the two need different work: FAIL is a defect in the engine, NO DATA is
        # a window that looked in the wrong week. `--days` counts back from the WALL clock, so a
        # seeded or historical population reports zero candidates unless the window is widened.
        f"  VERDICT           {_verdict(report)}",
    ]
    for capability, importances, utility_count in report.ranked_by_importance:
        lines.append(f"    {capability}: {importances} distinct importance -> "
                     f"{utility_count} distinct utility")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="K1 · the ranking-distribution gate")
    parser.add_argument("--org", required=True)
    parser.add_argument("--days", type=int, default=7,
                        help="whole days of evaluation_time to read (default 7)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json", action="store_true")
    add_database_argument(parser)
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be a whole number of days greater than zero")

    # `platform.db.get_engine`, not a bare `create_engine`: this codebase runs psycopg3, and a
    # `postgresql://` URL handed straight to SQLAlchemy resolves to psycopg2, which is not
    # installed — so the gate command doc 08 prints for K1 died with `ModuleNotFoundError` on
    # every invocation and the gate could never be RUN, let alone failed. `get_engine` performs
    # the same scheme rewrite the application performs, which is also the only way this report
    # reaches the database through the driver production uses.
    from genios_engine.platform.db import get_engine

    engine = get_engine(resolve_database_url(args, purpose="K1 ranking distribution"))
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=args.days)
    params = {"org": args.org, "since": since, "lim": args.limit}
    with read_only_connection(engine) as conn:
        candidates = conn.execute(sql(_CANDIDATES), params).mappings().all()
        outputs = conn.execute(sql(_OUTPUTS), params).mappings().all()
    report = measure(candidates, outputs, org_id=args.org, since=since, until=until)
    print(json.dumps(report.as_dict(), indent=2) if args.json else _render(report))
    return 0 if report.passed else 1


if __name__ == "__main__":       # pragma: no cover - entry point
    raise SystemExit(main())
