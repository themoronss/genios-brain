"""U09 · the wire that did not exist — residue becomes a question Layer 1 can answer.

⛔ THE MEASUREMENT HALF ALREADY EXISTED. `residue.py` has computed the demand since the day it
shipped: *"the layer measures what it could not explain."* Four kinds, and `signal_unreached`
counts *"the Layer 1 verdicts no Layer 2 reading consumes."* That number reached the model angles —
which ask a model to have an opinion about it — and reached `capture/` never. So the system knew
precisely what it was missing and had no way to go and get it.

This module is the missing half: residue in, `EvidenceNeed` out, written to a table Layer 1 reads.

⛔ AND IT FLOWS THROUGH DATA, NOT AN IMPORT. `context/` is layer 2 and `capture/` is layer 1, so
`context` may import `capture` — but it must not CALL it, because a sweep that fetched inline would
make a graph pass wait on a network. The need is a row; the executor picks it up. That is the same
mechanism `feedback/` uses to reach `reason/`, and `docs/LAYER_MAP.md` names it as the general rule.

⛔ ONLY ONE RESIDUE KIND BECOMES A NEED, AND THE OTHER THREE MUST NOT.

    signal_unreached     → a need. Layer 1 published a verdict no reading consumed: there may be
                           evidence behind it we never fetched.
    node_evidence_unread → NOT a need. The evidence is HELD. Nothing is missing; no reading spoke
                           about it. Fetching more would deliver what we already have.
    ball_in_court        → NOT a need. "They replied and we went quiet" is a fact about US.
    open_loop            → NOT a need. An ask attached to nothing is a linking gap, not an
                           evidence gap.

Raising needs for all four would send Layer 1 fetching for things Layer 1 already delivered — a
backfill with extra steps, and one that would then close itself successfully every time, teaching
the system that its questions are always answered. **The distinction is the whole value of this
module**, and without it the queue is noise.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.contracts.evidence import EvidenceNeed
from genios_engine.context.residue import RESIDUE_SIGNAL

#: ⛔ The closed set of residue kinds that indicate MISSING EVIDENCE rather than a missing reading.
#: See the module docstring for why the other three are excluded; the exclusion is the design.
NEED_WORTHY_KINDS = frozenset({RESIDUE_SIGNAL})

#: What we tell Layer 1 will not settle a question about a signal's source material. A summary of a
#: message is not the message: closing on one would let a paraphrase stand in for the text a span
#: has to be verifiable against.
DEFAULT_UNACCEPTABLE = ("email_summary", "chat_message", "model_paraphrase")


def need_id_for(org_id: str, question: str, subject_ref: str | None) -> str:
    """Deterministic over the org, the question and its subject.

    ⛔ This is what stops the queue growing forever. An unmet need is re-derived on every sweep —
    that is what "unexplained as of the last sweep" means — and without a stable id each sweep would
    file another row. The table would then measure how long we have been waiting rather than what we
    are waiting for.
    """
    material = f"{org_id}|{question.strip().lower()}|{subject_ref or ''}"
    return "en_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def need_from_residue(row: Mapping[str, Any], *, org_id: str,
                      trace_id: str) -> EvidenceNeed | None:
    """One residue row → one need, or `None` when this row is not an evidence question.

    `None` is the common answer and is not a failure: three of the four residue kinds are about a
    missing READING, and no amount of fetching fixes those.
    """
    kind = str(row.get("residue_kind") or "")
    if kind not in NEED_WORTHY_KINDS:
        return None

    subject = row.get("subject_ref") or None
    if not subject:
        # ⛔ A need with no subject cannot be executed OR closed: the executor has nothing to fetch
        # for and no way to know when it has. Better refused here than filed as a row that sits
        # open forever — which is the exact state this whole step exists to end.
        return None

    detail = row.get("detail") if isinstance(row.get("detail"), Mapping) else {}
    signal_type = str(detail.get("signal_type") or "").strip()
    named = f" ({signal_type})" if signal_type else ""

    question = (f"Layer 1 published a verdict about {subject}{named} that no reading consumed. "
                f"Is there source material behind it we have not fetched?")
    why = ("A published verdict nobody read is either evidence we never fetched or a reading we "
           "never wrote. Fetching settles which, and only one of the two is fixable here.")

    return EvidenceNeed(
        need_id=need_id_for(org_id, question, str(subject)),
        org_id=org_id,
        trace_id=trace_id,
        question=question,
        why_it_matters=why,
        subject_ref=str(subject),
        # Left open deliberately: we do not know which connector holds it, and an enumerated list
        # would refuse the answer from a source nobody anticipated. The NEGATIVE list is what does
        # the work here.
        acceptable_sources=(),
        unacceptable_sources=DEFAULT_UNACCEPTABLE,
        window_from=row.get("first_seen_at"),
        window_to=row.get("last_seen_at"),
    )


def needs_from_residue(rows: Sequence[Mapping[str, Any]], *, org_id: str,
                       trace_id: str) -> list[EvidenceNeed]:
    """A residue queue → the needs worth asking, de-duplicated by id.

    Two residue rows about one subject produce one need, because they are one question. Filing both
    would have the executor fetch twice for the same answer and charge the tenant for it.
    """
    seen: dict[str, EvidenceNeed] = {}
    for row in rows:
        need = need_from_residue(row, org_id=org_id, trace_id=trace_id)
        if need is not None:
            seen.setdefault(need.need_id, need)
    return list(seen.values())


__all__ = ["DEFAULT_UNACCEPTABLE", "NEED_WORTHY_KINDS", "need_from_residue", "need_id_for",
           "needs_from_residue"]
