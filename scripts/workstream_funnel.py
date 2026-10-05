"""Where each piece of WORK's mail went — one row per workstream group. Read, never re-run.

    python scripts/workstream_funnel.py --org <org_id> --groups <groups.json> \\
        --database-url postgresql://…

⛔ WHY THIS EXISTS. On 2026-10-05 the founder's own mailbox held 365 inbound mails over 60 days, and
only 27 of them reached the stage where GeniOS can reason at all. By piece of work it was starker:
programs and incubators 168 → 3, government (Startup India) 8 → 0, the networking agent's
introductions 35 → 1. `scripts/pipeline_funnel_report.py` answers *"what did each LAYER decide"*;
nothing answered *"what happened to each piece of WORK"* — the question the `speedrun008/YC-II W27/`
plan is built on, and the number every one of its steps has to move.

⛔ THE GROUPS ARE DATA, NOT CODE. Which sender belongs to which piece of work is the tenant's
knowledge, so it is read from a JSON file the operator supplies with `--groups`. No sender, domain
or company name lives in this module. The first matching pattern wins; a sender nobody matched is
reported as `other`, never dropped — a measurement that loses rows is the defect it exists to
measure.

⛔ EVERY MAIL LANDS IN EXACTLY ONE COLUMN. The fate columns are mutually exclusive and checked in a
fixed order (`fate_of`), so a group's columns always add up to its mail count. An overlap would let
one mail be counted twice and make the funnel look healthier than it is.

    parked              still in the park queue
    reached_reasoning   carries an ACTIVE qualified signal — what L2 pulls today
    read_no_signal      extracted, but no box fitted, so it never entered memory
    junked              the S2 model filter called it junk (confident or not)
    deleted             no content stored anywhere — a rule dropped it
    kept_unread         content kept, never read (e.g. a bulk-header short circuit)

READ-ONLY BY CONSTRUCTION. One connection from `scripts/_gate.read_only_connection`, whose first
statement is `set transaction read only`, so the server — not a reviewer — refuses a write. The
target is never implicit (`scripts/_db`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402
from scripts._gate import read_only_connection, sql                   # noqa: E402

#: The fate columns, in the order `fate_of` tests them. Exclusive by construction.
FATES = ("parked", "reached_reasoning", "read_no_signal", "junked", "deleted", "kept_unread")

#: Where a mail nobody's pattern matched is counted. Never silently dropped.
OTHER = "other"


@dataclass(frozen=True)
class Group:
    name: str
    patterns: tuple[re.Pattern, ...]


@dataclass
class GroupRow:
    name: str
    mails: int = 0
    fates: dict[str, int] = field(default_factory=lambda: {f: 0 for f in FATES})


def load_groups(path: str | Path) -> tuple[Group, ...]:
    """The tenant's grouping, validated. Refuses an empty list, a duplicate name, a name that
    shadows `other`, and a pattern that does not compile — each loudly, never by skipping."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("groups") if isinstance(data, dict) else None
    if not raw:
        raise ValueError(f"{path}: expected {{\"groups\": [{{\"name\": …, \"patterns\": […]}}]}}")
    seen: set[str] = set()
    groups: list[Group] = []
    for entry in raw:
        name = str(entry.get("name") or "").strip()
        if not name or name == OTHER or name in seen:
            raise ValueError(f"{path}: group name {name!r} is empty, reserved or repeated")
        patterns = entry.get("patterns") or []
        if not patterns:
            raise ValueError(f"{path}: group {name!r} has no patterns")
        try:
            compiled = tuple(re.compile(p, re.IGNORECASE) for p in patterns)
        except re.error as exc:
            raise ValueError(f"{path}: group {name!r} has a pattern that does not compile: {exc}")
        seen.add(name)
        groups.append(Group(name=name, patterns=compiled))
    return tuple(groups)


def group_of(sender: str, groups: tuple[Group, ...]) -> str:
    """The first group whose pattern matches the sender's address; `other` when none does."""
    address = (sender or "").lower()
    for group in groups:
        if any(p.search(address) for p in group.patterns):
            return group.name
    return OTHER


def fate_of(*, outcome: str, active_signal: bool, extracted: bool, junked: bool,
            has_content: bool) -> str:
    """One mail's single fate, tested in `FATES` order. Total: every input lands somewhere."""
    if outcome == "parked":
        return "parked"
    if active_signal:
        return "reached_reasoning"
    if extracted:
        return "read_no_signal"
    if junked:
        return "junked"
    if not has_content:
        return "deleted"
    return "kept_unread"


def tally(rows, groups: tuple[Group, ...]) -> list[GroupRow]:
    """Per-group rows from per-mail facts, in the groups' own order, `other` last."""
    out = {g.name: GroupRow(g.name) for g in groups}
    out[OTHER] = GroupRow(OTHER)
    for r in rows:
        row = out[group_of(r["sender"], groups)]
        row.mails += 1
        row.fates[fate_of(outcome=r["outcome"], active_signal=bool(r["active_signal"]),
                          extracted=bool(r["extracted"]), junked=bool(r["junked"]),
                          has_content=bool(r["has_content"]))] += 1
    return [out[g.name] for g in groups] + [out[OTHER]]


