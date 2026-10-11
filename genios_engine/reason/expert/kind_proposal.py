"""The expert proposes a file's kind of work — a line of the brief the founder accepts or rejects (STEP-12).

`speedrun008/YC-II W27/03` F132 and F151, tree `yc2_w27_s12` M32.C3.L-logic.V2.U08. A file's kind of work
comes from the brief: an accepted in-motion line names it, and the founder accepts the line (`06` D31).
Two kinds of file are filed wrong by their mail alone — a fund that liked the demo reads as a sales
opportunity (F151, case F53), an investor-run programme behaves like the fund behind it (F132) — and
the expert, reading the whole file, may see it. So a valid review may PROPOSE a kind
(`ExpertReview.proposed_kind`), and this writes that proposal where every proposal of the brief lives:
a pending in-motion line (`platform/company_brief_store.propose`), its counterparty's address or domain,
its kind, labelled — the words say the expert proposes it, `proposed_by` is `expert_review`, and the
evidence names the review and what it cites. NEVER A KIND THE ENGINE APPLIES: nothing changes until the
founder accepts the line.

Not proposed: a review that proposes nothing, or the kind the brief already gives the file; and —
the brief store's own rule — a counterparty the brief already holds a pending or accepted line for, or
one the founder rejected within `REJECTED_QUIET_DAYS`, so the expert cannot nag. ⛔ That rule also means
a kind the founder ACCEPTED is never re-proposed as another kind: correcting an accepted kind (F132's
programme already filed `program`) is the founder's own edit, and stays open (`03` F157).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.company_brief import MAX_LINE_CHARS
from genios_engine.contracts.expert_review import ExpertReview

#: Who a proposal of the expert's is from, in `company_brief_lines.proposed_by`.
PROPOSED_BY = "expert_review"


@dataclass(frozen=True, slots=True)
class KindProposal:
    file_id: str
    kind: str | None             # the kind the review proposed, if any
    line_id: str | None          # the brief's pending line, when one was written
    says: str                    # what happened, in words


def words_for(kind: str, counterparty: str, why: str) -> str:
    """The proposal's line: the kind, the counterparty, and that the expert proposes it, with why — cut
    at a word to the brief's line length, never inside one."""
    head = f"{kind.capitalize()} · {counterparty} — proposed by the expert: "
    room = MAX_LINE_CHARS - len(head)
    why = " ".join(why.split())
    if len(why) > room:
        cut = why[:room - 1].rsplit(" ", 1)[0] if " " in why[:room - 1] else why[:room - 1]
        why = cut.rstrip(" ,;:—-") + "…"
    return head + why


def propose_kind(conn, *, org_id: str, review: ExpertReview, file: Any, fingerprint: str,
                 at: datetime) -> KindProposal:
    """Write the review's proposed kind for `file` (`context/workstreams.WorkFile`) as a pending line of
    the brief — or say why not."""
    from genios_engine.platform import company_brief_store as store

    pk = review.proposed_kind
    if pk is None:
        return KindProposal(file.file_id, None, None, "the review proposes no kind")
    if pk.kind == file.work_kind:
        return KindProposal(file.file_id, pk.kind, None, f"the brief already names it {pk.kind}")
    key = str(file.counterparty_key or "")
    address, domain = (key, None) if "@" in key else (None, key or None)
    try:
        line_id = store.propose(
            conn, org_id=org_id, section="in_motion", words=words_for(pk.kind, file.counterparty, pk.why),
            proposed_by=PROPOSED_BY, at=at, address=address, domain=domain, kind=pk.kind,
            evidence=[{"review": fingerprint, "file": file.file_id, "cites": list(pk.evidence)}])
    except ValueError as exc:
        return KindProposal(file.file_id, pk.kind, None, f"not proposed: {exc}")
    if line_id is None:
        return KindProposal(file.file_id, pk.kind, None,
                            "not proposed: the brief already holds a line for this counterparty, or "
                            "the founder rejected one lately")
    return KindProposal(file.file_id, pk.kind, line_id, f"proposed {pk.kind} for the founder to accept")


__all__ = ["KindProposal", "PROPOSED_BY", "propose_kind", "words_for"]
