"""A file's timeline — every touch both ways, who did it, its evidence, and the gaps (STEP-10).

WHAT WAS WRONG (`STEP-10` §8.2). The directed timeline existed only inside `context/waiting`, rebuilt
over 180 days and reduced to four "last seen" facts; `reason/reasoners/timeline_unit` reads
`timeline.events`, which nothing writes, so it saw one event; and no timeline anywhere held a meeting.
A founder's file (`context/workstreams`, STEP-09) had its evidence ids and a last touch, and no story.

WHAT IS TRUE NOW (`yc2_w27_s10 · M29.C2.L-logic.V2.U01`). A file is one anchor's correlations, so its
timeline is their members, read — a read model, no table, no model, the same graph gives the same
timeline:

  a TOUCH is a mail or a meeting. A mail is `in` or `out` by who WROTE it — the event's actor, never
    the node a fact sits on: since STEP-09 an introduction writes the turn on the person introduced,
    and the touch is still the connector's (`STEP-10` N3). A meeting is one touch per calendar event,
    at its CURRENT start: every edit lands as its own event at the meeting's start (STEP-05), so the
    newest version captured is the meeting, and a cancelled one is no touch. A meeting still to come
    is BOOKED (`upcoming`) — not a touch, and it does not end a silence. Any other evidence in the
    file (a screen capture, a document) is the file's, not a touch of the counterparty;
  the GAPS are the closed intervals between consecutive touches, oldest first. The open stretch since
    the last touch is not a gap — it may close tomorrow (`timeline_unit._gaps`, the same rule) — it is
    `days_quiet`, one exact interval;
  the USUAL GAP is their median, a `Measured` with its n (`contracts/measured`): below `NORMAL_AT`
    gaps it is shown as what it is, never as the file's rhythm (`06` D37);
  SILENCE EXCEEDS PRIOR GAPS when the open stretch is longer than the longest gap the file ever
    closed — `timeline_unit`'s `silence_exceeds_prior_gaps`, the trigger `STEP-12` reads; `None` with
    no gap to compare, which is not a finding either way.

AN ORG-LEVEL READER, SO NOTHING PRIVATE (`context/fact_visibility`): an event a seat captured
privately is no touch. A file id from another tenant reads as an empty timeline here.

A TOUCH SAYS WHAT IT SAID (STEP-12, `yc2_w27_s12` M32.C2.L-data.V0.U06). Each touch carries its
ledger OUTCOME and its WORDS — the prepared text memory holds for it, cut at `WORDS_CHARS` on a word
and the cut counted (`words_cut`, per touch and for the file). The outcome is asked FIRST: a
correlation's membership ignores outcome (`03` F57), so an archived mail can be a member of a file,
and its words are never read through one — it stays a touch, `outcome` says what it is. This is what
lets the expert read a portal's notice (F99) and the reply a promise answered beside our own promise
(F147); which touches the dossier shows whole is the dossier's (`reason/expert/dossier`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.contracts.measured import Measured, median_of
from genios_engine.platform.self_identity import identity_for

#: The level a file's own numbers are measured at (`contracts/measured`).
FILE_BASIS = "file"

#: What a touch is, by the ledger's (source, object type).
MAIL = ("gmail", "email_message")
MEETING = ("gcal", "calendar_event")

#: A cancelled calendar event is no meeting (`capture/structured/registry` — gcal's `status`).
CANCELLED = "cancelled"

#: The most of one touch's words a timeline carries; the rest is counted in `words_cut`.
WORDS_CHARS = 1200


@dataclass(frozen=True, slots=True)
class Touch:
    """One mail or meeting in a file."""
    at: datetime
    kind: str                          # "mail" | "meeting"
    direction: str                     # "in" — they wrote · "out" — we wrote · "meeting"
    who: str | None                    # who WROTE it (the event's actor): an intro is the connector's
    who_name: str | None
    event_id: str                      # the evidence
    thread: str | None                 # the mail's conversation; None for a meeting
    mailbox: str | None = None         # the connection it came through — what a coverage receipt is about
    outcome: str | None = None         # the ledger's outcome, asked before any word is read (`03` F57)
    words: str | None = None           # what it said, cut at WORDS_CHARS — None for an archive or no text
    words_cut: int = 0                 # the characters of it left out


@dataclass(frozen=True, slots=True)
class FileTimeline:
    file_id: str
    as_of: datetime
    touches: tuple[Touch, ...]         # oldest first
    upcoming: tuple[Touch, ...]        # meetings booked after `as_of`, soonest first
    gaps_days: tuple[float, ...]       # closed intervals between consecutive touches, oldest first
    usual_gap: Measured                # their median, with its n
    longest_gap_days: float | None
    days_quiet: float | None           # the open stretch since the last touch — not a gap
    silence_exceeds_prior_gaps: bool | None
    words_cut: int = 0                 # every touch's words left out, summed


#: The words come only through a KEPT event (`se.outcome = 'emitted'` in the join): the outcome is
#: asked before the text is, so an archived member's words are never read (`03` F57).
_TOUCHES = text(
    "select distinct se.event_id, se.source, se.object_type, se.source_object_id, "
    "       se.parent_object_id, se.occurred_at, se.captured_at, se.connection_id, "
    "       lower(se.actor->>'email') as who, se.actor->>'name' as who_name, se.outcome, "
    "       pc.clean_text as words "
    "  from context_correlations k "
    "  join context_correlation_members m on m.org_id = k.org_id "
    "       and m.correlation_id = k.correlation_id "
    "  join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
    "  left join prepared_content pc on pc.org_id = se.org_id and pc.event_id = se.event_id "
    "       and se.outcome = 'emitted' "
    " where k.org_id = :o and k.anchor_node_id = :f "
    "   and se.visibility_scope is distinct from 'private' "
    "   and ((se.source = 'gmail' and se.object_type = 'email_message') "
    "        or (se.source = 'gcal' and se.object_type = 'calendar_event'))")

#: The meetings the calendar now says are cancelled: the meeting node's current status
#: (`context/structured` files it at the version's own time, so the newest edit holds it).
_CANCELLED = text(
    "select n.canonical_key from graph_nodes n "
    "  join graph_facts f on f.org_id = n.org_id and f.subject_node_id = n.node_id "
    " where n.org_id = :o and n.valid_to is null and n.canonical_key = any(:keys) "
    "   and f.field = 'meeting.status' and f.valid_to is null and f.value #>> '{}' = :cancelled")


def _said(words: str | None) -> tuple[str | None, int]:
    """A touch's words, cut on a word boundary at `WORDS_CHARS`, and how many characters were left
    out — never cut inside a word, never cut silently."""
    folded = " ".join(str(words or "").split())
    if not folded:
        return None, 0
    if len(folded) <= WORDS_CHARS:
        return folded, 0
    head = folded[:WORDS_CHARS]
    if folded[WORDS_CHARS] != " " and " " in head:      # the limit falls inside a word: cut before it
        head = head.rsplit(" ", 1)[0]
    head = head.rstrip()
    return head, len(folded) - len(head)


def _days(later: datetime, earlier: datetime) -> float:
    return round((later - earlier).total_seconds() / 86400.0, 2)


def timeline_for(conn, org_id: str, file_id: str, *, now: datetime) -> FileTimeline:
    """The timeline of one file — `file_id` is the anchor node `context/workstreams` names it by."""
    us = identity_for(conn, org_id)
    rows = list(conn.execute(_TOUCHES, {"o": org_id, "f": file_id}))

    # One touch per meeting: the newest version the calendar sent, at its start.
    newest: dict[str, object] = {}
    for r in rows:
        if (r.source, r.object_type) == MEETING:
            held = newest.get(r.source_object_id)
            if held is None or (r.captured_at, r.event_id) > (held.captured_at, held.event_id):
                newest[r.source_object_id] = r
    cancelled = {key.split(":", 1)[1] for (key,) in conn.execute(_CANCELLED, {
        "o": org_id, "keys": [f"gcal:{m}" for m in sorted(newest)], "cancelled": CANCELLED})}

    touches: list[Touch] = []
    upcoming: list[Touch] = []
    for r in rows:
        words, cut = _said(r.words)             # an archive's words never left the database
        if (r.source, r.object_type) == MAIL:
            touches.append(Touch(at=r.occurred_at, kind="mail",
                                 direction="out" if us.is_us(r.who) else "in", who=r.who,
                                 who_name=r.who_name, event_id=r.event_id,
                                 thread=r.parent_object_id, mailbox=r.connection_id,
                                 outcome=r.outcome, words=words, words_cut=cut))
        elif newest.get(r.source_object_id) is r and r.source_object_id not in cancelled:
            meeting = Touch(at=r.occurred_at, kind="meeting", direction="meeting", who=r.who,
                            who_name=r.who_name, event_id=r.event_id, thread=None,
                            mailbox=r.connection_id, outcome=r.outcome, words=words,
                            words_cut=cut)
            (touches if r.occurred_at <= now else upcoming).append(meeting)
    touches.sort(key=lambda t: (t.at, t.event_id))
    upcoming.sort(key=lambda t: (t.at, t.event_id))

    gaps = tuple(_days(touches[i + 1].at, touches[i].at) for i in range(len(touches) - 1))
    quiet = _days(now, touches[-1].at) if touches else None
    longest = max(gaps) if gaps else None
    return FileTimeline(
        file_id=file_id, as_of=now, touches=tuple(touches), upcoming=tuple(upcoming),
        gaps_days=gaps, usual_gap=median_of(gaps, basis=FILE_BASIS, unit="days"),
        longest_gap_days=longest, days_quiet=quiet,
        silence_exceeds_prior_gaps=(quiet > longest) if longest is not None else None,
        words_cut=sum(t.words_cut for t in touches))


def as_dict(tl: FileTimeline) -> dict:
    """The timeline as JSON — what `GET /v1/workstreams/{file_id}` serves."""
    def touch(t: Touch) -> dict:
        return {"at": t.at.isoformat(), "kind": t.kind, "direction": t.direction, "who": t.who,
                "who_name": t.who_name, "event_id": t.event_id, "thread": t.thread,
                "mailbox": t.mailbox, "outcome": t.outcome, "words": t.words,
                "words_cut": t.words_cut}
    return {"file_id": tl.file_id, "as_of": tl.as_of.isoformat(),
            "touches": [touch(t) for t in tl.touches],
            "upcoming": [touch(t) for t in tl.upcoming],
            "gaps_days": list(tl.gaps_days), "usual_gap": tl.usual_gap.as_dict(),
            "longest_gap_days": tl.longest_gap_days, "days_quiet": tl.days_quiet,
            "silence_exceeds_prior_gaps": tl.silence_exceeds_prior_gaps,
            "words_cut": tl.words_cut}


__all__ = ["CANCELLED", "FILE_BASIS", "FileTimeline", "Touch", "WORDS_CHARS", "as_dict",
           "timeline_for"]
