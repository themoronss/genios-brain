"""The dossier for ONE file — everything the expert is shown, in one fixed order, with what it may cite (STEP-12).

`speedrun008/YC-II W27/` STEP-12 §3.1 and §8.3 N6, tree `yc2_w27_s12` M32.C2.L-logic.V1.U04. The parts
existed and were unbounded or unread by file; this puts them in front of the expert, in an order that
never moves, each bounded and each cut COUNTED:

  brief          the company brief as every judging prompt carries it (STEP-07);
  file           the counterparty, the kind of work the brief gives it and its role, its open asks;
  timeline       the newest touches WHOLE — who, when, which way, the words memory holds for each
                 (`context/workstream_timeline`, an archive's words never read) — older touches one line
                 each, the rest counted; the meetings booked; the gaps, with the usual one and its n;
  promises       the promises made in the file's own mail, ours and theirs, each due when it says —
                 and a *"soon"* is no deadline (`06` D56): the expert judges whether soon has passed;
  numbers        each person's reply time and yours with their n (STEP-10) — yours on every answer,
                 not split by who wrote first, as decided (D52) — and the waves they were sent;
  coverage       every mailbox the file's mail came through, and whether "no reply" may be said;
  playbook       the kind's playbook, reviewed or labelled *"playbook not yet reviewed"* (D3): its stages
                 (the closed list the file's stage is named from), moves, claims, stop rule and what
                 doing nothing costs, every duration a labelled prior (STEP-11);
  situations     each situation anchored on the file against the quiet window its kind holds it to;
  judged_before  the expert's own past reviews of the file, the cards about its people with their
                 events and the founder's verdicts, how its situations ended, and its own history;
  what_if        what 3, 7 and 14 days of nothing do to it (`06` D39).

WHAT IT MAY CITE. Every item the expert may point at is printed with its id in brackets — an event id,
`loop:`, `promise:`, `num:`, `wave:`, `pb:`, `sit:`, `review:`, `card:`, `hist:`, `whatif:` — and the
`catalogue` (`contracts/expert_review.DossierCatalogue`) holds exactly those ids, every number written
anywhere in the dossier, and the playbook's stages. `validate` holds a review to it.

BOUNDED BY CONSTRUCTION. Each part has its own limit (the constants below), so a dossier cannot outgrow
`DOSSIER_CHARS` — the budget the expert's per-call ceiling was sized for (`reason/bundle/budget.OWN_
BUDGETS`) — and a test holds a maximal one under it. What a limit leaves out is counted per section,
never silent. A screen capture is no touch of a file (D53), as built.

`build_dossier` is pure over its parts; `read_parts` reads them for one file; `dossier_for` is both.

WHAT THE CHECK READS BACK (STEP-13, tree `yc2_w27_s13` M35.C2.L-logic.V0.U01). `reason/expert/verify` holds
each claim to the lines it cites, so the dossier is read back by id: `lines_by_id` maps every id the text
prints to each place it is printed — the line, the item it belongs to (a head line and the lines indented
under it: a touch's words, a person's numbers) and, for a touch, its words. `people_of` says who the file's
mail shows, who is us, and which connector introduced its counterparty — whom a draft may go to — named as
the person it is (`connector_of`, M35.C2.L-logic.V0.U13).
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.expert_review import DossierCatalogue, number_tokens
from genios_engine.platform.self_identity import PUBLIC_MAIL_DOMAINS, SelfIdentity

DOSSIER_VERSION = "dossier.v1"

#: The sections, in the one order a dossier is ever written in.
SECTIONS: tuple[str, ...] = ("brief", "file", "timeline", "promises", "numbers", "coverage",
                             "playbook", "situations", "judged_before", "what_if")
#: A section printed only when it has something to say — and the section it follows. A file with none of
#: them is printed byte for byte as before (STEP-13: the founder's answers, M36.C2.L-data.V2.U07).
OPTIONAL: Mapping[str, str] = {"answers": "timeline"}
TITLES: Mapping[str, str] = {
    "brief": "THE COMPANY BRIEF", "file": "THE FILE", "timeline": "WHAT HAPPENED",
    "answers": "WHAT YOU TOLD US",
    "promises": "PROMISES IN ITS MAIL", "numbers": "ITS NUMBERS", "coverage": "WHAT WAS CHECKED",
    "playbook": "WHAT A PROFESSIONAL KNOWS ABOUT THIS WORK", "situations": "ITS SITUATIONS",
    "judged_before": "WHAT WAS JUDGED BEFORE", "what_if": "IF NOTHING HAPPENS"}

TOUCHES_WHOLE = 8          # the newest touches, shown with their words
TOUCHES_LISTED = 30        # the older ones after them, one line each; the rest counted
PEOPLE_LIMIT = 10
WAVES_LIMIT = 5
PROMISES_LIMIT = 10
MOVES_LIMIT = 10
CLAIMS_LIMIT = 20
#: The most a dossier can be, in characters — measured on a maximal one, not cut to.
DOSSIER_CHARS = 60_000

#: The words that make a promise's time RELATIVE (`DateCertainty.RELATIVE`): never a deadline (D56).
RELATIVE_WORDS: tuple[str, ...] = ("soon", "shortly", "in a while", "in a bit", "at some point",
                                   "in due course")

_DIRECTION = {"in": "they wrote", "out": "we wrote", "meeting": "a meeting"}
#: A situation still open (`context/workstreams.OPEN_STATUSES`): an outcome on it was a decision.
_OPEN = ("active", "partial")
_WINDOW_FROM = {"kind": "the file's kind of work", "domain": "its domain's clock",
                "engine": "the engine's default"}
_NO_PLAYBOOK = {"no_kind": "the brief names no kind of work for it",
                "unknown_kind": "its kind of work is not one the corpus knows",
                "no_capability_for_kind": "no capability is written for its kind of work yet",
                "capability_not_authored": "its capability is not authored yet",
                "no_playbook_declares_stages": "no playbook of its capability declares its stages",
                "several_playbooks_declare_stages": "several playbooks claim to be its spine"}


# ── the parts ──────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Promise:
    """A promise made in the file's own mail: who made it, what, and when it is due — if it is."""
    promise_id: str
    words: str
    quote: str | None
    due_at: datetime | None
    status: str | None
    owner: str | None
    ours: bool | None
    event_id: str | None

    @property
    def relative(self) -> str | None:
        """The word that makes its time relative — a *"soon"* is no deadline (`06` D56) — read as a
        whole word from its words and its quote, or None."""
        said = f"{self.words} {self.quote or ''}".lower()
        return next((w for w in RELATIVE_WORDS if re.search(rf"\b{re.escape(w)}\b", said)), None)


