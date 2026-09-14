"""SCREEN PROMOTER — held screen deltas become `screen_session` source events (P2 §2).

`/v1/sessions` stores what a desktop app read as encrypted, `held` rows in
`screen_session_deltas`. This daemon thread (the warm lane's pattern: `threading.Event` wake plus
a poll fallback, Postgres `FOR UPDATE SKIP LOCKED` claims with a lease, no broker, no Celery, no
BackgroundTasks) turns them into Layer 1 events, one (org, seat) batch at a time:

  1. only for an org whose Layer 1 semantic lane is activated — anyone else's rows stay `held`
     (the filter is IN the claim, so an unactivated org never costs a claim or an attempt);
  2. decrypt, drop messages the fingerprint ledger has already seen (group C's module, loaded
     lazily: absent = no dedupe), count graph alias hits, render (`capture/screen/render.py`);
  3. the generic reader is capped per seat per org-local day (`screen_generic_daily_cap`); over
     the cap a delta is DEFERRED to the next local midnight, never dropped;
  4. the webhook door's own wiring (`api/routes.py` composio_webhook) with `mailbox_owner` = the
     seat's email → `finalize_l1(ManualSweep)` → `warm_lane.enqueue(source="screen_session")`;
  5. mark `promoted` with the event ids (or `skipped` / `deferred` / back off / `parked`).

Every event is PRIVATE to the seat (`device:screen_session:seat`), set here, at the door: the
source's own rule cannot know whose screen it was.

POOL BUDGET. The session pooler is 8+4. One worker thread per process, ONE batch per claim, and
the promoter's own statements per batch are fixed (claim 3, seat 1, alias 1, fingerprints ≤ 2,
cap ≤ 2, settle 1) whatever the batch size — the per-object work is the capture pipeline's.
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from datetime import time as dtime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.screen_promoter")

SOURCE = "screen_session"
GENERIC_KIND = "screen_generic"
GENERIC_APPS = frozenset({"generic", "web"})
VISIBILITY_DERIVED_FROM = "device:screen_session:seat"
MAX_ATTEMPTS = 5
LEASE_SECONDS = 300
HEARTBEAT_SECONDS = 60
POLL_SECONDS = float(os.environ.get("GENIOS_SCREEN_PROMOTER_POLL", "10"))
BACKOFF_BASE_SECONDS = 30.0
BACKOFF_CAP_SECONDS = 1800.0
COUNTER_RETENTION_DAYS = 7

_WORKER_BASE = f"{socket.gethostname()}:{os.getpid()}"
_wake = threading.Event()
_stop = threading.Event()
_threads: list[threading.Thread] = []
_housekeeping = {"prune": 0.0}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# ── pure policy ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Delta:
    org_id: str
    device_id: str
    session_key: str
    message_watermark: int
    seat_id: str
    app: str
    thread_key: str | None
    payload_enc: bytes
    captured_at: datetime | None
    received_at: datetime
    attempts: int = 0
    status: str = "held"

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.device_id, self.session_key, int(self.message_watermark))

    @property
    def generic(self) -> bool:
        return (self.app or "").lower() in GENERIC_APPS


@dataclass
class Outcome:
    status: str                              # promoted | skipped | deferred | parked | held
    event_ids: list[str] | None = None
    error: str | None = None
    not_before: datetime | None = None
    refund_attempt: bool = False             # a cap deferral is not a failed attempt


def backoff_seconds(attempts: int) -> float:
    return min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1)))


def failure_outcome(delta: Delta, error: str, *, now: datetime) -> Outcome:
    """A failed attempt: park after MAX_ATTEMPTS (counted at claim), else back off."""
    if delta.attempts >= MAX_ATTEMPTS:
        return Outcome("parked", error=error[:500])
    return Outcome("held", error=error[:500],
                   not_before=now + timedelta(seconds=backoff_seconds(delta.attempts)))


def _zone(tz_name: str | None):
    try:
        return ZoneInfo(tz_name or "UTC")
    except Exception:      # noqa: BLE001 — an unknown zone is UTC, never a failed batch
        return timezone.utc


def local_day(now: datetime, tz_name: str | None) -> date:
    return now.astimezone(_zone(tz_name)).date()


def next_local_midnight(now: datetime, tz_name: str | None) -> datetime:
    """The next org-local midnight, as a UTC instant."""
    tz = _zone(tz_name)
    nxt = datetime.combine(now.astimezone(tz).date() + timedelta(days=1), dtime(0), tzinfo=tz)
    return nxt.astimezone(timezone.utc)


def seat_scope(org_id: str, seat_id: str) -> str:
    return f"{org_id}:{seat_id}"


# ── doors (the wiring the promoter hands to Layer 1; injectable for tests) ─────────────────────
@dataclass
class Doors:
    """`wiring_for(org_id, seat_email, connection_id) -> PushIngestWiring`, the finalizer's
    stores, and the warm-lane trigger. The default is exactly the Composio webhook's wiring."""
    wiring_for: Callable[[str, str, str], Any]
    stores: Callable[[], Any]
    enqueue: Callable[..., int]


