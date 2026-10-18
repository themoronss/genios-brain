"""How long a file has been in the stage its review names — against its playbook's prior (STEP-12).

`speedrun008/YC-II W27/06` D39 and STEP-11 §4, tree `yc2_w27_s12` M32.C3.L-logic.V2.U07: the stage is the
expert's, the dwell code's. Once a review names the file's stage (`expected_vs_actual.stage` — one of its
playbook's stages; `validate` refuses any other), code measures how long the file has been there: from
the stage's FIRST CITED TOUCH — the earliest touch of the file the review cites for a fact — to the
dossier's as-of, in days. A loop, a number or a playbook line may be cited for a fact too; only a touch
has a date in the file, so only a touch can start a dwell.

It is set against the playbook's typical duration for the stage, which is a PRIOR — a reviewed author's
number, not measured here — and says so; it is never called normal (only a measurement at n ≥ 5 is, D37).

No stage, no playbook, a stage the playbook does not have, or no cited touch: no dwell, and
`why_no_dwell` says which. Pure: the review and the parts it was written over.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.contracts.measured import Measured

from .dossier import DossierParts


@dataclass(frozen=True, slots=True)
class StageDwell:
    stage: str
    label: str
    since_event: str                 # the stage's first cited touch
    since: datetime
    days: float
    prior: Measured                  # the playbook's typical duration for the stage — a prior

    @property
    def beyond_prior(self) -> bool | None:
        return None if self.prior.value is None else self.days > self.prior.value

    def says(self) -> str:
        return (f"{self.label}: {self.days:g} days since {self.since_event} — the playbook's prior for "
                f"it: {self.prior.says()}")


def _stage(review: ExpertReview, parts: DossierParts):
    stage = review.expected_vs_actual.stage
    pb = getattr(parts.playbook, "playbook", None)
    if pb is None:
        return stage, pb, None
    return stage, pb, next((s for s in pb.stages if s.name == stage), None)


def _first_cited_touch(review: ExpertReview, parts: DossierParts) -> tuple[datetime, str] | None:
    touched = {t.event_id: t.at for t in parts.timeline.touches}
    cited = [(touched[e], e) for fact in review.facts for e in fact.evidence if e in touched]
    return min(cited) if cited else None


def stage_dwell(review: ExpertReview, parts: DossierParts) -> StageDwell | None:
    """The file's dwell in the stage its review names, or None — `why_no_dwell` says why."""
    stage, _pb, prior = _stage(review, parts)
    first = _first_cited_touch(review, parts)
    if prior is None or first is None:
        return None
    since, event = first
    return StageDwell(stage=stage, label=prior.label, since_event=event, since=since,
                      days=round((parts.as_of - since).total_seconds() / 86400, 2),
                      prior=prior.typical)


def why_no_dwell(review: ExpertReview, parts: DossierParts) -> str:
    """Why a review has no dwell — or "" when it has one."""
    stage, pb, prior = _stage(review, parts)
    if not stage:
        return "the review names no stage"
    if pb is None:
        return "the file has no playbook"
    if prior is None:
        return f"{stage} is not a stage of its playbook"
    if _first_cited_touch(review, parts) is None:
        return "the review cites no touch of the file"
    return ""


__all__ = ["StageDwell", "stage_dwell", "why_no_dwell"]
