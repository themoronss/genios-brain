"""GeniOS-008 L2 · the run's input, as the six labelled blocks of the spec (§4, `02-PLAN.md` §4 A-F).

  A  THE SIGNALS      what L1 published for this subject this sweep, every carried field (E8), and the
                      mail's own words under each, so a fact can QUOTE them and the check can hold it;
  B  THE CONTEXT      the bounded snapshot (R2): nodes and edges around the seeds, its revision, its cap;
  C  THE HISTORY      comparable past work of the same kind (R3), each a `case:` id;
  D  THE EXPERTISE    for a file, the STEP-12 dossier WHOLE — brief, file, timeline, promises, numbers with
                      their n, what was checked, the playbook, its situations, what was judged before, what
                      doing nothing does; for a seed, the company brief (no kind of work, so no playbook);
  E  THE TOOLS        the tool results (R7), each a `tool:` id with its number;
  F  THE COVERAGE     per source, what was read and what was not; the snapshot's cap; what L1 could not settle.

⛔ THE FILE DOSSIER IS REUSED, NEVER REWRITTEN. Its ids (`ev:`, `loop:`, `pb:`, `sit:`, …), its quotes and
its numbers are what the STEP-13 check already knows how to hold. Every id this module prints is added to
the same catalogue, and the catalogue's numbers are read off the WHOLE text, so a number the model repeats
from any block is a number the dossier holds.

Pure: the same parts, the same dossier, byte for byte.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from genios_engine.contracts.expert_review import DossierCatalogue, number_tokens
from genios_engine.contracts.reasoning_result import HistoricalContext

from .inputs import Subject
from .snapshot import Snapshot
from .tools import ToolResult

L2_DOSSIER_VERSION = "l2-dossier.v5"        # v5: a waiting goal is no file's (H-22); v4: waiting goals printed with ids
#                                             (G012 H-19); v3: who you work for
#                                             (G012 H-14); v2: block G, the goals (S29.U1)

TITLES = {"A": "A · THE SIGNALS — what arrived for this subject", "B": "B · THE CONTEXT — what the company knows around it",
          "C": "C · THE HISTORY — comparable past work, and how it went",
          "D": "D · THE EXPERTISE AND THE FILE", "E": "E · THE TOOLS — numbers code computed",
          "F": "F · THE COVERAGE — what was read, and what was not",
          "G": "G · THE GOALS — what the company works toward"}


@dataclass(frozen=True, slots=True)
class L2Dossier:
    org_id: str
    subject_ref: str
    as_of: datetime
    text: str
    catalogue: DossierCatalogue
    digest: str
    version: str = L2_DOSSIER_VERSION

    @property
    def file_id(self) -> str:
        """The name `reason/expert` code reads a dossier's subject by."""
        return self.subject_ref


def _when(at: datetime | None) -> str:
    if at is None:
        return "unknown"
    at = at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)
    return at.strftime("%Y-%m-%d %H:%M UTC")


class _Cite:
    def __init__(self) -> None:
        self.seen: set[str] = set()

    def __call__(self, ref: str) -> str:
        self.seen.add(ref)
        return f"[{ref}]"


def _signals(subject: Subject, cite: _Cite) -> str:
    lines = []
    for s in subject.signals:
        bits = [s.signal_type]
        if s.sender:
            bits.append(f"from {s.sender}")
        if s.direction:
            bits.append(s.direction)
        if s.ball_in_court and s.ball_in_court != "unknown":
            bits.append(f"turn with: {s.ball_in_court}")
        bits.append(_when(s.occurred_at))
        if s.due_at is not None:
            bits.append(f"due {_when(s.due_at)}")
        if s.thread_key:
            bits.append(f"thread {s.thread_key}")
        if s.state and s.state != "active":
            bits.append(s.state)
        lines.append(f"- {cite('sig:' + s.signal_id)} {cite(s.event_id)} " + " · ".join(bits))
        for quote in s.quotes:
            lines.append(f"  “{quote}”")
    return "\n".join(lines) or "Nothing arrived."


