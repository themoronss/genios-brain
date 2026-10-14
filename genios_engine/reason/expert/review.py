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
                then held to its dossier: `validate` refuses its STRUCTURE whole (`verify.STRUCTURAL`: a
                moving mode with no move, a move resting on no fact of the review, a stage the playbook
                lacks), and the CHECK (`reason/expert/verify.check_review`, STEP-13 `yc2_w27_s13`
                M35.C3.L-integration.V1.U01) holds every claim to its lines — a line that fails drops
                and the review stays (`06` D59); a review none of whose facts stands is refused
                `nothing_stands`. A refusal on substance stands, never argued into passing.
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
  ON ITS DOSSIER (`06` D48, STEP-13 `yc2_w27_s13` M35.C3.L-integration.V1.U06, X13): every row keeps the
                dossier it was written against (0202), and a review checked again under a newer check
                version is checked on THAT dossier (`recheck`) — never today's, which may no longer print
                a line its facts cite. A row from before 0202 is checked on the dossier it is handed.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.claim_check import CHECK_VERSION, NOTHING_STANDS, REFUSED, CheckedReview
from genios_engine.contracts.expert_review import REFUSALS, ExpertReview, validate
from genios_engine.platform.self_identity import SelfIdentity
from genios_engine.platform.l4_activation import FEATURE_EXPERT_REVIEW
from genios_engine.reason.bundle.gate import MALFORMED, REPAIR_SYNTAX, RSiteGate
from genios_engine.reason.bundle.sites import (OUTCOME_FAILED_GENERATION, OUTCOME_FAILED_VALIDATION,
                                               OUTCOME_NO_BUDGET, OUTCOME_RAN, OUTCOME_TRUNCATED,
                                               SITE_EXPERT, tier_for)
from genios_engine.reason.llm_sites import SiteReceipt, SiteRejection, run_site, tier_model

from . import store
from .card_lines import CardLines
from .card_lines import card_lines
from .dossier import Dossier, DossierParts, FilePeople, Person
from .prompt import PROMPT_VERSION, build_prompt
from .verify import STRUCTURAL, check_review

#: Whom a review is checked against when its caller names nobody: no draft goes anywhere.
NOBODY = FilePeople(counterparty=Person(None, None), people=(), us=SelfIdentity())

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
    checked: CheckedReview | None = None    # a valid review's check (STEP-13)
    card_lines: CardLines | None = None     # what code wrote for its card (STEP-14, 0221) — a valid review's


def _status(outcome: str, codes: tuple[str, ...]) -> str | None:
    if outcome == OUTCOME_FAILED_VALIDATION:
        # Substance: the contract's refusals, and a review none of whose facts stood the check.
        return store.REFUSED if codes and (codes[0] in REFUSALS or codes[0] == NOTHING_STANDS) \
            else store.FAILED
    return STATUS_OF.get(outcome)


def check(review: ExpertReview, dossier: Dossier, people: FilePeople | None) -> CheckedReview:
    """`review` checked against the dossier it was written from (`reason/expert/verify`)."""
    return check_review(review, dossier.text, people or NOBODY,
                        evidence_ids=dossier.catalogue.evidence_ids)


def kept(dossier: Dossier) -> dict[str, Any]:
    """What a row keeps of the dossier its review was written against (0202): the text the check reads, and
    the ids it printed — the only ids a fact may cite."""
    return {"text": dossier.text, "evidence_ids": sorted(dossier.catalogue.evidence_ids)}


def recheck(row: store.StoredReview, people: FilePeople | None, *, today: Dossier) -> CheckedReview:
    """A standing valid review checked again — on the dossier it was written against (`06` D48, X13), or, on a
    row from before 0202 that kept none, on `today`'s."""
    if row.dossier is None:
        return check(row.review, today, people)
    return check_review(row.review, row.dossier["text"], people or NOBODY,
                        evidence_ids=frozenset(row.dossier["evidence_ids"]))


def review_file(engine, *, org_id: str, dossier: Dossier, fingerprint: str, inputs: Mapping[str, Any],
                triggers: Iterable[Any], gate: RSiteGate, at: datetime,
                people: FilePeople | None = None, parts: DossierParts | None = None) -> ReviewResult:
    """Review one file once for this fingerprint, check it, and keep what came of it. A standing valid
    row checked under an older check version — or before checks — is checked again, against this same
    dossier (the fingerprint is the dossier's inputs), and the check written onto it.

    STEP-14 (`yc2_w27_s14` M43.C2.L-integration.V2.U03): handed the dossier's `parts`, a valid review keeps beside
    its check the lines code writes for its card (`card_lines`, 0221) — from this dossier, with these triggers.
    A row written before 0221, or with no parts, keeps none: its card shows the review's own words."""
    triggers = tuple(triggers)
    file_id = dossier.file_id
    with engine.connect() as conn:
        standing = store.read_review(conn, org_id, file_id, fingerprint)
    if standing is not None and standing.status in store.STANDING:
        checked = standing.checked
        if standing.status == store.VALID and (checked is None or checked.version != CHECK_VERSION):
            checked = recheck(standing, people, today=dossier)
            with engine.begin() as conn:
                store.write_check(conn, org_id=org_id, file_id=file_id, fingerprint=fingerprint,
                                  checked=checked, at=at)
        return ReviewResult(file_id=file_id, fingerprint=fingerprint, status=standing.status,
                            reason=standing.reason, review=standing.review, receipt=None,
                            written=False, checked=checked, card_lines=standing.card_lines)

    last: dict[str, Any] = {}

    def _parse(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        last.clear()
        last["raw"] = dict(payload)
        try:
            review = ExpertReview.from_mapping(payload)
        except ValueError as exc:
            last["reason"] = f"{MALFORMED}: {exc}"
            raise SiteRejection(MALFORMED, str(exc)) from None
        structure = [(kind, detail) for kind, detail in validate(review, dossier.catalogue).problems
                     if kind in STRUCTURAL]
        if structure:
            last["reason"] = "; ".join(f"{kind}: {detail}" for kind, detail in structure)
            raise SiteRejection(structure[0][0], last["reason"])
        checked = check(review, dossier, people)
        if checked.fate == REFUSED:
            last["reason"] = f"{NOTHING_STANDS}: " + "; ".join(
                f"{v.line} {v.reason}" + (f" ({v.detail})" if v.detail else "") for v in checked.dropped)
            raise SiteRejection(NOTHING_STANDS, last["reason"])
        last["review"], last["checked"] = review, checked
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
    lines = card_lines(parts, review, triggers) if status == store.VALID and parts is not None else None
    with engine.begin() as conn:
        written = store.write_review(
            conn, org_id=org_id, file_id=file_id, fingerprint=fingerprint,
            model=receipt.model or tier_model(tier_for(SITE_EXPERT)), prompt_version=PROMPT_VERSION,
            dossier_digest=dossier.digest, status=status, reason=reason,
            review=review if status == store.VALID else last.get("raw"),
            input_tokens=receipt.input_tokens, output_tokens=receipt.output_tokens,
            cost_micro_usd=receipt.cost_micro_usd, at=at, inputs=inputs, triggers=triggers,
            checked=last.get("checked") if status == store.VALID else None, dossier=kept(dossier),
            card_lines=lines)
    return ReviewResult(file_id=file_id, fingerprint=fingerprint, status=status, reason=reason,
                        review=review, receipt=receipt, written=written,
                        checked=last.get("checked") if status == store.VALID else None, card_lines=lines)


__all__ = ["NOBODY", "ReviewResult", "STATUS_OF", "check", "kept", "recheck", "review_file"]
