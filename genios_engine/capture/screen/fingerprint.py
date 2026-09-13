"""One message, seen twice, extracted once (SCREEN_INTEL_P2_BUILD §3.3 — frozen contract).

The same email reaches the engine twice when a seat reads it on screen AND the mailbox connector
syncs it: once as a Gmail/Outlook event, once inside a `screen_session` event. Extracting both
pays the model twice for one sentence and makes the message corroborate itself. So each message
is FINGERPRINTED and CLAIMED; the first copy seen stays canonical (both ranks are equal, and
keeping the first avoids re-extraction — §3.4), and every later sighting, from either direction,
writes exactly one `graph_source_refs` row with `independence_group='same_message:'+fp` pointing at
the canonical event, and is not extracted.

    fp = sha256("v1|" + sender_key + "|" + utc_minute + "|" + body_key)

* `sender_key` — lower-cased email, else the `li:` profile handle, else a name key
  (`sender_key_for`).
* `utc_minute` — the message time truncated to the UTC minute; "" when the time is unknown.
  Screen timestamps are read off the UI and can sit a minute either side of the provider's, so a
  LOOKUP tries minutes −1/0/+1 (`candidate_fps`) while each message is RECORDED under its own
  minute only.
* `body_key` — the first 160 characters of the NFKC-normalised, lower-cased, whitespace-collapsed
  text with quoted reply history removed (`capture/preprocess/quoted.py:51`).

Callers: group A's screen promoter and group B's `run_semantic_lane` — both call `claim_messages`
(or `claim` with `alternates`) and `write_same_message_ref`, so there is one implementation.
Layer 1 module: imports nothing from Layer 2; the ref insert mirrors `GraphStore._write_ref`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping, Sequence

from sqlalchemy import bindparam, text

from genios_engine.capture.preprocess.quoted import quoted_regions
from genios_engine.platform.identity import linkedin_handle, norm_email, person_name_key

__all__ = [
    "FP_VERSION", "BODY_KEY_CHARS", "SAME_MESSAGE_PREFIX", "MessageKey",
    "body_key", "sender_key_for", "utc_minute", "message_fp", "candidate_fps",
    "claim", "claim_messages", "lookup", "write_same_message_ref",
]

_log = logging.getLogger(__name__)

FP_VERSION = "v1"
BODY_KEY_CHARS = 160
SAME_MESSAGE_PREFIX = "same_message:"


# ── pure keys ────────────────────────────────────────────────────────────────────────────────────
def body_key(body: str | None) -> str:
    """The comparable part of a message body: quoted history removed, NFKC, lower, 160 chars."""
    raw = str(body or "")
    if not raw:
        return ""
    live: list[str] = []
    cursor = 0
    for start, end in quoted_regions(raw):
        if start > cursor:
            live.append(raw[cursor:start])
        cursor = max(cursor, end)
    live.append(raw[cursor:])
    cleaned = unicodedata.normalize("NFKC", " ".join(live)).lower()
    return " ".join(cleaned.split())[:BODY_KEY_CHARS]


def sender_key_for(*, email: str | None = None, linkedin_url: str | None = None,
                   name: str | None = None) -> str:
    """Lower-cased email, else the `li:` handle, else a name key; "" when nothing names them.

    The email is lower-cased and trimmed only, NOT +tag-stripped: the contract says "lower email",
    and a connector and a screen reading the same From header see the same address.
    """
    mail = str(email or "").strip().lower()
    if mail and "@" in mail and norm_email(mail):
        return mail
    handle = linkedin_handle(linkedin_url) or (linkedin_handle(email) if email else None)
    if handle:
        return handle
    return person_name_key(name) or ""


def utc_minute(ts: datetime | None) -> str:
    """`YYYY-MM-DDTHH:MM` in UTC; a naive datetime is taken as UTC. "" when unknown."""
    if ts is None:
        return ""
    when = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def _fp(sender_key: str, minute: str, bkey: str) -> str:
    seed = f"{FP_VERSION}|{sender_key}|{minute}|{bkey}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def message_fp(sender_key: str, ts: datetime | None, body: str) -> str:
    """The frozen fingerprint of one message (§3.3)."""
    return _fp(str(sender_key or "").strip().lower(), utc_minute(ts), body_key(body))


def candidate_fps(sender_key: str, ts: datetime | None, body: str) -> list[str]:
    """[fp@minute, fp@minute−1, fp@minute+1] — what a LOOKUP must try. One entry when ts is None."""
    if ts is None:
        return [message_fp(sender_key, None, body)]
    return [message_fp(sender_key, ts + timedelta(minutes=delta), body) for delta in (0, -1, 1)]


# ── claims ───────────────────────────────────────────────────────────────────────────────────────
def _is_pg(conn) -> bool:
    return conn.dialect.name == "postgresql"


def _now_sql(conn) -> str:
    # clock_timestamp(), not now(): claims are serialised by an advisory lock, and now() is the
    # TRANSACTION start — a claimer that began earlier but waited on the lock would read as first.
    return "clock_timestamp()" if _is_pg(conn) else "strftime('%Y-%m-%d %H:%M:%f','now')"


def lookup(conn, org_id: str, fps: Iterable[str]) -> dict[str, str]:
    """fp → canonical event id (the FIRST row seen for that fp, any source). Missing = unseen."""
    wanted = sorted({f for f in fps if f})
    if not wanted:
        return {}
    rows = conn.execute(text(
        "select fp, event_id, source, seen_at from message_fingerprints "
        "where org_id = :o and fp in :fps").bindparams(bindparam("fps", expanding=True)),
        {"o": org_id, "fps": wanted}).fetchall()
    first: dict[str, tuple] = {}
    for r in rows:
        rank = (str(r.seen_at), str(r.source), str(r.event_id))
        if r.fp not in first or rank < first[r.fp][0]:
            first[r.fp] = (rank, str(r.event_id))
    return {fp: held[1] for fp, held in first.items()}


def claim(conn, org_id: str, fps: list[str], source: str, event_id: str, *,
          delta_key: str | None = None,
          alternates: Mapping[str, Sequence[str]] | None = None) -> dict[str, str]:
    """fp → canonical event id. First seen wins; existing claims are returned, new ones inserted.

    `fps` are this event's messages, each at its OWN minute. `alternates` (optional, keyed by fp)
    are the ±1-minute neighbours `candidate_fps` produced for it: an existing claim under any of
    them makes that claim's event canonical. Canonical is decided only from rows that existed
    BEFORE this call, so an event is never its own duplicate. A new fp is inserted (`on conflict do
    nothing`, so a retry is a no-op); an fp already claimed by ANOTHER event is not.

    Also correct for a caller that passes all three minute fps of one message as `fps` with no
    `alternates` (the Gmail lane): any value != `event_id` means the message is a duplicate.

    A returned id different from `event_id` means: do NOT extract that message — write
    `write_same_message_ref` instead. On PostgreSQL each fingerprint is claimed under a
    transaction-scoped advisory lock, so a connector and a promoter racing on one message cannot
    both come out canonical; claim in a short transaction.
    """
    out: dict[str, str] = {}
    for fp in dict.fromkeys(f for f in fps if f):
        family = [fp, *[a for a in ((alternates or {}).get(fp) or ()) if a and a != fp]]
        if _is_pg(conn):
            for key in sorted(family):          # sorted: two claimers never lock in opposite order
                conn.execute(text("select pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                             {"k": f"msgfp:{org_id}:{key}"})
        # Canonical is decided from the rows that existed BEFORE this claim — never by comparing
        # our own fresh timestamp against theirs, which ties at clock resolution.
        before = conn.execute(text(
            "select fp, event_id, source, seen_at from message_fingerprints "
            "where org_id = :o and fp in :fps").bindparams(bindparam("fps", expanding=True)),
            {"o": org_id, "fps": sorted(set(family))}).fetchall()
        if before:
            best = min(before, key=lambda r: (str(r.seen_at), str(r.source), str(r.event_id)))
            out[fp] = str(best.event_id)
            if out[fp] != event_id:
                # A copy of a message someone else already claimed: nothing to record. The
                # canonical row is what every later copy must find, and a copy's row would only
                # widen the ±1-minute window (a caller passing all three minute fps — the Gmail
                # lane — would otherwise leave rows at m−1 and m+1 that match m±2).
                continue
        else:
            out[fp] = event_id
        conn.execute(text(
            "insert into message_fingerprints (org_id, fp, source, event_id, delta_key, seen_at) "
            f"values (:o, :fp, :src, :ev, :dk, {_now_sql(conn)}) "
            "on conflict (org_id, fp, source) do nothing"),
            {"o": org_id, "fp": fp, "src": source, "ev": event_id, "dk": delta_key})
    return out


@dataclass(frozen=True)
class MessageKey:
    """One message as the fingerprint sees it."""
    sender_key: str
    ts: datetime | None
    body: str

    @property
    def fp(self) -> str:
        return message_fp(self.sender_key, self.ts, self.body)


def claim_messages(conn, org_id: str, messages: Sequence[MessageKey], source: str,
                   event_id: str, *, delta_key: str | None = None) -> dict[str, str]:
    """`claim` with the ±1-minute lookup built in. fp (own minute) → canonical event id."""
    fps: list[str] = []
    alternates: dict[str, list[str]] = {}
    for m in messages:
        cands = candidate_fps(m.sender_key, m.ts, m.body)
        fps.append(cands[0])
        alternates[cands[0]] = cands[1:]
    return claim(conn, org_id, fps, source, event_id, delta_key=delta_key, alternates=alternates)


# ── the one duplicate receipt ────────────────────────────────────────────────────────────────────
def write_same_message_ref(conn, *, org_id: str, fp: str, canonical_event_id: str,
                           duplicate_source: str, duplicate_event_id: str | None = None,
                           duplicate_source_object_id: str | None = None,
                           evidence: Mapping | None = None) -> str | None:
    """The single `graph_source_refs` row a second sighting leaves (§3.3, one per message).

    `event_id` = the CANONICAL event, `independence_group = 'same_message:' + fp` (so Rule 11 and
    corroboration never count the copy as independent), `source` / `source_object_id` = the copy's.
    No fact/edge/observation id: the copy asserts nothing new. Idempotent — the ref id is derived
    from (org, fp, copy), so a replay writes nothing. Returns the ref id, or None if it existed.

    NEVER RAISES INTO CAPTURE. The receipt is provenance, not the capture itself: a failed insert
    (e.g. the `orgs` FK on `graph_source_refs`) runs inside a SAVEPOINT, is logged and returns
    None, and the caller's transaction stays usable — the copy is still not extracted.
    """
    copy_id = duplicate_event_id or duplicate_source_object_id or duplicate_source
    ref_id = "ref_sm_" + hashlib.sha256(
        f"{org_id}|{fp}|{duplicate_source}|{copy_id}".encode("utf-8")).hexdigest()[:32]
    body = {**dict(evidence or {}), "same_message": fp, "duplicate_source": duplicate_source,
            "duplicate_event_id": duplicate_event_id}
    try:
        with conn.begin_nested():
            if duplicate_source_object_id is None and duplicate_event_id is not None:
                duplicate_source_object_id = conn.execute(text(
                    "select source_object_id from source_events "
                    "where org_id = :o and event_id = :e"),
                    {"o": org_id, "e": duplicate_event_id}).scalar()
            cast = "cast(:ev as jsonb)" if _is_pg(conn) else ":ev"
            inserted = conn.execute(text(
                "insert into graph_source_refs (source_ref_id, org_id, event_id, source, "
                "source_object_id, evidence, independence_group, extractor_version) "
                f"values (:id, :o, :e, :src, :soid, {cast}, :grp, :xv) "
                "on conflict (source_ref_id) do nothing"),
                {"id": ref_id, "o": org_id, "e": canonical_event_id, "src": duplicate_source,
                 "soid": duplicate_source_object_id, "ev": json.dumps(body, default=str),
                 "grp": SAME_MESSAGE_PREFIX + fp, "xv": f"message_fp.{FP_VERSION}"}).rowcount
    except Exception:      # noqa: BLE001 — provenance must never fail the capture it describes
        _log.warning("same_message ref not written (org=%s fp=%s copy=%s)",
                     org_id, fp[:12], copy_id, exc_info=True)
        return None
    return ref_id if inserted else None