@dataclass(frozen=True, slots=True)
class DossierParts:
    org_id: str
    file_id: str
    as_of: datetime
    brief: Any                 # contracts/company_brief.CompanyBrief, or None
    file: Any                  # context/workstreams.WorkFile
    timeline: Any              # context/workstream_timeline.FileTimeline
    numbers: Any               # context/workstream_numbers.FileNumbers, or None
    playbook: Any              # packs/compiler/playbook_reader.PlaybookAnswer
    judgments: Any             # context/file_judgments.FileJudgments
    lifecycle: Any             # context/workstreams.Lifecycle
    what_if: tuple = ()        # reason/simulation.TimePasses, one per step
    promises: tuple[Promise, ...] = ()
    promises_cut: int = 0
    #: The questions this file asked the founder and the founder answered (`context/founder_questions`,
    #: STEP-13 M36.C2.L-data.V2.U07) — newest answer first. Printed only when there is one.
    answers: tuple = ()


@dataclass(frozen=True, slots=True)
class Section:
    name: str
    text: str
    cut: int = 0               # the items this section's limit left out


@dataclass(frozen=True, slots=True)
class Dossier:
    org_id: str
    file_id: str
    as_of: datetime
    sections: tuple[Section, ...]
    catalogue: DossierCatalogue
    digest: str
    version: str = DOSSIER_VERSION

    @property
    def text(self) -> str:
        head = f"DOSSIER {self.version} — file {self.file_id}, as of {_when(self.as_of)}"
        return "\n\n".join([head, *(f"## {TITLES[s.name]}\n{s.text}" for s in self.sections)])

    @property
    def cut(self) -> dict[str, int]:
        return {s.name: s.cut for s in self.sections}


# ── writing ────────────────────────────────────────────────────────────────────────────────────

def _when(at: datetime | None) -> str:
    if at is None:
        return "unknown"
    at = at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)
    return at.strftime("%Y-%m-%d %H:%M UTC")


def _n(value: Any) -> str:
    if value is None:
        return "unknown"
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _says(measured: Any) -> str:
    return measured.says() if measured is not None else "not measured"


class _Ids:
    """Every id the dossier prints — and so every id the expert may cite."""

    def __init__(self) -> None:
        self.seen: set[str] = set()

    def __call__(self, ref: str) -> str:
        self.seen.add(ref)
        return f"[{ref}]"


def _brief(p: DossierParts, cite: _Ids) -> Section:
    block = p.brief.prompt_block().strip() if p.brief is not None and p.brief else ""
    return Section("brief", block or "No company brief is accepted for this tenant.")


