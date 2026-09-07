"""H5 · the situation-importance distribution report — **the Layer 2 ranking gate**, measured.

    python scripts/situation_importance_distribution.py --org <pilot> --since 30d \
        --database-url postgresql://…

WHAT THIS MEASURES AND WHY IT IS NOT A UNIT TEST. `context/situation_bso.py` stamped
`DEFAULT_IMPORTANCE_BP = 5000` on every `BusinessSituationObject` ever produced, and every test
around it passed: each situation was individually correct and the aggregate could not rank
anything. A composer is correct per situation and useless in aggregate the moment its inputs
collapse, and no test of one situation can see that. So the gate is a DISTRIBUTION over what the
production sweep actually STORED:

  | distinct `importance_bp` values      | > 50    | 5000-for-everything is the defect |
  | p90 - p50                            | > 1500  | a flat distribution cannot rank   |
  | situations at exactly 5000           | < 5%    | the constant is gone              |
  | `importance_components` populated    | 100%    | explainability                    |

**WHAT "AT EXACTLY 5000" MEANS NOW, AND WHY IT IS NOT THE SAME QUESTION IT WAS.** Step 1 of BLG-18
has already landed: `gather_l1_signals` reads Layer 1's real score and `build_business_situation`
records which of four sources it came from. `DEFAULT_IMPORTANCE_BP` survives as the DOCUMENTED
FALLBACK for a situation whose events published no live signal, and it is reachable and correct.
So this row is no longer a hardcode detector — it is a measure of the `importance_source =
'default'` SHARE, and the report prints the source breakdown beside it so a breach can be read as
what it is: too many situations with no Layer 1 supply, not a constant in the code.

**THE FIFTH ROW IS NOT HERE, AND THAT IS DELIBERATE.** "One critical + four routine signals >=
9000" is a statement about a CONSTRUCTED input, not about a tenant, and a report that went looking
for that shape in production data would either not find it (and fail a real tenant for having no
such situation) or find something like it and grade the composer on a coincidence. It is proven
where a constructed input belongs — `tests/context/test_situation_importance.py`, against the real
`gather_l1_signals` on a real database.

NOTHING IS RECOMPUTED HERE and no composer is imported for its arithmetic. The rows were written
by `context/situations.refresh_situations` on the sweep; if the composition never ran, this report
says so with a zero and a null count rather than by producing a number of its own.

THE PERCENTILE IS `importance.nearest_rank` — the same function Layer 1's G7 report and
`compute_org_baseline` take their p50 with. A second nearest-rank written here would let two gates
about the same idea disagree about the median by one row on an even-sized book, and both answers
would look right.

READ-ONLY, AT THE SERVER. `set transaction read only` is the first statement of the transaction
(`scripts/_gate.py`), and the target is resolved through `scripts/_db.py`, which has no fallback
to the application's configured database — the mechanism that keeps a "harmless" report off the
tenant database that serves live traffic.

THE CLOCK IS READ AT THE PROCESS BOUNDARY, ONCE, in `main`. `build_report` takes `since` and
`until` as arguments, so the report is a pure function of a window and a database and two runs
over the same window compare.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from genios_engine.capture.esqe.importance import BP_MAX, nearest_rank      # noqa: E402
from genios_engine.context.importance import (                              # noqa: E402
    FLAT_BASE_BP, IMPORTANCE_VERSION, ModifierName,
)
from scripts._db import add_database_argument, resolve_database_url         # noqa: E402
from scripts._gate import parse_since, read_only_connection, sql            # noqa: E402

#: Doc 09's own thresholds, named rather than inlined so a failure message can quote the gate it
#: failed and so moving one is a visible edit rather than a changed digit in a comparison.
MIN_DISTINCT = 50
MIN_SPREAD_BP = 1_500
#: "< 5%", in basis points, because everything on this path is an integer.
MAX_DEFAULT_SHARE_BP = 500
P50_BP = BP_MAX // 2
P90_BP = BP_MAX * 9 // 10

#: How many situations one report reads. A gate on a busy tenant must not turn into an unbounded
#: scan; the newest rows are the ones the newest composer wrote, so the cap keeps those.
DEFAULT_LIMIT = 50_000


@dataclass(frozen=True)
class ComposedRow:
    """One situation as the sweep stored it. Read, never recomputed."""

    situation_id: str
    domain: str
    situation_type: str
    importance_bp: int | None
    importance_version: str | None
    components: dict[str, Any]

    @property
    def composed(self) -> bool:
        """A null `importance_bp` is NOT a zero. It means the sweep that wrote this row predates
        the composer, and counting it as a score would report an unmeasured situation as a
        measured one at the bottom of the range."""
        return self.importance_bp is not None

    @property
    def has_components(self) -> bool:
        """An empty map is not components: it cannot answer "why 7400?", which is the entire
        content of the 100% row."""
        return bool(self.components)

    @property
    def base_source(self) -> str:
        """Which of `situation_bso`'s four sources the BASE came from — the field that turned
        "importance is 5000" from an undiagnosable number into a fact with a cause."""
        return str(self.components.get("base_source") or "unknown")

    def fired(self) -> frozenset[str]:
        """The modifier names that actually fired on this situation."""
        return frozenset(
            str(term.get("name")) for term in (self.components.get("modifiers") or ())
            if isinstance(term, dict) and term.get("fired"))


@dataclass(frozen=True)
class SituationImportanceDistribution:
    """The H5 verdict for one org over one window."""

    org_id: str
    since: datetime
    until: datetime
    situations: int
    composed: int
    distinct: int
    p50_bp: int
    p90_bp: int
    spread_bp: int
    at_default: int
    with_components: int
    versions: tuple[str, ...]
    #: `importance_source` -> count. The diagnosis for a failed "< 5%" row.
    sources: tuple[tuple[str, int], ...]
    #: modifier name -> how many composed situations it fired on. The diagnosis for a failed
    #: spread: a flat distribution with every modifier at zero is a WIRING failure, not a
    #: threshold that wants tuning.
    modifier_fires: tuple[tuple[str, int], ...]
    #: The five most common scores with their counts — what a collapse LOOKS like, so a reader is
    #: not left inferring it from "distinct: 3".
    top_scores: tuple[tuple[int, int], ...]
    #: Situations composed while doc 07's hard rule 7 had SUPPRESSED the modifiers, because Layer
    #: 1's supply for this tenant is flat. A flat H5 here is Layer 1's gate to fix, not this one.
    suppressed: int

    @property
    def default_share_bp(self) -> int:
        return 0 if not self.composed else self.at_default * BP_MAX // self.composed

    @property
    def components_bp(self) -> int:
        return 0 if not self.composed else self.with_components * BP_MAX // self.composed

    @property
    def distinct_passed(self) -> bool:
        return self.distinct > MIN_DISTINCT

    @property
    def spread_passed(self) -> bool:
        return self.spread_bp > MIN_SPREAD_BP

    @property
    def default_passed(self) -> bool:
        return self.default_share_bp < MAX_DEFAULT_SHARE_BP

    @property
    def components_passed(self) -> bool:
        return self.composed > 0 and self.with_components == self.composed

    @property
    def passed(self) -> bool:
        """A window with no COMPOSED situation is not a pass. Nothing was measured, and a gate
        that returns green for an empty table is how "the composer has no production caller"
        reads as success — which is the exact state this wave exists to end."""
        return bool(self.composed) and self.distinct_passed and self.spread_passed \
            and self.default_passed and self.components_passed

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": "H5", "org_id": self.org_id,
            "window": {"since": self.since.isoformat(), "until": self.until.isoformat()},
            "situations": self.situations, "composed": self.composed,
            "distinct": self.distinct, "min_distinct": MIN_DISTINCT,
            "p50_bp": self.p50_bp, "p90_bp": self.p90_bp,
            "spread_bp": self.spread_bp, "min_spread_bp": MIN_SPREAD_BP,
            "at_default_bp": FLAT_BASE_BP, "at_default": self.at_default,
            "default_share_bp": self.default_share_bp,
            "max_default_share_bp": MAX_DEFAULT_SHARE_BP,
            "with_components": self.with_components, "components_bp": self.components_bp,
            "importance_versions": list(self.versions),
            "expected_version": IMPORTANCE_VERSION,
            "importance_sources": [{"source": s, "count": n} for s, n in self.sources],
            "modifier_fires": [{"modifier": m, "count": n} for m, n in self.modifier_fires],
            "suppressed_by_flat_l1_supply": self.suppressed,
            "top_scores": [{"importance_bp": bp, "count": n} for bp, n in self.top_scores],
            "checks": {"distinct": self.distinct_passed, "spread": self.spread_passed,
                       "default_share": self.default_passed,
                       "components": self.components_passed},
            "passed": self.passed,
        }


def distribution(rows: Sequence[ComposedRow], *, org_id: str, since: datetime,
                 until: datetime) -> SituationImportanceDistribution:
    """The H5 numbers over a set of stored situations. PURE — no database, no clock, no float."""
    composed = [row for row in rows if row.composed]
    scores = sorted(int(row.importance_bp) for row in composed)   # type: ignore[arg-type]
    counts: dict[int, int] = {}
    for value in scores:
        counts[value] = counts.get(value, 0) + 1
    sources: dict[str, int] = {}
    for row in composed:
        sources[row.base_source] = sources.get(row.base_source, 0) + 1
    fires = {name.value: sum(1 for row in composed if name.value in row.fired())
             for name in ModifierName}
    return SituationImportanceDistribution(
        org_id=org_id, since=since, until=until,
        situations=len(rows), composed=len(composed),
        distinct=len(counts),
        p50_bp=nearest_rank(scores, P50_BP), p90_bp=nearest_rank(scores, P90_BP),
        spread_bp=nearest_rank(scores, P90_BP) - nearest_rank(scores, P50_BP),
        at_default=sum(1 for value in scores if value == FLAT_BASE_BP),
        with_components=sum(1 for row in composed if row.has_components),
        versions=tuple(sorted({str(row.importance_version) for row in composed
                               if row.importance_version})),
        sources=tuple(sorted(sources.items(), key=lambda kv: (-kv[1], kv[0]))),
        modifier_fires=tuple(sorted(fires.items())),
        suppressed=sum(1 for row in composed
                       if row.components.get("l1_importance_not_active")),
        top_scores=tuple(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]))


#: EVERY situation in the window, composed or not — the null share is the report's own honesty
#: about how much of the tenant the composer has reached. Windowed on `computed_at`, the instant
#: the sweep wrote the row, because that is when the composition happened; `last_seen_at` would
#: window on the EVIDENCE's age and would silently exclude every situation whose evidence is older
#: than the window while the composer was run on it yesterday.
_SITUATIONS_SQL = """
select s.situation_id, s.domain, s.situation_type,
       s.importance_bp, s.importance_version, s.importance_components as components
  from context_situations s
 where s.org_id = :org and s.computed_at >= :since and s.computed_at <= :until
 order by s.computed_at desc
 limit :cap
