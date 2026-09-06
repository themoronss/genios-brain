"""G7 · the importance-distribution report — **the Layer 4 unlock gate**, measured.

    python scripts/importance_distribution.py --org <pilot> --since 30d \
        --database-url postgresql://…

WHAT THIS MEASURES AND WHY IT IS A SEPARATE THING FROM A UNIT TEST. `reason/decision_maker.py:243`
records that "the formula has never once decided anything", and
`reason/reasoners/priority.py:165-197` handed 193 of 223 signals one identical score — while every
unit test around both passed. A formula is correct per-signal and useless in aggregate whenever
its inputs collapse, and no test of one signal can see that. So the gate is a DISTRIBUTION over
what the production path actually stored:

  | metric                              | gate           | why                                    |
  |-------------------------------------|----------------|----------------------------------------|
  | distinct `importance_bp` values     | > 50           | a handful means it is not deciding     |
  | p90 - p50                           | > 1500         | a flat distribution cannot rank        |
  | identical input replayed            | byte-identical | reproducibility                        |
  | every score has its components      | 100%           | explainability                         |

WHERE THE NUMBERS COME FROM — BOTH HALVES OF THE DECISION. `qualified_signals` (0089) holds what
crossed the tenant's floor; `qualification_drops` (0088) holds what did not, WITH the same
`importance_bp` and the same components map. The distribution ALG-17 produced is the union, and
reading only the published half would measure the floor rather than the formula: a floor at 2500
removes the bottom quarter of the range and would flatter the spread by construction.

Neither table is recomputed here and no scorer is imported. The rows were written by
`capture/esqe/qualification.py` and `capture/esqe/publisher.py` on the ingestion path; if the
formula never ran, this report says so with a zero rather than by producing a number of its own.

THE PERCENTILE IS `importance.nearest_rank`, THE SAME FUNCTION `compute_org_baseline` TAKES THE
ORG'S p50 WITH. A second nearest-rank written here would let the gate and the formula disagree
about the median by one row on an even-sized book, and both answers would look right.

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
from datetime import datetime, timezone
from typing import Any, Sequence

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from genios_engine.capture.esqe.importance import BP_MAX, nearest_rank   # noqa: E402
from scripts._db import add_database_argument, resolve_database_url      # noqa: E402
from scripts._gate import parse_since, read_only_connection, sql         # noqa: E402

#: The plan's own thresholds. Named rather than inlined so a failure message can quote the gate
#: it failed, and so moving one is a visible edit rather than a changed digit in a comparison.
MIN_DISTINCT = 50
MIN_SPREAD_BP = 1500
P50_BP = BP_MAX // 2
P90_BP = BP_MAX * 9 // 10

#: How many scored signals one report reads. A gate on a busy tenant must not turn into an
#: unbounded scan; the newest rows are the ones the newest formula wrote, so the cap keeps those.
DEFAULT_LIMIT = 50_000


@dataclass(frozen=True)
class ScoredRow:
    """One signal ALG-17 scored, from whichever half of the decision it landed in.

    `lane` is kept because "the drops are varied and the published half is flat" is a real and
    diagnosable state — it means the floor is cutting the interesting tail — and a union that
    forgot which side a row came from could not report it.
    """

    signal_id: str
    event_id: str
    #: The PROVIDER's id for the object this signal came from — `source_events.source_object_id`.
    #: Carried because `event_id` is minted fresh at landing (`landing/normalize.py:33`,
    #: `new_id("evt")`), so a corpus re-ingested from scratch produces the same decisions under
    #: entirely different ids. A replay digest keyed by `event_id` therefore only answers "are
    #: these the same rows", never "did the same input score the same way" — and the second is
    #: the question G7's byte-identical column is asking.
    source_object_id: str
    signal_type: str
    importance_bp: int
    importance_version: str
    components: dict[str, Any]
    lane: str                         # "published" | "dropped"

    @property
    def has_components(self) -> bool:
        """An empty map is NOT components. A row that stored `{}` cannot answer "why 8100?", which
        is the entire content of the 100% column, so it counts as a miss rather than as a row."""
        return bool(self.components)


@dataclass(frozen=True)
class ImportanceDistribution:
    """The G7 verdict for one org over one window."""

    org_id: str
    since: datetime
    until: datetime
    scored: int
    published: int
    dropped: int
    distinct: int
    p50_bp: int
    p90_bp: int
    spread_bp: int
    with_components: int
    versions: tuple[str, ...]
    digest: str
    #: The same distribution keyed by the PROVIDER's object id — see `content_digest`.
    content_digest: str
    #: The five most common scores with their counts — what a collapse LOOKS like when it
    #: happens, so the reader is not left to infer it from "distinct: 3".
    top_scores: tuple[tuple[int, int], ...]

    @property
    def components_bp(self) -> int:
        """Component coverage in basis points. Integer, like everything else on this path."""
        return BP_MAX if self.scored == 0 else self.with_components * BP_MAX // self.scored

    @property
    def distinct_passed(self) -> bool:
        return self.distinct > MIN_DISTINCT

    @property
    def spread_passed(self) -> bool:
        return self.spread_bp > MIN_SPREAD_BP

    @property
    def components_passed(self) -> bool:
        return self.with_components == self.scored

    @property
    def passed(self) -> bool:
        """A window with no scored signal is NOT a pass. Nothing was measured, and a gate that
        returns green for an empty table is how "the formula never ran" reads as success."""
        return bool(self.scored) and self.distinct_passed and self.spread_passed \
            and self.components_passed

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": "G7", "org_id": self.org_id,
            "window": {"since": self.since.isoformat(), "until": self.until.isoformat()},
            "scored": self.scored, "published": self.published, "dropped": self.dropped,
            "distinct": self.distinct, "min_distinct": MIN_DISTINCT,
            "p50_bp": self.p50_bp, "p90_bp": self.p90_bp,
            "spread_bp": self.spread_bp, "min_spread_bp": MIN_SPREAD_BP,
            "components_bp": self.components_bp,
            "with_components": self.with_components,
            "importance_versions": list(self.versions),
            "digest": self.digest,
            "content_digest": self.content_digest,
            "top_scores": [{"importance_bp": bp, "count": n} for bp, n in self.top_scores],
            "checks": {"distinct": self.distinct_passed, "spread": self.spread_passed,
                       "components": self.components_passed},
            "passed": self.passed,
        }


def _canonical(value: Any) -> Any:
    """A stored jsonb value in a form `json.dumps(sort_keys=True)` renders identically every run.

    psycopg hands back dicts whose key order is the server's; a digest taken over that order
    would change when the row is rewritten with the same content, and the replay column would go
    red for a reason that has nothing to do with the formula.
    """
    if isinstance(value, dict):
        return {str(k): _canonical(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def _digest_over(rows: Sequence[ScoredRow], project) -> str:
    """One sha256 over the whole distribution, each row projected by `project`.

    Sorted by the projection itself, so the database's row order — which is not a promise —
    cannot change the answer, and so two runs that returned the same rows in different orders
    still agree.
    """
    digest = hashlib.sha256()
    for value in sorted(json.dumps(project(row), sort_keys=True, separators=(",", ":"),
                                   default=str) for row in rows):
        digest.update(value.encode("utf-8"))
        digest.update(b"\x1e")
    return digest.hexdigest()


def replay_digest(rows: Sequence[ScoredRow]) -> str:
    """THE STORED distribution, identified by row. Two reads of the same window must agree.

    This is the column an operator compares between two runs of the report: it changes when a
    row was rewritten, added or removed, which is what "is the table still what it was" means.
    """
    return _digest_over(rows, lambda r: [r.signal_id, r.event_id, r.signal_type,
                                         r.importance_bp, r.importance_version,
                                         _canonical(r.components)])


def content_digest(rows: Sequence[ScoredRow]) -> str:
    """THE DECISION, identified by the provider's object — the byte-identical column that means
    something after a re-ingestion.

    `event_id` and `signal_id` are minted at landing, so re-capturing the same mailbox produces
    the same judgements under different ids and `replay_digest` would differ for a reason that
    has nothing to do with the formula. Keyed by `source_object_id` instead, this digest is
    stable across a wipe-and-replay of the same corpus and is therefore the one that can fail
    when — and only when — ALG-17 stopped being deterministic.
    """
    return _digest_over(rows, lambda r: [r.source_object_id, r.signal_type, r.importance_bp,
                                         r.importance_version, _canonical(r.components)])


def distribution(rows: Sequence[ScoredRow], *, org_id: str, since: datetime,
                 until: datetime) -> ImportanceDistribution:
    """The four G7 numbers over a set of scored rows. PURE — no database, no clock, no float."""
    scores = sorted(row.importance_bp for row in rows)
    counts: dict[int, int] = {}
    for value in scores:
        counts[value] = counts.get(value, 0) + 1
    p50 = nearest_rank(scores, P50_BP)
    p90 = nearest_rank(scores, P90_BP)
    return ImportanceDistribution(
        org_id=org_id, since=since, until=until,
        scored=len(rows),
        published=sum(1 for r in rows if r.lane == "published"),
        dropped=sum(1 for r in rows if r.lane == "dropped"),
        distinct=len(counts),
        p50_bp=p50, p90_bp=p90, spread_bp=p90 - p50,
        with_components=sum(1 for r in rows if r.has_components),
        versions=tuple(sorted({r.importance_version for r in rows})),
        digest=replay_digest(rows),
        content_digest=content_digest(rows),
        top_scores=tuple(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]))


#: Both halves join `source_events` for the provider's own object id — LEFT, because a signal
#: whose landing row has been aged out is still a signal that was scored, and dropping it from
#: the distribution to keep the join tidy would quietly narrow the very population under test.
_PUBLISHED_SQL = """
select q.signal_id, q.event_id, coalesce(e.source_object_id, q.event_id) as source_object_id,
       q.signal_type, q.importance_bp, q.importance_version,
       q.importance_components as components
  from qualified_signals q
  left join source_events e on e.event_id = q.event_id and e.org_id = q.org_id
 where q.org_id = :org and q.occurred_at >= :since and q.occurred_at <= :until
 order by q.occurred_at desc
 limit :cap
