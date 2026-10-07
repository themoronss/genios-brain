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
  bounced — when a delivery report said our mail to them failed (`delivery.status`, `context/delivery`).

And for the file: your normal across every counterparty (the tenant node's `derived.our_reply_*`);
the receipt of every mailbox its touches came through (`context/coverage_receipt`); the instant a
"no reply" would be about — our last mail in the file — and whether it may be said at all
(`coverage_receipt.covers`: a mailbox of the file reaches back that far and a completed sync has looked
since). Every statistic is a `Measured`; an instant is an instant.

AN ORG-LEVEL READER: no private fact is read, and the people are this tenant's file's own.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.context.coverage_receipt import MailboxReceipt, covers, receipt_for
from genios_engine.context.waiting import (conversation_our_reply_gaps, conversation_reply_gaps,
                                            directed_timelines)
from genios_engine.contracts.measured import Measured, median_of

#: The level a person's own numbers are measured at.
PERSON_BASIS = "person"

_PEOPLE = text(
    "select node_id, canonical_key, display_name from graph_nodes "
    " where org_id = :o and node_id = any(:ids) and valid_to is null")

#: The numbers the waiting pass and the delivery report wrote on the file's people, and on the tenant.
_FACTS = text(
    "select subject_node_id, field, value #>> '{}' as value, occurred_at from graph_facts "
    " where org_id = :o and subject_node_id = any(:ids) and valid_to is null "
    "   and status = 'active' and visibility_scope is distinct from 'private' "
    "   and field in ('party.reply_cadence_days', 'party.reply_cadence_basis', "
    "                 'party.reply_cadence_n', 'party.our_reply_days', 'party.our_reply_n', "
    "                 'derived.our_reply_days', 'derived.our_reply_n', 'delivery.status')")


@dataclass(frozen=True, slots=True)
class PersonNumbers:
    node_id: str
    key: str
    name: str | None
    their_reply_time: Measured             # measured on their own replies, any n
    their_normal: Measured | None          # the cascade's normal for them, where one holds
    your_reply_time: Measured              # measured on your answers to them, any n
    your_normal: Measured | None           # your normal with them, at NORMAL_AT
    bounced_at: datetime | None            # a report said our mail to them failed


@dataclass(frozen=True, slots=True)
class FileNumbers:
    file_id: str
    as_of: datetime
    people: tuple[PersonNumbers, ...]
    your_normal_overall: Measured | None   # across every counterparty, on the tenant node
    mailboxes: tuple[MailboxReceipt, ...]
    no_reply_since: datetime | None        # our last mail in the file
    no_reply_can_be_said: bool


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


def numbers_for(conn, org_id: str, file, timeline, *, now: datetime) -> FileNumbers:
    """The numbers of one file — `file` a `workstreams.WorkFile`, `timeline` its
    `workstream_timeline.FileTimeline`, both read as of `now`."""
    people = list(file.people)
    from genios_engine.context.periodic import tenant_node_id
    tenant = tenant_node_id(conn, org_id)
    ids = people + ([tenant] if tenant else [])
    facts: dict[str, dict[str, str]] = {}
    when: dict[str, dict[str, datetime]] = {}
    for r in conn.execute(_FACTS, {"o": org_id, "ids": ids}):
        facts.setdefault(r.subject_node_id, {})[r.field] = r.value
        when.setdefault(r.subject_node_id, {})[r.field] = r.occurred_at
    nodes = {r.node_id: r for r in conn.execute(_PEOPLE, {"o": org_id, "ids": people})}
    _per_node, _types, conversations = directed_timelines(conn, org_id, now=now)

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
            bounced_at=(when.get(node_id, {}).get("delivery.status")
                        if mine.get("delivery.status") == "failed" else None)))
    rows.sort(key=lambda p: p.key)

    mailboxes = tuple(receipt_for(conn, org_id, now=now, connection_ids={
        t.mailbox for t in timeline.touches if t.kind == "mail" and t.mailbox}))
    ours = [t.at for t in timeline.touches if t.direction == "out"]
    since = max(ours) if ours else None
    return FileNumbers(
        file_id=file.file_id, as_of=now, people=tuple(rows),
        your_normal_overall=(_normal(facts.get(tenant, {}), "derived.our_reply_days",
                                     "derived.our_reply_n", "tenant") if tenant else None),
        mailboxes=mailboxes, no_reply_since=since,
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
    }


__all__ = ["FileNumbers", "PERSON_BASIS", "PersonNumbers", "as_dict", "numbers_for"]
