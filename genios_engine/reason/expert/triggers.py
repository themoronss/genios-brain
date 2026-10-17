"""What made the expert look at a file again — and a file nothing touched is not looked at (STEP-12).

`speedrun008/YC-II W27/05` §5, tree `yc2_w27_s12` M32.C3.L-logic.V1.U09. The expert reviews a file only
when something in it changed:

  first_look       it was never judged — or what it was then was not kept (a row from before 0198);
  new_evidence     a mail, a meeting or a booking the last review did not see — and a meeting it saw
                   booked that has since been held;
  date_closing_in  the next meeting, or the nearest promised date, moved a rung closer;
  reply_overdue    their move, and since the last review the quiet has passed the time they usually
                   take to reply in this file;
  past_normal      since the last review a number crossed what is normal for the file: the quiet has
                   passed the longest gap it ever had — or, our move, the time we usually take;
  founder_asked    the founder asked about it;
  founder_corrected  you said something about it the last review did not see (STEP-16, `05` §5's "you ask about
                   it" given its door): a correction of the file or of its kind of work — so a correction for a
                   kind brings EVERY file of the kind back, nearest deadline first under the day's cap and
                   `MAX_PER_PASS` (S16-D3) — or a `wrong` you pressed on a card of the file (S16-D2), that file only.

  engine_moved     the engine the file reads moved since the last review (STEP-13b, `06` D48 as Rohit answered it —
                   the dossier changed, so the file is thought again; only the files whose engine lines moved): its
                   route key, the learned brains' snapshot for its subjects, or the units' roster. A review stored
                   before the engine was named saw none, and a file that reads one now has moved;
  self_moved       a file whose last review ASKED a question (held, or a find-out review that asked its own) and the
                   company's record has a line since it was asked (F52) — what the company has said of itself
                   elsewhere may answer it.

SINCE THE LAST REVIEW is a diff against what that review SAW — the fingerprint's inputs it kept
(`expert_reviews.inputs`, 0198) on the file's latest STANDING row (`store.latest_standing`) — never a
cut by time: mail that arrives late, or joins the file after it was read, is new to the expert all the
same. A crossing is read on the file's own clock: the quiet then is the quiet now less the time since.

WHAT IS NOT A TRIGGER. The brief's and the playbook's versions, the verdicts on its people's cards — but a
`wrong` (STEP-16, above) — and who decides are in the fingerprint — what a review stood on — and moving one of
them ALONE re-thinks nothing: it rides along with the next trigger. Taking a card (`run_play`, `do_it_myself`)
is no trigger: the work you then do reaches the file as evidence. That is `06` D48's default for the prompt (the decision
is open; its default "waits for inputs"), applied alike to all four; a founder who wants a file looked
at again asks. Time passing is no trigger either, unless it crosses one of the file's own patterns.

Pure: the file's parts, its inputs now, the last review, and whether the founder asked.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from genios_engine.contracts.claim_check import HELD

from .dossier import DossierParts

FIRST_LOOK = "first_look"
NEW_EVIDENCE = "new_evidence"
DATE_CLOSING_IN = "date_closing_in"
REPLY_OVERDUE = "reply_overdue"
PAST_NORMAL = "past_normal"
FOUNDER_ASKED = "founder_asked"
FOUNDER_CORRECTED = "founder_corrected"
ENGINE_MOVED = "engine_moved"
SELF_MOVED = "self_moved"
KINDS: tuple[str, ...] = (FIRST_LOOK, NEW_EVIDENCE, DATE_CLOSING_IN, REPLY_OVERDUE, PAST_NORMAL,
                          FOUNDER_ASKED, FOUNDER_CORRECTED, ENGINE_MOVED, SELF_MOVED)
#: What a fingerprint names when a file reads no engine line and the company's record has none for it
#: (`reason/expert/fingerprint.NONE`) — and what a review stored before they were named is read as having seen.
NONE = "none"

#: The dates that close in — the fingerprint's rungs — and how a trigger names each.
DATES: Mapping[str, str] = {"next_meeting": "the next meeting", "due": "the nearest promised date"}

#: The most new evidence ids a trigger lists; the rest it counts.
LISTED = 10


@dataclass(frozen=True, slots=True)
class Trigger:
    kind: str
    says: str


def _n(days: float) -> str:
    return f"{days:g}" if days != int(days) else str(int(days))


def _hours(rung: str | None) -> float:
    """A rung of `fingerprint.HOURS_UNTIL` as the hours it bounds — `<=72` is 72, `>2160` lies beyond
    2160, and no date at all is never close."""
    if not rung:
        return math.inf
    return float(rung[2:]) if rung.startswith("<=") else float(rung[1:]) + 0.5


def _ids(values: Any) -> set[str]:
    return {str(v) for v in (values or ())}


def _new_evidence(now: Mapping[str, Any], then: Mapping[str, Any]) -> list[Trigger]:
    out = []
    held = sorted(_ids(then.get("booked")) & _ids(now.get("events")))
    if held:
        out.append(Trigger(NEW_EVIDENCE, "held since the last review, which saw it booked: "
                           + ", ".join(held)))
    # The founder's answers are evidence like a mail (STEP-13 M36.C2.L-data.V2.U07): one the last review
    # did not see brings the file back, with the answer in front of the expert.
    fresh = sorted((_ids(now.get("events")) | _ids(now.get("booked")) | _ids(now.get("answers")))
                   - _ids(then.get("events")) - _ids(then.get("booked")) - _ids(then.get("answers")))
    if fresh:
        more = len(fresh) - LISTED
        out.append(Trigger(NEW_EVIDENCE, "new since the last review: " + ", ".join(fresh[:LISTED])
                           + (f" and {more} more" if more > 0 else "")))
    return out


def _corrected(now: Mapping[str, Any], then: Mapping[str, Any]) -> list[Trigger]:
    """What you said since the last review (STEP-16, `yc2_w27_s16` M46.C4.L-logic.V4.U05): a correction it did not see
    — the file's own or its kind's, by the id the dossier prints — and a `wrong` on a card of the file."""
    out = []
    fresh = sorted(_ids(now.get("corrections")) - _ids(then.get("corrections")))
    if fresh:
        more = len(fresh) - LISTED
        out.append(Trigger(FOUNDER_CORRECTED, "you corrected it since the last review: " + ", ".join(fresh[:LISTED])
                           + (f" and {more} more" if more > 0 else "")))
    seen = {tuple(v) for v in (then.get("verdicts") or ())}
    wrong = sorted(f"card:{v[0]} ({v[2]})" if v[2] else f"card:{v[0]}" for v in (now.get("verdicts") or ())
                   if tuple(v) not in seen and len(v) == 3 and v[1] == "wrong")
    if wrong:
        out.append(Trigger(FOUNDER_CORRECTED, "you called its card wrong: " + ", ".join(wrong)))
    return out


def _engine_parts(value: Any) -> dict[str, str]:
    """The engine a fingerprint names, as route · learned · units — `none` for a file that read no engine line."""
    seen = value if isinstance(value, Mapping) else {}
    return {key: str(seen.get(key) or NONE) for key in ("route", "learned", "units")}


def _engine_moved(now: Mapping[str, Any], then: Mapping[str, Any]) -> list[Trigger]:
    """The engine the file reads moved (STEP-13b): what changed, from what to what."""
    after, before = _engine_parts(now.get("engine")), _engine_parts(then.get("engine"))
    moved = [f"{key} {before[key]} → {after[key]}" for key in ("route", "learned", "units")
             if after[key] != before[key]]
    return [Trigger(ENGINE_MOVED, "the engine it reads moved since the last review: " + "; ".join(moved))] \
        if moved else []


def _asked(last: Any) -> bool:
    """Did the last review ask a question — held, or a find-out review that asked its own?"""
    checked = getattr(last, "checked", None)
    if checked is None:
        return False
    review = getattr(last, "review", None)
    return checked.fate == HELD or (getattr(review, "mode", None) == "find_out" and bool(checked.question))


def _self_moved(now: Mapping[str, Any], then: Mapping[str, Any], last: Any) -> list[Trigger]:
    """The company has spoken since a question was asked (STEP-13b, F52): a line of its record the last review did
    not see, on a file that asked."""
    said = str(now.get("self") or NONE)
    if said == NONE or said == str(then.get("self") or NONE) or not _asked(last):
        return []
    return [Trigger(SELF_MOVED, f"the company has spoken since it asked: {said}")]


def _closing_in(now: Mapping[str, Any], then: Mapping[str, Any]) -> list[Trigger]:
    return [Trigger(DATE_CLOSING_IN, f"{name}: {then.get(key) or 'none'} → {now.get(key)}")
            for key, name in DATES.items() if _hours(now.get(key)) < _hours(then.get(key))]


def _measured(values) -> float | None:
    found = [m.value for m in values if m is not None and m.n > 0 and m.value is not None]
    return max(found) if found else None


def their_usual(parts: DossierParts) -> float | None:
    """The longest any of the file's people usually take to reply, measured in this file — else the
    file's usual gap — in days; None when the file has no pattern yet."""
    people = parts.numbers.people if parts.numbers is not None else ()
    measured = _measured(p.their_reply_time for p in people)
    if measured is not None:
        return measured
    gap = parts.timeline.usual_gap
    return gap.value if gap is not None and gap.n > 0 else None


