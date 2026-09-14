"""Screen follow-ups — what a screen insight leaves behind (SCREEN_INTEL_MANAGER_VALUE_BUILD C2–C5, C8).

A shown (or budget-queued) screen insight about WORK becomes one `screen_followups` row the device
turns into a brief line, a wrap count or a nudge (migration 0159):

    kind       ask → ask; commitment → my_promise (owner me) / their_promise (owner them);
               deadline / risk / next_step → the same. A commitment with no owner has no row.
    topic_key  sha256(seat | thread_key or app | kind | lower(who) | local date): one row per topic
               per day; a repeat updates the note / due instead of a new popup (C2).
    nudge_at   ask +3 h · my_promise due −60 min, undated +3 working days · their_promise due +1 h,
               undated +2 working days · deadline due −24 h · risk / next_step none (brief only).
    resolved   answered — STRUCTURAL, never meaning: a later look at the same thread has a `You:`
               line after the line that holds the ask's quote; done / dismissed — the person;
               expired (lazily, on the next read: no periodic task) — a promise 2 days past its
               due; an ask 7 days unresolved; a deadline 1 day after its due (undated: 7 days);
               a risk / next step after 3 days (P9 K5).

`text` is the model's note (≤ 140 chars), never screen text. The item's ≤ 12-word grounding quote is
kept in `quote` (0161) so "answered" works for items saved WITHOUT a popup; rows from before 0161 fall
back to the insight moment's body. Every item of the one judge (screen_insight v4) is a row here —
this table is the seat's screen memory of asks, promises, deadlines, risks and next steps.

Web pages are judged per SITE (`verdict_key`: every Naukri page is one "personal" judgement);
chats, mail threads and app windows per thread.

`screen_thread_verdicts` keeps the model's latest "is this thread work?" and "is it worth memory?"
per (seat, thread); the screen relevance gate reads them for 24 h (C9, P9 K2/K3). `muted_until`
(K4): "Not useful" on an insight mutes the thread's popups for 7 days, "Mute chat" for good; the
seat's last ≤ 5 not-useful notes are shown to the model as kinds not to repeat. Never
credit-charged.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from datetime import time as dtime
from zoneinfo import ZoneInfo

from sqlalchemy import text

from genios_engine.platform import realtime
from genios_engine.reason.moments.common import aware, iso

KINDS = ("ask", "my_promise", "their_promise", "deadline", "risk", "next_step")
RESOLUTIONS = ("answered", "done", "dismissed", "expired")
TEXT_MAX = 140
WHO_MAX = 120
SLICE_MAX = 50
LIST_MAX = 200
VERDICT_HOURS = 24
EXPIRE_AFTER = timedelta(days=2)                   # promises: 2 days past due
ASK_EXPIRE = timedelta(days=7)                     # K5: an ask unresolved for 7 days
DEADLINE_EXPIRE = timedelta(days=1)                # K5: a deadline 1 day after its due …
UNDATED_EXPIRE = timedelta(days=7)                 # … or 7 days when it has no due
BRIEF_EXPIRE = timedelta(days=3)                   # K5: risk / next_step after 3 days
#: K4: "Not useful" mutes the thread's insight popups this long; "Mute chat" mutes it for good.
NOT_USEFUL_MUTE = timedelta(days=7)
MUTE_FOREVER = datetime(9999, 12, 31, tzinfo=timezone.utc)
MUTE_REASON = "mute_chat"
NOT_USEFUL_ACTION = "wrong"
NOT_USEFUL_NOTES = 5
ASK_NUDGE = timedelta(hours=3)
MY_PROMISE_LEAD = timedelta(minutes=60)
THEIR_PROMISE_GRACE = timedelta(hours=1)
DEADLINE_LEAD = timedelta(hours=24)
MY_PROMISE_UNDATED_DAYS = 3
THEIR_PROMISE_UNDATED_DAYS = 2
#: A day named without a time ("by Friday") is due at the end of that working day.
DAY_ONLY_HOUR = 18
VERDICT_RETENTION_DAYS = 7
_WEEKEND = (5, 6)


# ── pure policy ───────────────────────────────────────────────────────────────────────────────
def zone(tz_name: str | None):
    try:
        return ZoneInfo(tz_name or "UTC")
    except Exception:      # noqa: BLE001 — an unknown zone is UTC, never a failed request
        return timezone.utc


def map_kind(kind: str | None, owner: str | None) -> str | None:
    """The model's insight kind (+ owner) → the follow-up kind, or None (no follow-up)."""
    k = (kind or "").strip().lower()
    if k == "commitment":
        o = (owner or "").strip().lower()
        return {"me": "my_promise", "them": "their_promise"}.get(o)
    return k if k in ("ask", "deadline", "risk", "next_step") else None