def _context(snapshot: Snapshot, cite: _Cite) -> str:
    if not snapshot.nodes:
        return "No node of the company's memory was found around this subject."
    seeds = set(snapshot.seeds)
    lines = [f"Read at {snapshot.ref}, from {len(snapshot.seeds)} seed(s)."]
    for n in snapshot.nodes:
        lines.append(f"- {cite('node:' + n.node_id)} {n.node_type} · {n.name or '(no name)'}"
                     + (" · the subject" if n.node_id in seeds else ""))
    for edge_type, a, b in snapshot.edges:
        lines.append(f"- {cite('node:' + a)} —{edge_type}→ {cite('node:' + b)}")
    if snapshot.truncated:
        lines.append(f"⛔ The read was CAPPED ({snapshot.truncated_by}): there may be more. Never say something is "
                     "absent because it is not here.")
    return "\n".join(lines)


def _history(history: HistoricalContext, cite: _Cite) -> str:
    if not history.cases:
        return "No comparable past work of this kind is on record."
    lines = []
    for c in history.cases:
        lines.append(f"- {cite(c.case_id)} {c.subject} ({c.work_kind or 'no kind'}) — {c.summary}"
                     + (f"; it ended: {c.outcome}" if c.outcome else "; it has not ended"))
    return "\n".join(lines)


def _tools(tools: Sequence[ToolResult], cite: _Cite) -> str:
    return "\n".join(f"- {cite(t.tool_id)} {t.says}" for t in tools) or "No tool had anything to compute."


def _conflicts(subject: Subject, cite: _Cite) -> list[str]:
    """L2 audit · each open L1 disagreement this subject rests on — both sides by their own words, no winner."""
    lines = []
    for c in subject.conflicts:
        sides = " vs ".join(f"“{q}”" for q in c.quotes) or "both sides kept, no words to show"
        lines.append(f"- L1 found sources that disagree on {c.field} and did not settle it {cite(c.conflict_id)}: "
                     f"{sides} — in {', '.join(cite(e) for e in c.event_ids) or 'no event named'}")
    return lines


def _coverage(subject: Subject, snapshot: Snapshot, cite: _Cite | None = None) -> str:
    lines = []
    for cov in subject.coverage:
        for src in cov.get("sources", ()) or ():
            if not isinstance(src, Mapping):
                continue
            done = src.get("completeness_bp")
            lines.append(f"- {src.get('source', 'a source')}: "
                         + (f"{done} bp of it read" if done is not None else "how much was read is NOT known")
                         + (f", window {cov.get('window_from')} → {cov.get('window_to')}"
                            if cov.get("window_from") or cov.get("window_to") else ""))
    if not lines:
        lines.append("- No source said how much of it was read: a negative claim (\"nobody replied\") is not licensed.")
    if cite is not None:
        lines.extend(_conflicts(subject, cite))
    if snapshot.truncated:
        lines.append(f"- The context read was capped ({snapshot.truncated_by}).")
    for u in subject.unresolved:
        lines.append(f"- L1 could not settle: {u}")
    return "\n".join(lines)


def _goals(goals: Sequence[Any], proposals: Sequence[Any], cite: _Cite) -> str:
    """Block G (GeniOS-012 S29.U1): the goals a human made real, each with the id a move cites — and, apart, the
    proposals still waiting for the founder, so the work they name is not proposed again and none is ever taken for
    the company's goal.

    G012 H-19 · a waiting goal is printed WITH its id, so a move may say it serves one: printed with none, 262
    judgments on the design partner's org (24 Oct) wrote 0 impacts — every goal was still waiting — and "Raise the
    pre-seed round" rested on one investor's file alone. What a move says of a waiting goal is kept as the work that
    serves it (`context/goals.cover_work`); it reaches a card only once a human makes the goal real."""
    lines = [f"- {cite(g.ref)} {g.statement}" for g in goals]
    if not lines:
        lines = ["No goal is approved for this company yet."]
    if proposals:
        lines.append("Waiting for the founder — NOT the company's goals yet: a move may say it serves one, never that it "
                     "is the company's goal:")
        # G012 H-22 · no "(proposed for <file>)": printed with it, the model read a waiting goal as another file's and
        # called 22 of 23 of its moves' bearing on one "unclear" (24 Oct). A goal is the company's, whichever file first
        # proposed it.
        lines += [f"- {cite(p.ref)} {p.statement}" for p in proposals]
    return "\n".join(lines)