def our_usual(parts: DossierParts) -> float | None:
    """The longest we usually take to answer the file's people, measured here — else our normal across
    every counterparty — in days; None when there is none."""
    nb = parts.numbers
    if nb is None:
        return None
    measured = _measured(p.your_reply_time for p in nb.people)
    if measured is not None:
        return measured
    overall = nb.your_normal_overall
    return overall.value if overall is not None and overall.n > 0 else None


def _crossings(parts: DossierParts, now: Mapping[str, Any], then: Mapping[str, Any],
               since_days: float) -> list[Trigger]:
    quiet = parts.timeline.days_quiet
    if quiet is None:
        return []
    quiet_then = quiet - since_days
    out = []
    usual = their_usual(parts)
    if (usual is not None and now.get("whose_move") == "theirs" and quiet > usual
            and not (then.get("whose_move") == "theirs" and quiet_then > usual)):
        # The words name the basis (`03` F163): the file's usual gap may be OUR answer's.
        measured = _measured(p.their_reply_time for p in
                             (parts.numbers.people if parts.numbers is not None else ()))
        basis = (f"the {_n(usual)} days they usually take" if measured is not None
                 else f"the file's usual gap of {_n(usual)} days")
        out.append(Trigger(REPLY_OVERDUE, f"their move, quiet {_n(quiet)} days — past {basis}"))
    longest = parts.timeline.longest_gap_days
    if longest is not None and quiet > longest and not quiet_then > longest:
        out.append(Trigger(PAST_NORMAL, f"quiet {_n(quiet)} days — past the longest gap it ever had, "
                           f"{_n(longest)} days"))
    ours = our_usual(parts)
    if (ours is not None and now.get("whose_move") == "ours" and quiet > ours
            and not (then.get("whose_move") == "ours" and quiet_then > ours)):
        out.append(Trigger(PAST_NORMAL, f"our move, quiet {_n(quiet)} days — past the {_n(ours)} "
                           "days we usually take"))
    return out


