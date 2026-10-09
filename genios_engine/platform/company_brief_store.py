"""The company brief's one writer — propose, accept, edit, reject, remove, add (STEP-07).

Every line of a tenant's company brief is a row in `company_brief_lines` (migration 0195), and this is
the only module that writes one. Nothing counts until it is ACCEPTED, and nothing is ever deleted: a
rejected proposal stays rejected, a removed line stays as the line that was removed, with the instant
it stopped counting — so the brief in force at any moment can be rebuilt, and a judgment traced to the
brief it read (`platform/company_brief.brief_for(…, at=…)`).

WHO PROPOSES. The drafter (`reason/brief_drafter`), its weekly diff, a golden case's seed — or the
founder, whose own line is accepted as it is written (`add`). A proposal that repeats a pending or an
accepted line is not written twice; one the founder rejected is not proposed again for
`REJECTED_QUIET_DAYS`, so the weekly review cannot nag.

THE KIND OF WORK (STEP-11, `06` D31, migration 0196). An in-motion line may name its `kind` and its
counterparty (its `address` or `domain`); every write takes them and every read returns them. Accepting
may set, correct or clear either — the founder's edit, as their own words are (`AS_PROPOSED` keeps the
proposal's). An accepted line's kind changes the way its words do: removed, and added again, so the
brief in force at any instant still says what it said then — which is why `add` refuses a line the
brief already holds with another kind (`kind_differs`) rather than answer with the old line's id.

Every function takes the caller's connection and writes inside the caller's transaction, and every
write invalidates this process's cached brief for the tenant (`platform/company_brief.invalidate`).
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.company_brief import WORK_KINDS, CompanyBriefLine
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.company_brief.store")

PROPOSED = "proposed"
ACCEPTED = "accepted"
REJECTED = "rejected"
REMOVED = "removed"
STATUSES: tuple[str, ...] = (PROPOSED, ACCEPTED, REJECTED, REMOVED)

#: The founder's own line — proposed and accepted in one act.
BY_FOUNDER = "founder"
#: How long a rejected line keeps the drafter from proposing it again.
REJECTED_QUIET_DAYS = 90


class _AsProposed:
    """`accept`'s default for a field the founder did not edit — the proposal's own value."""

    def __repr__(self) -> str:
        return "AS_PROPOSED"


#: Pass a kind or a counterparty to `accept` to set or correct it, None to clear it, or leave this
#: default to keep what the proposal said.
AS_PROPOSED: Any = _AsProposed()


class CompanyBriefError(ValueError):
    """A decision the line's state does not allow. `code` is what an API answers with."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _checked(line: CompanyBriefLine) -> CompanyBriefLine:
    """What the contract cannot know without reaching above `platform`: a public mail host
    (`gmail.com`) is never a watchlist domain — anyone can write from it."""
    from genios_engine.platform.self_identity import PUBLIC_MAIL_DOMAINS
    if line.domain and line.domain in PUBLIC_MAIL_DOMAINS:
        raise ValueError(f"{line.domain} is a public mail host — anyone can write from it, so it "
                         "cannot be on a watchlist")
    return line


def _norm(value: str | None) -> str:
    return " ".join(str(value or "").lower().split())


def _invalidate(org_id: str) -> None:
    from genios_engine.platform.company_brief import invalidate
    invalidate(org_id)


def _same_line(conn, org_id: str, line: CompanyBriefLine, *, at: datetime) -> bool:
    """A pending or accepted line that says the same thing, or one rejected within the quiet window."""
    rows = conn.execute(text(
        "select text, address, domain, status, decided_at from company_brief_lines "
        " where org_id = :o and section = :s and status in ('proposed', 'accepted', 'rejected')"),
        {"o": org_id, "s": line.section}).fetchall()
    quiet = at - timedelta(days=REJECTED_QUIET_DAYS)
    for r in rows:
        same = (_norm(r.text) == _norm(line.text)
                or (line.address and r.address == line.address)
                or (line.domain and r.domain == line.domain))
        if not same:
            continue
        if r.status != REJECTED or (r.decided_at is not None and r.decided_at >= quiet):
            return True
    return False


