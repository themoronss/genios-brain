"""A file's fingerprint — what must move before the expert thinks about the file again (STEP-12 §8.4 item 3).

Tree `yc2_w27_s12` M32.C2.L-logic.V2.U05. The expert reviews a file once per fingerprint (`expert_reviews`
is keyed on it), so this decides when it thinks again — and when it costs nothing. Its inputs, read
off the dossier's parts (`reason/expert/dossier.DossierParts`):

  * the file's EVENTS — every touch, and every meeting booked — so a new mail is a new file;
  * its open ASKS, and WHOSE MOVE it is;
  * how long it has been QUIET, as a rung of `reason/fingerprint.DAY_LADDER` (STEP-02's rule: a wait
    crossing from 6 to 7 days re-thinks, fifteen minutes never does);
  * how soon its NEXT MEETING is, as a rung of `HOURS_UNTIL` — the urgency ladder's, with a 72-hour
    rung added, so a meeting moving from four days away to three re-thinks it;
  * how soon its nearest DEADLINE is — the due date of a promise still open in its own mail, ours or
    theirs — on the same ladder (M32.C2.L-logic.V2.U09): `05` §5's "a date comes close — a deadline, a
    meeting, a promised reply". A *"soon"* is no deadline (`06` D56) and a promise kept is owed no more;
    past due is a rung of its own. Read off the promises the dossier shows (`PROMISES_LIMIT`);
  * the BRIEF's version (STEP-07) and the PLAYBOOK's (`KindPlaybook.version`), or why it has none;
  * the founder's VERDICTS on the cards about its people — what they did with what was said;
  * WHO DECIDES: the model, the prompt version (`06` D48) and the dossier's version.

NEVER AN INSTANT, AND NEVER ITS OWN OUTPUT. A clock is read as a rung, so the same file read later is
the same file until a rung is crossed. The expert's own past reviews, the cards built and what happened
to them are outputs, not inputs: a review must never be the reason for the next one.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from genios_engine.platform.canonical import semantic_hash

from ..fingerprint import DAY_LADDER
from .dossier import DOSSIER_VERSION, DossierParts

#: Hours until the next meeting: the urgency ladder's rungs (`timeline_unit.URGENCY_LADDER`) with 72
#: added — four days away and three days away are different files.
HOURS_UNTIL: tuple[int, ...] = (0, 48, 72, 168, 336, 720, 2160)

#: A promise is still owed while its `commitment.status` says so — and one with no status is open.
OWED: tuple[str, ...] = ("", "open")


def _at_least(value: float | None, ladder: tuple[int, ...] = DAY_LADDER) -> str | None:
    """Elapsed days as the rung reached — `>=7` — as `reason/fingerprint` reads a wait."""
    if value is None:
        return None
    reached = [step for step in ladder if value >= step]
    return f">={reached[-1]}" if reached else f"<{ladder[0]}"


def _within(hours: float | None) -> str | None:
    """Hours until a moment as the smallest rung it is within — `<=72` — or beyond the last."""
    if hours is None:
        return None
    for bound in HOURS_UNTIL:
        if hours <= bound:
            return f"<={bound}"
    return f">{HOURS_UNTIL[-1]}"


def nearest_due(parts: DossierParts) -> datetime | None:
    """The nearest due date of a promise still owed in the file's own mail — ours or theirs — or None.
    A *"soon"* is never a deadline (`06` D56), even where a date was read beside it."""
    dues = [p.due_at for p in parts.promises
            if p.due_at is not None and p.relative is None
            and (p.status or "").strip().lower() in OWED]
    return min(dues) if dues else None


def fingerprint_inputs(parts: DossierParts, *, model: str, prompt_version: str) -> dict[str, Any]:
    """What the fingerprint is made of, readable — every clock a rung, nothing the expert wrote."""
    tl, work = parts.timeline, parts.file
    upcoming = sorted(tl.upcoming, key=lambda t: (t.at, t.event_id))
    next_meeting = ((upcoming[0].at - parts.as_of).total_seconds() / 3600) if upcoming else None
    due = nearest_due(parts)
    answer = parts.playbook
    pb = getattr(answer, "playbook", None)
    return {
        "file_id": parts.file_id,
        "events": sorted(t.event_id for t in tl.touches),
        "booked": sorted(t.event_id for t in upcoming),
        "asks": sorted([a.loop_id, a.kind, a.owed_by] for a in work.open_asks),
        "whose_move": work.whose_move,
        "quiet": _at_least(tl.days_quiet),
        "next_meeting": _within(next_meeting),
        "due": _within((due - parts.as_of).total_seconds() / 3600 if due is not None else None),
        "brief": getattr(parts.brief, "version", None) or None,
        "playbook": pb.version if pb is not None else f"none:{getattr(answer, 'reason', None)}",
        "verdicts": sorted([c.card_id, v.cause, v.reason or ""]
                           for c in parts.judgments.cards for v in c.verdicts),
        "who_decides": {"model": model, "prompt_version": prompt_version,
                        "dossier_version": DOSSIER_VERSION},
    }


def file_fingerprint(parts: DossierParts, *, model: str, prompt_version: str) -> str:
    """`ffp-` and 24 hex of the canonical hash of `fingerprint_inputs`."""
    inputs = fingerprint_inputs(parts, model=model, prompt_version=prompt_version)
    return "ffp-" + semantic_hash(inputs)[:24]


__all__ = ["HOURS_UNTIL", "OWED", "file_fingerprint", "fingerprint_inputs", "nearest_due"]