"""

_DROPPED_SQL = """
select d.signal_id, d.event_id, coalesce(e.source_object_id, d.event_id) as source_object_id,
       d.signal_type, d.importance_bp, d.importance_version, d.components as components
  from qualification_drops d
  left join source_events e on e.event_id = d.event_id and e.org_id = d.org_id
 where d.org_id = :org and d.evaluated_at >= :since and d.evaluated_at <= :until
 order by d.evaluated_at desc
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


def read_scored(conn, *, org_id: str, since: datetime, until: datetime,
                limit: int = DEFAULT_LIMIT) -> tuple[ScoredRow, ...]:
    """Both halves of the decision, as one list. The connection is already `read only`."""
    out: list[ScoredRow] = []
    for statement, lane in ((_PUBLISHED_SQL, "published"), (_DROPPED_SQL, "dropped")):
        for row in conn.execute(sql(statement),
                                {"org": org_id, "since": since, "until": until, "cap": limit}):
            out.append(ScoredRow(
                signal_id=str(row.signal_id), event_id=str(row.event_id),
                source_object_id=str(row.source_object_id),
                signal_type=str(row.signal_type), importance_bp=int(row.importance_bp),
                importance_version=str(row.importance_version),
                components=_as_map(row.components), lane=lane))
    return tuple(out)


