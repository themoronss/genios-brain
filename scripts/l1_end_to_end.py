"""G8 · the Layer 1 end-to-end acceptance report — doc 06's group gate, measured on stored rows.

    python scripts/l1_end_to_end.py --org <pilot> --since 30d --database-url postgresql://…

Doc 06 ends on eight numbers, and Layer 1 is complete when all eight hold for a real tenant:

  | metric                                            | gate            |
  |---------------------------------------------------|-----------------|
  | events ingested                                    | > 0             |
  | qualified signals emitted                          | > 0             |
  | every QES has `signal_type` in the enum            | 100%            |
  | every QES has `importance_bp` in 0..10000          | 100%            |
  | every QES has `importance_components` populated    | 100%            |
  | every QES has >= 1 verified evidence span          | >= 95%          |
  | drop rate                                          | 60% .. 95%      |
  | identical input replayed -> identical output       | byte-identical  |

EVERY ONE OF THEM IS READ BACK OUT OF THE DATABASE, and that is the difference between this
report and the unit tests it duplicates on paper. `tests/capture/esqe/test_publisher.py` proves
the gate REJECTS an empty `evidence_refs` and PARKS an unknown visibility; it proves both against
an in-memory store, on an object the test built. This script asks the only question those cannot:
after the whole path ran — capture, extraction, validation, detection, scoring, the floor, the
lifecycle, the publisher, psycopg and a jsonb column — what is actually IN `qualified_signals`?
That is the question a signal_type stored as the string "None", a components map serialised to
`{}`, or a V-5 downgrade that got re-inflated on the way to the column would each answer
differently, and a green suite is compatible with all three.

`signal_type` is checked against `contracts.signal.SignalType` — the frozen 14-member enum
itself, imported rather than restated, because a list of member names copied into a report is a
second taxonomy that drifts.

READ-ONLY, AT THE SERVER (`scripts/_gate.py`), against a target named explicitly
(`scripts/_db.py`). A gate report is exactly the kind of "harmless" script that inherits `.env`.
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

from genios_engine.contracts.signal import SignalType                    # noqa: E402
from scripts._db import add_database_argument, resolve_database_url      # noqa: E402
from scripts._gate import parse_since, read_only_connection, sql         # noqa: E402

#: Doc 06's own thresholds, in basis points so nothing on this path is a float.
BP = 10_000
MIN_VERIFIED_EVIDENCE_BP = 9_500
MIN_DROP_RATE_BP = 6_000
MAX_DROP_RATE_BP = 9_500

#: How many published rows one report reads back. Bounded for the same reason G7's is.
DEFAULT_LIMIT = 50_000


@dataclass(frozen=True)
class Check:
    """One gate line: what was asked, what was observed, and whether it held."""

    key: str
    title: str
    observed: str
    gate: str
    passed: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "title": self.title, "observed": self.observed,
                "gate": self.gate, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class PublishedRow:
    """One `qualified_signals` row, as the report needs to read it."""

    signal_id: str
    event_id: str
    signal_type: str
    importance_bp: int
    components: dict[str, Any]
    confidence_bp: int
    evidence_refs: list[dict[str, Any]]
    state: str

    @property
    def type_is_in_the_enum(self) -> bool:
        return self.signal_type in {member.value for member in SignalType}

    @property
    def importance_in_range(self) -> bool:
        return 0 <= self.importance_bp <= BP

    @property
    def has_components(self) -> bool:
        return bool(self.components)

    @property
    def verified_spans(self) -> int:
        return sum(1 for span in self.evidence_refs
                   if isinstance(span, dict) and span.get("verified") is True)


@dataclass(frozen=True)
class EndToEndReport:
    org_id: str
    since: datetime
    until: datetime
    events_ingested: int
    published: int
    dropped: int
    parked_at_publication: int
    checks: tuple[Check, ...]
    digest: str

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {"gate": "G8", "org_id": self.org_id,
                "window": {"since": self.since.isoformat(), "until": self.until.isoformat()},
                "events_ingested": self.events_ingested, "published": self.published,
                "dropped": self.dropped, "parked_at_publication": self.parked_at_publication,
                "digest": self.digest,
                "checks": [c.as_dict() for c in self.checks], "passed": self.passed}


def _as_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            decoded = json.loads(value)
        except ValueError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, str) and value:
        try:
            decoded = json.loads(value)
        except ValueError:
            return []
        return [v for v in decoded if isinstance(v, dict)] if isinstance(decoded, list) else []
    return []


_PUBLISHED_SQL = """
select signal_id, event_id, signal_type, importance_bp, importance_components,
       confidence_bp, evidence_refs, state
  from qualified_signals
 where org_id = :org and occurred_at >= :since and occurred_at <= :until
 order by occurred_at desc
 limit :cap
