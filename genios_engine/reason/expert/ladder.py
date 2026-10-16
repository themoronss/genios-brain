"""The expert's model ladder — the cheapest rung asks first, a stronger one only when the check says the writer erred (STEP-13b).

`speedrun008/YC-II W27/` STEP-13b §8.4 item 5, tree `yc2_w27_s13b` M38.C2.L-logic.V3.U02. Rohit, 12 Oct: *"in case opus is
needed … jarurat kam pade costly models ki"*. The rule is `contracts/model_ladder` (pure: when an answer is final, is
repaired, climbs, is exhausted, or carries the file); this is the mechanism that asks the models, one rung at a time:

  RUNG 1   Haiku-class — the whole checklist, over the dossier. The answer is parsed, held to its dossier and CHECKED
           (`reason/expert/verify`) exactly as a single consult was.
  REPAIR   an answer that fails the check for the WRITER's own fault is asked once more on its own rung, handed the
           check's verdicts — the lines dropped and why (crosscheck X32, s13b-D4).
  CLIMB    only a repaired answer that still fails goes up: Sonnet-class; Opus-class only where the tenant allows it
           (`reason/bundle/sites.expert_ladder`, s13b-D1 — built switched off). A cut answer is not repaired at its own
           ceiling: it climbs.
  FINAL    an answer the check shows, suppresses, or holds for the FILE's own state is final: a stronger model would be
           held for the same reason. When every rung failed, the BEST fate stands (shown > suppressed > held > refused).
  CARRIED  a day spent mid-climb (`over_budget`) is no fault of the writer: the climb stops and the file is carried (`06`
           D7).

One day for every rung: every rung's gate shares ONE `NarrativeBudget` (`reason/bundle/budget`), each consult priced at its
own rung's tier. Every consult is an ATTEMPT, kept (`store.write_attempt`, migration 0250) by the caller with the review
that stands. The prompt names no model — the rung's gate holds the client, and so the model; the ladder is configuration.

This module reads and writes no database: it returns what was asked and what stands (`review.review_file` keeps it).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from genios_engine.contracts import model_ladder as M
from genios_engine.contracts.claim_check import NOTHING_STANDS, REFUSED, CheckedReview
from genios_engine.contracts.expert_review import REFUSALS, ExpertReview, validate
from genios_engine.platform.l4_activation import FEATURE_EXPERT_REVIEW
from genios_engine.reason.bundle.gate import REPAIR_SYNTAX, RSiteGate
from genios_engine.reason.bundle.sites import (OUTCOME_FAILED_GENERATION, OUTCOME_FAILED_VALIDATION,
                                               OUTCOME_NO_BUDGET, OUTCOME_RAN, OUTCOME_TRUNCATED, SITE_EXPERT)
from genios_engine.reason.llm_sites import SiteReceipt, SiteRejection, run_site, tier_model

from . import store
from .dossier import Dossier, FilePeople
from .prompt import build_prompt
from .verify import STRUCTURAL

#: What a consult's outcome is as a ROW and as the ladder's table reads it (`store.STATUSES` = `model_ladder.STATUSES`).
STATUS_OF: dict[str, str] = {OUTCOME_RAN: store.VALID, OUTCOME_TRUNCATED: store.TRUNCATED,
                             OUTCOME_NO_BUDGET: store.OVER_BUDGET, OUTCOME_FAILED_GENERATION: store.FAILED}
FIRST, REPAIR = "first", "repair"


@dataclass(frozen=True, slots=True)
class Rung:
    """One rung of a file's ladder: the tier it calls (`reason/bundle/sites.TIER_*`) and the gate that asks it."""
    tier: str
    gate: RSiteGate


@dataclass(frozen=True, slots=True)
class Attempted:
    """One consult, and what it made of the file: how it ended, what the check made of it, and what it cost."""
    rung: int                                   # 1 = the cheapest
    tier: str
    model: str
    consult: str                                # `first` or `repair`
    status: str                                 # as `store.STATUSES`
    reason: str | None
    fate: str | None                            # the check's, when there was one
    climbed_because: str | None                 # the writer's fault that sent the file up a rung
    input_tokens: int
    output_tokens: int
    cost_micro_usd: int
    review: ExpertReview | None = None          # only an answer that parsed and validated
    checked: CheckedReview | None = None        # …and was checked (a refusal on substance keeps its check)
    raw: Any = None                             # what the model said, for a row that is not a valid review
    receipt: SiteReceipt | None = None


@dataclass(frozen=True, slots=True)
class Outcome:
    """Everything a file's climb asked, and which consult stands."""
    attempts: tuple[Attempted, ...]
    stood: Attempted | None                     # None: no consult reached the question (feature off, no model …)
    carried: bool = False                       # the day was spent mid-climb

    @property
    def cost_micro_usd(self) -> int:
        return sum(a.cost_micro_usd for a in self.attempts)

    @property
    def input_tokens(self) -> int:
        return sum(a.input_tokens for a in self.attempts)

    @property
    def output_tokens(self) -> int:
        return sum(a.output_tokens for a in self.attempts)