def works_for_line(name: str | None, company: str | None, addresses=()) -> str | None:
    """G012 H-14 · WHO THE MODEL WORKS FOR, said once in the head. The L2 pass read `us` and the org's names and never
    printed them: with no company brief accepted, no line of any block said who the founder is — and on the design
    partner's org (24 Oct) goals came back from the other side of the table ("applicants we decline", "we are
    supporting <a fellow cohort startup> through the accelerator", "the question we owe <the founder himself>")."""
    who = " ".join(str(name or company or "").split())
    if not who:
        return None
    of = f" of {company}" if company and company != who else ""
    reach = ", ".join(sorted(a for a in addresses if a)[:4])
    return (f"YOU WORK FOR {who}{of}" + (f" ({reach})" if reach else "") + ". \"We\", \"us\" and \"our\" are them: a "
            "mail they sent is the company's own act, and they are never the counterparty of a file.")


def build_l2_dossier(*, org_id: str, subject: Subject, as_of: datetime, snapshot: Snapshot,
                     history: HistoricalContext, tools: Sequence[ToolResult], file_dossier: Any = None,
                     brief_block: str | None = None, depth_note: str | None = None,
                     goals: Sequence[Any] = (), goal_proposals: Sequence[Any] = (),
                     works_for: str | None = None) -> L2Dossier:
    """The seven blocks, in order. `file_dossier` is the STEP-12 `Dossier` for a file subject (its text and
    catalogue are kept whole); a seed subject passes `brief_block` instead. `goals` are the live goals
    (`context/goals.live_goals`), `goal_proposals` the pending ones."""
    cite = _Cite()
    blocks = {"A": _signals(subject, cite), "B": _context(snapshot, cite), "C": _history(history, cite)}
    if file_dossier is not None:
        blocks["D"] = file_dossier.text
    else:
        blocks["D"] = "## THE COMPANY BRIEF\n" + (brief_block or "No company brief is accepted for this tenant.") \
            + "\n\nNo file holds this subject, so no kind of work and no playbook: judge from the brief, the signals " \
              "and the context."
    blocks["E"] = _tools(tools, cite)
    blocks["F"] = _coverage(subject, snapshot, cite)
    blocks["G"] = _goals(goals, goal_proposals, cite)
    head = f"L2 DOSSIER {L2_DOSSIER_VERSION} — subject {subject.subject_ref}, as of {_when(as_of)}"
    if works_for:
        head += f"\n{works_for}"
    if depth_note:
        head += f"\n{depth_note}"
    text = "\n\n".join([head, *(f"# {TITLES[k]}\n{blocks[k]}" for k in ("A", "B", "C", "D", "E", "F", "G"))])
    ids = set(cite.seen)
    stages: tuple[str, ...] = ()
    if file_dossier is not None:
        ids |= set(file_dossier.catalogue.evidence_ids)
        stages = tuple(file_dossier.catalogue.stages)
    catalogue = DossierCatalogue(evidence_ids=frozenset(ids), numbers=number_tokens(text), stages=stages)
    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    return L2Dossier(org_id=org_id, subject_ref=subject.subject_ref, as_of=as_of, text=text,
                     catalogue=catalogue, digest=digest)


__all__ = ["L2Dossier", "L2_DOSSIER_VERSION", "TITLES", "build_l2_dossier", "works_for_line"]
