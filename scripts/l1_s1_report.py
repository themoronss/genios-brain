"""G2 · the S1 acceptance report — the gate command, run against a real org.

    python scripts/l1_s1_report.py --org <pilot> --since 30d --database-url postgresql://…

The build order states G2 as three numbers over real captured data, and all of them name the same
kind of failure: **a loss that looks exactly like a success.** A fourth was added when the parked
queue turned out to have a third drain class (metric 4 below); it names the same failure.

  1. attachments stuck in NEEDS_REFETCH over 1h
        A parked attachment is a promise to look again (`capture/parked/refetch.py`). A backlog
        of them that nobody drains is the promise broken silently — the sync reports success, the
        park row says `pending`, and the contract is simply never read. Expected: 0.

  2. documents with empty text and no `ocr_failed` marker
        A scanned contract that yields "" is indistinguishable from a fax cover sheet that said
        nothing. Every layer above reads the empty string, finds no amount and no date, and
        reports — accurately, uselessly — that the document contained nothing. `documents/base.py`
        makes the marker a type-level invariant; this counts the rows where it does not hold on
        the data that already landed. Expected: 0.

  3. structural-token offset round-trip failures
        `EvidenceSpan` is only worth anything if `clean_text[start:end] == quote` holds
        byte-for-byte. An offset map that drifts is worse than no offset map, because every span
        above it inherits the drift and still reports itself verified. Expected: 0.

READ-ONLY, AND NOT AS A MATTER OF DISCIPLINE. The transaction is declared `read only` at the
SERVER before the first select, so a statement that tried to write would be refused by PostgreSQL
rather than by review. The target database is resolved through `scripts/_db.py`, which refuses to
run without an explicit `--database-url` or `GENIOS_TARGET_DATABASE_URL` and has NO fallback to the
application's configured database — because on any developer machine `.env` names the production
tenant, and a gate report is exactly the kind of "harmless" script that would inherit it.

STATUS AT W2. **This script cannot be executed end-to-end yet: no pilot org is wired.** That is
expected at this wave and is not a defect in the script — the three queries run, and against an
org with no captured data they return zeros, which is an honest "nothing observed" rather than a
pass. `--require-data` exists precisely so a caller cannot mistake the two: with it, an org whose
window contains no events exits non-zero and says so. When the pilot lands, the command in the
docstring above is the gate, unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url        # noqa: E402
from scripts._gate import parse_since, read_only_connection                # noqa: E402,F401
from scripts._gate import sql as _sql                                      # noqa: E402

#: How many prepared documents metric 3 re-scans. The check is O(text) per row and a 30-day window
#: on a busy org is tens of thousands of rows; the gate cares whether ANY offset drifts, and a
#: bounded sample that is reported as bounded is more honest than a report that times out. The
#: sample is the NEWEST rows, because a drift is introduced by a code change and the newest rows
#: are the ones the newest code wrote.
DEFAULT_SCAN_LIMIT = 2_000


# ── metric shapes ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GateMetric:
    """One of the gate's numbers, with everything needed to act on it.

    `observed` is what the gate asserts is zero. `sample` is the rows behind it — a metric that
    reports "7" and cannot say WHICH seven is a metric that gets argued with instead of fixed.
    """

    key: str
    title: str
    observed: int
    expected: int = 0
    scanned: int = 0
    detail: str = ""
    sample: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.observed == self.expected

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "title": self.title, "observed": self.observed,
                "expected": self.expected, "scanned": self.scanned, "passed": self.passed,
                "detail": self.detail, "sample": list(self.sample)}


@dataclass(frozen=True)
class S1Report:
    org_id: str
    since: datetime
    until: datetime
    events_in_window: int
    metrics: tuple[GateMetric, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return all(m.passed for m in self.metrics)

    def as_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "since": self.since.isoformat(),
                "until": self.until.isoformat(), "events_in_window": self.events_in_window,
                "passed": self.passed, "metrics": [m.as_dict() for m in self.metrics]}


# ── pure derivations (tested without a database) ─────────────────────────────────────────────

def document_body(clean_text: str) -> str:
    """The document's own text, with the filename line `pipeline.capture_event` prepends removed.

    A document event's prepared text is `f"{subject}\\n\\n{extracted}"` and its `subject` is the
    FILENAME (`connectors/composio.py::_attachment_stub`). So a contract that extracted nothing
    still has a non-empty `clean_text` — `"MSA-signed.pdf\\n\\n"` — and asking "is clean_text
    empty" would report every empty document as fine. Splitting on the first blank line is what
    makes the emptiness observable; a filename cannot contain one.
    """
    _, separator, body = clean_text.partition("\n\n")
    return body if separator else ""


def offset_map_failures(clean_text: str, offset_map: Sequence[dict],
                        masked_spans: Sequence[dict]) -> list[str]:
    """Every way this row's offset map fails to round-trip, as readable phrases.

    `preprocess/pii.py::mask` builds the map by CONSTRUCTION: passthrough segments copy source
    characters 1:1 and masked segments replace a source span with a `[TYPE]` token. Four
    properties follow from that, and each one is a real corruption if it does not hold:

      * the segments TILE `clean_text` from 0 to its length with no gap and no overlap — a gap
        means some characters have no source at all;
      * they tile the SOURCE in the same order — a non-monotonic map makes `to_source_offset`
        return an offset from the wrong sentence;
      * a passthrough segment spans the same NUMBER of characters on both sides — unequal lengths
        are drift, and every span built on top of it is off by the difference;
      * a masked segment's slice of `clean_text` IS the token that was recorded for it — this is
        the actual round-trip, and it is the check that would have caught a mask whose token
        changed length after the map was written.
    """
    failures: list[str] = []
    if not clean_text:
        return failures
    if not offset_map:
        return ["no offset map for non-empty clean_text"]

    tokens_by_source = {(int(m.get("src_start", -1)), int(m.get("src_end", -1))):
                        str(m.get("token", "")) for m in masked_spans}

    prep_cursor = 0
    src_cursor: int | None = None
    for index, seg in enumerate(offset_map):
        prep_start, prep_end = int(seg.get("prep_start", -1)), int(seg.get("prep_end", -1))
        src_start, src_end = int(seg.get("src_start", -1)), int(seg.get("src_end", -1))
        masked = bool(seg.get("masked"))

        if prep_start != prep_cursor:
            failures.append(f"segment {index}: prepared text is not tiled — expected to start at "
                            f"{prep_cursor}, starts at {prep_start}")
        if prep_end <= prep_start:
            failures.append(f"segment {index}: empty or inverted prepared span "
                            f"[{prep_start},{prep_end})")
        if src_end < src_start:
            failures.append(f"segment {index}: inverted source span [{src_start},{src_end})")
        if src_cursor is not None and src_start < src_cursor:
            failures.append(f"segment {index}: source offsets go backwards — {src_start} after "
                            f"{src_cursor}")
        if prep_end > len(clean_text):
            failures.append(f"segment {index}: prepared span ends at {prep_end}, past the "
                            f"{len(clean_text)}-character clean_text")
        elif masked:
            recorded = tokens_by_source.get((src_start, src_end))
            actual = clean_text[prep_start:prep_end]
            if recorded is None:
                failures.append(f"segment {index}: masked span [{src_start},{src_end}) has no "
                                "recorded token to round-trip against")
            elif recorded != actual:
                failures.append(f"segment {index}: masked token does not round-trip — recorded "
                                f"{recorded!r}, clean_text holds {actual!r}")
        elif (prep_end - prep_start) != (src_end - src_start):
            failures.append(f"segment {index}: passthrough length drift — {prep_end - prep_start} "
                            f"prepared characters map to {src_end - src_start} source characters")

        prep_cursor = max(prep_cursor, prep_end)
        src_cursor = src_end

    if prep_cursor != len(clean_text):
        failures.append(f"offset map covers {prep_cursor} of {len(clean_text)} clean_text "
                        "characters")
    return failures


def structural_token_failures(clean_text: str, *, scan: Callable[..., Any] | None = None
                              ) -> list[str]:
    """Every structural token whose offsets do not slice back to its own raw text.

    `capture/structural/tokens.py::scan` builds each token by slicing `clean_text` at the offsets
    it then carries, so this is a check that the token stream a reader would get TODAY, from the
    text we actually stored, still round-trips. It is deliberately re-derived rather than read
    from a table: structural tokens are not persisted, and a report that could only check what was
    persisted would be silent about the one artifact G2 names.

    `scan` is injectable so the derivation can be tested against a stub that returns a token with
    deliberately wrong offsets — a round-trip checker that only ever sees a correct scanner is a
    checker nobody has seen fail.
    """
    scanner = scan
    if scanner is None:
        from genios_engine.capture.structural.tokens import scan as scanner   # noqa: PLC0415
    failures: list[str] = []
    for token in scanner(clean_text).tokens:
        sliced = clean_text[token.start_offset:token.end_offset]
        if sliced != token.raw:
            failures.append(f"{token.token_type} at [{token.start_offset},{token.end_offset}) "
                            f"holds {sliced!r}, token says {token.raw!r}")
    return failures


# ── the metrics ──────────────────────────────────────────────────────────────────────────────

def stuck_refetch_metric(conn, *, org_id: str, now: datetime) -> GateMetric:
    """Metric 1 — attachments pending a refetch for longer than the stuck threshold."""
    from genios_engine.capture.parked.refetch import (ATTACHMENT_OBJECT_TYPE, DEFAULT_POLICY,
                                                      read_aging)
    aging = read_aging(conn, eval_time=now, policy=DEFAULT_POLICY, org_id=org_id)
    hours = DEFAULT_POLICY.stuck_after.days * 24 + DEFAULT_POLICY.stuck_after.seconds // 3600
    sample = tuple(
        f"{row.reason_code}/{row.object_type}: {row.stuck} stuck of {row.pending} pending, "
        f"oldest {row.oldest_age_seconds}s"
        for row in aging.rows if row.stuck)
    return GateMetric(
        key="attachments_stuck_in_needs_refetch",
        title=f"attachments stuck in NEEDS_REFETCH over {hours}h",
        observed=aging.stuck_attachments, scanned=aging.pending,
        detail=(f"{aging.pending} parks pending across "
                f"{len(aging.rows)} reason/object combinations; "
                f"{aging.stuck} of them past {aging.stuck_after_seconds}s "
                f"({aging.stuck_attachments} are {ATTACHMENT_OBJECT_TYPE})"),
        sample=sample[:10])


def stuck_recapture_metric(conn, *, org_id: str, now: datetime) -> GateMetric:
    """Metric 4 — parks that only a re-derivation or a later capture can settle, left waiting.

    `visibility_unknown` and `MUT-01` are held for reasons no payload and no provider can answer
    (`capture/parked/recapture.py`), and until that module existed they belonged to NO drain
    class: `drain_parked` counted them into `by_reason` and walked past, `parked_aging` called
    them "terminal", and this report — the G2 surface — could not see them at all. So a tenant
    whose Notion connector predated its source-family registration accumulated held events at
    `status='pending'` while every other number in this report read clean.

    READ ONLY, like the rest of this script: it counts the backlog, it does not drain it. The
    drain runs on the heartbeat; this says whether the heartbeat is keeping up.
    """
    from genios_engine.capture.parked.drain import STALE_AFTER
    from genios_engine.capture.parked.recapture import NEEDS_RECAPTURE, STATUS_PENDING
    rows = conn.execute(_sql(
        "select reason_code, count(*) as n, min(created_at) as oldest "
        "  from parked_events "
        " where org_id = :org and status = :pending and reason_code = any(:codes) "
        " group by reason_code order by n desc"),
        {"org": org_id, "pending": STATUS_PENDING,
         "codes": sorted(NEEDS_RECAPTURE)}).fetchall()
    stale_rows = conn.execute(_sql(
        "select reason_code, count(*) as n "
        "  from parked_events "
        " where org_id = :org and status = :pending and reason_code = any(:codes) "
        "   and created_at < :cutoff "
        " group by reason_code"),
        {"org": org_id, "pending": STATUS_PENDING, "codes": sorted(NEEDS_RECAPTURE),
         "cutoff": now - STALE_AFTER}).fetchall()
    stale = sum(int(r.n) for r in stale_rows)
    pending = sum(int(r.n) for r in rows)
    days = STALE_AFTER.days
    return GateMetric(
        key="recapture_parks_stuck",
        title=f"parks stuck in NEEDS_RECAPTURE over {days}d",
        observed=stale, scanned=pending,
        detail=(f"{pending} recapture parks pending across {len(rows)} reason codes "
                f"({', '.join(sorted(NEEDS_RECAPTURE))}); "
                f"{stale} of them older than {days}d"),
        sample=tuple(f"{r.reason_code}: {r.n} pending, oldest {r.oldest.isoformat()}"
                     for r in rows if r.oldest is not None)[:10])


def empty_document_metric(conn, *, org_id: str, since: datetime) -> GateMetric:
    """Metric 2 — documents whose text is empty while their status claims it was accepted.

    The join takes the LATEST `document_jobs` row per event: a document that failed and was later
    recovered by the attachment resolver has two provenance rows, and counting the failed one
    would report a loss that has already been repaired.
    """
    from genios_engine.capture.documents.base import DocumentStatus
    rows = conn.execute(_sql(
        "with latest as ("
        "  select distinct on (dj.event_id) dj.event_id, dj.status, dj.format"
        "    from document_jobs dj"
        "   where dj.org_id = :org"
        "   order by dj.event_id, dj.created_at desc"
        ")"
        "select se.event_id, l.status, l.format, pc.clean_text "
        "  from latest l "
        "  join source_events se on se.event_id = l.event_id and se.org_id = :org "
        "  join prepared_content pc on pc.event_id = se.event_id and pc.org_id = :org "
        " where se.captured_at >= :since "
        " order by se.captured_at desc"),
        {"org": org_id, "since": since}).fetchall()

    offenders: list[str] = []
    for row in rows:
        if document_body(row.clean_text or "").strip():
            continue
        if row.status != DocumentStatus.ACCEPTED.value:
            continue                                   # empty, but the marker explains why
        offenders.append(f"{row.event_id} ({row.format or 'no format'}) status={row.status}")
    return GateMetric(
        key="empty_documents_without_marker",
        title="documents with empty text and no ocr_failed marker",
        observed=len(offenders), scanned=len(rows),
        detail=(f"{len(rows)} document events with a prepared seam in the window; an empty body "
                f"is only counted when the latest document_jobs status is "
                f"{DocumentStatus.ACCEPTED.value!r}"),
        sample=tuple(offenders[:10]))


def offset_roundtrip_metric(conn, *, org_id: str, since: datetime,
                            limit: int = DEFAULT_SCAN_LIMIT) -> GateMetric:
    """Metric 3 — prepared rows whose offsets do not slice back to what they claim."""
    rows = conn.execute(_sql(
        "select event_id, clean_text, offset_map, masked_spans "
        "  from prepared_content "
        " where org_id = :org and created_at >= :since "
        " order by created_at desc limit :lim"),
        {"org": org_id, "since": since, "lim": limit}).fetchall()

    offenders: list[str] = []
    for row in rows:
        clean_text = row.clean_text or ""
        problems = offset_map_failures(clean_text, _as_rows(row.offset_map),
                                       _as_rows(row.masked_spans))
        problems += structural_token_failures(clean_text)
        if problems:
            offenders.append(f"{row.event_id}: {problems[0]}")
    return GateMetric(
        key="structural_offset_roundtrip_failures",
        title="structural-token offset round-trip failures",
        observed=len(offenders), scanned=len(rows),
        detail=(f"{len(rows)} prepared documents re-scanned (limit {limit}); each token is "
                "sliced back out of the stored clean_text and compared, and the PII offset map "
                "is checked for tiling, monotonicity and token round-trip"),
        sample=tuple(offenders[:10]))


def _as_rows(value: Any) -> list[dict]:
    """A jsonb column as a list of dicts, whichever way the driver handed it back."""
    if isinstance(value, str):
        value = json.loads(value or "[]")
    return [row for row in (value or []) if isinstance(row, dict)]


def build_report(conn, *, org_id: str, since: datetime, now: datetime,
                 scan_limit: int = DEFAULT_SCAN_LIMIT) -> S1Report:
    """Run every metric over one connection. The connection is already `read only`."""
    events = conn.execute(_sql(
        "select count(*) as n from source_events where org_id = :org and captured_at >= :since"),
        {"org": org_id, "since": since}).scalar() or 0
    return S1Report(
        org_id=org_id, since=since, until=now, events_in_window=int(events),
        metrics=(stuck_refetch_metric(conn, org_id=org_id, now=now),
                 stuck_recapture_metric(conn, org_id=org_id, now=now),
                 empty_document_metric(conn, org_id=org_id, since=since),
                 offset_roundtrip_metric(conn, org_id=org_id, since=since, limit=scan_limit)))


def render(report: S1Report) -> str:
    """The operator's view: the verdict first, then each number with what is behind it."""
    lines = [
        "",
        "G2 · Layer 1 S1 acceptance report",
        f"  org       {report.org_id}",
        f"  window    {report.since.isoformat()} → {report.until.isoformat()}",
        f"  events    {report.events_in_window} captured in the window",
        "",
    ]
    for metric in report.metrics:
        mark = "PASS" if metric.passed else "FAIL"
        lines.append(f"  [{mark}] {metric.title}: {metric.observed} "
                     f"(expected {metric.expected})")
        lines.append(f"         {metric.detail}")
        for row in metric.sample:
            lines.append(f"           · {row}")
    lines.append("")
    if report.events_in_window == 0:
        lines.append("  NOTE: no events were captured in this window, so every number above is "
                     "an absence of observation rather than a pass.")
        lines.append("")
    lines.append(f"  VERDICT   {'PASS' if report.passed else 'FAIL'}")
    lines.append("")
    return "\n".join(lines)


