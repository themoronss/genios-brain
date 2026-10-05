"""Mail captured while a tenant's Layer 1 was switched off, read again once it is on.

MEASURED ON PRODUCTION 2026-09-13. A tenant signed up, connected Gmail and synced two months:
375 events were emitted and none was ever extracted, because `l1_semantic_activation` had no row
for it. Switching the tenant on afterwards changed nothing for that mail. A re-sync fetches the
same messages, `land_raw_object` finds their dedup keys already in the ledger and returns
`duplicate` before the semantic lane is reached — so the only way back was wiping the org.

THIS MODULE IS THE WAY BACK, FROM WHAT IS ALREADY STORED. An event qualifies when it was emitted
BEFORE the tenant's L1 was switched on and nothing downstream ever touched it: no extraction, no
active qualified signal, no L2 run. Its payload is decrypted and rebuilt into the `RawObject` it
arrived as, and the caller captures that object again through the ordinary door.

STORE, DON'T DELETE. The old row is not removed. `set_aside` marks it `superseded` and moves its
dedup key out of the way so the new capture can land; `restore` puts back every row whose object
did not land again, so a failed re-read loses nothing and is simply tried on the next pass.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import bindparam, text

from genios_engine.capture.connectors.base import RawObject
from genios_engine.contracts.source_event import compute_dedup_key
from genios_engine.platform.crypto import decrypt
from genios_engine.platform.logging import get_logger

logger = get_logger(__name__)

SUPERSEDED = "superseded"
_MARK = "#superseded:"

_FIND = text(
    "select se.event_id, se.connection_id, se.source, se.object_type, se.source_object_id, "
    "       se.parent_object_id, se.dedup_key, se.actor, se.recipients, se.internal_kind, "
    "       se.occurred_at, rp.enc_content "
    "  from source_events se "
    "  join l1_semantic_activation a on a.org_id = se.org_id and a.disabled_at is null "
    "  join raw_payloads rp on rp.event_id = se.event_id and rp.org_id = se.org_id "
    " where se.org_id = :o and se.outcome = 'emitted' "
    "   and se.captured_at < a.enabled_at "
    "   and (rp.expires_at is null or rp.expires_at > now()) "
    "   and not exists (select 1 from l1_extraction_results x "
    "                    where x.org_id = se.org_id and x.event_id = se.event_id) "
    "   and not exists (select 1 from qualified_signals q "
    "                    where q.org_id = se.org_id and q.event_id = se.event_id "
    "                      and q.state = 'active') "
    "   and not exists (select 1 from l2_processing_runs r "
    "                    where r.org_id = se.org_id and r.event_id = se.event_id) "
    " order by se.occurred_at desc "
    " limit :lim")

_SET_ASIDE = text(
    "update source_events set outcome = :sup, dedup_key = dedup_key || :mark || event_id "
    " where org_id = :o and outcome = 'emitted' and event_id in :ids"
).bindparams(bindparam("ids", expanding=True))

# Only a row whose original key is still free goes back: a key that is taken belongs to the new
# capture of the same object, and that row is now the live one.
_RESTORE = text(
    "update source_events se set outcome = 'emitted', "
    "       dedup_key = split_part(se.dedup_key, :mark, 1) "
    " where se.org_id = :o and se.outcome = :sup and se.event_id in :ids "
    "   and not exists (select 1 from source_events n where n.org_id = se.org_id "
    "                    and n.dedup_key = split_part(se.dedup_key, :mark, 1))"
).bindparams(bindparam("ids", expanding=True))


# A pass that died between `set_aside` and `restore` (a deploy, a crash) leaves rows `superseded`
# with their original key still free, and `find_unread` only reads `emitted` — so without this they
# would never be read again. The chain holds the org's run lease, so when a pass STARTS no other
# re-read for the org is in flight and every such row is an orphan.
_RECOVER = text(
    "update source_events se set outcome = 'emitted', "
    "       dedup_key = split_part(se.dedup_key, :mark, 1) "
    " where se.org_id = :o and se.outcome = :sup "
    "   and not exists (select 1 from source_events n where n.org_id = se.org_id "
    "                    and n.dedup_key = split_part(se.dedup_key, :mark, 1))")


def recover_orphans(engine, org_id: str) -> int:
    """Put back every row an interrupted pass set aside and never re-landed. Call only at the
    start of a pass, under the org's run lease. Returns how many."""
    with engine.begin() as c:
        return c.execute(_RECOVER, {"o": org_id, "sup": SUPERSEDED, "mark": _MARK}).rowcount


def find_unread(engine, org_id: str, *, limit: int = 200) -> list[Any]:
    """Events emitted while this tenant's L1 was off that nothing downstream has read yet.

    An event whose dedup key carries a content version (a calendar event, a CRM record) is left
    out: rebuilding it without that version would land it under a different key, and the next poll
    would land it a third time.
    """
    with engine.connect() as c:
        rows = c.execute(_FIND, {"o": org_id, "lim": int(limit)}).fetchall()
    return [r for r in rows
            if compute_dedup_key(r.source, r.object_type, r.source_object_id, None) == r.dedup_key]


