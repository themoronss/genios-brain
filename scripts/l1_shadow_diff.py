"""G10 · the pilot shadow diff — L1 v2 beside the old L2 extraction, on one real tenant.

    python scripts/l1_shadow_diff.py --org <pilot> --days 7 --database-url postgresql://…

THE GATE IS NOT "DOES IT WORK", IT IS "WHAT DID IT STOP FINDING". Doc 09 is explicit that the old
L2 extraction path is removed only AFTER this report has been read, and the line that carries the
weight is the third one: every signal v1 found and v2 did not has to be **explained, each one**.
A count is not an explanation, so this report resolves each miss against the ledgers L1 v2 was
built to leave — the floor's `qualification_drops`, the publisher's `parked_events`, the
extraction cache's absence — and reports `unexplained` only when none of them answers. An
unexplained miss is the one state that fails this gate outright.

    | metric                                  | gate                                  |
    |-----------------------------------------|---------------------------------------|
    | events processed by both paths          | 100%                                  |
    | signals L1 v2 found that v1 missed      | reviewed, reported                    |
    | signals v1 found that L1 v2 missed      | reviewed and explained — each one     |
    | unverified span rate                    | < 5%                                  |
    | LLM cost per 1000 events                | within 2x of v1                       |
    | founder-visible regressions             | 0                                     |

ACTIVATION IS REPORTED FIRST, AND IT IS A ROW. Doc 09: *"the unit is done when its acceptance
command passes against a real tenant with activation enabled; built but not enabled is not
done."* `l1_semantic_activation` (migrations 0085 + 0090) is the table; a tenant with no live row
runs the old path only, and this report says so instead of printing a diff of one path against
itself and calling the zeros a pass.

THE UNVERIFIED-SPAN RATE IS `validate/spans.unverified_rate_bp`, NOT AN ARITHMETIC OF ITS OWN.
That function's docstring says dimensioning by org belongs to the metrics writer; this report IS
that writer. A second rate computed here would let the release gate the extractor is judged by
and the pilot gate the tenant is judged by disagree about the same spans.

READ-ONLY, AT THE SERVER — `set transaction read only` is the first statement of the transaction
(`scripts/_gate.py`) — and the target is named explicitly through `scripts/_db.py`, which has no
fallback to the application's configured database. This script runs against a LIVE PILOT TENANT;
of every gate report in this directory it is the one that must not be able to write.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from genios_engine.capture.validate.spans import (SpanCounters, SpanVerdict,   # noqa: E402
                                                  unverified_rate_bp)
from genios_engine.platform.metrics import llm_price                           # noqa: E402
from scripts._db import add_database_argument, resolve_database_url            # noqa: E402
from scripts._gate import parse_since, read_only_connection, sql               # noqa: E402

BP = 10_000

#: Doc 09's threshold, in basis points. 5% of distinct spans failing to resolve is the point at
#: which the evidence a founder is shown stops being evidence.
MAX_UNVERIFIED_RATE_BP = 500

#: "within 2x of v1", as an integer comparison: v2_per_1k * 10000 <= v1_per_1k * COST_CEILING_BP.
COST_CEILING_BP = 20_000

#: Nano-dollars per token, derived from `platform/metrics.LLM_PRICE` so the two cannot drift.
#: Integer, because a cost RATIO compared against a threshold is a decision, and a float ratio
#: decides differently on two machines at the boundary.
_NANO = 1_000_000_000


def nano_per_token(model: str) -> tuple[int, int]:
    """(input, output) price in whole nano-dollars per token, from the shared pricing table."""
    price_in, price_out = llm_price(model)
    return round(price_in * _NANO), round(price_out * _NANO)


def token_cost_nano(model: str, input_tokens: int, output_tokens: int) -> int:
    price_in, price_out = nano_per_token(model)
    return int(input_tokens or 0) * price_in + int(output_tokens or 0) * price_out


@dataclass(frozen=True)
class Miss:
    """One signal the old path found and L1 v2 did not, with the reason L1 v2 recorded."""

    event_id: str
    field: str
    reason: str
    detail: str = ""

    @property
    def explained(self) -> bool:
        return self.reason != "unexplained"

    def as_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "field": self.field, "reason": self.reason,
                "detail": self.detail, "explained": self.explained}


@dataclass(frozen=True)
class Activation:
    """Whether this tenant is actually on the new lane, from the table that decides it."""

    live: bool
    enabled_at: datetime | None = None
    enabled_by: str = ""
    notes: str = ""
    disabled_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"live": self.live,
                "enabled_at": self.enabled_at.isoformat() if self.enabled_at else None,
                "enabled_by": self.enabled_by, "notes": self.notes,
                "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None}


@dataclass(frozen=True)
class ShadowDiff:
    org_id: str
    since: datetime
    until: datetime
    activation: Activation
    events_in_window: int
    v1_processed: int
    v2_processed: int
    both_processed: int
    v2_only_events: tuple[str, ...]
    misses: tuple[Miss, ...]
    span_counters: SpanCounters
    v1_cost_nano_per_1k: int
    v2_cost_nano_per_1k: int
    founder_visible_regressions: tuple[str, ...]
    #: Reasons the report could not measure something, rather than a zero that reads as a pass.
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def both_bp(self) -> int:
        """Share of the OLD path's events the new lane also read, in basis points.

        ZERO when the old path processed nothing in the window, not 10000: a window with no v1
        rows has not been compared, and reporting a full percentage for an empty denominator is
        how "we never ran the old path here" reads as "the two agree completely". The check
        below requires `v1_processed > 0` for the same reason, and the observed string says so.
        """
        return 0 if self.v1_processed == 0 else self.both_processed * BP // self.v1_processed

    @property
    def unexplained(self) -> tuple[Miss, ...]:
        return tuple(m for m in self.misses if not m.explained)

    @property
    def unverified_bp(self) -> int:
        return unverified_rate_bp(self.span_counters)

    @property
    def cost_within_2x(self) -> bool:
        """No v1 spend in the window means there is nothing to be within 2x OF. Reported as a
        caveat and treated as not-failing, because a tenant whose old path made no model call is
        not a tenant whose new path got more expensive."""
        if self.v1_cost_nano_per_1k == 0:
            return True
        return self.v2_cost_nano_per_1k * BP <= self.v1_cost_nano_per_1k * COST_CEILING_BP

    @property
    def checks(self) -> tuple[tuple[str, str, str, bool], ...]:
        """(key, observed, gate, passed) for each of doc 09's six lines."""
        return (
            ("events_processed_by_both",
             (f"{self.both_processed}/{self.v1_processed} ({self.both_bp} bp)"
              if self.v1_processed else "the old path processed nothing in this window"),
             "100%", self.v1_processed > 0 and self.both_bp == BP),
            ("v2_only", f"{len(self.v2_only_events)} events", "reviewed, reported", True),
            ("v1_only_explained",
             f"{len(self.misses) - len(self.unexplained)}/{len(self.misses)} explained",
             "each one explained", not self.unexplained),
            ("unverified_span_rate",
             f"{self.unverified_bp} bp of {self.span_counters.total_spans} spans",
             f"< {MAX_UNVERIFIED_RATE_BP} bp",
             self.unverified_bp < MAX_UNVERIFIED_RATE_BP),
            ("llm_cost_per_1000_events",
             f"v2 {self.v2_cost_nano_per_1k} vs v1 {self.v1_cost_nano_per_1k} nano-USD",
             f"<= {COST_CEILING_BP // 100}% of v1", self.cost_within_2x),
            ("founder_visible_regressions", str(len(self.founder_visible_regressions)),
             "0", not self.founder_visible_regressions),
        )

    @property
    def passed(self) -> bool:
        """Activation is a precondition, not a metric: an inactive tenant has not been measured."""
        return self.activation.live and all(ok for _, _, _, ok in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": "G10", "org_id": self.org_id,
            "window": {"since": self.since.isoformat(), "until": self.until.isoformat()},
            "activation": self.activation.as_dict(),
            "events_in_window": self.events_in_window,
            "v1_processed": self.v1_processed, "v2_processed": self.v2_processed,
            "v2_only_events": list(self.v2_only_events),
            "misses": [m.as_dict() for m in self.misses],
            "span_counters": {"total": self.span_counters.total_spans,
                              "resolved": self.span_counters.resolved_spans,
                              "failed": self.span_counters.failed_spans},
            "checks": [{"key": k, "observed": o, "gate": g, "passed": p}
                       for k, o, g, p in self.checks],
            "caveats": list(self.caveats),
            "passed": self.passed,
        }


