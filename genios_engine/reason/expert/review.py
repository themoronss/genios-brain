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

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.claim_check import CHECK_VERSION, CheckedReview
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.platform.self_identity import SelfIdentity
from genios_engine.reason.bundle.gate import RSiteGate
from genios_engine.reason.bundle.sites import SITE_EXPERT, tier_for
from genios_engine.reason.llm_sites import SiteReceipt

from . import store
from .card_lines import CardLines
from .card_lines import card_lines
from .dossier import Dossier, DossierParts, FilePeople, Person
from .ladder import Attempted, Rung, run_ladder
from .prompt import PROMPT_VERSION
from .verify import check_review

#: Whom a review is checked against when its caller names nobody: no draft goes anywhere.
NOBODY = FilePeople(counterparty=Person(None, None), people=(), us=SelfIdentity())

@dataclass(frozen=True, slots=True)
class ReviewResult:
    file_id: str
    fingerprint: str
    status: str | None              # the row's status — None when no consult reached the question
    reason: str | None
    review: ExpertReview | None     # only for a valid review
    receipt: SiteReceipt | None     # the consult that STANDS; None when a standing row answered with no consult
    written: bool                   # whether this call wrote the row
    checked: CheckedReview | None = None    # a valid review's check (STEP-13)
    card_lines: CardLines | None = None     # what code wrote for its card (STEP-14, 0221) — a valid review's
    #: STEP-13b (`yc2_w27_s13b` M38.C2.L-integration.V11.U03): the rung whose review stands (1 = the cheapest), every
    #: consult the ladder made (`ladder.Attempted`, each kept in `expert_review_attempts`, 0250), what they all cost
    #: together, and whether the day was spent mid-climb (the file is carried).
    rung: int | None = None
    attempts: tuple[Attempted, ...] = ()
    cost_micro_usd: int = 0
    carried: bool = False


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
                triggers: Iterable[Any], gate: RSiteGate | None = None, at: datetime,
                people: FilePeople | None = None, parts: DossierParts | None = None,
                ladder: Sequence[Rung] | None = None) -> ReviewResult:
    """Review one file once for this fingerprint, check it, and keep what came of it. A standing valid
    row checked under an older check version — or before checks — is checked again, against this same
    dossier (the fingerprint is the dossier's inputs), and the check written onto it.

    STEP-14 (`yc2_w27_s14` M43.C2.L-integration.V2.U03): handed the dossier's `parts`, a valid review keeps beside
    its check the lines code writes for its card (`card_lines`, 0221) — from this dossier, with these triggers.
    A row written before 0221, or with no parts, keeps none: its card shows the review's own words.

    STEP-13b: `ladder` — the rungs (`ladder.Rung`) cheapest first, sharing one day's budget. The row is the consult that
    STANDS (`ladder.run_ladder`): its model, `rung`, and — beside the cost of every consult — the review and its check;
    every consult is kept in `expert_review_attempts` (0250). `gate` alone is a ladder of one rung asked once."""
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

    # THE LADDER (STEP-13b M38.C2.L-integration.V11.U03). Handed `ladder` — the rungs, cheapest first, each its own gate
    # over one shared day — a file climbs it (`reason/expert/ladder`): repaired once on a rung with the check's verdicts,
    # a stronger model only when that fails. Handed a lone `gate`, it is asked once, as before the ladder.
    if ladder:
        rungs, repairs = tuple(ladder), True
    else:
        rungs, repairs = (Rung(tier_for(SITE_EXPERT), gate),), False
    outcome = run_ladder(org_id=org_id, dossier=dossier, fingerprint=fingerprint, people=people, rungs=rungs,
                         check=check, repairs=repairs)
    stood = outcome.stood
    if stood is None:
        return ReviewResult(file_id=file_id, fingerprint=fingerprint, status=None, reason=outcome.why, review=None,
                            receipt=outcome.receipt, written=False)
    status, review = stood.status, stood.review
    lines = card_lines(parts, review, triggers) if status == store.VALID and parts is not None else None
    with engine.begin() as conn:
        written = store.write_review(
            conn, org_id=org_id, file_id=file_id, fingerprint=fingerprint, model=stood.model,
            prompt_version=PROMPT_VERSION, dossier_digest=dossier.digest, status=status, reason=stood.reason,
            review=review if status == store.VALID else stood.raw,
            input_tokens=outcome.input_tokens, output_tokens=outcome.output_tokens,
            cost_micro_usd=outcome.cost_micro_usd, at=at, inputs=inputs, triggers=triggers,
            checked=stood.checked if status == store.VALID else None, dossier=kept(dossier),
            card_lines=lines, rung=stood.rung)
        for attempt in outcome.attempts:
            store.write_attempt(
                conn, org_id=org_id, file_id=file_id, fingerprint=fingerprint, rung=attempt.rung,
                model=attempt.model, consult=attempt.consult, status=attempt.status, fate=attempt.fate,
                climbed_because=attempt.climbed_because, input_tokens=attempt.input_tokens,
                output_tokens=attempt.output_tokens, cost_micro_usd=attempt.cost_micro_usd, at=at)
    return ReviewResult(file_id=file_id, fingerprint=fingerprint, status=status, reason=stood.reason, review=review,
                        receipt=stood.receipt, written=written, checked=stood.checked if status == store.VALID else None,
                        card_lines=lines, rung=stood.rung, attempts=outcome.attempts,
                        cost_micro_usd=outcome.cost_micro_usd, carried=outcome.carried)


__all__ = ["NOBODY", "ReviewResult", "check", "kept", "recheck", "review_file"]