"""


def _as_map(value: Any) -> dict[str, Any]:
    """A jsonb column as a dict, whether the driver decoded it or handed back text."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            decoded = json.loads(value)
        except ValueError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def read_situations(conn, *, org_id: str, since: datetime, until: datetime,
                    limit: int = DEFAULT_LIMIT) -> tuple[ComposedRow, ...]:
    """The stored rows. The connection is already `read only`."""
    return tuple(ComposedRow(
        situation_id=str(row.situation_id), domain=str(row.domain or ""),
        situation_type=str(row.situation_type or ""),
        importance_bp=(None if row.importance_bp is None else int(row.importance_bp)),
        importance_version=(None if row.importance_version is None
                            else str(row.importance_version)),
        components=_as_map(row.components),
    ) for row in conn.execute(sql(_SITUATIONS_SQL),
                              {"org": org_id, "since": since, "until": until, "cap": limit}))


def build_report(conn, *, org_id: str, since: datetime, until: datetime,
                 limit: int = DEFAULT_LIMIT) -> SituationImportanceDistribution:
    return distribution(read_situations(conn, org_id=org_id, since=since, until=until,
                                        limit=limit),
                        org_id=org_id, since=since, until=until)


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def render(report: SituationImportanceDistribution) -> str:
    lines = [
        f"H5 situation importance distribution — org={report.org_id}",
        f"  window            {report.since:%Y-%m-%d %H:%M} .. {report.until:%Y-%m-%d %H:%M} UTC",
        f"  situations        {report.situations}  (composed {report.composed}, "
        f"not composed {report.situations - report.composed})",
        f"  importance vers.  {', '.join(report.versions) or '(none)'}",
        "",
        f"  [{_mark(report.distinct_passed)}] distinct scores   "
        f"{report.distinct}  (gate > {MIN_DISTINCT})",
        f"  [{_mark(report.spread_passed)}] p90 - p50         "
        f"{report.spread_bp}  (p50 {report.p50_bp}, p90 {report.p90_bp}, gate > {MIN_SPREAD_BP})",
        f"  [{_mark(report.default_passed)}] at exactly {FLAT_BASE_BP}   "
        f"{report.at_default}/{report.composed}  ({report.default_share_bp} bp, "
        f"gate < {MAX_DEFAULT_SHARE_BP})",
        f"  [{_mark(report.components_passed)}] with components   "
        f"{report.with_components}/{report.composed}  ({report.components_bp} bp, gate 10000)",
    ]
    if report.sources:
        lines += ["", "  base source (why a situation sits where it does):"]
        lines += [f"    {source:<24} x{count}" for source, count in report.sources]
    lines += ["", "  modifier fire rate over composed situations:"]
    lines += [f"    {name:<18} {count:>6} / {report.composed}"
              for name, count in report.modifier_fires]
    if report.suppressed:
        lines += ["", f"  NOTE: {report.suppressed} situations were composed with the modifiers "
                      "SUPPRESSED — over 90% of Layer 1's scored supply for this tenant sits at "
                      f"exactly {FLAT_BASE_BP} (doc 07 hard rule 7). A flat distribution here is "
                      "Layer 1's G7 gate to fix; composing a spread on a constant would be a "
                      "spread this layer invented."]
    if report.top_scores:
        lines += ["", "  most common scores:"]
        lines += [f"    {bp:>6}  x{count}" for bp, count in report.top_scores]
    if not report.composed:
        lines += ["", "  NOTHING WAS MEASURED: no situation in the window carries a composed "
                      "importance. An empty column is not a pass — it is the state a composer "
                      "with no production caller produces, which is the defect this gate exists "
                      "to catch."]
    lines += ["", f"  VERDICT: {_mark(report.passed)}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="situation_importance_distribution",
        description="H5 acceptance report: can this tenant's situations actually be ranked?")
    parser.add_argument("--org", required=True, help="org id to report on")
    parser.add_argument("--since", type=parse_since, default=parse_since("30d"),
                        help="window, as a whole number of days/hours/minutes (default 30d)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"situations to read (default {DEFAULT_LIMIT})")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    url = resolve_database_url(args, purpose="H5 situation importance report (read-only)")

    from genios_engine.platform.db import get_engine
    # THE ONLY CLOCK READ IN THIS FILE, at the process boundary. Everything below takes the
    # window as an argument.
    until = datetime.now(timezone.utc)
    conn = read_only_connection(get_engine(url))
    try:
        report = build_report(conn, org_id=args.org, since=until - args.since, until=until,
                              limit=args.limit)
    finally:
        conn.close()

    print(json.dumps(report.as_dict(), indent=2) if args.json else render(report))
    return 0 if report.passed else 1


if __name__ == "__main__":                              # pragma: no cover - CLI entry
    raise SystemExit(main())
