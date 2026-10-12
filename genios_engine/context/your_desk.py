"""Your desk, measured — your last mail out, and who has waited on you since when (STEP-15, F55).

`speedrun008/YC-II W27/` STEP-15 §8.4 item 1, tree `yc2_w27_s15` M44.C2.L-data.V0.U03 (`03` s15-F15). The golden
set's F55 — *"nothing sent for 28 days while three people wait"* — had no calculator: each person's file knew our
last mail TO THEM (`thread.last_outbound`), and nothing knew our last mail at all. A chief of staff reads the desk
first: three people asked you something, and you have written to nobody since the 14th.

  YOUR LAST MAIL — the newest mail any address of ours sent, from any mailbox, as of the instant asked about:
    who is us is `platform/self_identity` (STEP-04: the seats, the owner, the connected accounts, what the tenant
    declared). Its age is a COUNT of whole days (`contracts/measured.count_of` — exact, never a habit).
  MAY IT BE SAID — "nothing for 28 days" is a claim about every mailbox of ours: it stands only where EVERY
    connected mailbox's receipt reads back past that mail and a completed sync has looked since
    (`context/coverage_receipt.covers`). A mailbox that cannot vouch makes the silence unsayable — said so.
  WHO WAITS ON YOU — each file with an open ask owed by us (`context/workstreams.Ask.owed_by`), by the person who
    asked (a name, never an address: `platform/self_identity.spoken_name`), since their oldest such ask, its age a
    count of whole days; oldest first. Their count is a count too.

  THE QUESTIONS YOUR FILES ASK YOU (`open_questions`, M44.C2.L-data.V0.U02, `03` s15-F13) — every open question of
    the tenant asked by the instant, oldest first, with the card that asks it when one is open (STEP-13's question
    card: the open card on the signal the asking run raised for that file — its Answer is where the brief's line
    leads, `06` D60). A question was read one file at a time (`context/founder_questions.open_question`). The read
    lives here, beside who waits on you, because `context/founder_questions` is the STEP-16 builder's this step (the
    lead, 12 Oct); it reads the same table and writes nothing.

Read over one connection, as of an instant; no model, nothing written.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.context.coverage_receipt import MailboxReceipt, MAILBOX_SOURCES, covers, receipt_for
from genios_engine.contracts.measured import Measured, count_of
from genios_engine.platform.self_identity import identity_for, spoken_name

#: The level the desk's numbers are measured at: you.
DESK_BASIS = "you"

#: Every sender's newest mail as of the instant — one row per sender; which are ours is asked of the identity.
_LAST_BY_SENDER = text(
    "select distinct on (lower(se.actor->>'email')) lower(se.actor->>'email') as sender, se.event_id, "
    "       se.occurred_at, se.connection_id "
    "  from source_events se "
    " where se.org_id = :o and se.source = any(:mail) and se.occurred_at <= :now "
    "   and se.actor->>'email' is not null "
    " order by lower(se.actor->>'email'), se.occurred_at desc, se.event_id desc")

_NAMES = text(
    "select node_id, display_name, canonical_key from graph_nodes "
    " where org_id = :o and node_id = any(:ids) and valid_to is null")


#: The card states a founder can still see (`deliver/store.CardStore.OPEN_STATES`, read here, layers below it).
OPEN_CARD_STATES: tuple[str, ...] = ("queued", "surfaced", "snoozed", "claimed", "delivered")

#: Every open question asked by the instant, oldest first, with the open card on the signal its asking run raised.
_OPEN_QUESTIONS = text(
    "select q.question_id, q.file_id, q.fingerprint, q.run_id, q.question, q.asked_at, "
    "       (select k.card_id from cards k join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id "
    "         where k.org_id = q.org_id and s.subject_node_id = q.file_id and s.reasoning_run_id = q.run_id "
    "           and s.output_lane = 'investigation' and k.state = any(:open) order by k.card_id limit 1) as card_id "
    "  from founder_questions q "
    " where q.org_id = :o and q.state = 'open' and q.asked_at <= :now "
    " order by q.asked_at, q.question_id")


@dataclass(frozen=True, slots=True)
class OpenQuestion:
    """A question a file asks you, and the card that asks it."""
    question_id: str
    file_id: str
    fingerprint: str
    run_id: str | None
    question: str
    asked_at: datetime
    card_id: str | None


def open_questions(conn, org_id: str, *, now: datetime) -> tuple[OpenQuestion, ...]:
    """Every open question of the tenant asked by `now`, oldest first, each with its open card or None."""
    return tuple(OpenQuestion(question_id=r.question_id, file_id=r.file_id, fingerprint=r.fingerprint,
                              run_id=r.run_id, question=r.question, asked_at=r.asked_at, card_id=r.card_id)
                 for r in conn.execute(_OPEN_QUESTIONS, {"o": org_id, "now": now, "open": list(OPEN_CARD_STATES)}))


@dataclass(frozen=True, slots=True)
class Waiting:
    """One file waiting on you: who asked, since when, how long."""
    file_id: str
    who: str | None                  # the person who asked, by name — never an address
    since: datetime                  # their oldest open ask owed by us
    days: Measured                   # whole days since, a count
    loop_id: str


@dataclass(frozen=True, slots=True)
class Desk:
    as_of: datetime
    last_out: datetime | None        # your newest mail, across every mailbox of ours
    last_out_event: str | None
    days_since: Measured | None      # whole days since it, a count — None when you sent nothing in reach
    silence_can_be_said: bool        # every mailbox reads back past it, and has looked since
    mailboxes: tuple[MailboxReceipt, ...]
    waiting: tuple[Waiting, ...]     # oldest first
    waiting_count: Measured


def _whole_days(later: datetime, earlier: datetime) -> int:
    return max(0, math.floor((later - earlier).total_seconds() / 86400))


def desk_for(conn, org_id: str, files: Iterable, *, now: datetime) -> Desk:
    """Your desk as of `now`. `files` are the tenant's files (`context/workstreams.files_for`), read as of `now`."""
    us = identity_for(conn, org_id)
    last = None
    for r in conn.execute(_LAST_BY_SENDER, {"o": org_id, "mail": sorted(MAILBOX_SOURCES), "now": now}):
        if us.is_us(r.sender) and (last is None or (r.occurred_at, r.event_id) > (last.occurred_at, last.event_id)):
            last = r
    mailboxes = tuple(receipt_for(conn, org_id, now=now))
    silence = (last is not None and bool(mailboxes)
               and all(covers([m], last.occurred_at) for m in mailboxes))

    owed: dict[str, tuple[datetime, str, str]] = {}      # file → (since, loop, asker)
    for f in files:
        for ask in f.open_asks:
            if ask.owed_by != "us" or ask.opened_at is None:
                continue
            held = owed.get(f.file_id)
            if held is None or (ask.opened_at, ask.loop_id) < (held[0], held[1]):
                owed[f.file_id] = (ask.opened_at, ask.loop_id, ask.asked_by)
    nodes = {r.node_id: r for r in conn.execute(_NAMES, {"o": org_id,
                                                         "ids": sorted({a for _s, _l, a in owed.values()})})}
    waiting = []
    for file_id, (since, loop_id, asker) in owed.items():
        node = nodes.get(asker)
        waiting.append(Waiting(
            file_id=file_id, since=since, loop_id=loop_id,
            who=spoken_name(node.display_name, node.canonical_key) if node is not None else None,
            days=count_of(_whole_days(now, since), basis="person", unit="days")))
    waiting.sort(key=lambda w: (w.since, w.file_id))
    return Desk(as_of=now, last_out=None if last is None else last.occurred_at,
                last_out_event=None if last is None else last.event_id,
                days_since=None if last is None else count_of(_whole_days(now, last.occurred_at),
                                                               basis=DESK_BASIS, unit="days"),
                silence_can_be_said=silence, mailboxes=mailboxes, waiting=tuple(waiting),
                waiting_count=count_of(len(waiting), basis=DESK_BASIS, unit="people"))


__all__ = ["DESK_BASIS", "Desk", "OPEN_CARD_STATES", "OpenQuestion", "Waiting", "desk_for", "open_questions"]
