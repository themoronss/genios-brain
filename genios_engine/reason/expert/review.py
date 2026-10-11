"""One expert review of one file — through the one gate, held to its dossier, kept (STEP-12).

Tree `yc2_w27_s12` M32.C3.L-logic.V1.U02. The site is R-7 (`reason/bundle/sites.SITE_EXPERT`: Sonnet-class,
its own day's budget and per-call ceiling — `06` D7) and its switch the L4 feature `expert_review`.
The call goes through `reason/llm_sites.run_site`, and so through `RSiteGate` — activation, the
force-fail switch, the budget, the token ceiling, the one repair, the ledger — like every R-site,
never around it.

  THE PROMPT    the checklist over the file's dossier (`reason/expert/prompt`, `expert-review.v1`).
  ONCE          a fingerprint a standing row already answers is answered by that row, with no consult
                (`store.reviewed`): the fingerprint's own row is its cache.
  THE ANSWER    parsed into the contract (`ExpertReview.from_mapping`) — an answer that is JSON but not
                its shape is `malformed`, which the gate repairs ONCE (`repair="syntax"`, M32.C4.U03) —
                then held to its dossier (`validate`): a refusal on substance stands, never argued into
                passing.
  THE RECORD    every consult that reached the model, or was refused one for want of budget, is ONE
                row of `expert_reviews`: what the file was (the fingerprint's inputs), what triggered
                the review, the dossier's digest, the model and the prompt version, the cost, and —
                unless valid — the reason:

                  ran                           → valid
                  refused on substance          → refused      stands until the file moves
                  still misshapen after repair  → failed       its retry may replace it
                  cut at the token ceiling      → truncated    stands: the same ceiling cuts it again
                  no budget left today          → over_budget  carried to the next day (`06` D7)
                  the call failed               → failed

                A consult that never reached the question — the feature off, the force-fail switch, no
                model configured — writes no row: nothing was judged and nothing refused, and the
                receipt says why.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.expert_review import REFUSALS, ExpertReview, validate
from genios_engine.platform.l4_activation import FEATURE_EXPERT_REVIEW
from genios_engine.reason.bundle.gate import MALFORMED, REPAIR_SYNTAX, RSiteGate
from genios_engine.reason.bundle.sites import (OUTCOME_FAILED_GENERATION, OUTCOME_FAILED_VALIDATION,
                                               OUTCOME_NO_BUDGET, OUTCOME_RAN, OUTCOME_TRUNCATED,
                                               SITE_EXPERT, tier_for)
from genios_engine.reason.llm_sites import SiteReceipt, SiteRejection, run_site, tier_model

from . import store
from .dossier import Dossier
from .prompt import PROMPT_VERSION, build_prompt

#: What each consult outcome is on the row. A validation refusal is `refused` when it is one of the
#: contract's refusals (substance) and `failed` otherwise — still misshapen after its one repair, or a
#: validator that broke. An outcome not named here writes no row.
STATUS_OF: Mapping[str, str] = {
    OUTCOME_RAN: store.VALID,
    OUTCOME_TRUNCATED: store.TRUNCATED,
    OUTCOME_NO_BUDGET: store.OVER_BUDGET,
    OUTCOME_FAILED_GENERATION: store.FAILED,
}


@dataclass(frozen=True, slots=True)
class ReviewResult:
    file_id: str
    fingerprint: str
    status: str | None              # the row's status — None when no consult reached the question
    reason: str | None
    review: ExpertReview | None     # only for a valid review
    receipt: SiteReceipt | None     # None when a standing row answered with no consult
    written: bool                   # whether this call wrote the row


def _status(outcome: str, codes: tuple[str, ...]) -> str | None:
    if outcome == OUTCOME_FAILED_VALIDATION:
        return store.REFUSED if codes and codes[0] in REFUSALS else store.FAILED
    return STATUS_OF.get(outcome)


def review_file(engine, *, org_id: str, dossier: Dossier, fingerprint: str, inputs: Mapping[str, Any],
                triggers: Iterable[Any], gate: RSiteGate, at: datetime) -> ReviewResult:
    """Review one file once for this fingerprint, and keep what came of it."""
    file_id = dossier.file_id
    with engine.connect() as conn:
        standing = store.read_review(conn, org_id, file_id, fingerprint)
    if standing is not None and standing.status in store.STANDING:
        return ReviewResult(file_id=file_id, fingerprint=fingerprint, status=standing.status,
                            reason=standing.reason, review=standing.review, receipt=None,
                            written=False)

    last: dict[str, Any] = {}

    def _parse(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        last.clear()
        last["raw"] = dict(payload)
        try:
            review = ExpertReview.from_mapping(payload)
        except ValueError as exc:
            last["reason"] = f"{MALFORMED}: {exc}"
            raise SiteRejection(MALFORMED, str(exc)) from None
        verdict = validate(review, dossier.catalogue)
        if not verdict.ok:
            last["reason"] = "; ".join(f"{kind}: {detail}" for kind, detail in verdict.problems)
            raise SiteRejection(verdict.reasons[0], last["reason"])
        last["review"] = review
        return review.as_mapping()

    result = run_site(site=SITE_EXPERT, org_id=org_id, seed={"file": file_id, "fingerprint": fingerprint},
                      precondition=True, build_prompt=lambda feedback: build_prompt(dossier, feedback),
                      parse=_parse, fallback=dict, gate=gate, subject_ref=file_id,
                      feature=FEATURE_EXPERT_REVIEW, repair=REPAIR_SYNTAX)
    receipt = result.receipt
    status = _status(receipt.outcome, receipt.reason_codes)
    if status is None:
        return ReviewResult(file_id=file_id, fingerprint=fingerprint, status=None,
                            reason=", ".join(receipt.reason_codes) or receipt.outcome, review=None,
                            receipt=receipt, written=False)
    review = last.get("review")                  # set only by an answer that parsed and validated
    if status == store.VALID:
        reason = None
    elif receipt.outcome == OUTCOME_FAILED_VALIDATION and last.get("reason"):
        reason = "; ".join([last["reason"], *receipt.reason_codes[1:]])     # and why no repair, if any
    else:
        reason = ", ".join(receipt.reason_codes) or receipt.outcome
    with engine.begin() as conn:
        written = store.write_review(
            conn, org_id=org_id, file_id=file_id, fingerprint=fingerprint,
            model=receipt.model or tier_model(tier_for(SITE_EXPERT)), prompt_version=PROMPT_VERSION,
            dossier_digest=dossier.digest, status=status, reason=reason,
            review=review if status == store.VALID else last.get("raw"),
            input_tokens=receipt.input_tokens, output_tokens=receipt.output_tokens,
            cost_micro_usd=receipt.cost_micro_usd, at=at, inputs=inputs, triggers=triggers)
    return ReviewResult(file_id=file_id, fingerprint=fingerprint, status=status, reason=reason,
                        review=review, receipt=receipt, written=written)


__all__ = ["ReviewResult", "STATUS_OF", "review_file"]
