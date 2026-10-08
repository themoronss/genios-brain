"""A file's numbers — their reply time and yours, with what each rests on; its bounces; what was checked.

WHAT WAS WRONG (`STEP-10` §8.1). On the golden set the only reply times were two "tenant normals" built
from ONE reply counted twice, written on everyone with no n beside them; the founder's own reply time
existed nowhere; a bounce sat on the mail daemon's node; and "no reply" was said over a mailbox nobody
had shown was read. A file (STEP-09) had its evidence and its timeline (`context/workstream_timeline`),
and no number the expert could trust.

WHAT IS TRUE NOW (`yc2_w27_s10 · M29.C2.L-logic.V2.U04`). For each of the file's people, read — never
written here, no model:

  their reply time — measured on THEM, from their own replies, at any n: `median_of` over the gaps the
    waiting pass measures, each inside its own conversation (`waiting.conversation_reply_gaps` over
    `waiting.directed_timelines` — one reading of who wrote when, shared), so one reply reads
    *"once: 1.92 days"* and never a habit (`06` D37);
  their normal — what the cascade calls their normal (`party.reply_cadence_days` with its basis and
    n), present only where some level holds `NORMAL_AT` replies;
  your reply time — measured on your answers to them, at any n (`waiting.conversation_our_reply_gaps`); and
    your normal with them (`party.our_reply_*`), present only at `NORMAL_AT`;
  bounced — the latest delivery report that said our mail to them failed (`delivery.status`,
    `context/delivery`), shown while it is still the latest word between us: once they write, the
    address works, and once we write again, a newer mail is a new attempt — if it bounces too, its
    own report is the one shown (`M29.C3.L-logic.V2.U06`, found by STEP-10's crosscheck, X1).

And for the file: every WAVE one of its people was sent (`correlation_conversation.find_waves`, over the
waiting window — `M29.C2.L-logic.V2.U05`, found holding the build against STEP-10's vision, which says the
file serves the wave and nothing read it) with what came of it, overall and for this file's own people;
your normal across every counterparty (the tenant node's `derived.our_reply_*`);
the receipt of every mailbox its touches came through (`context/coverage_receipt`); the instant a
"no reply" would be about — our last mail in the file — and whether it may be said at all
(`coverage_receipt.covers`: a mailbox of the file reaches back that far and a completed sync has looked
since). Every statistic is a `Measured`; an instant is an instant.

AN ORG-LEVEL READER: no private fact is read, and the people are this tenant's file's own.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text

from genios_engine.context.correlation_conversation import Wave, find_waves
from genios_engine.context.coverage_receipt import MailboxReceipt, covers, receipt_for
from genios_engine.context.waiting import (conversation_our_reply_gaps, conversation_reply_gaps,
                                            directed_timelines)
from genios_engine.contracts.measured import Measured, median_of

#: The level a person's own numbers are measured at.
PERSON_BASIS = "person"

#: How far back a file looks for the waves its people were sent — the waiting window (`waiting`).
WAVE_LOOKBACK_DAYS = 180

_PEOPLE = text(
    "select node_id, canonical_key, display_name from graph_nodes "
    " where org_id = :o and node_id = any(:ids) and valid_to is null")

#: The numbers the waiting pass wrote on the file's people, and on the tenant.
_FACTS = text(
    "select subject_node_id, field, value #>> '{}' as value from graph_facts "
    " where org_id = :o and subject_node_id = any(:ids) and valid_to is null "
    "   and status = 'active' and visibility_scope is distinct from 'private' "
    "   and field in ('party.reply_cadence_days', 'party.reply_cadence_basis', "
    "                 'party.reply_cadence_n', 'party.our_reply_days', 'party.our_reply_n', "
    "                 'derived.our_reply_days', 'derived.our_reply_n')")

#: The LATEST report behind each person's `delivery.status = failed`, as of the instant asked about.
#: ⛔ NOT THE FACT'S OWN TIME: a second report on an address writes the same value, which the store
#: keeps as a corroborating reference on the first one's fact (`graph_store.fact_write_action`:
#: "noop"), so the fact's time is only the first report's — and a pitch that bounced after an older
#: one did would read the older bounce. Every report is a reference; the waves read them the same
#: way (`correlation_conversation._FAILED_DELIVERIES`).
_LATEST_BOUNCE = text(
    "select f.subject_node_id, max(e.occurred_at) as at from graph_facts f "
    "  join graph_source_refs r on r.org_id = f.org_id and r.fact_version_id = f.fact_version_id "
    "  join source_events e on e.org_id = r.org_id and e.event_id = r.event_id "
    " where f.org_id = :o and f.subject_node_id = any(:ids) and f.field = 'delivery.status' "
    "   and f.value #>> '{}' = 'failed' and f.valid_to is null and f.status = 'active' "
    "   and f.visibility_scope is distinct from 'private' and e.occurred_at <= :now "
    "   and (e.visibility_scope is null or e.visibility_scope <> 'private') "
    " group by f.subject_node_id")


@dataclass(frozen=True, slots=True)
class PersonNumbers:
    node_id: str
    key: str
    name: str | None
    their_reply_time: Measured             # measured on their own replies, any n
    their_normal: Measured | None          # the cascade's normal for them, where one holds
    your_reply_time: Measured              # measured on your answers to them, any n
    your_normal: Measured | None           # your normal with them, at NORMAL_AT
    bounced_at: datetime | None            # the latest report that our mail failed, while it stands


@dataclass(frozen=True, slots=True)
class FileNumbers:
    file_id: str
    as_of: datetime
    people: tuple[PersonNumbers, ...]
    your_normal_overall: Measured | None   # across every counterparty, on the tenant node
    mailboxes: tuple[MailboxReceipt, ...]
    no_reply_since: datetime | None        # our last mail in the file
    no_reply_can_be_said: bool
    waves: tuple[Wave, ...] = ()           # every wave one of the file's people was sent


def _number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normal(facts: dict, days: str, n: str, basis: str | None) -> Measured | None:
    """A normal the waiting pass wrote, as the `Measured` it is — or None where none holds."""
    value, count = _number(facts.get(days)), _number(facts.get(n))
    if value is None or not count:
        return None
    return Measured(value=value, n=int(count), basis=basis or PERSON_BASIS, unit="days")


def _standing(bounced_at: datetime | None, timeline) -> datetime | None:
    """A bounce while it is still the latest word between us and them — or None.

    `timeline` is the person's `(direction, at)` over the waiting window. A mail either way at or
    before the report leaves it standing; one after it ends it — they wrote (the address works: a
    full mailbox one day, an answer a week later), or we wrote again (a new attempt, whose own report
    is the latest if it bounces too). The wait reads the same order: a bounce ends it only at or
    after our last mail (`waiting._bounced_since_our_last_mail`).
    """
    if bounced_at is None or any(at > bounced_at for _direction, at in timeline):
        return None
    return bounced_at


def numbers_for(conn, org_id: str, file, timeline, *, now: datetime) -> FileNumbers:
    """The numbers of one file — `file` a `workstreams.WorkFile`, `timeline` its
    `workstream_timeline.FileTimeline`, both read as of `now`."""
    people = list(file.people)
    from genios_engine.context.periodic import tenant_node_id
    tenant = tenant_node_id(conn, org_id)
    ids = people + ([tenant] if tenant else [])
    facts: dict[str, dict[str, str]] = {}
    for r in conn.execute(_FACTS, {"o": org_id, "ids": ids}):
        facts.setdefault(r.subject_node_id, {})[r.field] = r.value
    bounced = {r.subject_node_id: r.at
               for r in conn.execute(_LATEST_BOUNCE, {"o": org_id, "ids": people, "now": now})}
    nodes = {r.node_id: r for r in conn.execute(_PEOPLE, {"o": org_id, "ids": people})}
    per_node, _types, conversations = directed_timelines(conn, org_id, now=now)

    rows: list[PersonNumbers] = []
    for node_id in people:
        node = nodes.get(node_id)
        if node is None:
            continue
        mine = facts.get(node_id, {})
        theirs = conversations.get(node_id, {})
        rows.append(PersonNumbers(
            node_id=node_id, key=node.canonical_key, name=node.display_name,
            their_reply_time=median_of(conversation_reply_gaps(theirs), basis=PERSON_BASIS,
                                       unit="days"),
            their_normal=_normal(mine, "party.reply_cadence_days", "party.reply_cadence_n",
                                 mine.get("party.reply_cadence_basis")),
            your_reply_time=median_of(conversation_our_reply_gaps(theirs), basis=PERSON_BASIS,
                                      unit="days"),
            your_normal=_normal(mine, "party.our_reply_days", "party.our_reply_n", PERSON_BASIS),
            bounced_at=_standing(bounced.get(node_id), per_node.get(node_id, ()))))
    rows.sort(key=lambda p: p.key)

    keys = {p.key for p in rows}
    waves = tuple(w for w in find_waves(conn, org_id, now=now,
                                        since=now - timedelta(days=WAVE_LOOKBACK_DAYS))
                  if keys & set(w.recipients))
    mailboxes = tuple(receipt_for(conn, org_id, now=now, connection_ids={
        t.mailbox for t in timeline.touches if t.kind == "mail" and t.mailbox}))
    ours = [t.at for t in timeline.touches if t.direction == "out"]
    since = max(ours) if ours else None
    return FileNumbers(
        file_id=file.file_id, as_of=now, people=tuple(rows),
        your_normal_overall=(_normal(facts.get(tenant, {}), "derived.our_reply_days",
                                     "derived.our_reply_n", "tenant") if tenant else None),
        mailboxes=mailboxes, no_reply_since=since, waves=waves,
        no_reply_can_be_said=since is not None and covers(mailboxes, since))


def as_dict(numbers: FileNumbers) -> dict:
    """The numbers as JSON — what `GET /v1/workstreams/{file_id}` serves beside the timeline."""
    def iso(at):
        return at.isoformat() if at else None

    def said(m):
        return m.as_dict() if m is not None else None
    return {
        "file_id": numbers.file_id, "as_of": iso(numbers.as_of),
        "people": [{"node_id": p.node_id, "key": p.key, "name": p.name,
                    "their_reply_time": said(p.their_reply_time),
                    "their_normal": said(p.their_normal),
                    "your_reply_time": said(p.your_reply_time),
                    "your_normal": said(p.your_normal), "bounced_at": iso(p.bounced_at)}
                   for p in numbers.people],
        "your_normal_overall": said(numbers.your_normal_overall),
        "mailboxes": [{"connection_id": m.connection_id, "address": m.address,
                       "window_days": m.window_days, "window_start": iso(m.window_start),
                       "last_finished_at": iso(m.last_finished_at),
                       "last_completed": m.last_completed} for m in numbers.mailboxes],
        "no_reply_since": iso(numbers.no_reply_since),
        "no_reply_can_be_said": numbers.no_reply_can_be_said,
        "waves": [_wave(w, {p.key for p in numbers.people}) for w in numbers.waves],
    }


def _wave(w: Wave, people: set[str]) -> dict:
    """One wave as JSON: what it was, what came of it, and what came of it for this file's people."""
    return {"wave_id": w.wave_id, "recognised_by": w.recognised_by, "line": w.line,
            "first_sent": w.first_sent.isoformat(), "last_sent": w.last_sent.isoformat(),
            "sent": w.sent.as_dict(), "replied": w.reply_rate.as_dict(),
            "bounced": w.bounce_rate.as_dict(), "followed_up": w.follow_up_rate.as_dict(),
            "days_since_last_send": w.days_since_last_send,
            "this_file": [{"key": k, "replied": k in w.replied, "bounced": k in w.bounced,
                           "followed_up": k in w.followed_up}
                          for k in sorted(people & set(w.recipients))]}


__all__ = ["FileNumbers", "PERSON_BASIS", "PersonNumbers", "as_dict", "numbers_for"]