def propose(conn, *, org_id: str, section: str, words: str, proposed_by: str, at: datetime,
            address: str | None = None, domain: str | None = None, kind: str | None = None,
            evidence: Iterable[Mapping[str, Any] | str] = ()) -> str | None:
    """Write one proposal — an in-motion line with the kind of work it names, if any. Returns its
    line id — or None when the brief already says it, or the founder rejected it within
    `REJECTED_QUIET_DAYS`. Raises `ValueError` on a malformed line."""
    line_id = new_id("cbl")
    line = _checked(CompanyBriefLine(line_id=line_id, section=section, text=words,
                                     address=address, domain=domain, kind=kind))
    if _same_line(conn, org_id, line, at=at):
        return None
    conn.execute(text(
        "insert into company_brief_lines (org_id, line_id, section, text, address, domain, kind, "
        " status, proposed_by, evidence, proposed_at) values (:o, :l, :s, :t, :a, :d, :k, "
        " 'proposed', :by, cast(:ev as jsonb), :at)"),
        {"o": org_id, "l": line_id, "s": line.section, "t": line.text, "a": line.address,
         "d": line.domain, "k": line.kind, "by": str(proposed_by), "at": at,
         "ev": json.dumps(list(evidence), sort_keys=True, default=str)})
    _invalidate(org_id)
    return line_id


def _row(conn, org_id: str, line_id: str):
    row = conn.execute(text(
        "select line_id, section, text, address, domain, kind, status from company_brief_lines "
        " where org_id = :o and line_id = :l for update"), {"o": org_id, "l": line_id}).first()
    if row is None:
        raise CompanyBriefError("not_found", f"no company brief line {line_id!r}")
    return row


def _edited(proposed: Any, founder: Any) -> Any:
    return proposed if founder is AS_PROPOSED else founder


def accept(conn, *, org_id: str, line_id: str, decided_by: str, at: datetime,
           words: str | None = None, kind: Any = AS_PROPOSED, address: Any = AS_PROPOSED,
           domain: Any = AS_PROPOSED) -> CompanyBriefLine:
    """Accept a proposal — as written, or as the founder edits it: their own words (`words`, the
    proposal's kept in `proposed_text`), the kind of work, the counterparty's address or domain. A
    field left `AS_PROPOSED` keeps the proposal's; None clears it. Only a pending proposal can be
    accepted, and an edited line is checked as a new one is."""
    row = _row(conn, org_id, line_id)
    if row.status != PROPOSED:
        raise CompanyBriefError("not_pending", f"line {line_id} is already {row.status}")
    words = row.text if words is None else words
    line = _checked(CompanyBriefLine(line_id=line_id, section=row.section, text=words,
                                     address=_edited(row.address, address),
                                     domain=_edited(row.domain, domain),
                                     kind=_edited(row.kind, kind)))
    edited = line.text != row.text
    conn.execute(text(
        "update company_brief_lines set status = 'accepted', text = :t, address = :a, "
        "       domain = :d, kind = :k, "
        "       proposed_text = case when :edited then text else proposed_text end, "
        "       decided_by = :by, decided_at = :at, accepted_at = :at "
        " where org_id = :o and line_id = :l"),
        {"o": org_id, "l": line_id, "t": line.text, "a": line.address, "d": line.domain,
         "k": line.kind, "edited": edited, "by": str(decided_by), "at": at})
    _invalidate(org_id)
    return line


def reject(conn, *, org_id: str, line_id: str, decided_by: str, at: datetime) -> None:
    """Reject a proposal. It stays, rejected — so the drafter does not propose it again soon."""
    row = _row(conn, org_id, line_id)
    if row.status != PROPOSED:
        raise CompanyBriefError("not_pending", f"line {line_id} is already {row.status}")
    conn.execute(text(
        "update company_brief_lines set status = 'rejected', decided_by = :by, decided_at = :at "
        " where org_id = :o and line_id = :l"),
        {"o": org_id, "l": line_id, "by": str(decided_by), "at": at})
    _invalidate(org_id)


def remove(conn, *, org_id: str, line_id: str, decided_by: str, at: datetime) -> None:
    """Take an accepted line out of the brief. It stays, removed, with the instant it stopped."""
    row = _row(conn, org_id, line_id)
    if row.status != ACCEPTED:
        raise CompanyBriefError("not_accepted", f"line {line_id} is {row.status}, not accepted")
    conn.execute(text(
        "update company_brief_lines set status = 'removed', decided_by = :by, removed_at = :at "
        " where org_id = :o and line_id = :l"),
        {"o": org_id, "l": line_id, "by": str(decided_by), "at": at})
    _invalidate(org_id)


