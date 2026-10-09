"""What a professional knows about one kind of work — the read model a file reads (STEP-11, §8.4 item 8).

`playbook_for(kind)` answers, for a file whose kind of work is `kind` (`06` D31: the brief's in-motion
line names it — `investor`, `program`, `compliance`, `hiring`, `intro`, `partner`), what the Founder
Office corpus says about that work: its STAGES, each with a typical duration as a labelled prior and
what quiet means there; its next MOVES with what success looks like and how long to wait for it; the
CLAIMS they rest on; what doing nothing costs; when the work is DORMANT; and whether a named human
reviewed it. STEP-12's dossier calls it per file, and `GET /v1/workstreams/{file}` names it.

THE KIND'S PLAYBOOK IS ITS SPINE. Each kind maps to one capability (`KIND_CAPABILITY`), and of that
capability's playbooks exactly one declares `stages` — the closed list STEP-12's expert picks a file's
current stage from. The other playbooks are its moves.

READ, NEVER GATED (D3). Admission gates what may carry authority on a CARD; this is what the expert
may READ, so an unreviewed playbook is answered — and says so: `reviewed` is True only when the
capability is admitted and a named human reviewed the spine, and otherwise `review_label` carries D3's
words, *"playbook not yet reviewed"*.

THE CURRENT STAGE IS NOT HERE. Nothing in this module reads a file's timeline or detects a stage:
stages are data, the current stage is the expert's judgment (STEP-12), and the dwell is code's (D39).

Pure over the catalog: a kind in, a frozen answer out. The catalog is the shipped corpus unless a
caller hands one in.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

from genios_engine.contracts.measured import PLAYBOOK_PRIOR, Measured

from .authoring import ExpertBrainCatalog, default_authoring_root
from .capability_resolver import _admission_reason, artifact_admission_reason
from .stage_priors import StagePrior, stage_priors

DOMAIN = "founder_office"

#: `06` D31's kinds of work → the Founder Office capability whose playbook a file of that kind reads.
#: `partner` has none yet: a partner file reads nothing, and the answer says so rather than borrowing.
KIND_CAPABILITY: Mapping[str, str | None] = {
    "investor": "founder_office.fundraising.investor_relations",
    "program": "founder_office.programs_and_applications.program_applications",
    "compliance": "founder_office.compliance.registrations_and_recognition",
    "hiring": "founder_office.hiring.offers_and_joining",
    "intro": "founder_office.networking_and_intros.introductions",
    "partner": None,
}

#: D3's words, on everything a named human has not reviewed.
REVIEW_LABEL = "playbook not yet reviewed"

#: Why a kind has no playbook — each is a different thing to fix, in a different place.
NO_KIND = "no_kind"                              # the file's line names no kind of work
UNKNOWN_KIND = "unknown_kind"                    # a kind outside D31's list
NO_CAPABILITY = "no_capability_for_kind"         # `partner`, today
NOT_AUTHORED = "capability_not_authored"         # the capability is missing or still a stub
NO_SPINE = "no_playbook_declares_stages"         # authored, but no playbook names the stages
SEVERAL_SPINES = "several_playbooks_declare_stages"


@dataclass(frozen=True, slots=True)
class Move:
    """One next move a professional would make — a playbook of the kind other than its spine."""
    artifact_id: str
    name: str
    steps: tuple[str, ...]
    success_signal: str | None
    outcome_window_days: int | None
    reviewed: bool

    def as_dict(self) -> dict[str, Any]:
        return {"artifact_id": self.artifact_id, "name": self.name, "steps": list(self.steps),
                "success_signal": self.success_signal,
                "outcome_window_days": self.outcome_window_days, "reviewed": self.reviewed}


@dataclass(frozen=True, slots=True)
class Claim:
    """One thing a professional knows — a heuristic: what it says, and why."""
    artifact_id: str
    statement: str
    why: str | None
    reviewed: bool

    def as_dict(self) -> dict[str, Any]:
        return {"artifact_id": self.artifact_id, "statement": self.statement, "why": self.why,
                "reviewed": self.reviewed}


@dataclass(frozen=True, slots=True)
class StopRule:
    """When this kind of work, left quiet, is dormant rather than waiting (`06` D33) — a prior."""
    dormant_after: Measured
    cited: str
    then: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"dormant_after": self.dormant_after.as_dict(), "cited": self.cited,
                "then": self.then}


@dataclass(frozen=True, slots=True)
class KindPlaybook:
    kind: str
    capability_id: str
    playbook_id: str
    name: str
    stages: tuple[StagePrior, ...]
    do_nothing_consequence: str | None
    success_signal: str | None
    outcome_window_days: int | None
    stop: StopRule | None
    moves: tuple[Move, ...]
    claims: tuple[Claim, ...]
    reviewed: bool
    review_label: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "capability_id": self.capability_id,
                "playbook_id": self.playbook_id, "name": self.name,
                "stages": [stage.as_dict() for stage in self.stages],
                "do_nothing_consequence": self.do_nothing_consequence,
                "success_signal": self.success_signal,
                "outcome_window_days": self.outcome_window_days,
                "stop": self.stop.as_dict() if self.stop else None,
                "moves": [move.as_dict() for move in self.moves],
                "claims": [claim.as_dict() for claim in self.claims],
                "reviewed": self.reviewed, "review_label": self.review_label}


@dataclass(frozen=True, slots=True)
class PlaybookAnswer:
    """The kind's playbook, or the named reason there is none."""
    kind: str | None
    playbook: KindPlaybook | None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "reason": self.reason,
                "playbook": self.playbook.as_dict() if self.playbook else None}