def _file(p: DossierParts, cite: _Ids) -> Section:
    f = p.file
    lines = [f"Counterparty: {f.counterparty} <{f.counterparty_key}> ({f.counterparty_type})",
             f"Kind of work: {f.work_kind or 'not named by the brief'}",
             f"Its role in the brief: {f.kind or 'none'}"
             + (f" — the brief says: “{f.line}”" if f.line else "")]
    if f.introduced_by:
        lines.append(f"Introduced by: {f.introduced_by}")
    lines.append(f"Domains: {', '.join(f.domains) or 'none'}")
    # From the timeline — touches up to the dossier's as-of — never a meeting booked ahead (`03` F159).
    touched = p.timeline.touches
    lines.append(f"First touch {_when(touched[0].at if touched else None)}; "
                 f"last touch {_when(touched[-1].at if touched else None)}")
    lines.append(f"Whose move: {f.whose_move or 'not written'}")
    if f.introductions is not None:
        lines.append(f"People it introduced: {_says(f.introductions)} {cite('num:introductions')}; "
                     f"of them wrote to us: {_says(f.replied)} {cite('num:replied')}; "
                     f"met us: {_says(f.calls)} {cite('num:calls')}")
    if f.open_asks:
        lines.append("Open asks:")
        for a in f.open_asks:
            lines.append(f"- {cite('loop:' + a.loop_id)} {a.kind}, "
                         + ("they wait on us" if a.owed_by == "us" else "we wait on them")
                         + f", open since {_when(a.opened_at)}")
    else:
        lines.append("Open asks: none")
    return Section("file", "\n".join(lines))


def _timeline(p: DossierParts, cite: _Ids) -> Section:
    tl = p.timeline
    newest = list(reversed(tl.touches))
    whole, listed = newest[:TOUCHES_WHOLE], newest[TOUCHES_WHOLE:TOUCHES_WHOLE + TOUCHES_LISTED]
    cut = len(newest) - len(whole) - len(listed)
    lines = [] if newest else ["No touch yet."]
    for t in whole:
        head = (f"- {cite(t.event_id)} {_when(t.at)} · {_DIRECTION.get(t.direction, t.direction)} · "
                f"{t.who_name or t.who or 'unknown'}")
        if t.outcome and t.outcome != "emitted":
            lines.append(head + f" · {t.outcome} — its words are not read")
            continue
        lines.append(head)
        if t.words:
            lines.append(f"  “{t.words}”" + (f" … ({t.words_cut} characters cut)"
                                              if t.words_cut else ""))
        else:
            lines.append("  (memory holds no words for it)")
    for t in listed:
        lines.append(f"- {cite(t.event_id)} {_when(t.at)} · {_DIRECTION.get(t.direction, t.direction)}"
                     f" · {t.who_name or t.who or 'unknown'} (older — its words not shown)")
    if cut:
        lines.append(f"… and {cut} older touch(es), not shown.")
    for t in tl.upcoming:
        lines.append(f"Booked: {cite(t.event_id)} a meeting at {_when(t.at)}")
    lines.append(f"Usual gap between touches: {_says(tl.usual_gap)} {cite('num:usual_gap')}; "
                 f"longest closed gap: {_n(tl.longest_gap_days)} days {cite('num:longest_gap')}; "
                 f"quiet now: {_n(tl.days_quiet)} days {cite('num:days_quiet')}"
                 + ("" if tl.silence_exceeds_prior_gaps is None else
                    (" — longer than any gap it closed before" if tl.silence_exceeds_prior_gaps
                     else " — within the gaps it closed before")))
    lines.append("Screen activity is not part of a file's timeline, as decided.")
    return Section("timeline", "\n".join(lines), cut)


def _answers(p: DossierParts, cite: _Ids) -> Section:
    """What the founder told us, answering a question this file asked: when, on a line of its own, then the
    answer's id (the expert may cite it) and the words. Their words are no mail's — printed on the head
    line, so no claim is asked to quote them.

    ⛔ YOUR ANSWER IS YOUR WORDS (STEP-13 M36.C2.L-data.V2.U12, `03` X05). The answer's line — the item a
    fact citing `answer:<id>` is held to (`reason/expert/verify`) — carries the id and the words and NOTHING
    else. Never the question's text: a held review's question IS the claim its check dropped ("Is it so:
    “…”?"), so a line carrying it let "No. He asked for the roadmap" ground "Send Neel the deck" again.
    Never its date either: a date's digits would ground any small number, and the invention rule reads a
    date's own month and day (`platform/grounding.corpus_of`) — so the date heads the answer on a line of
    its own, which no id prints on and no fact can cite."""
    lines: list[str] = []
    for a in p.answers:
        lines.append(f"You answered on {_when(a.answered_at)}:")
        lines.append(f"- {cite(f'answer:{a.question_id}')} “{' '.join(str(a.answer).split())}”")
    return Section("answers", "\n".join(lines))