def to_raw_object(row: Any, crypto_key: str) -> RawObject | None:
    """The `RawObject` this event was captured from: the stored payload plus the ledger columns.
    None when the payload cannot be decrypted or parsed — that row is skipped, not guessed."""
    try:
        payload = json.loads(decrypt(bytes(row.enc_content), crypto_key)) if row.enc_content else {}
    except Exception:      # noqa: BLE001 — an unreadable payload is a skip, never a crash
        logger.warning("unread: payload unreadable event=%s", row.event_id)
        return None
    if not isinstance(payload, dict):
        return None
    actor = row.actor if isinstance(row.actor, dict) else json.loads(row.actor or "{}")
    occurred = row.occurred_at
    if occurred is not None and occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=timezone.utc)
    return RawObject(
        source=row.source, object_type=row.object_type, source_object_id=row.source_object_id,
        occurred_at=occurred, actor_email=actor.get("email"), actor_name=actor.get("name"),
        actor_type=actor.get("type") or "external_contact",
        parent_object_id=row.parent_object_id, internal_kind=row.internal_kind,
        recipients=tuple(row.recipients or ()), raw=payload)


def set_aside(engine, org_id: str, event_ids: list[str]) -> int:
    """Mark the old rows `superseded` and free their dedup keys for the new capture."""
    if not event_ids:
        return 0
    with engine.begin() as c:
        return c.execute(_SET_ASIDE, {"o": org_id, "sup": SUPERSEDED, "mark": _MARK,
                                      "ids": list(event_ids)}).rowcount


def restore(engine, org_id: str, event_ids: list[str]) -> int:
    """Put back every set-aside row whose object did not land again. Returns how many."""
    if not event_ids:
        return 0
    with engine.begin() as c:
        return c.execute(_RESTORE, {"o": org_id, "sup": SUPERSEDED, "mark": _MARK,
                                    "ids": list(event_ids)}).rowcount


# =================================================================================================
# STEP-18 B18 · A PARKED EXTRACTION IS READ AGAIN — through the same door, under a bounded ladder
# =================================================================================================
#
# The extractor parks a message when the model's answer cannot be used (`capture/semantic/
# extractor.py` `PARK_*`). The event is already `emitted` and its payload is kept, so the parked
# drain's own recovery — flipping `outcome` — changes nothing, and until this pass nothing read
# them again: two mails on the design partner's org waited at `pending` from 3 Oct with zero
# attempts. They are re-landed exactly like unread mail (set aside → capture again → restore what
# did not land), so the second read is the first read's code path, not a parallel one.
#
# ⛔ THE LADDER FOLLOWS THE MESSAGE, NOT THE EVENT. A re-land mints a new event; if its extraction
# parks again, that is a NEW park row for the same message. So the attempt count is the number of
# extraction parks the message has accumulated — it can only go up — and a message is given up at
# `MAX_EXTRACTION_ATTEMPTS` with its last reason, never retried for ever on a model that keeps
# answering badly. A re-land that did not land at all advances its own row's counter instead, so
# that path is bounded too.

#: The extractor's park codes — the drain's `NEEDS_REEXTRACTION`, kept in one place.
from genios_engine.capture.parked.drain import NEEDS_REEXTRACTION  # noqa: E402

#: How many times a message's extraction may park before it is given up.
MAX_EXTRACTION_ATTEMPTS = 3
#: The wait before a parked message is read again: one hour, doubling with each park it has had.
EXTRACTION_RETRY_BASE = timedelta(hours=1)
#: The park status for the row whose event a later copy replaced.
PARK_SUPERSEDED = "superseded"

_FIND_PARKED = text(
    "select se.event_id, se.connection_id, se.source, se.object_type, se.source_object_id, "
    "       se.parent_object_id, se.dedup_key, se.actor, se.recipients, se.internal_kind, "
    "       se.occurred_at, rp.enc_content, pe.created_at as parked_at, "
    "       pe.refetch_attempts as row_attempts, pe.refetch_next_attempt_at as next_attempt_at, "
    "       (select count(*) from parked_events p2 "
    "          join source_events s2 on s2.org_id = p2.org_id and s2.event_id = p2.event_id "
    "         where p2.org_id = se.org_id and s2.source = se.source "
    "           and s2.source_object_id = se.source_object_id "
    "           and p2.reason_code in :codes) as message_parks "
    "  from source_events se "
    "  join parked_events pe on pe.org_id = se.org_id and pe.event_id = se.event_id "
    "  join raw_payloads rp on rp.event_id = se.event_id and rp.org_id = se.org_id "
    " where se.org_id = :o and se.outcome = 'emitted' "
    "   and pe.status = 'pending' and pe.reason_code in :codes "
    "   and (rp.expires_at is null or rp.expires_at > :now) "
    "   and not exists (select 1 from l1_extraction_results x "
    "                    where x.org_id = se.org_id and x.event_id = se.event_id) "
    " order by se.occurred_at desc "
    " limit :lim").bindparams(bindparam("codes", expanding=True))