def add(conn, *, org_id: str, section: str, words: str, decided_by: str, at: datetime,
        address: str | None = None, domain: str | None = None, kind: str | None = None,
        proposed_by: str = BY_FOUNDER) -> str:
    """The founder's own line, accepted as written — an in-motion line with its kind of work, if it
    names one. A line the brief already holds is not doubled: its id is returned instead — unless the
    founder names it another kind of work, which is refused (`kind_differs`), never dropped: an
    accepted line's kind changes as its words do, removed and added again."""
    line = _checked(CompanyBriefLine(line_id=new_id("cbl"), section=section, text=words,
                                     address=address, domain=domain, kind=kind))
    existing = conn.execute(text(
        "select line_id, kind from company_brief_lines where org_id = :o and section = :s "
        "   and status = 'accepted' and (lower(text) = lower(:t) "
        "        or (cast(:a as text) is not null and address = :a) "
        "        or (cast(:d as text) is not null and domain = :d)) "
        " order by accepted_at limit 1"),
        {"o": org_id, "s": line.section, "t": line.text, "a": line.address,
         "d": line.domain}).first()
    if existing is not None:
        if line.kind is not None and existing.kind != line.kind:
            raise CompanyBriefError(
                "kind_differs",
                f"the brief already holds this as line {existing.line_id}, "
                f"{'as ' + existing.kind if existing.kind else 'naming no kind of work'}; remove it "
                f"and add it again to name it {line.kind}")
        return str(existing.line_id)
    conn.execute(text(
        "insert into company_brief_lines (org_id, line_id, section, text, address, domain, kind, "
        " status, proposed_by, proposed_at, decided_by, decided_at, accepted_at) values "
        "(:o, :l, :s, :t, :a, :d, :k, 'accepted', :pb, :at, :by, :at, :at)"),
        {"o": org_id, "l": line.line_id, "s": line.section, "t": line.text, "a": line.address,
         "d": line.domain, "k": line.kind, "pb": str(proposed_by), "by": str(decided_by),
         "at": at})
    _invalidate(org_id)
    return line.line_id


def _stored_kind(org_id: str, line_id: str, section: str, kind: str | None) -> str | None:
    """A stored kind the contract still takes — or None, said in the log. The column is free text by
    design (0196), so a kind `WORK_KINDS` no longer holds, or one on a line that is not in motion
    (written outside this store), is read as no kind, as `l3_activation.activated_domains` filters a
    domain it has no corpus for: one row never makes the whole brief unreadable."""
    word = str(kind or "").strip().lower()
    if not word:
        return None
    if section == "in_motion" and word in WORK_KINDS:
        return word
    _log.warning("company brief line %s of org=%s (%s) stores the kind %r, which no %s line may "
                 "name — read as no kind of work", line_id, org_id, section, kind, section)
    return None


def accepted(conn, org_id: str, *, at: datetime | None = None) -> list[CompanyBriefLine]:
    """The lines in force — now, or at `at`: accepted by then and not removed by then, each with
    its kind of work. In the order they were accepted, the line id breaking a tie."""
    rows = conn.execute(text(
        "select line_id, section, text, address, domain, kind from company_brief_lines "
        " where org_id = :o and accepted_at is not null "
        "   and (cast(:at as timestamptz) is null or accepted_at <= :at) "
        "   and (removed_at is null or (cast(:at as timestamptz) is not null and removed_at > :at)) "
        " order by accepted_at, line_id"), {"o": org_id, "at": at}).fetchall()
    return [CompanyBriefLine(line_id=r.line_id, section=r.section, text=r.text,
                             address=r.address, domain=r.domain,
                             kind=_stored_kind(org_id, r.line_id, r.section, r.kind))
            for r in rows]


def pending(conn, org_id: str) -> list[dict[str, Any]]:
    """Proposals waiting for the founder, oldest first, each with the kind of work it names and
    what it rests on."""
    rows = conn.execute(text(
        "select line_id, section, text, address, domain, kind, proposed_by, evidence, proposed_at "
        "  from company_brief_lines where org_id = :o and status = 'proposed' "
        " order by proposed_at, line_id"), {"o": org_id}).fetchall()
    return [{"line_id": r.line_id, "section": r.section, "text": r.text, "address": r.address,
             "domain": r.domain, "kind": r.kind, "proposed_by": r.proposed_by,
             "evidence": r.evidence if isinstance(r.evidence, list) else json.loads(r.evidence or "[]"),
             "proposed_at": r.proposed_at.isoformat() if r.proposed_at else None} for r in rows]


__all__ = ["ACCEPTED", "AS_PROPOSED", "BY_FOUNDER", "PROPOSED", "REJECTED", "REJECTED_QUIET_DAYS",
           "REMOVED", "STATUSES", "CompanyBriefError", "accept", "accepted", "add", "pending",
           "propose", "reject", "remove"]
