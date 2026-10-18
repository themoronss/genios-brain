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
the brief store's own rule — a counterparty the brief already holds a pending line for, or one the
founder rejected within `REJECTED_QUIET_DAYS`, so the expert cannot nag.

⛔ CORRECTING AN ACCEPTED KIND (STEP-16, `yc2_w27_s16` M46.C5.L-logic.V2.U03; `03` F157, F132). Until now
an accepted kind could never be proposed as another: the store read the accepted line as "already said",
so F132's programme filed `program` that behaves like the fund behind it stayed `program`. Now a review
whose proposed kind differs from the one an accepted line gives the file writes a proposal that REPLACES
that line (`company_brief_store.propose(replaces=…)`) — the same counterparty, the new kind, labelled
"replacing <kind>" — for you to accept; accepting it removes the old line in the same act. NEVER APPLIED:
nothing changes until you accept. And *"this is not an investor"*, written as your correction of the file,
reaches the kind this way: the expert reads it, its review proposes the kind, and you accept the line.
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


def words_for(kind: str, counterparty: str, why: str, *, replacing: str | None = None) -> str:
    """The proposal's line: the kind, the counterparty, and that the expert proposes it — replacing the
    kind the brief gives the file, when it does — with why; cut at a word to the brief's line length,
    never inside one."""
    by = f"proposed by the expert, replacing {replacing}" if replacing else "proposed by the expert"
    head = f"{kind.capitalize()} · {counterparty} — {by}: "
    room = MAX_LINE_CHARS - len(head)
    why = " ".join(why.split())
    if len(why) > room:
        cut = why[:room - 1].rsplit(" ", 1)[0] if " " in why[:room - 1] else why[:room - 1]
        why = cut.rstrip(" ,;:—-") + "…"
    return head + why


def line_id_for(org_id: str, file: Any, kind: str, fingerprint: str) -> str:
    """The proposal's own line id, from what proposes it — the tenant, the file's counterparty, the
    kind and the review's fingerprint — so a review that proposes mints no id (`03` F170), and a later
    review proposing again after a rejection's quiet window writes a line of its own."""
    from genios_engine.platform.canonical import stable_id
    return stable_id("cbl", {"org": org_id, "counterparty": str(file.counterparty_key or ""),
                             "kind": kind, "review": fingerprint})


#: The file's people's keys — what an in-motion line names them by (`context/workstreams._work_kind`).
_PEOPLE_KEYS = (
    "select canonical_key from graph_nodes where org_id = :o and node_id = any(:ids) and valid_to is null")


def _anchor_domain(key: str) -> str | None:
    key = str(key or "").strip().lower()
    return (key.rsplit("@", 1)[1] if "@" in key else key) or None


def line_giving_the_kind(conn, *, org_id: str, file: Any):
    """The accepted in-motion line that gives the file its kind of work — `context/workstreams._work_kind`'s
    own rule: the FIRST accepted line naming one of the file's people by address, or its anchor's domain or
    a parent of it. None when the file has no kind, or that line is not the one in force."""
    from sqlalchemy import text

    from genios_engine.platform import company_brief_store as store

    addresses = {str(r.canonical_key).strip().lower() for r in conn.execute(
        text(_PEOPLE_KEYS), {"o": org_id, "ids": list(file.people)}) if r.canonical_key}
    key = str(file.counterparty_key or "").strip().lower()
    if "@" in key:
        addresses.add(key)
    domain = _anchor_domain(key)
    for line in store.accepted(conn, org_id):
        if not line.kind or not (line.address or line.domain):
            continue                     # only an in-motion line carries a kind (`_stored_kind`)
        named = ((line.address and line.address in addresses)
                 or (line.domain and domain and (domain == line.domain or domain.endswith("." + line.domain))))
        if named:
            return line if line.kind == file.work_kind else None
    return None


def propose_kind(conn, *, org_id: str, review: ExpertReview, file: Any, fingerprint: str,
                 at: datetime, why: str | None) -> KindProposal:
    """Write the review's proposed kind for `file` (`context/workstreams.WorkFile`) as a pending line of
    the brief — or say why not. `why` is the reason AS CHECKED (`contracts/claim_check.CardWords.kind`,
    M35.C3.L-integration.V2.U05, crosscheck X19): a number the check corrected is the corrected one, and a
    reason the check withheld (None) proposes nothing — the review's raw words are never written."""
    from genios_engine.platform import company_brief_store as store

    pk = review.proposed_kind
    if pk is None:
        return KindProposal(file.file_id, None, None, "the review proposes no kind")
    if pk.kind == file.work_kind:
        return KindProposal(file.file_id, pk.kind, None, f"the brief already names it {pk.kind}")
    if not why:
        return KindProposal(file.file_id, pk.kind, None, "not proposed: its reason did not stand the check")
    key = str(file.counterparty_key or "")
    address, domain = (key, None) if "@" in key else (None, key or None)
    replaced = None
    if file.work_kind:
        # STEP-16 (F157): a correction of the kind an accepted line gives the file — that line's
        # counterparty, the new kind, replacing it when you accept.
        replaced = line_giving_the_kind(conn, org_id=org_id, file=file)
        if replaced is None:
            return KindProposal(file.file_id, pk.kind, None,
                                f"not proposed: no accepted line in force gives the file {file.work_kind}")
        address, domain = replaced.address, replaced.domain
    try:
        line_id = store.propose(
            conn, org_id=org_id, section="in_motion",
            words=words_for(pk.kind, file.counterparty, why, replacing=file.work_kind),
            proposed_by=PROPOSED_BY, at=at, address=address, domain=domain, kind=pk.kind,
            evidence=[{"review": fingerprint, "file": file.file_id, "cites": list(pk.evidence)}],
            line_id=line_id_for(org_id, file, pk.kind, fingerprint),
            replaces=replaced.line_id if replaced is not None else None)
    except ValueError as exc:
        return KindProposal(file.file_id, pk.kind, None, f"not proposed: {exc}")
    if line_id is None:
        return KindProposal(file.file_id, pk.kind, None,
                            "not proposed: the brief already holds a line for this counterparty, or "
                            "the founder rejected one lately")
    if replaced is not None:
        return KindProposal(file.file_id, pk.kind, line_id,
                            f"proposed {pk.kind}, replacing {file.work_kind}, for the founder to accept")
    return KindProposal(file.file_id, pk.kind, line_id, f"proposed {pk.kind} for the founder to accept")


__all__ = ["KindProposal", "PROPOSED_BY", "line_giving_the_kind", "line_id_for", "propose_kind", "words_for"]