_SUPERSEDE_PARK = text(
    "update parked_events pe set status = :status "
    " where pe.org_id = :o and pe.status = 'pending' and pe.event_id in :ids "
    "   and exists (select 1 from source_events se where se.org_id = pe.org_id "
    "               and se.event_id = pe.event_id and se.outcome = :sup)"
).bindparams(bindparam("ids", expanding=True))

_ADVANCE_PARK = text(
    "update parked_events set refetch_attempts = refetch_attempts + 1, "
    "       refetch_first_attempt_at = coalesce(refetch_first_attempt_at, :now), "
    "       refetch_last_attempt_at = :now, refetch_next_attempt_at = :next "
    " where org_id = :o and event_id = :e and status = 'pending'")

_GIVE_UP = text(
    "update parked_events set status = 'dead_letter', refetch_next_attempt_at = null, "
    "       refetch_last_error = :why "
    " where org_id = :o and event_id = :e and status = 'pending'")


def _retry_wait(attempts: int) -> timedelta:
    return EXTRACTION_RETRY_BASE * (2 ** max(0, attempts - 1))


def find_parked_extractions(engine, org_id: str, *, limit: int = 50,
                            now: datetime | None = None) -> list[Any]:
    """Emitted events whose extraction parked, whose payload is kept, and that are due again.

    Due means: the message has parked fewer than `MAX_EXTRACTION_ATTEMPTS` times, this row's own
    re-land attempts are under it too, and the wait for the attempt it is on has passed. A message
    over the limit is not returned here — `give_up_parked_extractions` settles it, with its reason.
    """
    now = now or datetime.now(timezone.utc)
    with engine.connect() as c:
        rows = c.execute(_FIND_PARKED, {"o": org_id, "lim": int(limit), "now": now,
                                        "codes": sorted(NEEDS_REEXTRACTION)}).fetchall()
    due = []
    for r in rows:
        attempts = int(r.message_parks or 0) + int(r.row_attempts or 0)
        if attempts >= MAX_EXTRACTION_ATTEMPTS + 1:          # the first park is not a retry
            continue
        not_before = r.next_attempt_at or (r.parked_at + _retry_wait(attempts))
        if not_before.tzinfo is None:
            not_before = not_before.replace(tzinfo=timezone.utc)
        if not_before > now:
            continue
        if compute_dedup_key(r.source, r.object_type, r.source_object_id, None) != r.dedup_key:
            continue                                      # a versioned object: see find_unread
        due.append(r)
    return due


def give_up_parked_extractions(engine, org_id: str, *, now: datetime | None = None) -> int:
    """Dead-letter every pending extraction park whose message has reached the limit, saying why.
    Returns how many. A message given up is visible as such — never left `pending` for ever."""
    now = now or datetime.now(timezone.utc)
    with engine.connect() as c:
        rows = c.execute(_FIND_PARKED, {"o": org_id, "lim": 10_000, "now": now,
                                        "codes": sorted(NEEDS_REEXTRACTION)}).fetchall()
    over = [r for r in rows
            if int(r.message_parks or 0) + int(r.row_attempts or 0) >= MAX_EXTRACTION_ATTEMPTS + 1]
    if not over:
        return 0
    with engine.begin() as c:
        for r in over:
            c.execute(_GIVE_UP, {"o": org_id, "e": r.event_id,
                                 "why": (f"extraction parked {int(r.message_parks or 0)} time(s) and "
                                         f"was re-read {int(r.row_attempts or 0)} time(s) "
                                         "without landing; given up")})
    return len(over)


def settle_parked_extractions(engine, org_id: str, event_ids: list[str], *,
                              now: datetime | None = None) -> dict[str, int]:
    """After a re-land: the park of every event a new copy replaced is settled `superseded`; the
    park of every event that came back (`restore`) advances its own ladder."""
    if not event_ids:
        return {"superseded": 0, "advanced": 0}
    now = now or datetime.now(timezone.utc)
    with engine.begin() as c:
        superseded = c.execute(_SUPERSEDE_PARK, {"o": org_id, "status": PARK_SUPERSEDED,
                                                 "sup": SUPERSEDED,
                                                 "ids": list(event_ids)}).rowcount
        advanced = 0
        for e in event_ids:
            attempts = c.execute(text(
                "select refetch_attempts from parked_events where org_id = :o and event_id = :e "
                "and status = 'pending'"), {"o": org_id, "e": e}).scalar()
            if attempts is None:
                continue
            advanced += c.execute(_ADVANCE_PARK, {
                "o": org_id, "e": e, "now": now,
                "next": now + _retry_wait(int(attempts) + 2)}).rowcount
    return {"superseded": int(superseded or 0), "advanced": advanced}


__all__ = ["EXTRACTION_RETRY_BASE", "MAX_EXTRACTION_ATTEMPTS", "PARK_SUPERSEDED", "SUPERSEDED",
           "find_parked_extractions", "find_unread", "give_up_parked_extractions",
           "recover_orphans", "restore", "set_aside", "settle_parked_extractions",
           "to_raw_object"]