def default_doors() -> Doors:
    def wiring_for(org_id: str, seat_email: str, connection_id: str):
        from genios_engine.api import routes as R      # lazy: routes wires stores at import
        from genios_engine.capture.connectors.push_ingest import PushIngestWiring
        from genios_engine.capture.screen.relevance import ScreenDocRelevance
        from genios_engine.contracts.source_event import SyncMode
        from genios_engine.platform.db import get_engine
        from genios_engine.platform.wiring import make_relevance_classifier
        from genios_engine.reason.moments.followups import verdict_lookup
        # P8 C9: the screen-insight model's 24 h work / personal verdict per thread routes the
        # thread's memory before the AI gate. The seat is the one this connection belongs to.
        seat_id = connection_id.removeprefix("screen:")
        verdicts = verdict_lookup(get_engine(get_settings().database_url), org_id, seat_id)
        return PushIngestWiring(
            repo=R._repo, trace_repo=R._trace_repo, payload_store=R._payload_store,
            prepared_store=R._prepared_store, document_job_store=R._documents,
            parked_store=R._parked,
            relevance=ScreenDocRelevance(make_relevance_classifier(org_id), verdicts),
            sender_resolver=R._sender_resolver_for(org_id),
            mailbox_owner=seat_email, coverage_fn=R._coverage_fn_for(org_id),
            esqe=R._esqe_stage_for(org_id), semantic=R._semantic_lane_for(org_id),
            structured=R._structured_lane_for(org_id), sync_mode=SyncMode.incremental)

    def stores():
        from genios_engine.api import routes as R
        return R._l1_stores()

    def enqueue(engine, org_id, event_ids, source=SOURCE):
        from genios_engine.platform import warm_lane
        return warm_lane.enqueue(engine, org_id, event_ids, source=source)

    return Doors(wiring_for=wiring_for, stores=stores, enqueue=enqueue)


# ── wake / claim ────────────────────────────────────────────────────────────────────────────
def wake() -> None:
    _wake.set()


_CLAIMABLE = ("status in ('held', 'deferred') and (not_before is null or not_before <= now()) "
              "and (lease_until is null or lease_until < now())")
_COLS = ("org_id, device_id, session_key, message_watermark, seat_id, app, thread_key, "
         "payload_enc, captured_at, received_at, attempts, status")


def _delta(r) -> Delta:
    return Delta(org_id=r.org_id, device_id=r.device_id, session_key=r.session_key,
                 message_watermark=int(r.message_watermark), seat_id=r.seat_id, app=r.app,
                 thread_key=r.thread_key, payload_enc=bytes(r.payload_enc),
                 captured_at=r.captured_at, received_at=r.received_at,
                 attempts=int(r.attempts or 0), status=r.status)


