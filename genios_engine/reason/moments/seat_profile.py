"""The weekly manager profile — P10 (the persona the one screen judge can read).

≤ 5 short plain lines about ONE seat's manager: their likely role, key people and who they are,
usual work hours, what to ignore. Kept in `seat_profiles` (migration 0164); read with
`profile_text` (≤ 8 days old) — the lead wires it into the screen-insight prompt.

    inputs     the seat's OWN data only (30 days): the top 10 `who` of its screen follow-ups with
               counts, its follow-up kinds, its work / personal thread verdicts and the latest
               personal sites / chats, its last 10 "not useful" notes, and the local hours at
               which its follow-ups were created. Nothing from another seat, no screen text;
    the model  one Haiku call (`tier_model("T1")`) — only when a key is configured and the seat
               has at least `MIN_SIGNALS` things to go on; its cost is recorded (purpose
               `screen_profile`), never credit-charged;
    when       lazily from the screen-insight request (`ensure_profile`): a missing profile or one
               older than 7 days is rebuilt in a background thread — one in flight per seat, and
               each process looks at a seat at most once an hour. No periodic task.
"""
from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.moments.seat_profile")

PURPOSE = "screen_profile"
REBUILD_AFTER = timedelta(days=7)
READ_MAX_AGE = timedelta(days=8)
WINDOW = timedelta(days=30)
RECHECK_S = 3600.0
TIMEOUT_S = 20.0
MAX_OUTPUT_TOKENS = 300
MAX_LINES = 5
LINE_MAX_CHARS = 200
TOP_PEOPLE = 10
TOP_PERSONAL = 10
NOT_USEFUL = 10
#: Fewer follow-ups + verdicts than this and there is nothing to profile: no model call.
MIN_SIGNALS = 3
_MEMO_MAX = 5000

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="seat-profile")
_LOCK = threading.Lock()
_inflight: set[tuple[str, str]] = set()
_checked: dict[tuple[str, str], float] = {}

_PROMPT = """You write a short private profile of one busy manager, so that an assistant reading
their screen knows what matters to them. Use ONLY the facts below. Never invent names, companies,
roles or hours; write "unclear" where the facts do not show it.

The manager: {me}. Local time zone: {tz}.
People in the manager's follow-ups, last 30 days (name · how many):
{people}
Follow-up kinds, last 30 days: {kinds}
Chats / pages judged work: {work} · personal: {personal}
Recent personal sites / chats: {personal_threads}
Local hours when follow-ups were created (hour · how many): {hours}
Notes the manager marked NOT useful (newest first):
{not_useful}

Write at most 5 short plain lines (≤ 25 words each), no bullets, no headings, no numbering:
Likely role: ...
Key people: name (who they likely are), ...
Usual work hours: ...
Ignore: ... (personal sites / chats and the kinds of notes the manager found not useful)
One more line only if the facts clearly show something else that matters."""


# ── read ──────────────────────────────────────────────────────────────────────────────────────
def profile_text(conn, *, org_id: str, seat_id: str, now: datetime | None = None) -> str | None:
    """The seat's profile when it is at most 8 days old, else None."""
    now = now or datetime.now(timezone.utc)
    r = conn.execute(text(
        "select profile from seat_profiles where org_id = :o and seat_id = :s "
        "and built_at > :cut and profile is not null"),
        {"o": org_id, "s": seat_id, "cut": now - READ_MAX_AGE}).first()
    return (r.profile or None) if r is not None else None