# ── reads ────────────────────────────────────────────────────────────────────────────────────
def read_activation(conn, *, org_id: str) -> Activation:
    row = conn.execute(sql(
        "select enabled_at, enabled_by, coalesce(notes,'') as notes, disabled_at "
        "from l1_semantic_activation where org_id = :org"), {"org": org_id}).first()
    if row is None:
        return Activation(live=False)
    return Activation(live=row.disabled_at is None, enabled_at=row.enabled_at,
                      enabled_by=str(row.enabled_by), notes=str(row.notes),
                      disabled_at=row.disabled_at)


def _ids(conn, statement: str, params: dict) -> set[str]:
    return {str(r[0]) for r in conn.execute(sql(statement), params)}


def span_counters(conn, *, org_id: str, since: datetime, until: datetime) -> SpanCounters:
    """Every distinct evidence span L1 v2 published in the window, tallied by whether it resolved.

    DISTINCT by (source_ref, offsets), which is `SpanCounters`' own rule: four claims read out of
    one sentence share one receipt, and counting it four times would let one popular quote move
    the rate the extractor is judged by.
    """
    seen: dict[tuple[str, int, int], bool] = {}
    for row in conn.execute(sql(
            "select evidence_refs from qualified_signals where org_id = :org "
            "and occurred_at >= :since and occurred_at <= :until"),
            {"org": org_id, "since": since, "until": until}):
        refs = row.evidence_refs
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except ValueError:
                refs = []
        for span in refs or []:
            if not isinstance(span, dict):
                continue
            key = (str(span.get("source_ref", "")), int(span.get("start_offset", -1)),
                   int(span.get("end_offset", -1)))
            seen[key] = seen.get(key, False) or span.get("verified") is True
    verdicts = [SpanVerdict.VERIFIED if ok else SpanVerdict.UNVERIFIED for ok in seen.values()]
    return SpanCounters.from_verdicts(verdicts)


