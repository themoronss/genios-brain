"""U04 · a hold that asks — a held situation names the evidence that would free it.

`situation_publisher` HOLDs a candidate and records why. Today that is where it ends: the reason is
written to a ledger, the candidate waits, and nothing goes and gets the thing that would clear it. On
the pilot, 504 held against 28 admitted. Every one of those holds is a question nobody asked.

This module turns the ones that ARE evidence questions into `EvidenceNeed` rows, which
`capture/acquire/evidence_need.py` executes. Same door `residue` uses — see `evidence_needs.py`.

⛔ THREE OF SEVEN HOLD REASONS, AND THE EXCLUSIONS ARE THE DESIGN.

    qes_required                 → a need   ) ⛔ ONE need between them, not two. See below.
    verified_evidence_required   → a need   )
    source_coverage_insufficient → a need     — names a source whose coverage is short
    ---
    conflict_open                → NOT. Two incompatible facts are BOTH held. More evidence does
                                   not resolve a contradiction; an authority ruling does. Fetching
                                   would add a third fact to a disagreement between two.
    cross_domain_contradiction   → NOT. The same shape one layer up: two domains claiming opposite
                                   things about one subject. Neither is short of evidence.
    identity_review_required     → NOT. "Are these two people the same person" is a judgement about
                                   records we already hold, not a document we are missing.
    pattern_evidence_required    → NOT. The PATTERN LIBRARY lacks a rule. That is our gap, not the
                                   tenant's — fetching their documents cannot supply our rule, and
                                   the need would close successfully every time while the situation
                                   stayed held, teaching the system that its questions are answered.

⛔ AND `qes_required` + `verified_evidence_required` ARE ONE QUESTION. The codebase already proved
this and wrote the numbers down — `situation_bso.l1_refusal` and `_preflight`:

    "480 of those holds carry `qes_required` AND `verified_evidence_required` — the exact pair this
     function exists to clear. ... which reads like two independent defects. It is one: both are
     downstream of `l1` being `None`. Feeding the bundle clears both."

So the pair collapses. Filing two needs for 480 situations would put 960 rows in the queue for 480
questions, have Layer 1 fetch twice for one answer, and charge the tenant for both — the same
"one question, one fetch, one charge" rule `needs_from_residue` enforces, at a seam where the
duplication is measured rather than hypothetical.

⛔ AND IT FLOWS THROUGH DATA. This module never calls `capture/`. A publication pass that fetched
inline would make admission wait on a network. `docs/LAYER_MAP.md` records the rule.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.context.evidence_needs import DEFAULT_UNACCEPTABLE, need_id_for
from genios_engine.context.situation_publisher import HoldReason
from genios_engine.contracts.evidence import EvidenceNeed

#: ⛔ The two hold reasons that are ONE question. Kept as a set rather than two branches so the
#: collapse is a fact about the data and not a coincidence of control flow.
L1_EVIDENCE_HOLDS = frozenset({HoldReason.QES_REQUIRED.value,
                               HoldReason.VERIFIED_EVIDENCE_REQUIRED.value})

#: The coverage hold, which asks a different question: not "did Layer 1 publish" but "did we look at
#: all of it". A need for it names the source, because coverage is per-source and never blended.
COVERAGE_HOLD = HoldReason.SOURCE_COVERAGE_INSUFFICIENT.value

#: ⛔ The closed set of holds that are evidence questions. The four absent members are absent on
#: purpose; the module docstring says why for each, one at a time.
NEED_WORTHY_HOLDS = frozenset(L1_EVIDENCE_HOLDS | {COVERAGE_HOLD})

#: The two questions this module can ask. Fewer than the reasons above, and that is the point.
NEED_L1_EVIDENCE = "l1_evidence"
NEED_COVERAGE = "coverage"


def subject_for_hold(candidate: Any) -> str | None:
    """A reference the Layer 1 executor can actually act on, or `None`.

    Preference order, and it is a cost order: a document re-extraction is cheaper and more targeted
    than re-reading a window, so a span that names a document wins.

        chunk:<doc_id>:<n>  →  document:<doc_id>   →  REEXTRACT
        (otherwise)         →  signal:<signal_id>  →  BACKFILL_WINDOW

    ⛔ A `prepared_content:<event_id>` span is deliberately NOT mapped to `thread:<...>`. An event id
    is not a thread id, and inventing that mapping would file a need whose fetch names a thread that
    does not exist — a need that can never be met and never honestly closed.
    """
    for span in getattr(candidate, "evidence", ()) or ():
        if not isinstance(span, Mapping):
            continue
        ref = str(span.get("source_ref") or "")
        if ref.startswith("chunk:"):
            parts = ref.split(":")
            if len(parts) >= 2 and parts[1].strip():
                return f"document:{parts[1].strip()}"

    for signal_id in getattr(candidate, "signal_ids", ()) or ():
        if str(signal_id).strip():
            return f"signal:{str(signal_id).strip()}"

    # ⛔ Refused rather than filed. A need with no subject cannot be executed OR closed — the
    # executor has nothing to fetch for and no way to know when it is done — so it would sit open
    # forever, which is the exact state this step exists to end.
    return None


def _coverage_gap(reasons: Sequence[str]) -> str | None:
    """Which source the coverage hold was short on, when the reason says so.

    Coverage is measured per source and never blended, so a coverage need that cannot name the
    source is asking "fetch more of everything" — which is a backfill wearing a need's clothes.
    """
    for reason in reasons:
        text = str(reason)
        if text.startswith(COVERAGE_HOLD + ":"):
            named = text.split(":", 1)[1].strip()
            if named:
                return named
    return None


def _l1_need(candidate: Any, subject: str, *, trace_id: str) -> EvidenceNeed:
    question = (f"Layer 1 published no qualified signal with a verified span for {subject}. "
                f"Is there source material behind it we have not fetched or not re-extracted?")
    why = ("The situation is held and cannot publish without it. Both hold reasons are downstream of "
           "one missing bundle, so one answer clears both — and if the answer is that no such "
           "evidence exists, the card can say so instead of going quiet.")
    return EvidenceNeed(
        need_id=need_id_for(candidate.org_id, question, subject),
        org_id=candidate.org_id,
        trace_id=trace_id,
        question=question,
        why_it_matters=why,
        subject_ref=subject,
        # Left open on purpose, as in `evidence_needs`: we do not know which connector holds it, and
        # an enumerated list would refuse an answer from a source nobody anticipated.
        acceptable_sources=(),
        # ⛔ A paraphrase can never close this one. The hold is specifically about a VERIFIED SPAN,
        # and a span has to be checkable byte-for-byte against source text. A summary of a message
        # is not the message.
        unacceptable_sources=DEFAULT_UNACCEPTABLE,
    )


def _coverage_need(candidate: Any, subject: str, *, trace_id: str,
                   source: str | None) -> EvidenceNeed:
    named = source or "an unnamed source"
    question = (f"Coverage of {named} is insufficient for {subject}. Can the uncovered part of that "
                f"source be fetched, or is it genuinely unavailable?")
    why = ("An empty result over an unmeasured slice reported as a fact about the business is the "
           "failure coverage exists to prevent. Either the slice gets measured or the card has to "
           "say which part it could not see.")
    return EvidenceNeed(
        need_id=need_id_for(candidate.org_id, question, subject),
        org_id=candidate.org_id,
        trace_id=trace_id,
        question=question,
        why_it_matters=why,
        subject_ref=subject,
        # ⛔ Narrowed to the named source when we have it. A coverage need answered from a DIFFERENT
        # source has not improved that source's coverage at all — it has only made the gap harder to
        # see, because something arrived and the hold cleared.
        acceptable_sources=(source,) if source else (),
        unacceptable_sources=DEFAULT_UNACCEPTABLE,
    )


def needs_from_hold(candidate: Any, reasons: Sequence[str], *,
                    trace_id: str) -> list[EvidenceNeed]:
    """One held candidate and its hold reasons → the needs worth asking. Often empty.

    Empty is a normal answer, not a failure: four of the seven hold reasons are not evidence
    questions, and a situation held only on those must keep waiting for a ruling, not a fetch.
    """
    plain = {str(r).split(":", 1)[0] for r in reasons}
    worthy = plain & NEED_WORTHY_HOLDS
    if not worthy:
        return []

    subject = subject_for_hold(candidate)
    if subject is None:
        return []

    out: list[EvidenceNeed] = []
    if worthy & L1_EVIDENCE_HOLDS:
        # ⛔ ONE need whether one of the pair fired or both. See the module docstring: on the pilot
        # 480 of 504 holds carry both, and they are one question.
        out.append(_l1_need(candidate, subject, trace_id=trace_id))
    if COVERAGE_HOLD in worthy:
        out.append(_coverage_need(candidate, subject, trace_id=trace_id,
                                  source=_coverage_gap(reasons)))
    return out


def needs_from_holds(held: Sequence[tuple[Any, Sequence[str]]], *,
                     trace_id: str) -> list[EvidenceNeed]:
    """A sweep's worth of holds → the needs worth asking, de-duplicated by id.

    Two situations held on the same subject for the same reason are one question. Filing both would
    have the executor fetch twice for one answer and charge the tenant for it.
    """
    seen: dict[str, EvidenceNeed] = {}
    for candidate, reasons in held:
        for need in needs_from_hold(candidate, reasons, trace_id=trace_id):
            seen.setdefault(need.need_id, need)
    return list(seen.values())


__all__ = ["COVERAGE_HOLD", "L1_EVIDENCE_HOLDS", "NEED_COVERAGE", "NEED_L1_EVIDENCE",
           "NEED_WORTHY_HOLDS", "needs_from_hold", "needs_from_holds", "subject_for_hold"]
