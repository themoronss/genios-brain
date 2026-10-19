"""GeniOS-008 L2 R8 · the Evidence Coordinator — L2 asks L1 for the one fact, and re-enters ONCE.

Both ends existed and nothing joined them: `contracts/evidence.EvidenceNeed` and its queue
(`context/evidence_need_store`) on one side, L1's executor (`capture/acquire/need_executor`, worked from
`reason/domain_shadow.work_the_needs`) on the other — and only L3 ever raised a need. L2, the layer the
contract's own docstring says it is for ("L2 → L1 · the one fact that would change the conclusion"), never
did. This is the middle:

  RAISE      a need the model marks `decision_changing` becomes one `EvidenceNeed`, its id derived from
             the subject and the question — the same question on the next sweep is the same row, and the
             store's `on conflict do nothing` keeps a closed question closed. A need that would NOT change
             the answer is not asked: fetching for it would spend the tenant's budget on curiosity.
  RE-ENTER   when a need this pass raised closes `met`, the subject is reasoned again, ONCE: the need's
             state is a fingerprint input, so the run after the answer is a new fingerprint and the run after
             that is not. `unavailable` closes the question with its reason and never loops.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta

from sqlalchemy import text

from genios_engine.contracts.evidence import EvidenceNeed
from genios_engine.contracts.reasoning_result import ReasoningResult, stable_ref

#: The prefix that marks a need L2 raised — so the re-entry read finds L2's own questions only.
NEED_PREFIX = "l2need"
#: How long a question stays worth answering. After it, the answer would land after the work moved on.
NEED_TTL = timedelta(days=7)
#: What one question may cost L1 to answer — `capture/acquire/evidence_need.MIN_FETCH_USD` is the floor.
NEED_MAX_USD = 0.05
#: A run asks at most this many — the ones that would change the answer most are the model's first.
MAX_NEEDS_PER_RUN = 2

_STATES = text("select need_id, state from evidence_needs where org_id = :o and need_id = any(:ids)")
_MET_SINCE = text(
    "select need_id from evidence_needs where org_id = :o and state = 'met' and need_id like :p "
    "   and (cast(:since as timestamptz) is null or closed_at > cast(:since as timestamptz))")
_ASKED_BY = text(
    "select subject_ref, fingerprint, bundle_ids from reasoning_results "
    " where org_id = :o and receipt -> 'needs_raised' ? :need order by reasoned_at desc limit 1")


def need_id_for(org_id: str, subject_ref: str, question: str) -> str:
    return stable_ref(NEED_PREFIX, {"org": org_id, "subject": subject_ref,
                                    "question": " ".join(question.lower().split())})


def needs_from(result: ReasoningResult, *, org_id: str, trace_id: str, eval_time: datetime) -> list[EvidenceNeed]:
    """The decision-changing needs of one result, as the queue's contract. Pure."""
    out: list[EvidenceNeed] = []
    for raised in [n for n in result.evidence_needs if n.decision_changing][:MAX_NEEDS_PER_RUN]:
        unacceptable = tuple(s for s in raised.unacceptable_sources if s not in raised.acceptable_sources)
        out.append(EvidenceNeed(
            need_id=need_id_for(org_id, result.subject_ref, raised.question), org_id=org_id, trace_id=trace_id,
            question=raised.question, why_it_matters=raised.why_it_matters, subject_ref=raised.subject_ref,
            acceptable_sources=tuple(raised.acceptable_sources), unacceptable_sources=unacceptable,
            max_cost_usd=NEED_MAX_USD, expires_at=eval_time + NEED_TTL))
    return out


def need_states(conn, org_id: str, need_ids: Iterable[str]) -> dict[str, str]:
    ids = sorted(set(need_ids))
    if not ids:
        return {}
    return {str(r.need_id): str(r.state) for r in conn.execute(_STATES, {"o": org_id, "ids": ids})}


def reentries(conn, org_id: str, *, since: datetime | None) -> list[tuple[str, tuple[str, ...]]]:
    """The subjects whose L2 need was MET since `since`: (subject, the bundles its asking run read)."""
    out: dict[str, tuple[str, ...]] = {}
    for row in conn.execute(_MET_SINCE, {"o": org_id, "p": f"{NEED_PREFIX}:%", "since": since}):
        asked = conn.execute(_ASKED_BY, {"o": org_id, "need": str(row.need_id)}).first()
        if asked is not None and asked.subject_ref not in out:
            bundles = asked.bundle_ids if isinstance(asked.bundle_ids, list) else []
            out[str(asked.subject_ref)] = tuple(str(b) for b in bundles)
    return sorted(out.items())


def ids_of(needs: Sequence[EvidenceNeed]) -> tuple[str, ...]:
    return tuple(n.need_id for n in needs)


__all__ = ["MAX_NEEDS_PER_RUN", "NEED_MAX_USD", "NEED_PREFIX", "NEED_TTL", "ids_of", "need_id_for",
           "need_states", "needs_from", "reentries"]