def _promises(p: DossierParts, cite: _Ids) -> Section:
    if not p.promises:
        return Section("promises", "No promise was found in its mail.", p.promises_cut)
    lines = []
    for pr in p.promises:
        who = {True: "we promised", False: "they promised"}.get(pr.ours, "a promise")
        word = pr.relative
        due = (f"no deadline — its words say “{word}”; judge from this file's own gaps whether "
               f"{word} has passed" if word else
               f"due {_when(pr.due_at)}" if pr.due_at else "no date")
        lines.append(f"- {cite('promise:' + pr.promise_id)} {who}: {pr.words} · {due} · "
                     f"{pr.status or 'open'}" + (f" · from {cite(pr.event_id)}" if pr.event_id else ""))
    if p.promises_cut:
        lines.append(f"… and {p.promises_cut} more promise(s), not shown.")
    return Section("promises", "\n".join(lines), p.promises_cut)


def _numbers(p: DossierParts, cite: _Ids) -> Section:
    nb = p.numbers
    if nb is None:
        return Section("numbers", "No numbers were read for this file.")
    people, waves = nb.people[:PEOPLE_LIMIT], nb.waves[:WAVES_LIMIT]
    cut = len(nb.people) - len(people) + len(nb.waves) - len(waves)
    lines = []
    for person in people:
        k = person.key
        lines.append(f"- {person.name or k} <{k}>")
        lines.append(f"  their reply time: {_says(person.their_reply_time)} "
                     f"{cite('num:their_reply_time:' + k)}")
        if person.their_normal is not None:
            lines.append(f"  their normal: {_says(person.their_normal)} {cite('num:their_normal:' + k)}")
        lines.append(f"  your reply time to them: {_says(person.your_reply_time)} "
                     f"{cite('num:your_reply_time:' + k)} — on every answer you sent them, not split by "
                     "who wrote first, as decided")
        if person.your_normal is not None:
            lines.append(f"  your normal with them: {_says(person.your_normal)} "
                         f"{cite('num:your_normal:' + k)}")
        if person.bounced_at is not None:
            lines.append(f"  our mail to them BOUNCED at {_when(person.bounced_at)}")
    if not people:
        lines.append("No person in this file has numbers yet.")
    if nb.your_normal_overall is not None:
        lines.append(f"Your reply time across every counterparty: {_says(nb.your_normal_overall)} "
                     f"{cite('num:your_normal_overall')}")
    for w in waves:
        lines.append(f"- {cite('wave:' + w.wave_id)} a wave “{w.line}”: sent to {_says(w.sent)}, "
                     f"replied {_says(w.reply_rate)}, bounced {_says(w.bounce_rate)}, followed up "
                     f"{_says(w.follow_up_rate)}; last sent {_n(w.days_since_last_send)} days ago")
    if cut:
        lines.append(f"… and {cut} more person(s) or wave(s), not shown.")
    return Section("numbers", "\n".join(lines), cut)


def _coverage(p: DossierParts, cite: _Ids) -> Section:
    nb = p.numbers
    if nb is None:
        return Section("coverage", "Nothing was checked.")
    lines = [f"- {m.address or m.connection_id}: reads {_n(m.window_days)} days back, from "
             f"{_when(m.window_start)}; last sync "
             + (f"completed {_when(m.last_finished_at)}" if m.last_completed else
                f"not completed (last finished {_when(m.last_finished_at)})")
             for m in nb.mailboxes] or ["No mailbox is shown to have read this file's mail."]
    # Each line says what was read, and only that (`03` F160): no absence without a mailbox that read
    # it, no "no reply" when they wrote after our last mail, and never past what a mailbox finished.
    if nb.no_reply_since is None:
        lines.append("We have not written in this file." if nb.mailboxes else
                     "Whether we wrote in this file cannot be said: no mailbox is shown to have read its "
                     "mail.")
        return Section("coverage", "\n".join(lines))
    since = nb.no_reply_since
    answered = [t for t in p.timeline.touches if t.direction == "in" and t.at > since]
    # How far EVERY mailbox that finished has read — a reply could sit in the one that read least.
    read_to = min((m.last_finished_at for m in nb.mailboxes
                   if m.last_completed and m.last_finished_at), default=None)
    if answered:
        lines.append(f"Our last mail in the file: {_when(since)} — they wrote after it "
                     f"{cite(answered[0].event_id)}, so “no reply” is not to be said.")
    elif nb.no_reply_can_be_said and read_to is not None:
        lines.append(f"Our last mail in the file: {_when(since)} — “no reply since then” may be said up to "
                     f"{_when(read_to)}: a mailbox has read that far and finished; after it, nothing was "
                     "read.")
    else:
        lines.append(f"Our last mail in the file: {_when(since)} — “no reply” may NOT be said: no mailbox "
                     "is shown to have read that far and finished since.")
    return Section("coverage", "\n".join(lines))