def _cost_nano_per_1k(total_nano: int, events: int) -> int:
    """Nano-dollars per 1000 events, integer. Zero events reports 0 — read it beside the count."""
    return 0 if events <= 0 else total_nano * 1000 // events


def v1_cost_nano(conn, *, org_id: str, since: datetime, until: datetime) -> int:
    """The old path's model spend, from `llm_costs` — the ledger the deployed breaker reads."""
    total = 0
    for row in conn.execute(sql(
            "select model, input_tokens, output_tokens from llm_costs where org_id = :org "
            "and purpose = 'extract' and created_at >= :since and created_at <= :until"),
            {"org": org_id, "since": since, "until": until}):
        total += token_cost_nano(str(row.model), row.input_tokens, row.output_tokens)
    return total


def v2_cost_nano(conn, *, org_id: str, since: datetime, until: datetime) -> int:
    """The new lane's model spend, priced from `l1_extraction_results`' own token counts.

    NOT from `llm_costs`: the L1 v2 semantic lane writes its tokens to its extraction cache and
    files NO `llm_costs` row (only `capture/gate/relevance.py` does, under `relevance_gate`). So
    the one comparison G10 asks for cannot be made from a single ledger, and reading only
    `llm_costs` would report the new lane as free — which is the most flattering possible wrong
    answer. Priced with the same table `llm_costs` is summed with, so the two sides are
    comparable; the missing ledger row is reported as a caveat rather than papered over.

    `profile_id is not null` is what makes these rows the NEW lane's. Both lanes write to this
    table, so without the filter the old path's own extractions were added to the new path's
    bill — the cost gate would have been reading a number inflated by the very path it is being
    compared against, and a lane that was actually 1.5x would report 2.5x.
    """
    total = 0
    for row in conn.execute(sql(
            "select x.model_snapshot as model, x.input_tokens, x.output_tokens "
            "from l1_extraction_results x join source_events e "
            "  on e.event_id = x.event_id and e.org_id = x.org_id "
            "where x.org_id = :org and x.profile_id is not null "
            "and e.occurred_at >= :since and e.occurred_at <= :until"),
            {"org": org_id, "since": since, "until": until}):
        total += token_cost_nano(str(row.model or ""), row.input_tokens, row.output_tokens)
    return total


_V1_FACTS_SQL = """
select f.created_by_event_id as event_id, f.field as field
  from graph_facts f
  join source_events e on e.event_id = f.created_by_event_id and e.org_id = f.org_id
 where f.org_id = :org and f.valid_to is null and f.status = 'active'
   and e.occurred_at >= :since and e.occurred_at <= :until
"""