def build_report(conn, *, org_id: str, since: datetime,
                 until: datetime, limit: int = DEFAULT_LIMIT) -> ImportanceDistribution:
    return distribution(read_scored(conn, org_id=org_id, since=since, until=until, limit=limit),
                        org_id=org_id, since=since, until=until)


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def render(report: ImportanceDistribution) -> str:
    lines = [
        f"G7 importance distribution — org={report.org_id}",
        f"  window            {report.since:%Y-%m-%d %H:%M} .. {report.until:%Y-%m-%d %H:%M} UTC",
        f"  scored signals    {report.scored}  "
        f"(published {report.published}, dropped {report.dropped})",
        f"  importance vers.  {', '.join(report.versions) or '(none)'}",
        "",
        f"  [{_mark(report.distinct_passed)}] distinct scores   "
        f"{report.distinct}  (gate > {MIN_DISTINCT})",
        f"  [{_mark(report.spread_passed)}] p90 - p50         "
        f"{report.spread_bp}  (p50 {report.p50_bp}, p90 {report.p90_bp}, gate > {MIN_SPREAD_BP})",
        f"  [{_mark(report.components_passed)}] with components   "
        f"{report.with_components}/{report.scored}  ({report.components_bp} bp, gate 10000)",
        f"  [--] replay digest   {report.digest}",
        f"  [--] content digest  {report.content_digest}",
    ]
    if report.top_scores:
        lines += ["", "  most common scores:"]
        lines += [f"    {bp:>6}  x{count}" for bp, count in report.top_scores]
    if not report.scored:
        lines += ["", "  NOTHING WAS MEASURED: no scored signal in the window. An empty table is "
                      "not a pass — it is the state a formula with no production caller produces."]
    lines += ["", f"  VERDICT: {_mark(report.passed)}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="importance_distribution",
        description="G7 acceptance report: is ALG-17 actually deciding anything for this tenant?")
    parser.add_argument("--org", required=True, help="org id to report on")
    parser.add_argument("--since", type=parse_since, default=parse_since("30d"),
                        help="window, as a whole number of days/hours/minutes (default 30d)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"scored rows to read per table (default {DEFAULT_LIMIT})")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    url = resolve_database_url(args, purpose="G7 importance distribution report (read-only)")

    from genios_engine.platform.db import get_engine
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