def triggers_for(parts: DossierParts, inputs: Mapping[str, Any], *, last: Any = None,
                 asked: bool = False) -> tuple[Trigger, ...]:
    """What touched the file since `last` — the latest standing review (`store.StoredReview`, or any
    object with its `inputs` and `reviewed_at`) — or `()`: a file nothing touched is not reviewed."""
    then = getattr(last, "inputs", None)
    out: list[Trigger] = []
    if then is None:
        out.append(Trigger(FIRST_LOOK, "never judged" if last is None
                           else "what it was when last judged was not kept"))
    else:
        since = (parts.as_of - last.reviewed_at).total_seconds() / 86400
        out += _new_evidence(inputs, then)
        out += _corrected(inputs, then)
        out += _closing_in(inputs, then)
        out += _crossings(parts, inputs, then, since)
        out += _engine_moved(inputs, then)
        out += _self_moved(inputs, then, last)
    if asked:
        out.append(Trigger(FOUNDER_ASKED, "the founder asked about it"))
    return tuple(out)


__all__ = ["DATE_CLOSING_IN", "DATES", "ENGINE_MOVED", "FIRST_LOOK", "NONE", "SELF_MOVED", "FOUNDER_ASKED", "FOUNDER_CORRECTED", "KINDS", "LISTED",
           "NEW_EVIDENCE",
           "PAST_NORMAL", "REPLY_OVERDUE", "Trigger", "our_usual", "their_usual", "triggers_for"]
