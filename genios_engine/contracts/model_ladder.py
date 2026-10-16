"""The ladder's rule — when the expert's answer is final, when it is repaired, when it climbs (STEP-13b).

`speedrun008/YC-II W27/` STEP-13b §8.4 item 5, tree `yc2_w27_s13b` M38.C1.L-contract.V2.U01. Rohit, 12 Oct: *"in case
opus is needed … jarurat kam pade costly models ki"* — the cheapest model asks first, and a stronger one is asked only
when a cheaper one's answer fails the check for the WRITER's own fault. This is that rule, pure: a rung's consults in,
what to do next out. The mechanism that asks the models is `reason/expert/ladder`; the rungs and their prices are
`reason/bundle/sites` and `budget`. **"Climb", never "escalate"** — the executive's escalation ladder owns that word
(`executive/reminder.py`).

AN ANSWER IS FINAL when its check SHOWS it, SUPPRESSES it (the ask it answers is answered), or HOLDS it for the file's
own state — an ask answered but another still waiting on the founder, the founder's own answer to confirm, a correction
of his to heed, a card he called wrong. A stronger model would hold it for the same reason: climbing would only spend.
A find-out review asking its own question is SHOWN. A day spent mid-climb (`over_budget`) is no fault of the writer and
stops the climb: the file is carried (`06` D7).

AN ANSWER FAILS for the writer's faults only (`CLIMB_REASONS`, the table's closed list): malformed after its repair; cut
at the ceiling; refused (nothing stands); held because a fact the move rests on dropped — uncited, unknown_evidence,
unquoted, misquoted, unsupported, wrong_number, or resting only on the engine (`engine_is_no_fact`); the headline failing;
the move addressed to us or to the connector.

A FAILED ANSWER IS REPAIRED ONCE on its own rung, handed the check's verdicts (`complaint`: the lines dropped and why —
crosscheck X32, s13b-D4), and CLIMBS only when the repaired answer still fails. A cut answer is never repaired at the same
ceiling — it would only be cut again (`03` F140). At most two consults a rung. Off the top rung, `EXHAUSTED`: when every
rung failed the BEST FATE stands (`best_of`: shown > suppressed > held > refused; on a tie, the higher rung).

Pure and frozen: no I/O, no clock, no model.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from . import claim_check as C

#: The ladder's own version — what a file's fingerprint names instead of any model (`reason/expert/fingerprint`): a
#: climb to another rung never re-keys a file, a change of rule does.
LADDER_VERSION = "ladder.v1"

# ── why an answer climbed — closed; the attempts table (0250) admits exactly these ─────────────
MALFORMED = "malformed"
TRUNCATED = "truncated"
NOTHING_STANDS = "nothing_stands"
HEADLINE_FAILED = "headline_failed"
RECIPIENT_IS_US = "recipient_is_us"
RECIPIENT_IS_CONNECTOR = "recipient_is_connector"
CLIMB_REASONS: tuple[str, ...] = (MALFORMED, TRUNCATED, NOTHING_STANDS, C.UNCITED, C.UNKNOWN_EVIDENCE, C.UNQUOTED,
                                  C.MISQUOTED, C.UNSUPPORTED, C.WRONG_NUMBER, C.ENGINE_IS_NO_FACT, HEADLINE_FAILED,
                                  RECIPIENT_IS_US, RECIPIENT_IS_CONNECTOR)

#: A fact the move rests on dropped for one of these: the writer cited, quoted, named or counted wrongly.
FACT_FAULTS: frozenset[str] = frozenset({C.UNCITED, C.UNKNOWN_EVIDENCE, C.UNQUOTED, C.MISQUOTED, C.UNSUPPORTED,
                                         C.WRONG_NUMBER, C.ENGINE_IS_NO_FACT})
#: A move held for the FILE's own state, not for how it was written: a stronger model is held for the same reason.
STATE_REASONS: frozenset[str] = frozenset({C.ANSWERED, C.ON_YOUR_ANSWER, C.DECLINED_BY_YOU, C.CORRECTION_UNHEEDED,
                                           C.CALLED_WRONG, C.NOT_OURS_TO_ANSWER})
#: The check's fates, best first — what stands when every rung failed.
FATE_ORDER: tuple[str, ...] = (C.SHOWN, C.SUPPRESSED, C.HELD, C.REFUSED)

# ── what to do next ────────────────────────────────────────────────────────────────────────────
FINAL = "final"              # the answer stands
REPAIR = "repair"            # ask again on this rung with the check's verdicts
CLIMB = "climb"              # ask the next rung
EXHAUSTED = "exhausted"      # off the top rung: the best fate stands
CARRIED = "carried"          # the day is spent: the file is carried, said
STEPS: tuple[str, ...] = (FINAL, REPAIR, CLIMB, EXHAUSTED, CARRIED)

STATUSES: tuple[str, ...] = ("valid", "refused", "truncated", "over_budget", "failed")


def _fact_line(line: str) -> tuple[int, int] | None:
    kind, _, n = line.partition(":")
    return (int(n), 0 if kind == "fact" else 1) if kind in ("fact", "quote") and n.isdigit() else None


def writer_fault(status: str, checked: C.CheckedReview | None) -> str | None:
    """The writer's fault in a consult's answer — one of `CLIMB_REASONS` — or None when the answer is final (or
    no fault of the writer's, as a day spent). Raises on a status the table does not have, or `valid` with no check:
    a consult that parsed was checked."""
    if status not in STATUSES:
        raise ValueError(f"a consult's status is one of {STATUSES}, not {status!r}")
    if status == "over_budget":
        return None
    if status == "truncated":
        return TRUNCATED
    if status in ("refused", "failed"):
        return MALFORMED
    if checked is None:
        raise ValueError("a valid answer was checked: the ladder reads its check")
    if checked.fate in (C.SHOWN, C.SUPPRESSED):
        return None
    if checked.fate == C.REFUSED:
        return NOTHING_STANDS
    dropped = [(v.line, v.reason) for v in checked.verdicts if v.verdict == C.DROPPED]
    if any(reason in STATE_REASONS for _line, reason in dropped):
        return None                                  # held for the file's own state: a stronger model is held too
    for line, reason in dropped:
        if line == "to" and reason == C.RECIPIENT_IS_US:
            return RECIPIENT_IS_US
        if line == "to" and reason == C.RECIPIENT_IS_CONNECTOR:
            return RECIPIENT_IS_CONNECTOR
    facts = sorted((key, reason) for line, reason in dropped
                   if (key := _fact_line(line)) is not None and reason in FACT_FAULTS)
    if facts:
        return facts[0][1]
    if any(line == "move" for line, _reason in dropped):
        return HEADLINE_FAILED
    return None                                      # held, and no fault of the writer's in it: final


@dataclass(frozen=True, slots=True)
class Consult:
    """One ask on a rung: how it ended, and — if it parsed — what the check made of it."""
    status: str                                      # one of STATUSES
    checked: C.CheckedReview | None = None
    repair: bool = False                             # the rung's second ask, with the check's verdicts


@dataclass(frozen=True, slots=True)
class Step:
    """What to do next, and — for a repair, a climb or an exhausted ladder — the writer's fault that decided it."""
    kind: str
    fault: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in STEPS:
            raise ValueError(f"a step is one of {STEPS}, not {self.kind!r}")
        if self.fault is not None and self.fault not in CLIMB_REASONS:
            raise ValueError(f"a fault is one of {CLIMB_REASONS}, not {self.fault!r}")


def next_step(consults: Sequence[Consult], *, rung: int, rungs: int) -> Step:
    """What to do after the consults made so far on rung `rung` of `rungs` (1-based, cheapest first)."""
    if not 1 <= len(consults) <= 2:
        raise ValueError("a rung is consulted once, and once more to repair: one or two consults")
    last = consults[-1]
    if last.status == "over_budget":
        return Step(CARRIED)
    fault = writer_fault(last.status, last.checked)
    if fault is None:
        return Step(FINAL)
    if len(consults) == 1 and last.status != "truncated":
        return Step(REPAIR, fault)
    return Step(CLIMB if rung < rungs else EXHAUSTED, fault)


def complaint(status: str, checked: C.CheckedReview | None) -> str:
    """The prompt's complaint for a repair: the check's verdicts — the lines dropped and why — handed back (X32)."""
    if checked is None:
        said = {"truncated": "was cut off before it ended; answer shorter, in the same shape",
                "refused": "did not hold against the dossier it was shown",
                "failed": "was not valid JSON in the shape asked for"}.get(status, "could not be read")
        return f"Your previous answer {said}. Answer again with one JSON object in exactly that shape."
    lines = "; ".join(f"{v.line} ({v.reason}{': ' + v.detail if v.detail else ''})"
                      for v in checked.verdicts if v.verdict == C.DROPPED)
    return ("Your previous answer was checked against the dossier and these lines did not stand: "
            f"{lines or 'the move did not hold'}. Answer again: cite only ids the dossier prints, quote the mail's "
            "own words, and keep every name and number to what the dossier holds.")


def best_of(attempts: Sequence[tuple[int, C.CheckedReview | None]]) -> int | None:
    """The index of the answer that stands when every rung failed: the best fate (`FATE_ORDER`), on a tie the higher
    rung — the repair, on the same rung. An answer that never became a review stands for nothing; none at all is None."""
    best: tuple[int, int, int] | None = None
    for index, (rung, checked) in enumerate(attempts):
        if checked is None:
            continue
        key = (len(FATE_ORDER) - FATE_ORDER.index(checked.fate), rung, index)
        if best is None or key[:2] >= best[:2]:    # a tie on the same rung: the later, repaired, answer
            best = key
    return None if best is None else best[2]


__all__ = ["CARRIED", "CLIMB", "CLIMB_REASONS", "Consult", "EXHAUSTED", "FACT_FAULTS", "FATE_ORDER", "FINAL",
           "HEADLINE_FAILED", "LADDER_VERSION", "MALFORMED", "NOTHING_STANDS", "RECIPIENT_IS_CONNECTOR",
           "RECIPIENT_IS_US", "REPAIR", "STATE_REASONS", "STATUSES", "STEPS", "Step", "TRUNCATED", "best_of",
           "complaint", "next_step", "writer_fault"]