def _playbook(p: DossierParts, cite: _Ids) -> tuple[Section, tuple[str, ...]]:
    answer = p.playbook
    pb = getattr(answer, "playbook", None)
    if pb is None:
        reason = getattr(answer, "reason", None)
        return Section("playbook", "No playbook for this file: "
                       f"{_NO_PLAYBOOK.get(reason, reason or 'none')}."), ()
    lines = [f"{pb.name} {cite('pb:' + pb.playbook_id)}, version {pb.version} — "
             + ("reviewed by a named human" if pb.reviewed else (pb.review_label or "not reviewed"))]
    lines.append("Stages — the file's current stage is named from these only:")
    for s in pb.stages:
        lines.append(f"- {s.name} ({s.label}): typically {_says(s.typical)}, {s.cited}"
                     + (f"; quiet means: {s.quiet_means}" if s.quiet_means else "")
                     + (f"; it ends when: {s.leaves_when}" if s.leaves_when else ""))
    if pb.do_nothing_consequence:
        lines.append(f"What doing nothing costs (a prior): {pb.do_nothing_consequence}")
    if pb.success_signal:
        lines.append(f"What success looks like: {pb.success_signal}")
    if pb.outcome_window_days:
        lines.append(f"How long to wait for it: {pb.outcome_window_days} days (a prior)")
    if pb.stop is not None:
        lines.append(f"The work is dormant after this much quiet: {_says(pb.stop.dormant_after)} "
                     f"({pb.stop.cited})" + (f"; then: {pb.stop.then}" if pb.stop.then else ""))
    moves, claims = pb.moves[:MOVES_LIMIT], pb.claims[:CLAIMS_LIMIT]
    if moves:
        lines.append("Moves:")
    for m in moves:
        lines.append(f"- {cite('pb:' + m.artifact_id)} {m.name}: " + "; ".join(m.steps)
                     + (f" — success: {m.success_signal}" if m.success_signal else "")
                     + (f" — wait {m.outcome_window_days} days" if m.outcome_window_days else "")
                     + ("" if m.reviewed else " (not yet reviewed)"))
    if claims:
        lines.append("What it rests on:")
    for c in claims:
        lines.append(f"- {cite('pb:' + c.artifact_id)} {c.statement}"
                     + (f" — why: {c.why}" if c.why else "") + ("" if c.reviewed else
                                                               " (not yet reviewed)"))
    cut = len(pb.moves) - len(moves) + len(pb.claims) - len(claims)
    if cut:
        lines.append(f"… and {cut} more move(s) or claim(s), not shown.")
    return Section("playbook", "\n".join(lines), cut), tuple(s.name for s in pb.stages)


def _quiet(s) -> str:
    """A situation's quiet — or, when it was last seen at a meeting booked ahead, that (`03` F159)."""
    if s.days_since_seen is not None and s.days_since_seen < 0:
        return f"last seen at a booking {_n(-s.days_since_seen)} days ahead, so no quiet yet"
    return f"quiet {_n(s.days_since_seen)} days"


def _situations(p: DossierParts, cite: _Ids) -> Section:
    life = p.lifecycle
    lines = [f"- {cite('sit:' + s.situation_id)} {s.situation_type} ({s.domain}) · {s.status} · seen "
             f"{_when(s.first_seen_at)} → {_when(s.last_seen_at)} ({_n(s.days_seen)} days) · "
             + _quiet(s) + f" of a {s.quiet_window_days}-day window "
             f"({_WINDOW_FROM.get(s.window_from, s.window_from)})"
             + (" · PAST its window" if s.past_window else "")
             for s in life.situations] or ["No situation is anchored on this file."]
    if life.cut:
        lines.append(f"… and {life.cut} older situation(s), not shown.")
    return Section("situations", "\n".join(lines), life.cut)