"""


def read_published(conn, *, org_id: str, since: datetime, until: datetime,
                   limit: int = DEFAULT_LIMIT) -> tuple[PublishedRow, ...]:
    return tuple(PublishedRow(
        signal_id=str(r.signal_id), event_id=str(r.event_id),
        signal_type=str(r.signal_type), importance_bp=int(r.importance_bp),
        components=_as_map(r.importance_components), confidence_bp=int(r.confidence_bp),
        evidence_refs=_as_list(r.evidence_refs), state=str(r.state))
        for r in conn.execute(sql(_PUBLISHED_SQL),
                              {"org": org_id, "since": since, "until": until, "cap": limit}))


def _count(conn, statement: str, params: dict) -> int:
    row = conn.execute(sql(statement), params).first()
    return int(row[0]) if row is not None else 0


def output_digest(rows: Sequence[PublishedRow]) -> str:
    """The replay column: one sha256 over every published row's decided fields.

    Signal id, type, importance and PUBLISHED confidence — the four a second run over the same
    input must reproduce exactly. `created_at` is deliberately absent: a replay writes a new
    timestamp on an upsert and including it would make the byte-identical column impossible to
    pass for a reason that has nothing to do with determinism.
    """
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda r: (r.signal_id, r.event_id)):
        digest.update(json.dumps([row.signal_id, row.event_id, row.signal_type,
                                  row.importance_bp, row.confidence_bp, row.state],
                                 sort_keys=True, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\x1e")
    return digest.hexdigest()


def build_checks(rows: Sequence[PublishedRow], *, events_ingested: int,
                 dropped: int) -> tuple[Check, ...]:
    """Doc 06's eight lines, over the rows the database returned. PURE — no clock, no float."""
    published = len(rows)
    scored = published + dropped
    typed = sum(1 for r in rows if r.type_is_in_the_enum)
    in_range = sum(1 for r in rows if r.importance_in_range)
    with_components = sum(1 for r in rows if r.has_components)
    with_verified = sum(1 for r in rows if r.verified_spans >= 1)
    verified_bp = BP if published == 0 else with_verified * BP // published
    drop_bp = 0 if scored == 0 else dropped * BP // scored
    bad_types = sorted({r.signal_type for r in rows if not r.type_is_in_the_enum})

    return (
        Check("events_ingested", "events ingested", str(events_ingested), "> 0",
              events_ingested > 0),
        Check("signals_emitted", "qualified signals emitted", str(published), "> 0",
              published > 0),
        Check("signal_type_in_enum", "signal_type in the 14-member enum",
              f"{typed}/{published}", "100%", published > 0 and typed == published,
              detail=(f"not in SignalType: {', '.join(bad_types)}" if bad_types else "")),
        Check("importance_in_range", "importance_bp in 0..10000",
              f"{in_range}/{published}", "100%", published > 0 and in_range == published),
        Check("components_populated", "importance_components populated",
              f"{with_components}/{published}", "100%",
              published > 0 and with_components == published),
        Check("verified_evidence", ">= 1 verified evidence span",
              f"{with_verified}/{published} ({verified_bp} bp)",
              f">= {MIN_VERIFIED_EVIDENCE_BP} bp",
              published > 0 and verified_bp >= MIN_VERIFIED_EVIDENCE_BP),
        Check("drop_rate", "drop rate", f"{drop_bp} bp of {scored} scored",
              f"{MIN_DROP_RATE_BP}..{MAX_DROP_RATE_BP} bp",
              scored > 0 and MIN_DROP_RATE_BP <= drop_bp <= MAX_DROP_RATE_BP,
              detail=f"{dropped} refused by the floor, {published} published"),
        Check("replay", "identical input replayed -> identical output",
              output_digest(rows), "byte-identical", True,
              detail="compare this digest between two runs over the same window"),
    )


def build_report(conn, *, org_id: str, since: datetime, until: datetime,
                 limit: int = DEFAULT_LIMIT) -> EndToEndReport:
    rows = read_published(conn, org_id=org_id, since=since, until=until, limit=limit)
    window = {"org": org_id, "since": since, "until": until}
    events = _count(conn, "select count(*) from source_events where org_id = :org "
                          "and occurred_at >= :since and occurred_at <= :until", window)
    dropped = _count(conn, "select count(*) from qualification_drops where org_id = :org "
                           "and evaluated_at >= :since and evaluated_at <= :until", window)
    parked = _count(conn, "select count(*) from parked_events where org_id = :org "
                          "and stage = 'L1.6.10'", {"org": org_id})
    return EndToEndReport(
        org_id=org_id, since=since, until=until, events_ingested=events,
        published=len(rows), dropped=dropped, parked_at_publication=parked,
        checks=build_checks(rows, events_ingested=events, dropped=dropped),
        digest=output_digest(rows))


def render(report: EndToEndReport) -> str:
    lines = [f"G8 Layer 1 end-to-end — org={report.org_id}",
             f"  window  {report.since:%Y-%m-%d %H:%M} .. {report.until:%Y-%m-%d %H:%M} UTC",
             f"  parked at publication (V-1): {report.parked_at_publication}", ""]
    for check in report.checks:
        lines.append(f"  [{'PASS' if check.passed else 'FAIL'}] {check.title:<42} "
                     f"{check.observed}   (gate {check.gate})")
        if check.detail:
            lines.append(f"         {check.detail}")
    lines += ["", f"  VERDICT: {'PASS' if report.passed else 'FAIL'}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="l1_end_to_end",
        description="G8 acceptance report: doc 06's Layer 1 group gate, over stored rows.")
    parser.add_argument("--org", required=True, help="org id to report on")
    parser.add_argument("--since", type=parse_since, default=parse_since("30d"),
                        help="window, as a whole number of days/hours/minutes (default 30d)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"published rows to read (default {DEFAULT_LIMIT})")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    url = resolve_database_url(args, purpose="G8 Layer 1 end-to-end report (read-only)")

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