def claim_batch(engine, worker_id: str, *, batch: int | None = None
                ) -> tuple[str, str, list[Delta]] | None:
    """Claim the oldest claimable (org, seat) batch of an ACTIVATED org, in one transaction."""
    from genios_engine.platform.activation import _LIVE, L1_SEMANTIC_TABLE
    n = int(batch or get_settings().screen_promoter_batch or 50)
    with engine.begin() as c:
        first = c.execute(text(
            f"select org_id, seat_id from screen_session_deltas d where {_CLAIMABLE} "
            f"and exists (select 1 from {L1_SEMANTIC_TABLE} a where a.org_id = d.org_id "
            f"and a.{_LIVE}) order by received_at limit 1 for update skip locked")).first()
        if first is None:
            return None
        keys = c.execute(text(
            f"select device_id, session_key, message_watermark from screen_session_deltas "
            f"where org_id = :o and seat_id = :s and {_CLAIMABLE} "
            f"order by received_at, message_watermark limit :n for update skip locked"),
            {"o": first.org_id, "s": first.seat_id, "n": n}).fetchall()
        if not keys:
            return None
        rows = c.execute(text(
            "update screen_session_deltas t set claimed_by = :w, attempts = t.attempts + 1, "
            "lease_until = now() + make_interval(secs => :ttl) "
            "from unnest(cast(:ds as text[]), cast(:ks as text[]), cast(:ws as bigint[])) "
            "as u(d, k, w) where t.org_id = :o and t.device_id = u.d and t.session_key = u.k "
            "and t.message_watermark = u.w "
            f"returning {', '.join('t.' + x.strip() for x in _COLS.split(','))}"),
            {"w": worker_id[:120], "ttl": LEASE_SECONDS, "o": first.org_id,
             "ds": [k.device_id for k in keys], "ks": [k.session_key for k in keys],
             "ws": [int(k.message_watermark) for k in keys]}).fetchall()
    deltas = sorted((_delta(r) for r in rows),
                    key=lambda d: (d.received_at, d.session_key, d.message_watermark))
    return first.org_id, first.seat_id, deltas


def _beat(engine, org_id: str, worker_id: str) -> None:
    with engine.begin() as c:
        c.execute(text(
            "update screen_session_deltas set lease_until = now() + make_interval(secs => :ttl) "
            "where org_id = :o and claimed_by = :w and status in ('held', 'deferred')"),
            {"o": org_id, "w": worker_id[:120], "ttl": LEASE_SECONDS})