def _judged_before(p: DossierParts, cite: _Ids) -> Section:
    j = p.judgments
    lines = []
    for r in j.reviews:
        lines.append(f"- {cite('review:' + r.fingerprint)} the expert's review of {_when(r.reviewed_at)}: "
                     f"{r.status}" + (f", mode {r.mode}" if r.mode else "")
                     + (f" — {r.reason}" if r.reason else ""))
    for c in j.cards:
        events = ", ".join(e.kind + (f" ({e.cause})" if e.cause else "") for e in c.events)
        verdicts = "; ".join(v.cause + (f" — {v.reason}" if v.reason else "") for v in c.verdicts)
        lines.append(f"- {cite('card:' + c.card_id)} a card “{c.headline}”, {c.state}"
                     + (f"; what happened to it: {events}" if events else "")
                     + (f"; the founder's verdict: {verdicts}" if verdicts else ""))
    for s in j.situations:
        # An outcome on a situation still open is a DECISION, not an ending (`03` F161).
        why = f" — {s.reason}" if s.reason else ""
        if s.outcome and s.status in _OPEN:
            said = f"{s.status}; last decided: {s.outcome}{why}"
        elif s.outcome:
            said = f"ended: {s.outcome}{why}"
        else:
            said = f"{s.status or 'open'}, no end recorded"
        lines.append(f"- {cite('sit:' + s.situation_id)} {s.situation_type} {said}")
    for h in j.history:
        lines.append(f"- {cite('hist:' + h.field)} {h.field} = {h.value}")
    cut = sum(j.cut.values())
    if not lines:
        lines.append("Nothing was judged about this file before.")
    if cut:
        lines.append(f"… and {cut} older item(s), not shown.")
    return Section("judged_before", "\n".join(lines), cut)


def _what_if(p: DossierParts, cite: _Ids) -> Section:
    lines = [f"- {cite(f'whatif:{w.days}')} {w.says}" for w in p.what_if] or [
        "Not measured."]
    words = next((w.do_nothing for w in p.what_if if w.do_nothing), None)
    if words:
        lines.append(f"What doing nothing costs, as its playbook says (a prior): {words}")
    return Section("what_if", "\n".join(lines))


def build_dossier(parts: DossierParts) -> Dossier:
    """The dossier from its parts — pure, the same parts the same dossier, byte for byte."""
    cite = _Ids()
    playbook, stages = _playbook(parts, cite)
    by_name = {s.name: s for s in (
        _brief(parts, cite), _file(parts, cite), _timeline(parts, cite), _promises(parts, cite),
        _numbers(parts, cite), _coverage(parts, cite), playbook, _situations(parts, cite),
        _judged_before(parts, cite), _what_if(parts, cite))}
    names = list(SECTIONS)
    if parts.answers:
        # ⛔ ONLY WHEN THERE IS ONE: a file with no answer is printed byte for byte as before (STEP-13).
        by_name["answers"] = _answers(parts, cite)
        names.insert(names.index(OPTIONAL["answers"]) + 1, "answers")
    sections = tuple(by_name[name] for name in names)
    draft = Dossier(org_id=parts.org_id, file_id=parts.file_id, as_of=parts.as_of,
                    sections=sections, catalogue=DossierCatalogue(frozenset(), frozenset()),
                    digest="")
    body = draft.text
    catalogue = DossierCatalogue(evidence_ids=frozenset(cite.seen), numbers=number_tokens(body),
                                 stages=stages)
    digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    return Dossier(org_id=parts.org_id, file_id=parts.file_id, as_of=parts.as_of,
                   sections=sections, catalogue=catalogue, digest=digest)


# ── reading ────────────────────────────────────────────────────────────────────────────────────

#: The promises made in the file's own mail: each commitment whose words an event of the file wrote,
#: with its quote, its due date, its status and its owner — the newest first, bounded, counted.
_PROMISES = text(
    "select t.subject_node_id as promise_id, t.value #>> '{}' as words, "
    "       t.created_by_event_id as event_id, "
    "       (select r.evidence ->> 'text' from graph_source_refs r "
    "         where r.org_id = t.org_id and r.fact_version_id = t.fact_version_id "
    "         order by r.created_at limit 1) as quote, "
    "       (select d.value #>> '{}' from graph_facts d where d.org_id = t.org_id "
    "           and d.subject_node_id = t.subject_node_id and d.field = 'commitment.due_at' "
    "           and d.valid_to is null limit 1) as due_at, "
    "       (select s.value #>> '{}' from graph_facts s where s.org_id = t.org_id "
    "           and s.subject_node_id = t.subject_node_id and s.field = 'commitment.status' "
    "           and s.valid_to is null limit 1) as status, "
    "       (select w.value #>> '{}' from graph_facts w where w.org_id = t.org_id "
    "           and w.subject_node_id = t.subject_node_id and w.field = 'commitment.owner' "
    "           and w.valid_to is null limit 1) as owner, "
    "       count(*) over () as total "
    "  from graph_facts t "
    " where t.org_id = :o and t.field = 'commitment.text' and t.valid_to is null "
    "   and t.visibility_scope <> 'private' and t.created_by_event_id = any(:events) "
    " order by t.occurred_at desc, t.subject_node_id limit :n")


