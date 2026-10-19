"""GeniOS-008 L2 R6/R9/R10 · ONE judgment of one subject — through the one gate, checked, made a result.

The STEP-12 review's path (`reason/expert/review.review_file`), generalised and kept on the same rails:

  THE CALL      R-9 (`reason/bundle/sites.SITE_REASON`) through `reason/llm_sites.run_site`, so through
                `RSiteGate`: activation (`l2_reasoning`), the force-fail switch, its own $2 day and per-call
                ceiling, the token ceiling, the repair, the ledger (`l4_r_site_calls`). Never around it.
  THE REPAIR    one, for an answer that is not JSON at any depth; at DEEP depth, one for any refusal — the
                spec's third call ("an unresolved material issue → CALL 3").
  THE ANSWER    parsed as BOTH halves — `ExpertReview.from_mapping` and `L2Judgment.from_mapping`; a shape
                error in either is `malformed`. Then held to its dossier:
                  structure   the review's (`verify.STRUCTURAL`: a moving mode with no move, a move on no
                              fact, a stage the playbook lacks) and the judgment's (a mode the review's mode
                              does not allow) — refused whole;
                  the check   STEP-13's claim check (`reason/expert/verify.check_review`) over every fact,
                              quote, name and number — a line that fails drops; nothing standing is refused
                              `nothing_stands`;
                  the rest    `validate_judgment` names every unprinted ref (dropped, `drop_unprinted`), a
                              number the dossier does not hold, a needed decision with no owner and a move
                              due before the run (`review_required`).
  THE RESULT    a `ReasoningResult`, its lane by code (`lane_for`).

Never writes: the sweep keeps the row and writes the sweep's rows together (`reason/l2/store`).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.claim_check import NOTHING_STANDS, REFUSED as CHECK_REFUSED
from genios_engine.contracts.expert_review import REFUSALS, ExpertReview, validate
from genios_engine.contracts.reasoning_result import (DEPTH_DEEP, ENDED_FAILED, ENDED_OVER_BUDGET,
                                                      ENDED_REFUSED, ENDED_RESULT, ENDED_TRUNCATED,
                                                      STRUCTURAL as JUDGMENT_STRUCTURAL, L2Judgment,
                                                      ReasoningResult, drop_unprinted, lane_for,
                                                      validate_judgment)
from genios_engine.platform.l4_activation import FEATURE_L2_REASONING
from genios_engine.reason.bundle.gate import MALFORMED, REPAIR_ANY, REPAIR_SYNTAX
from genios_engine.reason.bundle.sites import (OUTCOME_FAILED_GENERATION, OUTCOME_FAILED_VALIDATION,
                                               OUTCOME_NO_BUDGET, OUTCOME_RAN, OUTCOME_TRUNCATED, SITE_REASON)
from genios_engine.reason.expert.review import NOBODY
from genios_engine.reason.expert.verify import STRUCTURAL as REVIEW_STRUCTURAL, check_review
from genios_engine.reason.llm_sites import SiteReceipt, SiteRejection, run_site

from .dossier import L2Dossier
from .plan import L2Plan
from .prompt import build_prompt

#: How each consult outcome ends the run. An outcome not named here reached no question (the feature off,
#: no client, force-failed): the run ends with nothing written, and the receipt says why.
ENDS_OF: Mapping[str, str] = {
    OUTCOME_RAN: ENDED_RESULT,
    OUTCOME_TRUNCATED: ENDED_TRUNCATED,
    OUTCOME_NO_BUDGET: ENDED_OVER_BUDGET,
    OUTCOME_FAILED_GENERATION: ENDED_FAILED,
}


@dataclass(frozen=True, slots=True)
class Judged:
    ended: str | None                 # one of `ENDS` — None when no consult reached the question
    reason: str | None
    result: ReasoningResult | None    # only when `ended == result`
    receipt: SiteReceipt
    raw: Mapping[str, Any] | None = None


def _end(outcome: str, codes: tuple[str, ...]) -> str | None:
    if outcome == OUTCOME_FAILED_VALIDATION:
        substance = codes and (codes[0] in REFUSALS or codes[0] == NOTHING_STANDS
                               or codes[0] in JUDGMENT_STRUCTURAL)
        return ENDED_REFUSED if substance else ENDED_FAILED
    return ENDS_OF.get(outcome)


def judge(*, org_id: str, request_ref: str, dossier: L2Dossier, plan: L2Plan, gate: Any, fingerprint: str,
          context_ref: str, expertise_ref: str, at: datetime, people: Any = None) -> Judged:
    """Judge one subject once. Returns what came of it; writes nothing."""
    last: dict[str, Any] = {}
    people = people or NOBODY

    def _parse(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        last.clear()
        last["raw"] = dict(payload)
        try:
            review = ExpertReview.from_mapping(payload)
            judgment = L2Judgment.from_mapping(payload)
        except ValueError as exc:
            last["reason"] = f"{MALFORMED}: {exc}"
            raise SiteRejection(MALFORMED, str(exc)) from None
        structure = [(k, d) for k, d in validate(review, dossier.catalogue).problems if k in REVIEW_STRUCTURAL]
        structure += [(k, d) for k, d in validate_judgment(review, judgment, dossier.catalogue)
                      if k in JUDGMENT_STRUCTURAL]
        if structure:
            last["reason"] = "; ".join(f"{k}: {d}" for k, d in structure)
            raise SiteRejection(structure[0][0], last["reason"])
        checked = check_review(review, dossier.text, people, evidence_ids=dossier.catalogue.evidence_ids)
        if checked.fate == CHECK_REFUSED:
            last["reason"] = f"{NOTHING_STANDS}: " + "; ".join(
                f"{v.line} {v.reason}" + (f" ({v.detail})" if v.detail else "") for v in checked.dropped)
            raise SiteRejection(NOTHING_STANDS, last["reason"])
        problems = validate_judgment(review, judgment, dossier.catalogue, as_of=at)
        kept = drop_unprinted(judgment, dossier.catalogue, len(review.facts))
        lane, why = lane_for(kept)
        last["result"] = ReasoningResult(
            request_ref=request_ref, subject_ref=dossier.subject_ref, context_ref=context_ref,
            expertise_ref=expertise_ref, depth=plan.depth, review=review, judgment=kept, lane=lane,
            lane_reason=why, check_fate=checked.fate, problems=problems)
        return {**review.as_mapping(), **kept.as_mapping()}

    site = run_site(site=SITE_REASON, org_id=org_id, seed={"l2": dossier.subject_ref, "fingerprint": fingerprint},
                    precondition=True, build_prompt=lambda feedback: build_prompt(dossier, plan, feedback),
                    parse=_parse, fallback=dict, gate=gate, subject_ref=dossier.subject_ref,
                    feature=FEATURE_L2_REASONING,
                    repair=REPAIR_ANY if plan.depth == DEPTH_DEEP else REPAIR_SYNTAX)
    receipt = site.receipt
    ended = _end(receipt.outcome, receipt.reason_codes)
    if ended is None:
        return Judged(ended=None, reason=", ".join(receipt.reason_codes) or receipt.outcome, result=None,
                      receipt=receipt)
    if ended == ENDED_RESULT and last.get("result") is None:
        # A cached answer: the gate's cache held the payload and `_parse` did not run on it this time.
        try:
            ended, reason = ENDED_RESULT, None
            _parse(site.payload)
        except SiteRejection as rejection:
            ended, reason = ENDED_FAILED, f"the cached answer no longer stands: {rejection.reason}"
            return Judged(ended=ended, reason=reason, result=None, receipt=receipt, raw=last.get("raw"))
    if ended == ENDED_RESULT:
        return Judged(ended=ended, reason=None, result=last["result"], receipt=receipt)
    if receipt.outcome == OUTCOME_FAILED_VALIDATION and last.get("reason"):
        reason = "; ".join([last["reason"], *receipt.reason_codes[1:]])
    else:
        reason = ", ".join(receipt.reason_codes) or receipt.outcome
    return Judged(ended=ended, reason=reason, result=None, receipt=receipt, raw=last.get("raw"))


__all__ = ["ENDS_OF", "Judged", "judge"]