def _consult(rung: int, step: Rung, *, org_id: str, dossier: Dossier, fingerprint: str, people: FilePeople | None,
             kind: str, complaint: str | None, check) -> tuple[Attempted | None, str | None]:
    """Ask one rung once (or, with the check's verdicts, once more) through its own gate. Returns the attempt — None
    when no consult reached the question (the feature off, the force-fail switch, no model) — and the receipt's reason."""
    last: dict[str, Any] = {}

    def _parse(payload):
        last.clear()
        last["raw"] = dict(payload)
        try:
            review = ExpertReview.from_mapping(payload)
        except ValueError as exc:
            last["reason"] = f"{M.MALFORMED}: {exc}"
            raise SiteRejection(M.MALFORMED, str(exc)) from None
        structure = [(k, d) for k, d in validate(review, dossier.catalogue).problems if k in STRUCTURAL]
        if structure:
            last["reason"] = "; ".join(f"{k}: {d}" for k, d in structure)
            raise SiteRejection(structure[0][0], last["reason"])
        checked = check(review, dossier, people)
        last["review"], last["checked"] = review, checked
        if checked.fate == REFUSED:
            last["reason"] = f"{NOTHING_STANDS}: " + "; ".join(
                f"{v.line} {v.reason}" + (f" ({v.detail})" if v.detail else "") for v in checked.dropped)
            raise SiteRejection(NOTHING_STANDS, last["reason"])
        return review.as_mapping()

    result = run_site(site=SITE_EXPERT, org_id=org_id,
                      seed={"file": dossier.file_id, "fingerprint": fingerprint, "rung": step.tier, "consult": kind},
                      precondition=True, build_prompt=lambda feedback: build_prompt(dossier, feedback or complaint),
                      parse=_parse, fallback=dict, gate=step.gate, subject_ref=dossier.file_id,
                      feature=FEATURE_EXPERT_REVIEW, repair=REPAIR_SYNTAX, tier=step.tier)
    receipt = result.receipt
    status = _status(receipt.outcome, receipt.reason_codes)
    if status is None:
        return None, ", ".join(receipt.reason_codes) or receipt.outcome
    review, checked = last.get("review"), last.get("checked")
    if status == store.VALID:
        reason = None
    elif receipt.outcome == OUTCOME_FAILED_VALIDATION and last.get("reason"):
        reason = "; ".join([last["reason"], *receipt.reason_codes[1:]])
    else:
        reason = ", ".join(receipt.reason_codes) or receipt.outcome
    return Attempted(
        rung=rung, tier=step.tier, model=receipt.model or step.gate.model or tier_model(step.tier), consult=kind,
        status=status, reason=reason, fate=None if checked is None else checked.fate, climbed_because=None,
        input_tokens=receipt.input_tokens, output_tokens=receipt.output_tokens, cost_micro_usd=receipt.cost_micro_usd,
        review=review if status == store.VALID else None, checked=checked,
        raw=last.get("raw"), receipt=receipt), reason


def _status(outcome: str, codes: tuple[str, ...]) -> str | None:
    """The row's status for a consult's outcome — `review.STATUS_OF`'s table, with its substance rule."""
    if outcome == OUTCOME_FAILED_VALIDATION:
        return store.REFUSED if codes and (codes[0] in REFUSALS or codes[0] == NOTHING_STANDS) else store.FAILED
    return STATUS_OF.get(outcome)


def run_ladder(*, org_id: str, dossier: Dossier, fingerprint: str, people: FilePeople | None,
               rungs: Sequence[Rung], check) -> Outcome:
    """Climb the file's ladder (see the module docstring) and return every consult and the one that stands.

    `check(review, dossier, people)` is the check (`review.check`). Never raises past a consult: a consult that failed
    is a failed attempt and the rule decides."""
    if not rungs:
        raise ValueError("a ladder has at least one rung")
    attempts: list[Attempted] = []
    for number, step in enumerate(rungs, start=1):
        on_rung: list[M.Consult] = []
        complaint: str | None = None
        while True:
            kind = REPAIR if on_rung else FIRST
            attempted, _why = _consult(number, step, org_id=org_id, dossier=dossier, fingerprint=fingerprint,
                                       people=people, kind=kind, complaint=complaint, check=check)
            if attempted is None:
                return Outcome(tuple(attempts), None) if not attempts else _stand(attempts)
            on_rung.append(M.Consult(attempted.status, attempted.checked, kind == REPAIR, attempted.reason))
            decision = M.next_step(on_rung, rung=number, rungs=len(rungs))
            attempts.append(_with(attempted, climbed_because=decision.fault if decision.kind == M.CLIMB else None))
            if decision.kind == M.FINAL:
                return Outcome(tuple(attempts), attempts[-1])
            if decision.kind == M.CARRIED:
                return Outcome(tuple(attempts), attempts[-1], carried=True)
            if decision.kind == M.REPAIR:
                complaint = M.complaint(attempted.status, attempted.checked)
                continue
            break                                                         # CLIMB, or EXHAUSTED on the top rung
        if decision.kind == M.EXHAUSTED:
            return _stand(attempts)
    return _stand(attempts)


def _with(attempt: Attempted, **over: Any) -> Attempted:
    from dataclasses import replace
    return replace(attempt, **over)


def _stand(attempts: list[Attempted]) -> Outcome:
    """When every rung failed (or a later consult could not be made), the BEST fate stands (`model_ladder.best_of`); with
    no check among them, the last consult's own ending."""
    index = M.best_of([(a.rung, a.checked) for a in attempts])
    return Outcome(tuple(attempts), attempts[-1] if index is None else attempts[index])


__all__ = ["Attempted", "FIRST", "Outcome", "REPAIR", "Rung", "STATUS_OF", "run_ladder"]