def _instant(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        at = value
    else:
        try:
            at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def read_promises(conn, org_id: str, events: Iterable[str], *, us: Any = None,
                  limit: int = PROMISES_LIMIT) -> tuple[tuple[Promise, ...], int]:
    """The promises the file's own events wrote, newest first, at most `limit` — and how many more."""
    ids = sorted({str(e) for e in events if e})
    if not ids:
        return (), 0
    rows = conn.execute(_PROMISES, {"o": org_id, "events": ids, "n": limit}).fetchall()
    promises = tuple(Promise(
        promise_id=r.promise_id, words=" ".join(str(r.words or "").split()),
        quote=" ".join(str(r.quote).split()) if r.quote else None, due_at=_instant(r.due_at),
        status=r.status, owner=r.owner,
        ours=(bool(us.is_us(r.owner)) if us is not None and r.owner else None),
        event_id=r.event_id) for r in rows)
    return promises, max(0, int(rows[0].total) - limit) if rows else 0


def read_parts(conn, org_id: str, file_id: str, *, now: datetime) -> DossierParts | None:
    """Every part of one file's dossier, read on one connection — None for a file it does not hold."""
    from genios_engine.context.file_judgments import judgments_for
    from genios_engine.context.founder_questions import answers_for
    from genios_engine.context.workstream_numbers import numbers_for
    from genios_engine.context.workstream_timeline import timeline_for
    from genios_engine.context.workstreams import file_for, lifecycle_for
    from genios_engine.packs.compiler.playbook_reader import playbook_for
    from genios_engine.platform.company_brief import brief_for
    from genios_engine.platform.self_identity import identity_for
    from genios_engine.reason.simulation import what_if_nothing

    brief = brief_for(conn, org_id)
    work = file_for(conn, org_id, file_id, now=now, company_brief=brief)
    if work is None:
        return None
    timeline = timeline_for(conn, org_id, file_id, now=now)
    playbook = playbook_for(work.work_kind)
    lifecycle = lifecycle_for(conn, org_id, file_id, now=now)
    pb = playbook.playbook
    stop = pb.stop if pb is not None else None
    promises, promises_cut = read_promises(conn, org_id, (t.event_id for t in timeline.touches),
                                           us=identity_for(conn, org_id))
    return DossierParts(
        org_id=org_id, file_id=str(file_id), as_of=now, brief=brief, file=work, timeline=timeline,
        numbers=numbers_for(conn, org_id, work, timeline, now=now), playbook=playbook,
        judgments=judgments_for(conn, org_id, file_id, people=work.people), lifecycle=lifecycle,
        what_if=what_if_nothing(
            now=now, quiet_days=timeline.days_quiet,
            stop_after_days=(int(stop.dormant_after.value)
                             if stop is not None and stop.dormant_after.value else None),
            stop_cited=stop.cited if stop is not None else None,
            do_nothing=pb.do_nothing_consequence if pb is not None else None,
            lifecycle=lifecycle,
            next_date=timeline.upcoming[0].at if timeline.upcoming else None),
        promises=promises, promises_cut=promises_cut, answers=answers_for(conn, org_id, str(file_id)))


# ── reading it back (STEP-13) ──────────────────────────────────────────────────────────────────

#: An id as the dossier prints it: in brackets, no spaces (`_Ids`).
_PRINTED = re.compile(r"\[([^\[\]\s]+)\]")
#: A touch's words, as `_timeline` prints them under its head line.
_WORDS = re.compile(r"^\s+“(.*)”(?: … \(\d+ characters cut\))?\s*$")


@dataclass(frozen=True, slots=True)
class DossierLine:
    """One place the dossier prints an id: the line, the item it belongs to (the head line and the lines
    indented under it), and — on a touch's head line — the touch's words."""
    line: str
    item: str
    words: str | None = None


def lines_by_id(text: str, ids: Iterable[str] | None = None) -> dict[str, tuple[DossierLine, ...]]:
    """Every id `text` prints — or only those of `ids`, the dossier's own catalogue — to each place it is
    printed, in the order printed. Pure."""
    keep = None if ids is None else set(ids)
    items: list[list[str]] = []
    for line in text.splitlines():
        if line.startswith("  ") and items:
            items[-1].append(line)
        else:
            items.append([line])
    out: dict[str, list[DossierLine]] = {}
    for group in items:
        item = "\n".join(group)
        words = next((m.group(1) for line in group[1:] if (m := _WORDS.match(line))), None)
        for n, line in enumerate(group):
            for found in _PRINTED.findall(line):
                if keep is None or found in keep:
                    out.setdefault(found, []).append(
                        DossierLine(line=line.strip(), item=item, words=words if n == 0 else None))
    return {k: tuple(v) for k, v in out.items()}


@dataclass(frozen=True, slots=True)
class Person:
    name: str | None
    key: str | None                    # an address, or a company's domain


@dataclass(frozen=True, slots=True)
class FilePeople:
    """Whom a draft of this file may go to: who its mail shows, who is us, and the connector that
    introduced its counterparty (None on the connector's own file, and on a file nobody introduced)."""
    counterparty: Person
    people: tuple[Person, ...]         # the counterparty, the file's people, whoever wrote to us in it
    us: SelfIdentity
    our_names: tuple[str, ...] = ()    # the company's name and the founder's (`platform/self_identity.names_us`)
    connector: Person | None = None
    head: str = ""                     # the file's own section, as the dossier printed it


def label_of(key: str | None) -> str | None:
    """A key's own name: an address's or a domain's first label — never a public mail host's."""
    host = str(key or "").casefold().rsplit("@", 1)[-1]
    if not host or "." not in host or host in PUBLIC_MAIL_DOMAINS:
        return None
    return host.split(".", 1)[0]


def connector_of(parts: DossierParts) -> Person | None:
    """The connector that introduced the file's counterparty, NAMED AS THE PERSON it is (STEP-13
    M35.C2.L-logic.V0.U13, `03` X07) — None on the connector's own file, and on a file nobody introduced.

    An address is a person: named by the name its own mail in the file signs, else by its own words
    (`pankaj@saka.vc` is Pankaj, `pankaj.mehta@saka.vc` Pankaj Mehta) — never by its domain's label, which
    named Pankaj "saka" and let "Send Pankaj the short deck", to Pankaj Mehta, pass the connector check.
    A connector known only by its company's domain (`boardy.ai`) is named by that domain's first label, as
    before. ⛔ The graph's own node name is not read: the name the connector's mail signs is the one the
    graph took it from, and a read here would be the dossier's first of a node it does not print."""
    f = parts.file
    if not f.introduced_by or f.kind == "connector":
        return None
    key = str(f.introduced_by)
    signed = next((t.who_name for t in reversed(parts.timeline.touches)
                   if str(t.who or "").casefold() == key.casefold() and t.who_name
                   and t.who_name.casefold() != key.casefold()), None)
    if "@" not in key:
        return Person(name=signed or label_of(key), key=key)
    words = [w for w in re.split(r"[._+-]+", key.split("@", 1)[0]) if w]
    return Person(name=signed or " ".join(w[:1].upper() + w[1:].lower() for w in words) or None, key=key)


def people_of(parts: DossierParts, *, us: SelfIdentity, our_names: Iterable[str] = ()) -> FilePeople:
    """The file's people as its dossier shows them (see `FilePeople`). Pure over the parts."""
    f = parts.file
    counterparty = Person(name=f.counterparty, key=f.counterparty_key)
    seen = [counterparty]
    for person in (getattr(parts.numbers, "people", None) or ()):
        seen.append(Person(name=person.name, key=person.key))
    for t in parts.timeline.touches:
        if t.direction == "in" and (t.who or t.who_name):
            seen.append(Person(name=t.who_name, key=t.who))
    people = tuple(dict.fromkeys(seen))
    return FilePeople(counterparty=counterparty, people=people, us=us,
                      our_names=tuple(n for n in our_names if n), connector=connector_of(parts),
                      head=_file(parts, _Ids()).text)


def dossier_for(conn, org_id: str, file_id: str, *, now: datetime) -> Dossier | None:
    """The dossier the expert is shown for one file, or None for a file the tenant does not hold."""
    parts = read_parts(conn, org_id, file_id, now=now)
    return build_dossier(parts) if parts is not None else None


__all__ = ["CLAIMS_LIMIT", "DOSSIER_CHARS", "DOSSIER_VERSION", "Dossier", "DossierLine", "DossierParts",
           "FilePeople", "MOVES_LIMIT", "PEOPLE_LIMIT", "PROMISES_LIMIT", "Person", "Promise",
           "OPTIONAL", "RELATIVE_WORDS", "SECTIONS", "Section", "TITLES", "TOUCHES_LISTED", "TOUCHES_WHOLE",
           "WAVES_LIMIT", "build_dossier", "connector_of", "dossier_for", "label_of", "lines_by_id", "people_of",
           "read_parts", "read_promises"]
