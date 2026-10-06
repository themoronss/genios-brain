"""The material fingerprint — what a decision depends on, with time taken out (STEP-02, the change gate).

Every sweep re-decides every subject, and on a sweep that brought nothing new it pays the decider and
R-1 again for the same answer (`speedrun008/YC-II W27/` STEP-02 §8.1). The gate
(`reason/change_gate.should_skip`) skips a subject whose fingerprint is the one its last decision was
made on; this module says what goes into that fingerprint.

THE DECISION'S OWN REQUEST, NOT A LIST OF GUESSED INPUTS. A lane builds a context snapshot and a
capability manifest and hands both to the decider; that is everything the decision reads. Measured on
all 40 golden cases: a request repeated on a sweep 15 minutes later that brought nothing new differs
only in what the clock and the writers re-stamp — `evaluation_time`, `graph_version`, each fact's
`occurred_at` (the derived and waiting passes re-write every fact every drain, with the same value),
each evidence item's `evidence_id` (and so the evidence list's order), and the compiled capability's
derived `version` and `expertise_id`. With those out, every repeated request was identical.

TWO THINGS CAN CHANGE THE RIGHT ANSWER WITHOUT TOUCHING THE REQUEST, and `MaterialInputs` carries them:
the pack's `authority_revision` (a calibration, a pack change) and the human verdicts on the
subject's cards.

A CLOCK IS COMPARED BY ITS RUNG. A deadline or an elapsed time is read relative to the evaluation
instant and reduced to its rung on a ladder — deadline hours on Layer 4's own urgency ladder, elapsed
days on `DAY_LADDER` — so a wait crossing from 6 to 7 days re-decides, and 15 minutes never does.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from genios_engine.reason.reasoners.timeline_unit import URGENCY_LADDER

#: Hours until a deadline: the rungs `timeline_unit.urgency_from_hours` already decides urgency on.
HOUR_LADDER: tuple[int, ...] = tuple(hours for hours, _ in URGENCY_LADDER)

#: Elapsed days — how long a thread has waited, since a meeting, since contact. Seven is a rung:
#: STEP-02 §4's *"Theresa's wait crosses from 6 to 7 days"* is exactly the change that must re-decide.
DAY_LADDER: tuple[int, ...] = (0, 1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90, 180, 365)


def verdict_key(feedback_id: str, verdict_version: int) -> str:
    """One human verdict, as the fingerprint carries it: which feedback, at which version."""
    if not feedback_id:
        raise ValueError("a verdict key needs its feedback id")
    return f"{feedback_id}:{int(verdict_version)}"


@dataclass(frozen=True)
class MaterialInputs:
    """What can change the right answer without touching the decision's request.

    `authority_revision` — `tenant_packs.authority_revision` of the pack the decision runs under.
    `verdicts` — `verdict_key`s of the human verdicts on the subject's cards, held in one order.
    """

    authority_revision: int | None = None
    verdicts: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdicts", tuple(sorted(set(self.verdicts))))