def topic_key(*, seat_id: str, thread_key: str | None, app: str | None, kind: str,
              who: str | None, local_date: date) -> str:
    blob = "|".join([seat_id, (thread_key or app or "").strip(), kind,
                     " ".join((who or "").split()).casefold(), local_date.isoformat()])
    return hashlib.sha256(blob.encode()).hexdigest()


def followup_id(org_id: str, seat_id: str, topic: str) -> str:
    return "fu_" + hashlib.sha256(f"{org_id}|{seat_id}|{topic}".encode()).hexdigest()[:24]


def add_working_days(start: datetime, n: int, tz_name: str | None) -> datetime:
    """`n` working days (Mon–Fri, in the seat's zone) after `start`, same wall-clock time."""
    tz = zone(tz_name)
    local = aware(start).astimezone(tz)
    day = local.date()
    for _ in range(max(0, n)):
        day += timedelta(days=1)
        while day.weekday() in _WEEKEND:
            day += timedelta(days=1)
    return datetime.combine(day, local.time(), tzinfo=tz).astimezone(timezone.utc)


def nudge_at(kind: str, *, created_at: datetime, due_at: datetime | None,
             tz_name: str | None) -> datetime | None:
    if kind == "ask":
        return created_at + ASK_NUDGE
    if kind == "my_promise":
        return (due_at - MY_PROMISE_LEAD if due_at
                else add_working_days(created_at, MY_PROMISE_UNDATED_DAYS, tz_name))
    if kind == "their_promise":
        return (due_at + THEIR_PROMISE_GRACE if due_at
                else add_working_days(created_at, THEIR_PROMISE_UNDATED_DAYS, tz_name))
    if kind == "deadline":
        return due_at - DEADLINE_LEAD if due_at else None
    return None                                      # risk / next_step: brief only