def gather(conn, *, org_id: str, seat_id: str, now: datetime) -> dict:
    """The seat's own facts the profile is written from (also stored as `facts`)."""
    from genios_engine.reason.moments import followups as F
    from genios_engine.reason.moments import screen_insight as SI
    tz = F.seat_tz(conn, org_id, seat_id)
    p = {"o": org_id, "s": seat_id, "since": now - WINDOW}
    people = [{"who": r.who, "count": int(r.n)} for r in conn.execute(text(
        "select min(who) as who, count(*) as n from screen_followups where org_id = :o "
        "and seat_id = :s and created_at >= :since and who is not null "
        "group by lower(who) order by n desc, min(who) limit :k"), {**p, "k": TOP_PEOPLE})]
    kinds = {r.kind: int(r.n) for r in conn.execute(text(
        "select kind, count(*) as n from screen_followups where org_id = :o and seat_id = :s "
        "and created_at >= :since group by kind order by kind"), p)}
    v = conn.execute(text(
        "select count(*) filter (where work) as w, count(*) filter (where not work) as p "
        "from screen_thread_verdicts where org_id = :o and seat_id = :s "
        "and judged_at >= :since"), p).first()
    personal = [r.thread_key for r in conn.execute(text(
        "select thread_key from screen_thread_verdicts where org_id = :o and seat_id = :s "
        "and not work and judged_at >= :since order by judged_at desc limit :k"),
        {**p, "k": TOP_PERSONAL})]
    hours = {str(int(r.h)): int(r.n) for r in conn.execute(text(
        "select extract(hour from created_at at time zone :tz) as h, count(*) as n "
        "from screen_followups where org_id = :o and seat_id = :s and created_at >= :since "
        "group by 1 order by 1"), {**p, "tz": tz})}
    notes = F.not_useful_notes(conn, org_id=org_id, seat_id=seat_id,
                               capability_id=SI.CAPABILITY_ID, limit=NOT_USEFUL)
    return {"tz": tz, "people": people, "kinds": kinds,
            "verdicts": {"work": int(v.w or 0), "personal": int(v.p or 0)},
            "personal_threads": personal, "hours": hours, "not_useful": notes}


def signals(facts: dict) -> int:
    return sum((facts.get("kinds") or {}).values()) + sum((facts.get("verdicts") or {}).values())


def build_prompt(facts: dict, *, email: str | None) -> str:
    people = "\n".join(f"- {p['who']} · {p['count']}" for p in facts.get("people") or [])
    kinds = ", ".join(f"{k} {n}" for k, n in (facts.get("kinds") or {}).items())
    hours = ", ".join(f"{int(h):02d}:00 · {n}" for h, n in (facts.get("hours") or {}).items())
    notes = "\n".join(f"- {n}" for n in facts.get("not_useful") or [])
    v = facts.get("verdicts") or {}
    return _PROMPT.format(
        me=email or "(unknown)", tz=facts.get("tz") or "UTC", people=people or "(none)",
        kinds=kinds or "(none)", work=int(v.get("work") or 0),
        personal=int(v.get("personal") or 0),
        personal_threads=", ".join(facts.get("personal_threads") or []) or "(none)",
        hours=hours or "(none)", not_useful=notes or "(none)")


_BULLET = re.compile(r"^\s*(?:[-*•·]+|\d+[.)])\s*")


def clean(raw: str | None) -> str | None:
    """The model's answer → ≤ 5 plain lines (bullets / numbering stripped), or None."""
    lines = []
    for line in (raw or "").splitlines():
        s = " ".join(_BULLET.sub("", line).split()).strip("\"“”")
        if s:
            lines.append(s[:LINE_MAX_CHARS])
        if len(lines) >= MAX_LINES:
            break
    return "\n".join(lines) or None


# ── the one model call (shared with reply_draft) ─────────────────────────────────────────────
def model_available() -> bool:
    from genios_engine.platform.config import get_settings
    settings = get_settings()
    return bool(getattr(settings, "use_real_llm", False) and settings.anthropic_api_key)