@lru_cache(maxsize=1)
def _shipped_catalog() -> ExpertBrainCatalog:
    """The shipped corpus, loaded once per process: it changes only with a deploy."""
    return ExpertBrainCatalog(default_authoring_root())


def _text(value: Any) -> str | None:
    folded = " ".join(str(value).split()) if value is not None else ""
    return folded or None


def _window(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else None


def _reviewed(content: Mapping[str, Any]) -> bool:
    return artifact_admission_reason(content) is None


def _steps(content: Mapping[str, Any]) -> tuple[str, ...]:
    steps = []
    for step in content.get("steps") or ():
        text = _text(step.get("description") or step.get("name")) if isinstance(step, Mapping) \
            else _text(step)
        if text:
            steps.append(text)
    return tuple(steps)


def _stop(content: Mapping[str, Any], basis: str) -> StopRule | None:
    block = content.get("stop")
    if not isinstance(block, Mapping):
        return None
    days, cited = block.get("dormant_after_days"), _text(block.get("source"))
    if _window(days) is None or not cited:
        return None
    return StopRule(dormant_after=Measured(value=days, n=0, basis=basis, source=PLAYBOOK_PRIOR,
                                           unit="days"),
                    cited=cited, then=_text(block.get("then")))


def _ids(manifest: Mapping[str, Any], key: str) -> list[str]:
    block = manifest.get(key) or {}
    return [str(item) for part in ("core", "scoped") for item in (block.get(part) or ())]


def playbook_for(kind: str | None, *, catalog: ExpertBrainCatalog | None = None) -> PlaybookAnswer:
    """What the Founder Office corpus says about one kind of work. A file reads
    `playbook_for(file.work_kind)`; a file no line names has no kind, and no playbook."""
    if not kind:
        return PlaybookAnswer(kind=None, playbook=None, reason=NO_KIND)
    if kind not in KIND_CAPABILITY:
        return PlaybookAnswer(kind=kind, playbook=None, reason=UNKNOWN_KIND)
    capability_id = KIND_CAPABILITY[kind]
    if capability_id is None:
        return PlaybookAnswer(kind=kind, playbook=None, reason=NO_CAPABILITY)
    catalog = catalog or _shipped_catalog()
    domain = catalog.domains.get(DOMAIN)
    capability = domain.capabilities.get(capability_id) if domain is not None else None
    if capability is None or (capability.content.get("identity") or {}).get("stub"):
        return PlaybookAnswer(kind=kind, playbook=None, reason=NOT_AUTHORED)
    manifest = domain.knowledge_manifests[capability_id].content
    playbooks = [domain.artifacts[pid] for pid in _ids(manifest, "playbooks")
                 if pid in domain.artifacts]
    spines = [doc for doc in playbooks if doc.content.get("stages")]
    if not spines:
        return PlaybookAnswer(kind=kind, playbook=None, reason=NO_SPINE)
    if len(spines) > 1:
        return PlaybookAnswer(kind=kind, playbook=None, reason=SEVERAL_SPINES)
    spine = spines[0].content
    spine_id = spines[0].id
    basis = f"playbook {spine_id}"
    moves = tuple(
        Move(artifact_id=doc.id,
             name=_text((doc.content.get("identity") or {}).get("name")) or doc.id,
             steps=_steps(doc.content),
             success_signal=_text(doc.content.get("success_signal")),
             outcome_window_days=_window(doc.content.get("outcome_window_days")),
             reviewed=_reviewed(doc.content))
        for doc in sorted(playbooks, key=lambda d: d.id) if doc.id != spine_id)
    claims = []
    for hid in sorted(_ids(manifest, "heuristics")):
        doc = domain.artifacts.get(hid)
        heuristic = (doc.content.get("heuristic") or {}) if doc is not None else {}
        statement = _text(heuristic.get("statement"))
        if statement:
            claims.append(Claim(artifact_id=hid, statement=statement,
                                why=_text(heuristic.get("why")), reviewed=_reviewed(doc.content)))
    reviewed = _admission_reason(capability) is None and _reviewed(spine)
    return PlaybookAnswer(kind=kind, playbook=KindPlaybook(
        kind=kind, capability_id=capability_id, playbook_id=spine_id,
        name=_text((spine.get("identity") or {}).get("name")) or spine_id,
        stages=stage_priors(spine),
        do_nothing_consequence=_text(spine.get("do_nothing_consequence")),
        success_signal=_text(spine.get("success_signal")),
        outcome_window_days=_window(spine.get("outcome_window_days")),
        stop=_stop(spine, basis),
        moves=moves, claims=tuple(claims),
        reviewed=reviewed, review_label=None if reviewed else REVIEW_LABEL))


__all__ = ["DOMAIN", "KIND_CAPABILITY", "KindPlaybook", "Claim", "Move", "NOT_AUTHORED", "NO_CAPABILITY",
           "NO_KIND", "NO_SPINE", "PlaybookAnswer", "REVIEW_LABEL", "SEVERAL_SPINES", "StopRule",
           "UNKNOWN_KIND", "playbook_for"]