def parse_due(value, *, tz_name: str | None, now: datetime) -> datetime | None:
    """The model's `due` ("YYYY-MM-DDTHH:MM" in the seat's local time, or a bare date) → UTC.
    Unparseable, or implausibly far from now (a misread year), → None."""
    s = str(value or "").strip()
    try:
        if len(s) == 10:
            local = datetime.combine(date.fromisoformat(s), dtime(DAY_ONLY_HOUR))
        else:
            local = datetime.strptime(s[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    at = local.replace(tzinfo=zone(tz_name)).astimezone(timezone.utc)
    return at if now - timedelta(days=2) <= at <= now + timedelta(days=400) else None


def _norm(s: str) -> str:
    from genios_engine.reason.moments.screen_insight import _norm as norm
    return norm(s)


def answered(lines: list[str], quote: str) -> bool:
    """STRUCTURAL: a `You:` line comes after the (last) line that holds the ask's quote."""
    q = _norm(quote)
    if len(q) < 3:
        return False
    at = None
    for i, line in enumerate(lines):
        if q in _norm(line):
            at = i
    return at is not None and any(line.lstrip().casefold().startswith("you:")
                                  for line in lines[at + 1:])


def _unquote(body: str | None) -> str:
    return (body or "").strip().strip("“”\"").strip()


#: Hosts whose pages are conversations: one verdict per thread there, not per site.
CHAT_HOSTS = ("mail.google.com", "outlook.live.com", "outlook.office.com", "outlook.office365.com",
              "web.whatsapp.com", "app.slack.com", "teams.microsoft.com", "teams.live.com",
              "www.linkedin.com/messaging", "linkedin.com/messaging")
#: Hosts where every page is a different document or conversation (a CV and a client proposal
#: both live on docs.google.com): judged per page, never per site.
SHARED_HOSTS = ("google.com", "notion.so", "notion.site", "github.com", "gitlab.com", "linkedin.com",
                "figma.com", "dropbox.com", "box.com", "onedrive.live.com", "sharepoint.com",
                "office.com", "atlassian.net", "canva.com", "airtable.com", "trello.com", "asana.com",
                "monday.com", "clickup.com", "miro.com", "claude.ai", "chatgpt.com", "openai.com",
                "perplexity.ai", "youtube.com", "zoho.com", "zoho.in", "slack.com", "whatsapp.com")
_WEB_DOC = re.compile(r"^doc:[^:]+:(?!title:)(?P<host>[^/\s]+)(?P<path>/\S*)?$")


def verdict_key(thread_key: str | None) -> str | None:
    """Where the work / personal verdict lives: a web page → its site (`site:naukri.com`), so one
    judgement covers every page of a job board or a shop; a chat, a mail thread or an app window
    → the thread itself."""
    t = (thread_key or "").strip()
    m = _WEB_DOC.match(t)
    if not m:
        return t or None
    host = m.group("host").lower()
    if any((host + (m.group("path") or "")).startswith(h) for h in CHAT_HOSTS):
        return t
    if any(host == h or host.endswith("." + h) for h in SHARED_HOSTS):
        return t
    return "site:" + host.removeprefix("www.")


# ── reads ─────────────────────────────────────────────────────────────────────────────────────
_COLS = ("id, kind, text, who, thread_key, app, due_at, nudge_at, created_at, updated_at, "
         "resolved_at, resolution")


def item_out(r, *, full: bool = False) -> dict:
    out = {"id": r.id, "kind": r.kind, "text": r.text, "who": r.who, "thread_key": r.thread_key,
           "app": r.app, "due_at": iso(aware(r.due_at)), "nudge_at": iso(aware(r.nudge_at)),
           "created_at": iso(aware(r.created_at))}
    if full:
        out.update({"updated_at": iso(aware(r.updated_at)),
                    "resolved_at": iso(aware(r.resolved_at)), "resolution": r.resolution})
    return out


def seat_tz(conn, org_id: str, seat_id: str) -> str:
    """The seat's zone: its own delivery preference, else the org's (`orgs.timezone`), else UTC."""
    tz = conn.execute(text(
        "select coalesce((select d.tz_name from delivery_preferences d where d.org_id = o.id "
        " and d.seat_id in (:s, '*') and d.tz_name is not null "
        " order by (d.seat_id = :s) desc limit 1), o.timezone) from orgs o where o.id = :o"),
        {"o": org_id, "s": seat_id}).scalar()
    return tz if tz and zone(tz) is not timezone.utc else "UTC"


def topic_shown(conn, *, org_id: str, seat_id: str, capability_id: str, topic: str,
                now: datetime) -> bool:
    """C2: was an insight on this topic already SHOWN today (a queued / suppressed one is not)?"""
    return conn.execute(text(
        "select 1 from moments m where m.org_id = :o and m.seat_id = :s and m.display "
        "and m.capability_id = :cap and m.created_at > :now - interval '1 day' "
        "and m.evidence @> cast(:ev as jsonb) limit 1"),
        {"o": org_id, "s": seat_id, "cap": capability_id, "now": now,
         "ev": json.dumps([{"topic_key": topic}])}).first() is not None


def shown_last_hour(conn, *, org_id: str, seat_id: str, capability_id: str,
                    now: datetime) -> int:
    """C3: screen insights shown to the seat in the rolling hour."""
    return int(conn.execute(text(
        "select count(*) from moments m where m.org_id = :o and m.seat_id = :s and m.display "
        "and m.capability_id = :cap and m.created_at > :now - interval '1 hour'"),
        {"o": org_id, "s": seat_id, "cap": capability_id, "now": now}).scalar() or 0)


def open_items(conn, *, org_id: str, seat_id: str, limit: int = SLICE_MAX) -> list[dict]:
    rows = conn.execute(text(
        f"select {_COLS} from screen_followups where org_id = :o and seat_id = :s "
        "and resolved_at is null order by created_at desc, id desc limit :n"),
        {"o": org_id, "s": seat_id, "n": limit}).fetchall()
    return [item_out(r) for r in rows]


def seat_names(conn, *, org_id: str, email: str | None) -> list[str]:
    """Who the manager is, for the model: the seat's email, and its person node's name when the
    node carries a real name (not the email again)."""
    from genios_engine.platform.identity import norm_email
    e = norm_email(email)
    if not e:
        return []
    r = conn.execute(text(
        "select n.display_name from graph_aliases a join graph_nodes n on n.org_id = a.org_id "
        "and n.node_id = a.node_id and n.valid_to is null where a.org_id = :o "
        "and a.alias_type = 'email' and a.alias_key = :e limit 1"), {"o": org_id, "e": e}).first()
    name = (r.display_name or "").strip() if r is not None else ""
    return [e] + ([name] if name and name.casefold() != e else [])


def open_context(conn, *, org_id: str, seat_id: str, thread_key: str | None, screen: str,
                 limit: int = 5) -> list[dict]:
    """The open follow-ups the model should see for this screen: this thread's, and those whose
    `who` is named on screen (the same person elsewhere → "repeat ask" / "same ask elsewhere")."""
    hay = " ".join((screen or "").split()).casefold()
    out: list[dict] = []
    for it in open_items(conn, org_id=org_id, seat_id=seat_id, limit=LIST_MAX):
        names = [w for w in re.split(r"[\s,()/]+", (it.get("who") or "").casefold()) if len(w) >= 4]
        if (thread_key and it.get("thread_key") == thread_key) or any(n in hay for n in names):
            out.append(it)
            if len(out) >= limit:
                break
    return out


def removed_since(conn, *, org_id: str, seat_id: str, threshold: datetime) -> list[str]:
    return [r.id for r in conn.execute(text(
        "select id from screen_followups where org_id = :o and seat_id = :s "
        "and resolved_at is not null and resolved_at >= :t order by resolved_at limit 1000"),
        {"o": org_id, "s": seat_id, "t": threshold})]


def thread_verdict(conn, *, org_id: str, seat_id: str, thread_key: str | None,
                   now: datetime, hours: int = VERDICT_HOURS) -> dict | None:
    """C9 + K2: the model's judgement of the thread in the last 24 h — `{"work": bool,
    "memory": bool | None}` (memory None: the model gave none, e.g. a P8 row) — or None."""
    if not thread_key:
        return None
    r = conn.execute(text(
        "select work, memory from screen_thread_verdicts where org_id = :o and seat_id = :s "
        "and thread_key = :t and judged_at > :now - make_interval(hours => :h)"),
        {"o": org_id, "s": seat_id, "t": thread_key, "now": now, "h": hours}).first()
    return None if r is None else {"work": bool(r.work), "memory": r.memory}


def is_muted(conn, *, org_id: str, seat_id: str, thread_key: str | None, now: datetime) -> bool:
    """K4: is this thread's insight popup muted right now (Not useful → 7 days, Mute chat)?"""
    if not thread_key:
        return False
    return conn.execute(text(
        "select 1 from screen_thread_verdicts where org_id = :o and seat_id = :s "
        "and thread_key = :t and muted_until > :now"),
        {"o": org_id, "s": seat_id, "t": thread_key, "now": now}).first() is not None


def not_useful_notes(conn, *, org_id: str, seat_id: str, capability_id: str,
                     limit: int = NOT_USEFUL_NOTES) -> list[str]:
    """K4: the seat's last ≤ 5 insight notes it marked "not useful", newest first — the model's
    own notes (moments.headline), never screen text."""
    return [r.headline for r in conn.execute(text(
        "select m.headline from moments m join lateral (select max(f.at) as at "
        " from moment_feedback f where f.moment_id = m.moment_id and f.action = :a) f on true "
        "where m.org_id = :o and m.seat_id = :s and m.capability_id = :cap and f.at is not null "
        "order by f.at desc limit :n"),
        {"o": org_id, "s": seat_id, "cap": capability_id, "a": NOT_USEFUL_ACTION,
         "n": max(0, int(limit))}) if r.headline]


def verdict_lookup(engine, org_id: str, seat_id: str):
    """`thread_key -> {"work", "memory"} | None` for one promotion batch (one read per thread,
    memoised)."""
    memo: dict[str, dict | None] = {}

    def lookup(thread_key: str | None) -> dict | None:
        if not thread_key:
            return None
        if thread_key not in memo:
            with engine.connect() as c:
                memo[thread_key] = thread_verdict(c, org_id=org_id, seat_id=seat_id,
                                                  thread_key=verdict_key(thread_key),
                                                  now=datetime.now(timezone.utc))
        return memo[thread_key]

    return lookup


# ── writes ────────────────────────────────────────────────────────────────────────────────────
_BUMP_SEAT = text(
    "with up as (update seat_slice_versions set version = greatest(version + 1, "
    " cast(extract(epoch from clock_timestamp()) * 1000 as bigint)), updated_at = now() "
    " where org_id = :o and seat_id = :s returning version) "
    "insert into realtime_events (org_id, seat_id, kind, payload) "
    "select :o, :s, 'slice.delta', jsonb_build_object('version', version) from up")


def _bump(conn, org_id: str, seat_id: str) -> bool:
    """The seat's slice changed (a follow-up opened / closed): bump its version and announce
    `slice.delta` so its other devices fetch it. No row yet = no device has read a slice."""
    if conn.dialect.name != "postgresql":
        return False
    return bool(conn.execute(_BUMP_SEAT, {"o": org_id, "s": seat_id}).rowcount)


def set_verdict(engine, *, org_id: str, seat_id: str, thread_key: str, work: bool,
                now: datetime, memory: bool | None = None) -> None:
    """The instant call's latest judgement of the thread (K2). A mute is left as it is."""
    mem = False if not work else memory
    with engine.begin() as c:
        c.execute(text(
            "insert into screen_thread_verdicts (org_id, seat_id, thread_key, work, memory, "
            "judged_at) values (:o, :s, :t, :w, :m, :now) on conflict (org_id, seat_id, "
            "thread_key) do update set work = excluded.work, memory = excluded.memory, "
            "judged_at = excluded.judged_at"),
            {"o": org_id, "s": seat_id, "t": thread_key, "w": bool(work), "m": mem, "now": now})


def mute(engine, *, org_id: str, seat_id: str, thread_key: str, until: datetime,
         now: datetime) -> None:
    """K4: no insight popups for (seat, thread) until `until` (a longer mute is never shortened).
    A thread with no verdict row gets one that is NOT a verdict (judged before the 24 h window),
    so a mute never changes how the thread's memory is routed."""
    with engine.begin() as c:
        c.execute(text(
            "insert into screen_thread_verdicts as v (org_id, seat_id, thread_key, work, "
            "judged_at, muted_until) values (:o, :s, :t, true, :old, :u) "
            "on conflict (org_id, seat_id, thread_key) do update "
            "set muted_until = greatest(coalesce(v.muted_until, excluded.muted_until), "
            "excluded.muted_until)"),
            {"o": org_id, "s": seat_id, "t": thread_key, "u": until,
             "old": now - timedelta(hours=VERDICT_HOURS + 1)})


def learn_from_feedback(engine, *, org_id: str, seat_id: str, moment_id: str, action: str,
                        reason: str | None, capability_id: str, now: datetime) -> datetime | None:
    """K4: feedback on a screen-insight moment → mute its thread. "Not useful" (`wrong`) → 7 days;
    reason `mute_chat` (the device's Mute chat, any action) → for good. Returns the mute's end,
    or None (another capability, no thread on the moment, or an ordinary action)."""
    muting = (reason or "").strip().lower() == MUTE_REASON
    if action != NOT_USEFUL_ACTION and not muting:
        return None
    with engine.connect() as c:
        r = c.execute(text(
            "select capability_id, actions from moments where moment_id = :m and org_id = :o "
            "and seat_id = :s"), {"m": moment_id, "o": org_id, "s": seat_id}).first()
    if r is None or r.capability_id != capability_id:
        return None
    actions = r.actions if isinstance(r.actions, list) else json.loads(r.actions or "[]")
    thread = next((str((a.get("payload") or {}).get("thread_key") or "") for a in actions
                   if isinstance(a, dict) and a.get("id") == MUTE_REASON), "").strip()
    if not thread:
        return None
    until = MUTE_FOREVER if muting else now + NOT_USEFUL_MUTE
    mute(engine, org_id=org_id, seat_id=seat_id, thread_key=thread, until=until, now=now)
    return until


def upsert(engine, *, org_id: str, seat_id: str, kind: str, note: str, who: str | None,
           due_at: datetime | None, thread_key: str | None, app: str | None, topic: str,
           tz_name: str | None, now: datetime, quote: str | None = None) -> dict | None:
    """Open (or refresh) the topic's follow-up. A topic already resolved today stays closed →
    None. The nudge clock runs from the row's FIRST sighting, so a repeat never delays it."""
    if kind not in KINDS:
        raise ValueError(f"unknown follow-up kind: {kind}")
    note = " ".join((note or "").split())[:TEXT_MAX]
    who = (" ".join(who.split())[:WHO_MAX] or None) if who else None
    fid = followup_id(org_id, seat_id, topic)
    shown = False
    with engine.begin() as c:
        prev = c.execute(text(
            "select created_at, due_at, resolved_at from screen_followups "
            "where org_id = :o and seat_id = :s and topic_key = :k for update"),
            {"o": org_id, "s": seat_id, "k": topic}).first()
        if prev is not None and prev.resolved_at is not None:
            return None
        created = aware(prev.created_at) if prev is not None else now
        due = due_at or (aware(prev.due_at) if prev is not None else None)
        r = c.execute(text(
            "insert into screen_followups as f (id, org_id, seat_id, thread_key, app, kind, text, "
            "who, due_at, nudge_at, topic_key, created_at, updated_at, quote) values (:id, :o, "
            ":s, :t, :app, :kind, :text, :who, :due, :nudge, :k, :now, :now, :quote) "
            "on conflict (org_id, seat_id, topic_key) do update set text = excluded.text, "
            "who = coalesce(excluded.who, f.who), due_at = excluded.due_at, "
            "quote = coalesce(excluded.quote, f.quote), "
            # what memory holds changed → it is written to the graph again (0162)
            "graph_written_at = case when f.text is distinct from excluded.text "
            "or f.due_at is distinct from excluded.due_at "
            "or coalesce(excluded.who, f.who) is distinct from f.who "
            "then null else f.graph_written_at end, "
            "nudge_at = excluded.nudge_at, updated_at = excluded.updated_at "
            "where f.resolved_at is null returning " + _COLS),
            {"id": fid, "o": org_id, "s": seat_id, "t": thread_key, "app": app, "kind": kind,
             "text": note, "who": who, "due": due, "k": topic, "now": now,
             "quote": (" ".join(quote.split())[:200] or None) if quote else None,
             "nudge": nudge_at(kind, created_at=created, due_at=due, tz_name=tz_name)}).first()
        if r is not None:
            shown = _bump(c, org_id, seat_id)
    if shown:
        realtime.wake()
    return item_out(r) if r is not None else None


def mark_answered(engine, *, org_id: str, seat_id: str, thread_key: str | None,
                  lines: list[str], capability_id: str, now: datetime) -> list[str]:
    """C4 ask answered: the open asks of this thread whose quote line has a `You:` line after it
    on the screen now → `answered`. Returns the ids closed."""
    if not thread_key or not lines:
        return []
    with engine.connect() as c:
        asks = c.execute(text(
            "select f.id, coalesce(f.quote, q.body) as body from screen_followups f "
            "left join lateral (select m.body from moments m "
            " where m.org_id = f.org_id and m.seat_id = f.seat_id and m.capability_id = :cap "
            " and m.created_at > f.created_at - interval '1 hour' "
            " and m.evidence @> jsonb_build_array(jsonb_build_object('topic_key', f.topic_key)) "
            " order by m.created_at desc limit 1) q on true "
            "where f.org_id = :o and f.seat_id = :s and f.thread_key = :t and f.kind = 'ask' "
            "and f.resolved_at is null and coalesce(f.quote, q.body) is not null"),
            {"o": org_id, "s": seat_id, "t": thread_key, "cap": capability_id}).fetchall()
    done = [a.id for a in asks if answered(lines, _unquote(a.body))]
    if not done:
        return []
    shown = False
    with engine.begin() as c:
        n = c.execute(text(
            "update screen_followups set resolved_at = :now, resolution = 'answered', "
            "updated_at = :now where org_id = :o and seat_id = :s and id = any(:ids) "
            "and resolved_at is null"), {"o": org_id, "s": seat_id, "ids": done, "now": now}
        ).rowcount or 0
        if n:
            shown = _bump(c, org_id, seat_id)
    if shown:
        realtime.wake()
    return done


def resolve(engine, *, org_id: str, seat_id: str, followup_id: str, resolution: str,
            now: datetime) -> dict | None:
    """The person closes one (`done` / `dismissed`). Idempotent: an already-closed follow-up
    answers its current state. None when it is not this seat's."""
    if resolution not in ("done", "dismissed"):
        raise ValueError(f"resolution must be done or dismissed, not {resolution}")
    shown = False
    with engine.begin() as c:
        r = c.execute(text(
            "update screen_followups set resolved_at = :now, resolution = :r, updated_at = :now "
            "where id = :id and org_id = :o and seat_id = :s and resolved_at is null "
            "returning " + _COLS),
            {"id": followup_id, "o": org_id, "s": seat_id, "r": resolution, "now": now}).first()
        if r is None:
            r = c.execute(text(f"select {_COLS} from screen_followups where id = :id "
                               "and org_id = :o and seat_id = :s"),
                          {"id": followup_id, "o": org_id, "s": seat_id}).first()
        else:
            shown = _bump(c, org_id, seat_id)
    if shown:
        realtime.wake()
    return item_out(r, full=True) if r is not None else None


def expire(conn, *, org_id: str, seat_id: str, now: datetime) -> int:
    """Open follow-ups past their life → `expired`. Run on read (slice, list): no periodic task.
    Promises 2 days past due (undated: never); asks 7 days after they were first seen; deadlines
    1 day after due (undated: 7 days); risks / next steps after 3 days (K5)."""
    return conn.execute(text(
        "update screen_followups set resolved_at = :now, resolution = 'expired', updated_at = :now "
        "where org_id = :o and seat_id = :s and resolved_at is null and ("
        " (kind in ('my_promise', 'their_promise') and due_at is not null and due_at < :promise)"
        " or (kind = 'ask' and created_at < :ask)"
        " or (kind = 'deadline' and ((due_at is not null and due_at < :deadline)"
        "      or (due_at is null and created_at < :undated)))"
        " or (kind in ('risk', 'next_step') and created_at < :brief))"),
        {"o": org_id, "s": seat_id, "now": now, "promise": now - EXPIRE_AFTER,
         "ask": now - ASK_EXPIRE, "deadline": now - DEADLINE_EXPIRE,
         "undated": now - UNDATED_EXPIRE, "brief": now - BRIEF_EXPIRE}).rowcount or 0


def listing(engine, *, org_id: str, seat_id: str, status: str = "open", limit: int = 50,
            now: datetime | None = None) -> dict:
    """`GET /v1/followups`: open (newest first) or all, with resolution fields."""
    now = now or datetime.now(timezone.utc)
    limit = max(1, min(int(limit or 50), LIST_MAX))
    with engine.begin() as c:
        expire(c, org_id=org_id, seat_id=seat_id, now=now)
        rows = c.execute(text(
            f"select {_COLS} from screen_followups where org_id = :o and seat_id = :s "
            "and (:all or resolved_at is null) order by created_at desc, id desc limit :n"),
            {"o": org_id, "s": seat_id, "all": status == "all", "n": limit}).fetchall()
    return {"followups": [item_out(r, full=True) for r in rows]}


def week_bounds(week_start: date | None, *, tz_name: str | None,
                now: datetime) -> tuple[date, datetime, datetime]:
    """(week_start, start, end): the local week [Mon 00:00, next Mon 00:00) as UTC instants.
    No week_start → the current local week."""
    tz = zone(tz_name)
    if week_start is None:
        today = now.astimezone(tz).date()
        week_start = today - timedelta(days=today.weekday())
    start = datetime.combine(week_start, dtime(0), tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(week_start + timedelta(days=7), dtime(0),
                           tzinfo=tz).astimezone(timezone.utc)
    return week_start, start, end


def weekly_report(engine, *, org_id: str, seat_id: str, capability_id: str,
                  week_start: date | None = None, now: datetime | None = None) -> dict:
    """C8: the seat's week in counts — follow-ups created that week (and how they ended), and the
    screen insights shown that week (and what the person said about them)."""
    now = now or datetime.now(timezone.utc)
    with engine.connect() as c:
        tz = seat_tz(c, org_id, seat_id)
        ws, start, end = week_bounds(week_start, tz_name=tz, now=now)
        p = {"o": org_id, "s": seat_id, "a": start, "b": end, "cap": capability_id}
        f = c.execute(text(
            "select count(*) filter (where kind in ('my_promise', 'their_promise')) as caught, "
            "count(*) filter (where kind in ('my_promise', 'their_promise') "
            " and resolution = 'done') as kept, "
            "count(*) filter (where kind = 'ask') as asks, "
            "count(*) filter (where kind = 'ask' and resolution in ('answered', 'done')) as answered, "
            "count(*) filter (where kind = 'deadline') as deadlines, "
            "count(*) filter (where kind = 'risk') as risks "
            "from screen_followups where org_id = :o and seat_id = :s "
            "and created_at >= :a and created_at < :b"), p).mappings().first()
        m = c.execute(text(
            "select count(*) filter (where m.display) as shown, "
            "count(*) filter (where exists (select 1 from moment_feedback x "
            " where x.moment_id = m.moment_id and x.action = 'useful')) as useful, "
            "count(*) filter (where exists (select 1 from moment_feedback x "
            " where x.moment_id = m.moment_id and x.action = 'wrong')) as not_useful "
            "from moments m where m.org_id = :o and m.seat_id = :s and m.capability_id = :cap "
            "and m.created_at >= :a and m.created_at < :b"), p).mappings().first()
    return {"week_start": ws.isoformat(), "week_end": (ws + timedelta(days=6)).isoformat(),
            "promises_caught": int(f["caught"] or 0), "promises_kept": int(f["kept"] or 0),
            "asks_flagged": int(f["asks"] or 0), "asks_answered": int(f["answered"] or 0),
            "deadlines_flagged": int(f["deadlines"] or 0), "risks_flagged": int(f["risks"] or 0),
            "popups_shown": int(m["shown"] or 0), "useful": int(m["useful"] or 0),
            "not_useful": int(m["not_useful"] or 0)}


def purge(conn, *, now: datetime) -> dict:
    """Retention (maintenance heartbeat, via store.purge_expired): resolved follow-ups on their
    org's capture `retention_days` (90 without a policy row), like the moments they came from;
    thread verdicts a week after their 24 h use — unless a mute on them is still running."""
    fu = conn.execute(text(
        "delete from screen_followups f where f.resolved_at is not null and f.resolved_at < "
        ":now - make_interval(days => coalesce((select p.retention_days from capture_policies p "
        "where p.org_id = f.org_id), 90))"), {"now": now}).rowcount or 0
    vd = conn.execute(text(
        "delete from screen_thread_verdicts where judged_at < :cut "
        "and (muted_until is null or muted_until < :now)"),
        {"cut": now - timedelta(days=VERDICT_RETENTION_DAYS), "now": now}).rowcount or 0
    return {"screen_followups": fu, "screen_thread_verdicts": vd}


__all__ = ["KINDS", "MUTE_FOREVER", "NOT_USEFUL_MUTE", "RESOLUTIONS", "add_working_days",
           "answered", "expire", "followup_id", "is_muted", "item_out", "learn_from_feedback",
           "listing", "map_kind", "mark_answered", "mute", "not_useful_notes", "nudge_at",
           "open_items",
           "parse_due", "purge", "removed_since", "resolve", "seat_tz", "set_verdict",
           "shown_last_hour", "thread_verdict", "topic_key", "topic_shown", "upsert",
           "verdict_lookup", "week_bounds", "weekly_report"]
