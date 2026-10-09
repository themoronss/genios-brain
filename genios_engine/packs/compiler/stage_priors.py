"""A playbook's stages, each with its typical duration as a PRIOR — never a habit (STEP-11, `06` D37).

STEP-11 §8.4 (4): *stages are data; the current stage is a judgment.* A Founder Office playbook may
declare the stages its kind of work moves through (`Domain Expertise/_schema/artifact.schema.json`,
`stages`), each with a typical duration that is a profession's usual value — with its source — what
quiet means at that stage, and the event that ends it. STEP-12's expert names a file's current stage
from its timeline, constrained to this closed list; code computes the dwell (D39).

THE DURATION IS A `Measured`, AND ITS SOURCE IS `playbook_prior`. STEP-10 made every number a file
shows carry what it rests on (`contracts/measured.py`); a prior rests on no observation of this
founder, so its `n` is 0, it is never `normal`, and its words say what it is — *"21 days — a
playbook's prior, not measured here"*. A card says *"a typical programme takes…"*, never *"you
usually…"* (STEP-11 §8.7). The citation travels beside it, because a prior without its source is a
number somebody made up.

Pure: a playbook mapping in, frozen stage priors out. No I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from genios_engine.contracts.measured import PLAYBOOK_PRIOR, Measured


@dataclass(frozen=True, slots=True)
class StagePrior:
    """One declared stage of a playbook's kind of work."""
    name: str                  # the stage's id — what STEP-12's expert names, from a closed list
    label: str                 # how a reader sees it
    typical: Measured          # the typical duration in days: source `playbook_prior`, n = 0
    cited: str                 # where that duration comes from — a URL or a named reference
    quiet_means: str | None    # what silence from the other side means at this stage
    leaves_when: str | None    # the observable event that ends the stage

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "label": self.label, "typical": self.typical.as_dict(),
                "cited": self.cited, "quiet_means": self.quiet_means,
                "leaves_when": self.leaves_when}


def _text(value: Any) -> str | None:
    folded = " ".join(str(value).split()) if value is not None else ""
    return folded or None


def stage_priors(playbook: Mapping[str, Any]) -> tuple[StagePrior, ...]:
    """The playbook's declared stages, in its order. A playbook that declares none has none.

    A stage without its name, its typical duration or its source is REFUSED, loudly: the corpus's
    validator already rejects one, so reaching this function with one means a file skipped
    validation, and a prior without a source is the one thing this module exists not to produce.
    """
    identity = playbook.get("identity") if isinstance(playbook.get("identity"), Mapping) else {}
    basis = f"playbook {identity.get('id') or '(unnamed)'}"
    out: list[StagePrior] = []
    seen: set[str] = set()
    for position, stage in enumerate(playbook.get("stages") or (), 1):
        if not isinstance(stage, Mapping):
            raise ValueError(f"{basis}: stage {position} is not a mapping")
        name = _text(stage.get("name"))
        source = _text(stage.get("source"))
        days = stage.get("typical_duration_days")
        if not name or not source or isinstance(days, bool) or not isinstance(days, int) or days < 0:
            raise ValueError(f"{basis}: stage {position} needs a name, a whole number of days and "
                             "the source of that number")
        if name in seen:
            raise ValueError(f"{basis}: stage {name!r} is declared twice")
        seen.add(name)
        out.append(StagePrior(
            name=name,
            label=_text(stage.get("label")) or name.replace("_", " "),
            typical=Measured(value=days, n=0, basis=basis, source=PLAYBOOK_PRIOR, unit="days"),
            cited=source,
            quiet_means=_text(stage.get("quiet_means")),
            leaves_when=_text(stage.get("leaves_when"))))
    return tuple(out)


__all__ = ["StagePrior", "stage_priors"]