def explain_miss(conn, *, org_id: str, event_id: str, field_name: str) -> Miss:
    """Why did L1 v2 produce nothing for an event the old path drew a fact from?

    Resolved in the order the pipeline runs, so the FIRST stage that stopped is the one reported —
    an event that was never extracted is not also "below the floor", and reporting the later
    reason would send a reviewer to the wrong unit.
    """
    drop = conn.execute(sql(
        "select importance_bp, floor_bp, signal_type from qualification_drops "
        "where org_id = :org and event_id = :ev order by evaluated_at desc limit 1"),
        {"org": org_id, "ev": event_id}).first()
    parked = conn.execute(sql(
        "select reason_code, stage from parked_events where org_id = :org and event_id = :ev "
        "order by created_at desc limit 1"), {"org": org_id, "ev": event_id}).first()
    # Same discriminator, same reason, and here it decides what a REVIEWER is told: without it
    # an event the semantic lane never touched — but the old lane did — was explained as "the v2
    # lane extracted this and no predicate fired", which sends the reviewer to the wrong unit.
    extracted = conn.execute(sql(
        "select 1 from l1_extraction_results where org_id = :org and event_id = :ev "
        "and profile_id is not null limit 1"), {"org": org_id, "ev": event_id}).first()

    if parked is not None:
        return Miss(event_id, field_name, "parked",
                    f"{parked.stage}: {parked.reason_code}")
    if extracted is None:
        return Miss(event_id, field_name, "not_extracted",
                    "no l1_extraction_results row carrying a profile_id — the v2 lane never "
                    "read this event (the old lane's own rows on it are null-profile)")
    if drop is not None:
        return Miss(event_id, field_name, "below_floor",
                    f"{drop.signal_type} scored {drop.importance_bp} against a floor of "
                    f"{drop.floor_bp}")
    return Miss(event_id, field_name, "no_signal_detected",
                "the v2 lane extracted this event and no ALG-15 predicate fired")