def t1_text(engine, *, org_id: str, prompt: str, max_tokens: int, timeout_s: float,
            purpose: str, temperature: float = 0.0) -> str | None:
    """One Haiku (`tier_model("T1")`) call → its text, or None (no model, failure, timeout). The
    cost is recorded in `llm_costs` under `purpose`; never credit-charged."""
    if not model_available():
        return None
    from anthropic import Anthropic

    from genios_engine.platform.config import get_settings
    from genios_engine.reason.llm_sites import tier_model
    model = tier_model("T1")
    try:
        client = Anthropic(api_key=get_settings().anthropic_api_key, timeout=timeout_s,
                           max_retries=0)
        resp = client.messages.create(model=model, max_tokens=max_tokens,
                                      temperature=temperature,
                                      messages=[{"role": "user", "content": prompt}])
    except Exception:      # noqa: BLE001 — timeout / transport: nothing, never an error
        _log.info("%s: model call failed or timed out org=%s", purpose, org_id)
        return None
    usage = getattr(resp, "usage", None)
    try:
        from genios_engine.context.graph_store import GraphStore
        GraphStore(engine=engine).record_cost(
            org_id=org_id, model=model, purpose=purpose,
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0))
    except Exception:      # noqa: BLE001 — cost bookkeeping never fails the call
        _log.exception("%s: cost record failed", purpose)
    return "".join(getattr(b, "text", "") for b in resp.content
                   if getattr(b, "type", None) == "text").strip() or None


# ── build ─────────────────────────────────────────────────────────────────────────────────────
def build_if_stale(engine, *, org_id: str, seat_id: str, email: str | None,
                   now: datetime | None = None) -> str | None:
    """Rebuild the profile when it is missing or older than 7 days. Returns the new profile, or
    None (still fresh, no model, too little to go on, the model gave nothing)."""
    now = now or datetime.now(timezone.utc)
    with engine.connect() as c:
        built = c.execute(text("select built_at from seat_profiles where org_id = :o "
                               "and seat_id = :s"), {"o": org_id, "s": seat_id}).scalar()
        if built is not None and now - built < REBUILD_AFTER:
            return None
        if not model_available():
            return None
        facts = gather(c, org_id=org_id, seat_id=seat_id, now=now)
    if signals(facts) < MIN_SIGNALS:
        return None
    profile = clean(t1_text(engine, org_id=org_id, prompt=build_prompt(facts, email=email),
                            max_tokens=MAX_OUTPUT_TOKENS, timeout_s=TIMEOUT_S, purpose=PURPOSE))
    if profile is None:
        return None
    with engine.begin() as c:
        c.execute(text(
            "insert into seat_profiles (org_id, seat_id, profile, facts, built_at) "
            "values (:o, :s, :p, cast(:f as jsonb), :now) on conflict (org_id, seat_id) "
            "do update set profile = excluded.profile, facts = excluded.facts, "
            "built_at = excluded.built_at"),
            {"o": org_id, "s": seat_id, "p": profile, "f": json.dumps(facts, default=str),
             "now": now})
    _log.info("seat profile built org=%s seat=%s signals=%d", org_id, seat_id, signals(facts))
    return profile


def _run(engine, org_id: str, seat_id: str, email: str | None, now: datetime | None) -> None:
    try:
        build_if_stale(engine, org_id=org_id, seat_id=seat_id, email=email, now=now)
    except Exception:      # noqa: BLE001 — a profile is a bonus, never a failure anywhere
        _log.exception("seat profile build failed org=%s seat=%s", org_id, seat_id)
    finally:
        with _LOCK:
            _inflight.discard((org_id, seat_id))


def ensure_profile(engine, *, org_id: str, seat_id: str, email: str | None,
                   now: datetime | None = None) -> Future | None:
    """Never blocks: schedules `build_if_stale` in the background at most once an hour per seat
    and process, one in flight per seat. Returns the scheduled future, or None."""
    k = (org_id, seat_id)
    with _LOCK:
        last = _checked.get(k)
        if k in _inflight or (last is not None and time.monotonic() - last < RECHECK_S):
            return None
        if len(_checked) >= _MEMO_MAX and k not in _checked:
            _checked.pop(next(iter(_checked)))
        _checked[k] = time.monotonic()
        _inflight.add(k)
    try:
        return _POOL.submit(_run, engine, org_id, seat_id, email, now)
    except RuntimeError:       # interpreter shutting down
        with _LOCK:
            _inflight.discard(k)
        return None


__all__ = ["PURPOSE", "build_if_stale", "build_prompt", "clean", "ensure_profile", "gather",
           "model_available", "profile_text", "t1_text"]