def inbound_mail(conn, org: str) -> list[dict]:
    """One row per inbound message — the tenant's own seats excluded, re-reads excluded."""
    result = conn.execute(sql(
        "select lower(se.actor ->> 'email') as sender, se.outcome, "
        "       exists (select 1 from qualified_signals qs where qs.org_id = se.org_id "
        "                and qs.event_id = se.event_id and qs.state = 'active') as active_signal, "
        "       exists (select 1 from l1_extraction_results l where l.org_id = se.org_id "
        "                and l.event_id = se.event_id) as extracted, "
        "       exists (select 1 from event_trace et where et.org_id = se.org_id "
        "                and et.event_id = se.event_id and et.stage = 'S2' "
        "                and et.reason_code in ('llm_junk', 'llm_junk_unconfident')) as junked, "
        "       (exists (select 1 from prepared_content pc where pc.org_id = se.org_id "
        "                 and pc.event_id = se.event_id) "
        "        or exists (select 1 from raw_payloads rp where rp.org_id = se.org_id "
        "                    and rp.event_id = se.event_id)) as has_content "
        "  from source_events se "
        " where se.org_id = :o and se.source = 'gmail' and se.object_type = 'email_message' "
        "   and se.outcome <> 'superseded' "
        "   and lower(coalesce(se.actor ->> 'email', '')) not in "
        "       (select lower(s.email) from org_seats s where s.org_id = :o and s.email is not null)"),
        {"o": org})
    return [dict(r._mapping) for r in result]


def beyond_mail(conn, org: str, *, days: int) -> dict[str, list[tuple]]:
    """Calendar, screen, cards, model calls and the context an expert would need — counts only.

    Every statement is handed to `sql()` as a literal at its own call site, so the read-only test
    can see each one; a statement built elsewhere and passed by name would escape it."""
    def rows(clause, **params) -> list[tuple]:
        return [tuple(r) for r in conn.execute(clause, {"o": org, **params}).fetchall()]

    return {
        "calendar": rows(sql(
            "select (select count(*) from source_events where org_id = :o and source = 'gcal'), "
            "       (select count(*) from graph_nodes where org_id = :o "
            "         and node_type = 'meeting' and valid_to is null)")),
        "screen": rows(sql(
            "select kind, count(*), count(*) filter (where resolved_at is null) "
            "  from screen_followups where org_id = :o group by 1 order by 2 desc")),
        "cards": rows(sql(
            "select state, count(*) from cards where org_id = :o group by 1 order by 2 desc")),
        "calls": rows(sql(
            "select purpose, count(*), count(*) filter (where not success) "
            "  from llm_costs where org_id = :o "
            "   and created_at > now() - make_interval(days => :d) "
            " group by 1 order by 2 desc"), d=days),
        "context": rows(sql(
            "select (select count(*) from seat_objectives where org_id = :o), "
            "       (select count(*) from org_mission_critical_entities where org_id = :o), "
            "       (select count(*) from user_models where org_id = :o), "
            "       (select count(*) from learned_brain_entries where org_id = :o), "
            "       (select count(*) from card_feedback_verdicts where org_id = :o), "
            "       (select count(*) from unclassified_observations where org_id = :o), "
            "       (select count(*) from unclassified_observations where org_id = :o "
            "         and reviewed_at is not null)")),
    }


def render(table: list[GroupRow], extra: dict[str, list[tuple]], *, days: int) -> str:
    lines = []
    header = f"{'workstream':<28}{'mails':>6}" + "".join(f"{f:>19}" for f in FATES)
    lines.append(header)
    lines.append("─" * len(header))
    total = GroupRow("TOTAL")
    for row in table:
        lines.append(f"{row.name:<28}{row.mails:>6}" + "".join(f"{row.fates[f]:>19}" for f in FATES))
        total.mails += row.mails
        for f in FATES:
            total.fates[f] += row.fates[f]
    lines.append("─" * len(header))
    lines.append(f"{total.name:<28}{total.mails:>6}" + "".join(f"{total.fates[f]:>19}" for f in FATES))
    (gcal, meetings), = extra["calendar"]
    lines += ["", f"calendar events {gcal} → meeting nodes {meetings}"]
    lines += ["", "screen follow-ups (kind · total · open)"]
    lines += [f"  {k:<16}{n:>6}{o:>6}" for k, n, o in extra["screen"]]
    lines += ["", "cards (state · count)"]
    lines += [f"  {s:<16}{n:>6}" for s, n in extra["cards"]]
    lines += ["", f"model calls, last {days} days (purpose · calls · failed)"]
    lines += [f"  {p:<24}{n:>7}{b:>7}" for p, n, b in extra["calls"]]
    (obj, mce, um, lbe, cfv, uo, uo_rev), = extra["context"]
    lines += ["", "context an expert would need",
              f"  seat_objectives {obj} · org_mission_critical_entities {mce} · user_models {um}",
              f"  learned_brain_entries {lbe} · card_feedback_verdicts {cfv}",
              f"  unclassified_observations {uo} (reviewed {uo_rev})"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="org_id to measure")
    ap.add_argument("--groups", required=True, help="JSON file: the tenant's workstream groups")
    ap.add_argument("--days", type=int, default=3, help="window for the model-call counts")
    args = ap.parse_args()

    groups = load_groups(args.groups)
    url = resolve_database_url(args, purpose="workstream funnel (read-only)")

    from genios_engine.platform.db import get_engine
    conn = read_only_connection(get_engine(url))
    try:
        table = tally(inbound_mail(conn, args.org), groups)
        extra = beyond_mail(conn, args.org, days=args.days)
    finally:
        conn.close()
    print(render(table, extra, days=args.days))
    return 0


if __name__ == "__main__":        # pragma: no cover
    raise SystemExit(main())