#: G2's own spelling of the shared helper, kept so the acceptance test that asserts this report
#: opens a server-side read-only transaction keeps naming the function this module uses.
_read_only_connection = read_only_connection

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="l1_s1_report",
        description="G2 acceptance report for Layer 1 S1 (deterministic extraction).")
    parser.add_argument("--org", required=True, help="org id to report on")
    parser.add_argument("--since", type=parse_since, default=parse_since("30d"),
                        help="window, as a whole number of days/hours/minutes (default 30d)")
    parser.add_argument("--scan-limit", type=int, default=DEFAULT_SCAN_LIMIT,
                        help=f"prepared documents to re-scan for metric 3 "
                             f"(default {DEFAULT_SCAN_LIMIT})")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument("--require-data", action="store_true",
                        help="exit non-zero when the window contains no events, so an empty org "
                             "cannot be mistaken for a passing one")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    url = resolve_database_url(args, purpose="G2 Layer 1 S1 acceptance report (read-only)")

    from genios_engine.platform.db import get_engine
    now = datetime.now(timezone.utc)
    engine = get_engine(url)
    conn = _read_only_connection(engine)
    try:
        report = build_report(conn, org_id=args.org, since=now - args.since, now=now,
                              scan_limit=args.scan_limit)
    finally:
        conn.close()

    print(json.dumps(report.as_dict(), indent=2) if args.json else render(report))
    if args.require_data and report.events_in_window == 0:
        print(f"no events captured for org {args.org!r} in the window — nothing was measured",
              file=sys.stderr)
        return 2
    return 0 if report.passed else 1


if __name__ == "__main__":                              # pragma: no cover - CLI entry
    raise SystemExit(main())