class _Heartbeat:
    def __init__(self, fn: Callable[[], None]) -> None:
        self._fn, self._stop = fn, threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True, name="screen-promoter-beat")
        self._t.start()

    def _run(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            try:
                self._fn()
            except Exception:      # noqa: BLE001 — a missed beat is not fatal
                _log.warning("screen promoter heartbeat failed", exc_info=True)

    def stop(self) -> None:
        self._stop.set()


def settle(engine, org_id: str, worker_id: str, outcomes: dict[tuple, Outcome]) -> None:
    """Write every delta's outcome in ONE statement. Guarded on `claimed_by`: a row whose lease
    ran out and was reclaimed by another worker is that worker's to settle."""
    if not outcomes:
        return
    items = list(outcomes.items())
    with engine.begin() as c:
        c.execute(text(
            "update screen_session_deltas t set status = u.st, "
            "event_ids = case when u.ev is null then t.event_ids "
            "else array(select jsonb_array_elements_text(cast(u.ev as jsonb))) end, "
            "promoted_at = case when u.st = 'promoted' then now() else t.promoted_at end, "
            "not_before = u.nb, last_error = u.er, lease_until = null, claimed_by = null, "
            "attempts = greatest(t.attempts - u.rf, 0) "
            "from unnest(cast(:ds as text[]), cast(:ks as text[]), cast(:ws as bigint[]), "
            "cast(:sts as text[]), cast(:evs as text[]), cast(:nbs as timestamptz[]), "
            "cast(:ers as text[]), cast(:rfs as int[])) as u(d, k, w, st, ev, nb, er, rf) "
            "where t.org_id = :o and t.device_id = u.d and t.session_key = u.k "
            "and t.message_watermark = u.w and t.claimed_by = :wk"),
            {"o": org_id, "wk": worker_id[:120],
             "ds": [k[0] for k, _ in items], "ks": [k[1] for k, _ in items],
             "ws": [int(k[2]) for k, _ in items], "sts": [o.status for _, o in items],
             "evs": [None if o.event_ids is None else json.dumps(o.event_ids)
                     for _, o in items],
             "nbs": [o.not_before for _, o in items], "ers": [o.error for _, o in items],
             "rfs": [1 if o.refund_attempt else 0 for _, o in items]})


# ── the per-batch steps ─────────────────────────────────────────────────────────────────────
def _seat(engine, org_id: str, seat_id: str) -> tuple[str | None, str]:
    with engine.connect() as c:
        r = c.execute(text(
            "select lower(s.email) as email, coalesce(o.timezone, 'UTC') as tz from orgs o "
            "left join org_seats s on s.org_id = o.id and s.seat_id = :s where o.id = :o"),
            {"o": org_id, "s": seat_id}).first()
    if r is None:
        return None, "UTC"
    return (r.email or None), str(r.tz or "UTC")


def reserve_generic(engine, scope_key: str, day: date, n: int, cap: int) -> int:
    """Take up to `n` of today's `cap`; returns how many were granted. Atomic under
    concurrency: the upsert's increment is one statement, so `new - n` is exactly the old count."""
    if n <= 0:
        return 0
    with engine.begin() as c:
        new = int(c.execute(text(
            "insert into rate_counters as r (scope_key, kind, window_start, count) "
            "values (:k, :kind, :d, :n) on conflict (scope_key, kind, window_start) "
            "do update set count = r.count + :n returning count"),
            {"k": scope_key, "kind": GENERIC_KIND, "d": day, "n": n}).scalar())
        granted = max(0, min(n, cap - (new - n)))
        if granted < n:
            c.execute(text(
                "update rate_counters set count = count - :back where scope_key = :k "
                "and kind = :kind and window_start = :d"),
                {"k": scope_key, "kind": GENERIC_KIND, "d": day, "back": n - granted})
    return granted


def release_generic(engine, scope_key: str, day: date, n: int) -> None:
    if n <= 0:
        return
    with engine.begin() as c:
        c.execute(text(
            "update rate_counters set count = greatest(count - :n, 0) where scope_key = :k "
            "and kind = :kind and window_start = :d"),
            {"k": scope_key, "kind": GENERIC_KIND, "d": day, "n": n})


def alias_candidates(doc: dict) -> set[tuple[str, str]]:
    """(alias_type, alias_key) pairs a session names: emails, LinkedIn profiles, full names."""
    from genios_engine.capture.screen.render import norm_linkedin_url
    from genios_engine.platform.identity import norm_email, person_name_key
    out: set[tuple[str, str]] = set()
    names: list[str] = []
    for p in doc.get("participants") or []:
        if not isinstance(p, dict) or p.get("self"):
            continue
        e = norm_email(p.get("email"))
        if e:
            out.add(("email", e))
        li = norm_linkedin_url(p.get("linkedin_url"))
        if li:
            out.update({("linkedin_url", li), ("linkedin_url", "li:" + li)})
        names.append(p.get("name") or "")
    texts: list[str] = []
    for m in (doc.get("messages") or []) + (doc.get("blocks") or []):
        if not isinstance(m, dict):
            continue
        if not m.get("is_outgoing"):
            names.append(m.get("sender") or "")
        texts.extend(str(v) for k, v in m.items()
                     if k in ("text", "value", "label") and v is not None)
        for row in m.get("rows") or []:
            texts.extend(str(c) for c in (row or []) if c is not None)
    for t in texts:
        for e in _EMAIL.findall(t):
            ne = norm_email(e)
            if ne:
                out.add(("email", ne))
    for n in names:
        k = person_name_key(n)
        if k and " " in k:                 # a full name only — a first name alone matches anyone
            out.add(("person_name", k))
    return out


def count_alias_hits(engine, org_id: str, docs: dict[tuple, dict]) -> dict[tuple, int]:
    cands = {k: alias_candidates(d) for k, d in docs.items()}
    keys = sorted({key for c in cands.values() for _, key in c})
    if not keys:
        return {k: 0 for k in docs}
    with engine.connect() as c:
        found = {(r.alias_type, r.alias_key) for r in c.execute(text(
            "select alias_type, alias_key from graph_aliases where org_id = :o "
            "and alias_key = any(cast(:keys as text[]))"), {"o": org_id, "keys": keys})}
    return {k: len(c & found) for k, c in cands.items()}


def _fingerprint_module():
    """Group C's `capture/screen/fingerprint.py` (§3.3), loaded by name because it is built in
    parallel with this module. Absent = no dedupe (the watermark still stops re-promotion)."""
    import importlib
    try:
        return importlib.import_module("genios_engine.capture.screen.fingerprint")
    except ImportError:
        return None


def _sender_key(message: dict, people, seat_email: str) -> str:
    from genios_engine.capture.screen.render import is_outgoing
    from genios_engine.platform.identity import person_name_key
    if is_outgoing(message):
        return seat_email
    ident, name = people.identity_of(message)
    return ident or person_name_key(name) or ""


def message_fps(F, message: dict, people, seat_email: str) -> tuple[str, list[str]]:
    """(the minute-0 fingerprint, all three lookup variants −1/0/+1 minute)."""
    from genios_engine.capture.screen.render import _parse_ts
    sk = _sender_key(message, people, seat_email)
    ts = _parse_ts(message.get("ts"))
    body = str(message.get("text") or "")
    fp0 = F.message_fp(sk, ts, body)
    if ts is None:
        return fp0, [fp0]
    return fp0, [F.message_fp(sk, ts + timedelta(minutes=d), body) for d in (-1, 0, 1)]


def lookup_fps(F, engine, org_id: str, fps: list[str]) -> dict[str, str]:
    """fp → canonical event id for fingerprints already claimed by any source.

    CONTRACT GAP (§3.3): `claim()` inserts as it answers, so it cannot be asked BEFORE an event
    exists. Pre-ingest dedupe therefore needs a read-only `lookup(conn, org_id, fps)` from
    group C's module; until it exists the promoter lands every message and claims after."""
    lookup = getattr(F, "lookup", None)
    if not fps or not callable(lookup):
        return {}
    try:
        with engine.connect() as c:
            return dict(lookup(c, org_id, sorted(set(fps))) or {})
    except Exception:      # noqa: BLE001 — no ledger yet = no dedupe, never a failed batch
        _log.warning("fingerprint lookup unavailable org=%s — promoting without dedupe", org_id,
                     exc_info=True)
        return {}


@dataclass
class _Plan:
    delta: Delta
    doc: dict
    fps_by_msg: dict[int, str] = field(default_factory=dict)       # id(message) → fp0
    seen: list[tuple[str, str]] = field(default_factory=list)       # (fp, canonical event id)


def _dedupe(F, engine, org_id: str, plans: list[_Plan], seat_email: str) -> None:
    """Remove messages any source already landed; remember them for a `same_message` ref."""
    from genios_engine.capture.screen.render import People
    variants: dict[int, tuple[_Plan, dict, str, list[str]]] = {}
    for p in plans:
        people = People(p.doc.get("participants") or [], seat_email)
        for m in p.doc.get("messages") or []:
            if isinstance(m, dict) and str(m.get("text") or "").strip():
                fp0, vs = message_fps(F, m, people, seat_email)
                variants[id(m)] = (p, m, fp0, vs)
                p.fps_by_msg[id(m)] = fp0
    known = lookup_fps(F, engine, org_id, [v for *_, vs in variants.values() for v in vs])
    if not known:
        return
    for p, m, fp0, vs in variants.values():
        hit = next((known[v] for v in vs if v in known), None)
        if hit:
            p.seen.append((fp0, hit))
            p.doc["messages"] = [x for x in p.doc.get("messages") or [] if x is not m]


def _record_claims(F, engine, org_id: str, claims: list[tuple[str, list[str]]],
                   refs: list[dict]) -> None:
    """After landing: claim each event's fingerprints; one `same_message` ref per duplicate."""
    if not claims and not refs:
        return
    try:
        with engine.begin() as c:
            for event_id, fps in claims:
                if fps:
                    F.claim(c, org_id, fps, SOURCE, event_id)
            if refs:
                from genios_engine.platform.ids import new_id
                c.execute(text(
                    "insert into graph_source_refs (source_ref_id, org_id, event_id, source, "
                    "source_object_id, evidence, independence_group) "
                    "select i, :o, e, :src, so, cast(ev as jsonb), g from unnest("
                    "cast(:ids as text[]), cast(:es as text[]), cast(:sos as text[]), "
                    "cast(:evs as text[]), cast(:gs as text[])) as u(i, e, so, ev, g)"),
                    {"o": org_id, "src": SOURCE,
                     "ids": [new_id("sref") for _ in refs],
                     "es": [r["event_id"] for r in refs],
                     "sos": [r["source_object_id"] for r in refs],
                     "evs": [json.dumps(r["evidence"]) for r in refs],
                     "gs": [r["independence_group"] for r in refs]})
    except Exception:      # noqa: BLE001 — a missed claim costs one duplicate extraction later
        _log.exception("fingerprint claims failed org=%s", org_id)


def promote_batch(engine, org_id: str, seat_id: str, deltas: list[Delta], *,
                  doors: Doors | None = None, now: datetime | None = None,
                  cap: int | None = None, crypto_key: str | None = None) -> dict[tuple, Outcome]:
    from genios_engine.capture.connectors.push_ingest import ingest_pushed_objects
    from genios_engine.capture.esqe.finalize import ManualSweep, finalize_l1
    from genios_engine.capture.screen.render import render_session
    from genios_engine.contracts.visibility import PRIVATE, Visibility
    from genios_engine.platform.capture_policy import screen_connection_id
    from genios_engine.platform.crypto import decrypt

    doors = doors or default_doors()
    now = now or datetime.now(timezone.utc)
    s = get_settings()
    cap = int(s.screen_generic_daily_cap if cap is None else cap)
    key = crypto_key or s.crypto_key
    out: dict[tuple, Outcome] = {}
    seat_email, tz = _seat(engine, org_id, seat_id)
    if not seat_email:
        return {d.key: Outcome("parked", error="seat_email_missing") for d in deltas}

    plans: list[_Plan] = []
    for d in deltas:
        try:
            plans.append(_Plan(d, json.loads(decrypt(d.payload_enc, key))))
        except Exception as exc:      # noqa: BLE001 — undecryptable is permanent: park now
            out[d.key] = Outcome("parked", error=f"undecryptable: {type(exc).__name__}")

    # per-seat generic cap, in arrival order; over it → the next org-local midnight
    day, scope = local_day(now, tz), seat_scope(org_id, seat_id)
    generic = [p for p in plans if p.delta.generic]
    granted = reserve_generic(engine, scope, day, len(generic), cap) if generic else 0
    midnight = next_local_midnight(now, tz)
    for p in generic[granted:]:
        out[p.delta.key] = Outcome("deferred", error="generic_daily_cap", not_before=midnight,
                                   refund_attempt=True)
    plans = [p for p in plans if p.delta.key not in out]
    if not plans:
        return out

    F = _fingerprint_module()
    if F is not None:
        _dedupe(F, engine, org_id, plans, seat_email)
    hits = count_alias_hits(engine, org_id, {p.delta.key: p.doc for p in plans})

    visibility = Visibility(scope=PRIVATE, principals=[seat_email],
                            derived_from=VISIBILITY_DERIVED_FROM)
    objects, owner, fps_of, refs = [], {}, {}, []
    for p in plans:
        d = p.delta
        for fp, canonical in p.seen:
            refs.append({"event_id": canonical, "independence_group": f"same_message:{fp}",
                         "source_object_id": f"{d.thread_key or d.session_key}"
                                             f"#{d.message_watermark}",
                         "evidence": {"seen_on": SOURCE, "session_key": d.session_key}})
        rendered = render_session(p.doc, seat_email=seat_email, watermark=d.message_watermark,
                                  received_at=d.received_at, captured_at=d.captured_at,
                                  alias_hits=hits.get(d.key, 0))
        if not rendered:
            out[d.key] = Outcome("skipped", event_ids=[],
                                 error="already_seen" if p.seen else "nothing_new")
            continue
        for r in rendered:
            r.raw.visibility = visibility
            objects.append(r.raw)
            owner[r.raw.source_object_id] = d.key
            fps_of[r.raw.source_object_id] = [p.fps_by_msg[id(m)] for m in r.messages
                                              if id(m) in p.fps_by_msg]
    by_key = {p.delta.key: p.delta for p in plans}
    pending = [k for k in by_key if k not in out]
    if not objects:
        if F is not None and refs:
            _record_claims(F, engine, org_id, [], refs)
        return out

    connection_id = screen_connection_id(seat_id)
    try:
        wiring = doors.wiring_for(org_id, seat_email, connection_id)
        if getattr(wiring, "mailbox_owner", None) != seat_email:
            wiring = replace(wiring, mailbox_owner=seat_email)
        result = ingest_pushed_objects(tuple(objects), org_id=org_id,
                                       connection_id=connection_id, wiring=wiring)
    except Exception as exc:      # noqa: BLE001 — the whole batch retries
        _log.exception("screen promotion failed org=%s seat=%s", org_id, seat_id)
        fail = {k: failure_outcome(by_key[k], f"{type(exc).__name__}: {exc}", now=now)
                for k in pending}
        release_generic(engine, scope, day, sum(1 for k in fail if by_key[k].generic))
        return {**out, **fail}

    events: dict[tuple, list[str]] = {k: [] for k in pending}
    claims: list[tuple[str, list[str]]] = []
    emitted: list[str] = []
    for r in result.results:
        k = owner.get(r.event.source_object_id)
        if k is None or r.outcome == "duplicate":
            continue
        events[k].append(r.event.event_id)
        claims.append((r.event.event_id, fps_of.get(r.event.source_object_id) or []))
        if r.outcome == "emitted":
            emitted.append(r.event.event_id)
    failed = {owner[oid] for oid in result.quarantined if oid in owner}
    for k in pending:
        if k in failed:
            out[k] = failure_outcome(by_key[k], "quarantined object", now=now)
        elif events[k]:
            out[k] = Outcome("promoted", event_ids=events[k])
        else:
            out[k] = Outcome("skipped", event_ids=[], error="duplicate")
    release_generic(engine, scope, day, sum(1 for k in failed if by_key[k].generic))

    if result.results:
        finalize_l1(ManualSweep(org_id=org_id, results=result.results, emitted=len(emitted),
                                scanned=len(objects)),
                    org_id=org_id, stores=doors.stores())
    if emitted:
        doors.enqueue(engine, org_id, emitted, source=SOURCE)
    if F is not None:
        _record_claims(F, engine, org_id, claims, refs)
    return out


def run_once(engine, worker_id: str, *, doors: Doors | None = None,
             batch: int | None = None, now: datetime | None = None,
             cap: int | None = None) -> bool:
    """One claim → one batch → settle. True when a batch was taken."""
    claimed = claim_batch(engine, worker_id, batch=batch)
    if claimed is None:
        return False
    org_id, seat_id, deltas = claimed
    beat = _Heartbeat(lambda: _beat(engine, org_id, worker_id))
    now = now or datetime.now(timezone.utc)
    try:
        from genios_engine.platform.stage_timer import stage
        with stage("screen.promote", org_id, deltas=len(deltas)) as st:
            try:
                outcomes = promote_batch(engine, org_id, seat_id, deltas, doors=doors, now=now,
                                         cap=cap)
            except Exception as exc:      # noqa: BLE001 — a crashed batch is a failed attempt
                _log.exception("screen promoter batch crashed org=%s", org_id)
                outcomes = {d.key: failure_outcome(d, f"{type(exc).__name__}: {exc}", now=now)
                            for d in deltas}
            st["promoted"] = sum(1 for o in outcomes.values() if o.status == "promoted")
        settle(engine, org_id, worker_id, outcomes)
        parked = [k for k, o in outcomes.items() if o.status == "parked"]
        if parked:
            _log.error("screen promoter PARKED %d delta(s) org=%s", len(parked), org_id)
    finally:
        beat.stop()
    return True


def housekeep(engine, *, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    if now - _housekeeping["prune"] >= 3600:
        _housekeeping["prune"] = now
        with engine.begin() as c:
            c.execute(text("delete from rate_counters where kind = :k "
                           "and window_start < current_date - :d"),
                      {"k": GENERIC_KIND, "d": COUNTER_RETENTION_DAYS})


# ── the worker ──────────────────────────────────────────────────────────────────────────────
def _resolve_engine():
    from genios_engine.api import routes      # lazy: routes wires the stores at import
    return routes._graph.engine if routes._graph is not None else None


def _loop(worker_id: str, initial_delay: float) -> None:
    if _stop.wait(initial_delay):
        return
    while not _stop.is_set():
        ran = False
        try:
            engine = _resolve_engine()
            if engine is None:
                _log.info("screen promoter: no graph store — worker exiting")
                return
            _wake.clear()
            ran = run_once(engine, worker_id)
            housekeep(engine)
        except Exception:      # noqa: BLE001 — a crash must never kill the loop
            _log.exception("screen promoter tick crashed")
        if not ran:
            _wake.wait(POLL_SECONDS)


def worker_alive() -> bool:
    return any(t.is_alive() for t in _threads)


def start_screen_promoter(initial_delay: float | None = None) -> bool:
    """Start the one worker thread. Idempotent. main.py gates the call on use_real_db."""
    if not get_settings().screen_promoter_enabled:
        _log.info("screen promoter disabled (GENIOS_SCREEN_PROMOTER_ENABLED=false)")
        return False
    if worker_alive():
        return True
    _stop.clear()
    _threads.clear()
    worker_id = f"{_WORKER_BASE}:screen:{uuid.uuid4().hex[:6]}"
    t = threading.Thread(target=_loop, args=(worker_id, 8.0 if initial_delay is None
                                             else float(initial_delay)),
                         daemon=True, name="genios-screen-promoter")
    t.start()
    _threads.append(t)
    _log.info("screen promoter started (poll=%ss, lease=%ss)", POLL_SECONDS, LEASE_SECONDS)
    return True


def stop_screen_promoter(timeout: float = 5.0) -> None:
    _stop.set()
    _wake.set()
    for t in list(_threads):
        t.join(timeout)
    _threads.clear()


__all__ = ["Delta", "Doors", "Outcome", "backoff_seconds", "claim_batch", "count_alias_hits",
           "default_doors", "failure_outcome", "local_day", "next_local_midnight",
           "promote_batch", "reserve_generic", "run_once", "settle", "start_screen_promoter",
           "stop_screen_promoter", "wake"]
