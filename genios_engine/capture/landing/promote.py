"""Promotion out of the archive — the half STEP-03 handed to STEP-05.

The gate archives what a noise rule or the AI filter calls noise: kept, encrypted for 180 days, read by
no model (`capture/attention`, STEP-03). Boardy's introductions are archived on their unsubscribe header
(N-02) — and they are the one place Pankaj, Silas and Ori are named with what they do. Since STEP-05 an
archive enters memory as names and dates only (`context/memory_lanes`); promotion is how its WORDS get
read: the mail goes back to the ledger as KEPT — `emitted`, attention `deep`, `promoted:<rule>` — and the
re-read ladder (`capture/landing/unread.queue_unread`) reads it on the next pass, through the gate as a
re-read, so the rule that archived it does not archive it again (`capture/gate`, W-06).

NEVER A MODEL'S GUESS. A promotion names the rule that archived the mail — its `attention_reason` —
narrowed, if asked, to one sender domain, and is started by an operator (`scripts/promote_archived.py`)
or, once STEP-07 writes the company brief, by a connector the brief names. Dry run first: without
`apply` it only counts, and lists what it would promote by event, date and sender domain — never a
subject or a body (`03` F37, F57). An archive past its keep window has nothing left to read; it is
counted and left archived.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.capture.gate.rules import REASON_LABELS

#: The codes the gate ARCHIVES with: the noise rules (N-05 is the availability notice, which is read,
#: never archived) and the model's confident junk.
ARCHIVE_CODES: frozenset[str] = frozenset(
    {code for code in REASON_LABELS if code.startswith("N-") and code != "N-05"} | {"llm_junk"})
#: How many promoted events a report lists.
SAMPLE = 20

_ARCHIVED_BY = text(
    "select se.event_id, se.occurred_at, "
    "       split_part(lower(coalesce(se.actor->>'email', '')), '@', 2) as sender_domain, "
    "       (rp.event_id is not null and (rp.expires_at is null or rp.expires_at > :now)) "
    "           as readable "
    "  from source_events se "
    "  left join raw_payloads rp on rp.event_id = se.event_id and rp.org_id = se.org_id "
    " where se.org_id = :o and se.outcome = 'archived' and se.attention_reason = :rule "
    "   and (cast(:domain as text) is null "
    "        or split_part(lower(coalesce(se.actor->>'email', '')), '@', 2) = :domain) "
    " order by se.occurred_at desc, se.event_id")

_PROMOTE = text(
    "update source_events set outcome = 'emitted', attention = 'deep', "
    "       attention_reason = 'promoted:' || :rule, "
    "       route = coalesce(route, 'needs_extraction'), triage_lane = coalesce(triage_lane, 'P3') "
    " where org_id = :o and outcome = 'archived' and event_id = any(:ids)")


@dataclass(frozen=True)
class Promotion:
    """What one promotion found and did. `sample` is `(event_id, occurred_at, sender_domain)` —
    the ledger's columns, never the mail's words."""
    rule: str
    sender_domain: str | None
    archived: int
    unreadable: int
    promoted: int
    sample: tuple[tuple[str, str, str], ...]


def promote_archived(engine, org_id: str, *, rule: str, sender_domain: str | None = None,
                     apply: bool = False, now: datetime | None = None) -> Promotion:
    """Put one tenant's mail archived by `rule` (and, if given, sent from `sender_domain`) back in
    the ledger as kept, for the re-read ladder to read. A dry run unless `apply`."""
    if rule not in ARCHIVE_CODES:
        raise ValueError(f"{rule!r} is not a code the gate archives with — one of "
                         f"{sorted(ARCHIVE_CODES)}")
    domain = (sender_domain or "").strip().lower().lstrip("@") or None
    now = now or datetime.now(timezone.utc)
    with engine.connect() as c:
        rows = c.execute(_ARCHIVED_BY, {"o": org_id, "rule": rule, "domain": domain,
                                        "now": now}).fetchall()
    readable = [r for r in rows if r.readable]
    promoted = 0
    if apply and readable:
        with engine.begin() as c:
            promoted = c.execute(_PROMOTE, {"o": org_id, "rule": rule,
                                            "ids": [r.event_id for r in readable]}).rowcount
    return Promotion(rule=rule, sender_domain=domain, archived=len(readable),
                     unreadable=len(rows) - len(readable), promoted=promoted,
                     sample=tuple((r.event_id, r.occurred_at.isoformat(), r.sender_domain)
                                  for r in readable[:SAMPLE]))


__all__ = ["ARCHIVE_CODES", "Promotion", "promote_archived"]