def build_report(conn, *, org_id: str, since: datetime, until: datetime) -> ShadowDiff:
    window = {"org": org_id, "since": since, "until": until}
    activation = read_activation(conn, org_id=org_id)

    events = _ids(conn, "select event_id from source_events where org_id = :org "
                        "and occurred_at >= :since and occurred_at <= :until", window)
    v1_done = _ids(conn, "select r.event_id from l2_processing_runs r "
                         "join source_events e on e.event_id = r.event_id and e.org_id = r.org_id "
                         "where r.org_id = :org and r.status = 'done' "
                         "and e.occurred_at >= :since and e.occurred_at <= :until", window)
    # `profile_id is not null` IS the lane discriminator, and leaving it out was a false PASS
    # on the gate's headline line. `l1_extraction_results` is written by BOTH lanes — migration
    # 0080: "existing rows keep profile_id null because the L2 lane never had a profile" — so
    # without the filter the OLD path's own extraction row counted as proof that the NEW path
    # had read the event, and a tenant whose semantic lane never ran reported 100% coverage.
    v2_read = _ids(conn, "select x.event_id from l1_extraction_results x "
                         "join source_events e on e.event_id = x.event_id and e.org_id = x.org_id "
                         "where x.org_id = :org and x.profile_id is not null "
                         "and e.occurred_at >= :since and e.occurred_at <= :until", window)
    v2_signals = _ids(conn, "select event_id from qualified_signals where org_id = :org "
                            "and occurred_at >= :since and occurred_at <= :until", window)

    v1_facts: dict[str, str] = {}
    for row in conn.execute(sql(_V1_FACTS_SQL), window):
        v1_facts.setdefault(str(row.event_id), str(row.field))

    misses = tuple(explain_miss(conn, org_id=org_id, event_id=event_id, field_name=field_name)
                   for event_id, field_name in sorted(v1_facts.items())
                   if event_id not in v2_signals)
    v2_only = tuple(sorted(v2_signals - set(v1_facts)))

    # A regression is a card whose OWN subject lost its evidence: the founder is looking at a
    # card built on a Layer 4 signal about some subject, and a fact on THAT subject came from an
    # event L1 v2 produced no signal for — remove the old path and the card stops existing.
    #
    # The join runs through `signals.subject_node_id` because that is the only link the schema
    # carries between a card and a graph fact. It was previously
    # `on f.created_by_event_id is not null and f.org_id = c.org_id`, which relates a card to
    # NOTHING: every card paired with every un-signalled event in the window, so the gate's last
    # line failed for any tenant that had both a card and one quiet email. `card_id` rather than
    # `signal_id` because the founder-visible object is the card.
    regressions = tuple(sorted(_ids(conn,
        "select distinct c.card_id from cards c "
        " join signals s on s.signal_id = c.signal_id and s.org_id = c.org_id "
        " join graph_facts f on f.org_id = c.org_id and f.subject_node_id = s.subject_node_id "
        "   and f.valid_to is null and f.status = 'active' and f.created_by_event_id is not null "
        " join source_events e on e.event_id = f.created_by_event_id and e.org_id = f.org_id "
        "where c.org_id = :org and e.occurred_at >= :since and e.occurred_at <= :until "
        "  and not exists (select 1 from qualified_signals q "
        "                   where q.org_id = :org and q.event_id = f.created_by_event_id)",
        window)))

    v1_nano = v1_cost_nano(conn, org_id=org_id, since=since, until=until)
    v2_nano = v2_cost_nano(conn, org_id=org_id, since=since, until=until)

    caveats: list[str] = []
    if not activation.live:
        caveats.append("this tenant has NO live row in l1_semantic_activation — the v2 semantic "
                       "lane did not run, so every number below is a diff of the old path "
                       "against nothing. 'Built but not enabled is not done.'")
    if not any(True for _ in ()) and len(v1_done) == 0:
        caveats.append("the old L2 extraction path processed NO event in this window, so there "
                       "is nothing to diff against: every 'v2 only' below is v2 against an "
                       "empty comparison rather than against v1.")
    if v1_nano == 0:
        caveats.append("no llm_costs rows with purpose='extract' in the window: there is no v1 "
                       "spend to be within 2x of, so the cost line is not a measurement.")
    caveats.append("v2 spend is priced from l1_extraction_results token counts because the L1 v2 "
                   "semantic lane files no llm_costs row (only capture/gate/relevance.py does). "
                   "The two sides use the same price table but not the same ledger.")

    return ShadowDiff(
        org_id=org_id, since=since, until=until, activation=activation,
        events_in_window=len(events), v1_processed=len(v1_done), v2_processed=len(v2_read),
        both_processed=len(v1_done & v2_read), v2_only_events=v2_only, misses=misses,
        span_counters=span_counters(conn, org_id=org_id, since=since, until=until),
        v1_cost_nano_per_1k=_cost_nano_per_1k(v1_nano, len(events)),
        v2_cost_nano_per_1k=_cost_nano_per_1k(v2_nano, len(events)),
        founder_visible_regressions=regressions, caveats=tuple(caveats))


def render(report: ShadowDiff) -> str:
    act = report.activation
    lines = [f"G10 shadow diff — org={report.org_id}",
             f"  window     {report.since:%Y-%m-%d} .. {report.until:%Y-%m-%d} UTC",
             f"  activation {'LIVE' if act.live else 'NOT ACTIVATED'}"
             + (f"  (since {act.enabled_at:%Y-%m-%d}, by {act.enabled_by})" if act.enabled_at
                else ""),
             f"  events     {report.events_in_window}  "
             f"(v1 processed {report.v1_processed}, v2 read {report.v2_processed})", ""]
    for key, observed, gate, ok in report.checks:
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {key:<32} {observed}   (gate {gate})")
    if report.misses:
        lines += ["", "  signals v1 found that L1 v2 did not:"]
        for miss in report.misses:
            lines.append(f"    {miss.event_id}  {miss.field:<24} {miss.reason}: {miss.detail}")
    for caveat in report.caveats:
        lines += ["", f"  NOTE: {caveat}"]
    lines += ["", f"  VERDICT: {'PASS' if report.passed else 'FAIL'}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="l1_shadow_diff",
        description="G10 pilot report: L1 v2 beside the old L2 extraction on one tenant.")
    parser.add_argument("--org", required=True, help="pilot org id")
    parser.add_argument("--days", type=int, default=7, help="window in whole days (default 7)")
    parser.add_argument("--since", type=parse_since, default=None,
                        help="window as 30d/12h/90m; overrides --days when given")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    url = resolve_database_url(args, purpose="G10 L1 v2 shadow diff (read-only)")

    from genios_engine.platform.db import get_engine
    until = datetime.now(timezone.utc)
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
