"""Hot-lane API — SCREEN_INTEL_P3_BUILD.md §2.1–2.4, §2.6 (frozen + pinned 2026-09-13).

  GET  /v1/seats/me/slice?since=<version>        device token   the seat's graph slice
  POST /v1/moments/evaluate                       device token   server moments (P-02), no LLM
  POST /v1/moments                                device token   device-local moments (P-01/P-18)
  POST /v1/moments/{moment_id}/feedback           device or seat
  GET  /v1/moments?limit&before&kind              device or seat the seat's own history
  GET  /v1/followups?status=open|all&limit        device or seat P8 C5 screen follow-ups
  POST /v1/followups/{id}/resolve                 device or seat done | dismissed
  POST /v1/followups/{id}/snooze                  device or seat P10 move the nudge
  POST /v1/followups/{id}/draft                   device or seat P10 a reply draft (never stored)
  GET  /v1/seats/me/weekly-report?week_start      device or seat P8 C8 the week in counts

NEVER CREDIT-CHARGED (D6). Every handler is a few statements on the process's one pool (session
pooler 8+4): auth is one, the slice ~9, an evaluate ~10 including the persist transaction.
"""
from __future__ import annotations

import gzip
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from genios_engine.api.device_routes import _bearer, _err
from genios_engine.contracts.moments import (KINDS, DeviceMoment, EvaluateRequest,
                                             FeedbackRequest, FollowupResolveRequest,
                                             FollowupSnoozeRequest)
from genios_engine.platform import capture_policy as P
from genios_engine.platform import devices as D
from genios_engine.platform.auth import check_org_kill, jwt_decode, verify_bearer
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger
from genios_engine.reason.moments import guards as G
from genios_engine.reason.moments import recall as R
from genios_engine.reason.moments import slice as S
from genios_engine.reason.moments import store as M
from genios_engine.reason.moments.common import viewer_key

router = APIRouter(tags=["moments"])
_log = get_logger("genios.moments")
_NO_CONTENT = 204


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Principal:
    org_id: str
    seat_id: str
    device_id: str | None          # None = a signed-in seat (dashboard), not a device
    email: str | None
    expires_at: float | None       # the access token's `exp` (epoch seconds)


def _exp(token: str | None) -> float | None:
    payload = jwt_decode(token or "", get_settings().jwt_secret, verify_exp=False) if token else None
    try:
        return float(payload["exp"]) if payload and payload.get("exp") else None
    except (TypeError, ValueError):
        return None


def principal(request: Request, dstore, *, device_only: bool = False):
    """A device token → its seat + device. Otherwise (device_only=False) a signed-in seat's
    session token. API keys are refused either way: they have no seat. Returns a Principal or the
    JSONResponse refusing it; auth HTTPExceptions propagate."""
    token = _bearer(request)
    try:
        ctx = D.resolve_device_token(token, dstore)
        request.state.org_id = ctx.org_id
        return Principal(ctx.org_id, ctx.seat_id, ctx.device_id, ctx.email, _exp(token))
    except D.DeviceAuthError as e:
        if (device_only or e.code != D.DEVICE_TOKEN_REQUIRED or not token
                or token.startswith("gn_")):
            return _err(e.status, e.code, e.message)
    ctx = verify_bearer(token)
    if not ctx.seat_id:
        return _err(403, "SEAT_REQUIRED", "A signed-in seat is required.")
    check_org_kill(ctx.org_id)
    request.state.org_id = ctx.org_id
    return Principal(ctx.org_id, ctx.seat_id, None, ctx.email, _exp(token))


# ── §2.1 slice ────────────────────────────────────────────────────────────────────────────────
@router.get("/v1/seats/me/slice")
def get_slice(request: Request, since: int | None = Query(default=None, ge=0)):
    dstore, cstore = D.stores()
    p = principal(request, dstore, device_only=True)
    if isinstance(p, JSONResponse):
        return p
    doc = S.build(cstore.engine, org_id=p.org_id, seat_id=p.seat_id, email=p.email, since=since)
    body = S.encode(doc)
    headers = {"Cache-Control": "no-store", "Vary": "Accept-Encoding"}
    if "gzip" in (request.headers.get("accept-encoding") or "").lower():
        return Response(gzip.compress(body, 5), media_type="application/json",
                        headers={**headers, "Content-Encoding": "gzip"})
    return Response(body, media_type="application/json", headers=headers)


# ── §2.2 evaluate ─────────────────────────────────────────────────────────────────────────────
def _stored(c, *, moment_id: str, org_id: str, seat_id: str) -> dict | None:
    r = c.execute(text(
        "select m.*, null as feedback from moments m where m.moment_id = :m "
        "and m.org_id = :o and m.seat_id = :s"),
        {"m": moment_id, "o": org_id, "s": seat_id}).mappings().first()
    if r is None:
        return None
    out = M.moment_out(r)
    keys = ("moment_id", "kind", "priority", "headline", "body", "actions", "evidence",
            "ttl_seconds", "capability_id", "capability_version", "display", "reason")
    return {k: out[k] for k in keys}


def _seat_emails(c, org_id: str) -> frozenset[str]:
    return frozenset(r.e for r in c.execute(text(
        "select lower(email) as e from org_seats where org_id = :o and email is not null"),
        {"o": org_id}))


@router.post("/v1/moments/evaluate")
def evaluate(body: EvaluateRequest, request: Request):
    started = time.perf_counter()
    dstore, cstore = D.stores()
    p = principal(request, dstore, device_only=True)
    if isinstance(p, JSONResponse):
        return p
    if body.device_id and body.device_id != p.device_id:
        return _err(403, "DEVICE_MISMATCH", "The body names a different device than the token.")
    if body.seat_id and body.seat_id != p.seat_id:
        return _err(403, "SEAT_MISMATCH", "The body names a different seat than the token.")
    now = _now()
    org, seat, _ = cstore.load(p.org_id, p.seat_id)
    eff = P.effective_policy(org, seat, now=now)
    s = body.surface
    # A moment is about what is on screen: nothing is evaluated while capture is off or paused,
    # nor on a surface the privacy gate blocks (banking, SSO, password managers …).
    if not eff["capture_on"]:
        return Response(status_code=_NO_CONTENT)
    engine = cstore.engine
    # P5 P-15: the desktop's meeting timer. Prep reads the calendar graph, never the screen, so the
    # surface privacy gate does not apply to it (capture off/paused still answers 204).
    if body.features.meeting_node_id:
        return _meeting_prep(body, p, engine, now, started)
    if P.is_blocked(s.url_domain, s.bundle_id, eff):
        return Response(status_code=_NO_CONTENT)
    # P4 §3.4 draft review: only when the org allows it AND the seat turned it on. Otherwise the
    # draft is ignored (never stored either way) and the request is an ordinary evaluate.
    if body.draft_text and body.draft_text.strip() and eff.get("draft_assist"):
        return _draft_review(body, p, engine, now, started)
    # P-20 screen insight: one short, grounded note about whatever is on screen (known people or
    # new ones). The screen text is never stored.
    if body.insight and body.visible_messages:
        return _screen_insight(body, p, engine, now, started)
    viewer = viewer_key(p.email)
    moment_id = M.server_moment_id(p.seat_id, body.moment_request_id)
    chosen = None
    with engine.connect() as c:
        prior = _stored(c, moment_id=moment_id, org_id=p.org_id, seat_id=p.seat_id)
        if prior is not None:                 # a retried request answers what the first did
            return prior
        subjects, me = R.resolve(c, org_id=p.org_id, participants=body.participants,
                                 entities=body.features.entities, seat_email=p.email)
        if not subjects:
            return Response(status_code=_NO_CONTENT)
        seat_emails = _seat_emails(c, p.org_id)
        for subj in subjects[:3]:
            version = R.subject_version(c, org_id=p.org_id, node_ids=[subj.node_id])
            # "last touch N d ago" changes daily, so the day is part of the trigger.
            trig = M.trigger_digest(R.CAPABILITY_ID, subj.node_id, now.date().isoformat())
            key = M.cache_key(seat_id=p.seat_id, capability_id=R.CAPABILITY_ID,
                              subject_ids=[subj.node_id], trigger=trig, subject_version=version)
            hit = M.cached(c, key, now)
            if hit is not None and hit.get("displayed"):      # only a SHOWN twin is a duplicate
                return {**M._public(hit), "display": False, "reason": G.DUPLICATE}
            content = R.compose(R.read(c, org_id=p.org_id, subject=subj, me=me, viewer=viewer,
                                       seat_emails=seat_emails, now=now), now=now)
            if content is not None:
                chosen = (subj, key, content)
                break
    if chosen is None:
        return Response(status_code=_NO_CONTENT)
    subj, key, content = chosen
    try:
        out = M.persist(engine, org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id,
                        origin="server", moment={"moment_id": moment_id, **content},
                        subject_ids=[subj.node_id], now=now, key=key)
    except M.MomentConflict:
        return _err(409, "MOMENT_ID_CONFLICT", "That moment id belongs to another seat.")
    _log.info("moment evaluated org=%s seat=%s cap=%s display=%s reason=%s ms=%.0f", p.org_id,
              p.seat_id, R.CAPABILITY_ID, out["display"], out["reason"],
              (time.perf_counter() - started) * 1000)
    return out


def _meeting_prep(body: EvaluateRequest, p: Principal, engine, now: datetime, started: float):
    """P-15 (P5 §3): `moment.meeting_prep` for a meeting the seat attends — the precomputed prep
    (re-timed) or one built now; 204 unless the seat attends a live meeting with something to say.
    Deterministic, no LLM, never credit-charged."""
    from genios_engine.reason.meetings import prep as MP
    moment_id = M.server_moment_id(p.seat_id, body.moment_request_id)
    with engine.connect() as c:
        prior = _stored(c, moment_id=moment_id, org_id=p.org_id, seat_id=p.seat_id)
        if prior is not None:
            return prior
        res = MP.lookup(c, org_id=p.org_id, seat_id=p.seat_id, email=p.email,
                        meeting_node_id=body.features.meeting_node_id or "", now=now)
    if res is None:
        return Response(status_code=_NO_CONTENT)
    if res.duplicate:
        return {**res.content, "display": False, "reason": G.DUPLICATE}
    try:
        out = M.persist(engine, org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id,
                        origin="server", moment={"moment_id": moment_id, **res.content},
                        subject_ids=res.subject_ids, now=now, key=res.key)
    except M.MomentConflict:
        return _err(409, "MOMENT_ID_CONFLICT", "That moment id belongs to another seat.")
    _log.info("meeting prep org=%s seat=%s display=%s reason=%s ms=%.0f", p.org_id, p.seat_id,
              out["display"], out["reason"], (time.perf_counter() - started) * 1000)
    return out


def _draft_review(body: EvaluateRequest, p: Principal, engine, now: datetime, started: float):
    """≤ 2 notes about the draft, or 204 (nothing to say / the 2.8 s budget ran out). The draft
    text is never stored: only its hash is in the dedupe key and the evidence."""
    from genios_engine.reason.moments import draft_review as DR
    moment_id = M.server_moment_id(p.seat_id, body.moment_request_id)
    with engine.connect() as c:
        prior = _stored(c, moment_id=moment_id, org_id=p.org_id, seat_id=p.seat_id)
    if prior is not None:
        return prior
    res = DR.review(engine, org_id=p.org_id, email=p.email, participants=body.participants,
                    entities=body.features.entities, draft=body.draft_text or "", now=now,
                    seat_id=p.seat_id)
    if res is None:
        return Response(status_code=_NO_CONTENT)
    key = M.cache_key(seat_id=p.seat_id, capability_id=DR.CAPABILITY_ID,
                      subject_ids=res["subject_ids"],
                      trigger=M.trigger_digest(DR.CAPABILITY_ID,
                                               DR.draft_digest(body.draft_text or "")),
                      subject_version="draft")
    try:
        out = M.persist(engine, org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id,
                        origin="server", moment={"moment_id": moment_id, **res["content"]},
                        subject_ids=res["subject_ids"], now=now, key=key)
    except M.MomentConflict:
        return _err(409, "MOMENT_ID_CONFLICT", "That moment id belongs to another seat.")
    _log.info("draft review org=%s seat=%s display=%s reason=%s ms=%.0f", p.org_id, p.seat_id,
              out["display"], out["reason"], (time.perf_counter() - started) * 1000)
    return out


QUEUED_FOR_BRIEF = "queued_for_brief"


_MEETINGS_TTL_S = 600.0
_MEETINGS_MEMO_MAX = 5000
_meetings_memo: dict[tuple[str, str], tuple[float, list]] = {}
_meetings_inflight: set[tuple[str, str]] = set()
_MEETINGS_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="clash-meetings")


def _refresh_meetings(engine, org_id: str, seat_id: str, email: str | None) -> None:
    from datetime import timedelta

    from genios_engine.platform.identity import norm_email
    from genios_engine.reason.moments import slice as S
    from genios_engine.reason.moments.common import parse_ts
    k = (org_id, seat_id)
    out = (_meetings_memo.get(k) or (0.0, []))[1]          # a failure keeps the last known list
    try:
        now = datetime.now(timezone.utc)
        with engine.connect() as c:
            doc = S._build(c, org_id=org_id, seat_id=seat_id,
                           email=norm_email(email) or viewer_key(email),
                           viewer=viewer_key(email), now=now, threshold=None)
        end = now + timedelta(days=2)
        out = [m for m in doc.get("meetings") or []
               if (s := parse_ts(m.get("start_at"))) is not None and s <= end]
    except Exception:      # noqa: BLE001 — a clash check is a bonus, never a failed request
        _log.info("screen insight: meetings for the clash check not read org=%s", org_id)
    finally:
        if len(_meetings_memo) >= _MEETINGS_MEMO_MAX and k not in _meetings_memo:
            _meetings_memo.pop(next(iter(_meetings_memo)))
        _meetings_memo[k] = (time.monotonic(), out)
        _meetings_inflight.discard(k)


def _meetings_soon(engine, p: Principal, now: datetime) -> list[dict]:
    """The seat's meetings in the next 2 days, for the one judge's "does this clash?". Never on
    the request's critical path: the last known list is returned at once and a stale or missing
    one is refreshed in the background (the slice's own graph read, at most every 10 min per seat
    and process)."""
    k = (p.org_id, p.seat_id)
    hit = _meetings_memo.get(k)
    if (hit is None or time.monotonic() - hit[0] >= _MEETINGS_TTL_S) and k not in _meetings_inflight:
        _meetings_inflight.add(k)
        try:
            _MEETINGS_POOL.submit(_refresh_meetings, engine, p.org_id, p.seat_id, p.email)
        except RuntimeError:       # interpreter shutting down
            _meetings_inflight.discard(k)
    return hit[1] if hit is not None else []


def _screen_insight(body: EvaluateRequest, p: Principal, engine, now: datetime, started: float):
    """P-20 · the ONE judge (docs/screen-intelligence/index.html phase 1): 204 unless the screen ADDS
    something the manager cannot see on it. Every judged item is saved either way.

      waste rules  the same screen is judged once (screen-hash key); `screen_insight_daily_cap`
                   model checks per seat per day; a web SITE judged personal in the last 24 h
                   gets no model call; a muted thread gets none either (K4); an open ask whose
                   quote now has a `You:` line after it is closed `answered` first (structural);
      the model    one call judges work / remember (verdict per thread, per site for web pages),
                   0–3 grounded items, and a note only when it adds (repeat ask, promise owed,
                   calendar clash, same ask elsewhere, urgent risk);
      items        every item → a follow-up with its quote (nudges, brief, "answered", memory);
      C2 topic     one SHOWN note per topic per day;
      C3 budget    ≤ `screen_insight_max_per_hour` shown per seat; over → stored hidden
                   (`queued_for_brief`)."""
    from genios_engine.reason.moments import followups as F
    from genios_engine.reason.moments import screen_insight as SI
    from genios_engine.reason.moments import screen_rules as RU
    from genios_engine.reason.moments import screen_triage as T
    screen = SI.visible_text(body.visible_messages)
    if len(screen) < SI.MIN_TEXT_CHARS:
        return Response(status_code=_NO_CONTENT)
    # Free before paid: a screen no rule can call work does not buy a model call. It still
    # reaches the promoter and the hourly memory batch, which judges work / personal itself —
    # late and at half price instead of instantly and dear. Counted, never silent.
    if getattr(get_settings(), "screen_insight_triage_enabled", True):
        why = T.skip_reason(app=body.surface.app, bundle_id=body.surface.bundle_id,
                            url_domain=body.surface.url_domain,
                            thread_key=body.surface.thread_key,
                            entities=body.features.entities, participants=body.participants,
                            seat_email=p.email)
        if why is not None:
            SI.note_skipped(engine, org_id=p.org_id, seat_id=p.seat_id, now=now)
            _log.info("screen insight skipped org=%s seat=%s why=%s", p.org_id, p.seat_id, why)
            return Response(status_code=_NO_CONTENT)
    moment_id = M.server_moment_id(p.seat_id, body.moment_request_id)
    digest = SI.text_digest(screen)
    thread = (body.surface.thread_key or "").strip() or None
    vkey = F.verdict_key(thread)
    app = (body.surface.app or "").strip().lower() or None
    key = M.cache_key(seat_id=p.seat_id, capability_id=SI.CAPABILITY_ID, subject_ids=[],
                      trigger=M.trigger_digest(SI.CAPABILITY_ID, digest), subject_version="screen")
    with engine.connect() as c:
        prior = _stored(c, moment_id=moment_id, org_id=p.org_id, seat_id=p.seat_id)
        if prior is not None:
            return prior
        judged = M.cached(c, key, now) is not None     # this exact screen was already judged
        tz = F.seat_tz(c, p.org_id, p.seat_id)
        muted = F.any_muted(c, org_id=p.org_id, seat_id=p.seat_id,
                            thread_keys=[thread, vkey], now=now)
        site = (F.thread_verdict(c, org_id=p.org_id, seat_id=p.seat_id, thread_key=vkey, now=now)
                if vkey and vkey != thread else None)
        # This THREAD's own verdict (router check 5 reads it): once somebody has judged the chat
        # work, a rule may answer every later screen on it without a model.
        verdict = (F.thread_verdict(c, org_id=p.org_id, seat_id=p.seat_id, thread_key=thread,
                                    now=now) if thread else None)
        # PERSONAL IS A JUDGEMENT ABOUT A SCREEN, NOT A SENTENCE ON A CHAT.
        #
        # It lasts 24 hours and, until now, silenced everything on that thread for all of them.
        # Measured on the founder's own tenant on 17 Sep: 39 threads judged personal against 8
        # judged work, and among the 39 were his colleague's chat and his entire Gmail. He wrote a
        # real request in one of them, waited, and nothing came — because nothing was ever read.
        # Worse, it ratchets: the more he used it, the more threads locked, the quieter it got.
        #
        # So a personal verdict now silences only what looks personal. If the lines that ARRIVED
        # SINCE carry a plain request or a promise — the deterministic extractor's own reading,
        # not a guess — the screen is judged again and the verdict is re-earned.
        personal_site = ((site is not None and site["work"] is False)
                         or (verdict is not None and verdict["work"] is False))
        if personal_site and _looks_like_work(body, tz, me=None, now=now):
            personal_site = False
            _log.info("screen insight: personal thread spoke up org=%s seat=%s", p.org_id,
                      p.seat_id)
        # P13: an AI assistant's own chat page is the manager thinking out loud — never judged.
        assistant = F.is_assistant_page(thread)
        skip = judged or muted or personal_site or assistant
        # K4 + P15: what the seat refused and what it kept — one statement, not two.
        taught = ({"useful": [], "not_useful": []} if skip
                  else F.taught_notes(c, org_id=p.org_id, seat_id=p.seat_id,
                                      capability_id=SI.CAPABILITY_ID))
        notes, kept = taught["not_useful"], taught["useful"]
        context = [] if skip else F.open_context(c, org_id=p.org_id, seat_id=p.seat_id,
                                                 thread_key=thread, screen=screen)
        me = [] if skip else F.seat_names(c, org_id=p.org_id, email=p.email)
        # the chat's earlier batch summary (S4) and the seat's weekly profile (S8), for context
        from genios_engine.reason.moments import screen_memory_batch as MB
        from genios_engine.reason.moments import seat_profile as SPF
        summary = None if skip else MB.thread_summary(c, org_id=p.org_id, seat_id=p.seat_id,
                                                      thread_key=thread, now=now)
        profile = None if skip else SPF.profile_text(c, org_id=p.org_id, seat_id=p.seat_id, now=now)
    viewer = " ".join((body.viewer_name or "").split())[:200]
    if viewer and not skip and viewer.casefold() not in {m.casefold() for m in me}:
        me.append(viewer)                              # the device account's full name
    F.mark_answered(engine, org_id=p.org_id, seat_id=p.seat_id, thread_key=thread,
                    lines=screen.split("\n"), capability_id=SI.CAPABILITY_ID, now=now)
    if judged:
        return Response(status_code=_NO_CONTENT)
    if muted:                                          # K4: the person said this chat is noise
        _log.info("screen insight: thread muted org=%s seat=%s", p.org_id, p.seat_id)
        return Response(status_code=_NO_CONTENT)
    if personal_site:                                  # one judgement per site per day
        _log.info("screen insight: site judged personal org=%s seat=%s", p.org_id, p.seat_id)
        return Response(status_code=_NO_CONTENT)
    if assistant:                                      # P13: an AI chat is not a person's request
        _log.info("screen insight: assistant page org=%s seat=%s", p.org_id, p.seat_id)
        return Response(status_code=_NO_CONTENT)
    settings = get_settings()
    # ROUTER CHECK 5 (plan Fig 10.1): what a RULE can answer, the model is not asked. A message
    # line carries its own sender and its own words, and the device already resolved its dates —
    # so "Priya Shah: kal tak revised quote bhej dena" is an ask, a who and a due without anyone
    # reading it. The quote IS the item, so no paraphrase and no model. The one judgement no rule
    # makes is work-vs-personal, which is why this only applies once the thread has a verdict:
    # the first sighting costs a call, every one for the next 24 h can be free.
    # G1. AN ITEM IS BORN FROM SOMETHING THAT HAPPENED, NOT FROM SOMETHING ON SCREEN.
    #
    # A screen holds every line still visible; re-opening last week's chat puts the same words in
    # front of the judge, which — being shown only a screen — read them as though they had just
    # arrived: "asked 1 min ago" on a message from Monday, and a model call to produce it. The
    # device now says which lines it had never seen. Everything else stays on the screen the model
    # reads (a request makes no sense without its thread) but cannot become an item: `said` is what
    # `reject` checks every quote against.
    fresh = body.new_messages if body.new_messages is not None else body.visible_messages
    ruled: list[dict] = []
    if getattr(settings, "screen_rules_enabled", True):
        ruled = [it for it in RU.extract(fresh, dates=body.features.dates,
                                         tz_name=tz, me=me, now=now)
                 # …answered on the WHOLE screen, though: the reply that settles it is often a
                 # line the device saw on an earlier read.
                 if not (it["kind"] == "ask"
                         and RU.answered_after(body.visible_messages, it["quote"], me))]
        judged_before = site is not None or verdict is not None
        if RU.enough(ruled, verdict_known=judged_before):
            return _rule_items(ruled, body, p, engine, thread, app, tz, now, started)
        # ROUTER CHECK 6: no rule could read it — but is there anything here to read? A screen
        # with no question, no request word, no date and no amount is not ambiguous, it is empty,
        # and the model answers nothing for it. That answer is free here.
        #
        # Never on a thread nobody has judged yet, though: that FIRST sighting is what produces
        # the work/personal verdict the rest of the product runs on, and a quiet screen is as
        # good a place to earn it as a loud one.
        if judged_before and not ruled and not RU.worth_asking(fresh, body.features.dates):
            SI.note_skipped(engine, org_id=p.org_id, seat_id=p.seat_id, now=now)
            _log.info("screen rules: nothing to ask about org=%s seat=%s", p.org_id, p.seat_id)
            return Response(status_code=_NO_CONTENT)
    cap = int(getattr(settings, "screen_insight_daily_cap", SI.DEFAULT_DAILY_CAP) or 0)
    if not SI.reserve(engine, org_id=p.org_id, seat_id=p.seat_id, cap=cap, now=now):
        _log.info("screen insight capped org=%s seat=%s", p.org_id, p.seat_id)
        return Response(status_code=_NO_CONTENT)
    _ensure_profile(engine, p, now)
    meetings = _meetings_soon(engine, p, now)
    res = SI.insight(engine, org_id=p.org_id, email=p.email, app=body.surface.app,
                     participants=body.participants, entities=body.features.entities,
                     screen=screen, now_local=SI.local_label(now, tz),
                     dates=body.features.dates, not_useful=notes,
                     useful=kept, said=RU.said(fresh, me), me=me,
                     open_items=context, meetings=meetings,
                     thread_key=thread, tz_name=tz, today=now.astimezone(F.zone(tz)).date(),
                     summary=summary, profile=profile)
    if res is not None and vkey and res["work"] is not None:
        F.set_verdict(engine, org_id=p.org_id, seat_id=p.seat_id, thread_key=vkey,
                      work=res["work"], memory=res.get("memory"), now=now)
    j = res["judged"] if res is not None else None
    local_date = now.astimezone(F.zone(tz)).date()
    topics: list[str] = []
    first_followup: str | None = None
    for it in (j["items"] if j else []):
        topic = F.topic_key(seat_id=p.seat_id, thread_key=thread, app=app, kind=it["kind"],
                            who=it["who"], local_date=local_date)
        saved = F.upsert(engine, org_id=p.org_id, seat_id=p.seat_id, kind=it["kind"],
                         note=it["text"], who=it["who"],
                         due_at=F.parse_due(it["due"], tz_name=tz, now=now), thread_key=thread,
                         app=app, topic=topic, tz_name=tz, now=now, quote=it["quote"])
        if not topics and saved is not None:           # the popup's first item is a follow-up
            first_followup = F.followup_id(p.org_id, p.seat_id, topic)
        topics.append(topic)
    # THE INTERRUPT IS CODE'S. The model proposed one of the five reasons a popup may exist;
    # `verify_adds` checks it against the open items read BEFORE this screen was judged and the
    # meetings the prompt already carried. Unverifiable ⇒ the items are saved and nobody is
    # interrupted — counted, because the suppression rate is the earliest drift signal there is.
    verified = None if j is None else SI.verify_adds(
        j["adds_candidate"], items=j["items"], open_items=context, meetings=meetings,
        thread_key=thread, tz_name=tz, now=now)
    if j is not None and j["note_candidate"] is not None and verified is None:
        SI.note_skipped(engine, org_id=p.org_id, seat_id=p.seat_id, now=now,
                        kind=SI.UNVERIFIED_KIND)
        _log.info("screen insight: note unverified org=%s seat=%s adds=%s", p.org_id, p.seat_id,
                  j["adds_candidate"])
    floor = float(getattr(settings, "screen_insight_confidence_floor", 0.0) or 0.0)
    below = bool(j and j["items"] and floor > 0
                 and (j["items"][0].get("confidence") or 1.0) < floor)
    if j is None or j["note_candidate"] is None or verified is None or below:
        _log.info("screen insight: saved silently org=%s seat=%s work=%s items=%d ms=%.0f",
                  p.org_id, p.seat_id, res and res["work"], len(topics),
                  (time.perf_counter() - started) * 1000)
        return Response(status_code=_NO_CONTENT)
    topic = topics[0]
    content = SI.moment_content(j, digest=digest, adds=verified, note=j["note_candidate"],
                                topic_key=topic, thread_key=thread, followup_id=first_followup)
    with engine.connect() as c:
        repeat = F.topic_shown(c, org_id=p.org_id, seat_id=p.seat_id,
                               capability_id=SI.CAPABILITY_ID, topic=topic, now=now)
        # …and the same sentence is the same interruption even when the topic differs: one site's
        # standing notice lived on four pages, so it was four topics and four popups.
        repeat = repeat or F.words_shown(c, org_id=p.org_id, seat_id=p.seat_id,
                                         capability_id=SI.CAPABILITY_ID,
                                         headline=content["headline"], now=now)
        shown = 0 if repeat else F.shown_last_hour(c, org_id=p.org_id, seat_id=p.seat_id,
                                                   capability_id=SI.CAPABILITY_ID, now=now)
    if repeat:                                         # C2: the follow-up is refreshed, no popup
        return Response(status_code=_NO_CONTENT)
    budget = int(getattr(settings, "screen_insight_max_per_hour", 3) or 0)
    try:
        out = M.persist(engine, org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id,
                        origin="server", moment={"moment_id": moment_id, **content},
                        subject_ids=res["subject_ids"], now=now, key=key,
                        hidden_reason=QUEUED_FOR_BRIEF if shown >= budget else None)
    except M.MomentConflict:
        return _err(409, "MOMENT_ID_CONFLICT", "That moment id belongs to another seat.")
    _log.info("screen insight org=%s seat=%s display=%s reason=%s adds=%s items=%d ms=%.0f",
              p.org_id, p.seat_id, out["display"], out["reason"], verified, len(topics),
              (time.perf_counter() - started) * 1000)
    return out


def _looks_like_work(body: EvaluateRequest, tz: str | None, *, me, now: datetime) -> bool:
    """Did somebody just ask for something, or promise something, on this screen?

    The rules only, and only over the lines that are NEW: a chat judged personal yesterday stays
    quiet through small talk, and speaks the moment a real request lands in it.
    """
    from genios_engine.reason.moments import screen_rules as RU
    fresh = body.new_messages if body.new_messages is not None else body.visible_messages
    if not fresh:
        return False
    return any(it["kind"] in ("ask", "my_promise", "their_promise")
               for it in RU.extract(fresh, dates=body.features.dates, tz_name=tz, me=me, now=now))


def _rule_items(items: list[dict], body: EvaluateRequest, p: Principal, engine, thread, app, tz,
                now: datetime, started: float):
    """Router check 5's answer: the screen said it outright, so nothing was asked and nothing was
    paid for. From here on it is the ordinary path — the same follow-up rows, the same topic
    keys, the same nudge ladder, and a popup only through the same gate the model's answers pass.
    The manager cannot tell which lane produced a card, and should not be able to."""
    from genios_engine.reason.moments import followups as F
    from genios_engine.reason.moments import screen_insight as SI
    from genios_engine.reason.moments import screen_rules as RU
    local_date = now.astimezone(F.zone(tz)).date()
    meetings = _meetings_soon(engine, p, now)
    with engine.connect() as c:
        context = F.open_context(c, org_id=p.org_id, seat_id=p.seat_id, thread_key=thread,
                                 screen=SI.visible_text(body.visible_messages))
    topics: list[str] = []
    first_followup: str | None = None
    for it in items:
        topic = F.topic_key(seat_id=p.seat_id, thread_key=thread, app=app, kind=it["kind"],
                            who=it["who"], local_date=local_date)
        saved = F.upsert(engine, org_id=p.org_id, seat_id=p.seat_id, kind=it["kind"],
                         note=it["text"], who=it["who"],
                         due_at=F.parse_due(it["due"], tz_name=tz, now=now), thread_key=thread,
                         app=app, topic=topic, tz_name=tz, now=now, quote=it["quote"])
        if not topics and saved is not None:
            first_followup = F.followup_id(p.org_id, p.seat_id, topic)
        topics.append(topic)
    proposed = RU.propose_adds(items, open_items=context, meetings=meetings, thread_key=thread,
                               tz_name=tz, now=now)
    if proposed is None:                               # the product rule: it adds nothing → silent
        _log.info("screen rules: saved silently org=%s seat=%s items=%d ms=%.0f", p.org_id,
                  p.seat_id, len(topics), (time.perf_counter() - started) * 1000)
        return Response(status_code=_NO_CONTENT)
    adds, note = proposed
    topic = topics[0]
    with engine.connect() as c:
        repeat = F.topic_shown(c, org_id=p.org_id, seat_id=p.seat_id,
                               capability_id=SI.CAPABILITY_ID, topic=topic, now=now)
        shown = 0 if repeat else F.shown_last_hour(c, org_id=p.org_id, seat_id=p.seat_id,
                                                   capability_id=SI.CAPABILITY_ID, now=now)
    if repeat:
        return Response(status_code=_NO_CONTENT)
    budget = int(getattr(get_settings(), "screen_insight_max_per_hour", 3) or 0)
    digest = SI.text_digest(SI.visible_text(body.visible_messages))
    content = SI.moment_content({"items": items}, digest=digest, adds=adds, note=note,
                                topic_key=topic, thread_key=thread, followup_id=first_followup)
    moment_id = M.server_moment_id(p.seat_id, body.moment_request_id)
    key = M.cache_key(seat_id=p.seat_id, capability_id=SI.CAPABILITY_ID, subject_ids=[],
                      trigger=M.trigger_digest(SI.CAPABILITY_ID, digest), subject_version="screen")
    try:
        out = M.persist(engine, org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id,
                        origin="server", moment={"moment_id": moment_id, **content},
                        subject_ids=[], now=now, key=key,
                        hidden_reason=QUEUED_FOR_BRIEF if shown >= budget else None)
    except M.MomentConflict:
        return _err(409, "MOMENT_ID_CONFLICT", "That moment id belongs to another seat.")
    _log.info("screen rules org=%s seat=%s display=%s adds=%s items=%d ms=%.0f", p.org_id,
              p.seat_id, out["display"], adds, len(topics), (time.perf_counter() - started) * 1000)
    return out


def _ensure_profile(engine, p: Principal, now: datetime) -> None:
    """P10: the weekly manager profile is (re)built in the background when missing or a week
    old — never on the request's critical path, never a failed request."""
    try:
        from genios_engine.reason.moments import seat_profile as SP
        SP.ensure_profile(engine, org_id=p.org_id, seat_id=p.seat_id, email=p.email, now=now)
    except Exception:      # noqa: BLE001
        _log.exception("seat profile schedule failed org=%s", p.org_id)


# ── P8 C5 follow-ups + C8 weekly report ───────────────────────────────────────────────────────
@router.get("/v1/followups")
def list_followups(request: Request, status: str = Query(default="open", pattern="^(open|all)$"),
                   limit: int = Query(default=50, ge=1, le=200)):
    from genios_engine.reason.moments import followups as F
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    return F.listing(cstore.engine, org_id=p.org_id, seat_id=p.seat_id, status=status,
                     limit=limit, now=_now())


@router.post("/v1/followups/{followup_id}/resolve")
def resolve_followup(followup_id: str, body: FollowupResolveRequest, request: Request):
    from genios_engine.reason.moments import followups as F
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    res = F.resolve(cstore.engine, org_id=p.org_id, seat_id=p.seat_id, followup_id=followup_id,
                    resolution=body.resolution, now=_now())
    if res is None:
        return _err(404, "FOLLOWUP_NOT_FOUND", "No such follow-up for this seat.")
    return res


@router.post("/v1/followups/{followup_id}/snooze")
def snooze_followup(followup_id: str, body: FollowupSnoozeRequest, request: Request):
    """P10: `{"preset": "1h" | "tonight" | "tomorrow"}` or `{"until": iso}` → the nudge moves
    (an open row only; a resolved one answers unchanged). Returns the full item."""
    from genios_engine.reason.moments import followups as F
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    if (body.preset is None) == (body.until is None):
        return _err(422, "INVALID_SNOOZE", "Send one of preset (1h, tonight, tomorrow) or until.")
    now = _now()
    engine = cstore.engine
    if body.preset is not None:
        with engine.connect() as c:
            tz = F.seat_tz(c, p.org_id, p.seat_id)
        until = F.snooze_until(body.preset, now=now, tz_name=tz)
    else:
        until = body.until if body.until.tzinfo else body.until.replace(tzinfo=timezone.utc)
        if until <= now or until > now + F.SNOOZE_MAX:
            return _err(422, "INVALID_SNOOZE", "until must be within the next 60 days.")
    res = F.snooze(engine, org_id=p.org_id, seat_id=p.seat_id, followup_id=followup_id,
                   until=until, now=now)
    if res is None:
        return _err(404, "FOLLOWUP_NOT_FOUND", "No such follow-up for this seat.")
    return res


@router.post("/v1/followups/{followup_id}/draft")
def draft_followup(followup_id: str, request: Request):
    """P10: `{"text": "..."}` — a short reply the manager could send to the item's `who`, in the
    quote's language / style. 204 when no model answers. Never stored, never sent."""
    from genios_engine.reason.moments import followups as F
    from genios_engine.reason.moments import reply_draft as RD
    from genios_engine.reason.moments import seat_profile as SP
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    engine = cstore.engine
    with engine.connect() as c:
        item = F.get_item(c, org_id=p.org_id, seat_id=p.seat_id, followup_id=followup_id)
        tz = F.seat_tz(c, p.org_id, p.seat_id) if item is not None else "UTC"
    if item is None:
        return _err(404, "FOLLOWUP_NOT_FOUND", "No such follow-up for this seat.")
    if not SP.model_available():
        return Response(status_code=_NO_CONTENT)
    from genios_engine.reason.moments.common import parse_ts
    due = parse_ts(item["due_at"]) if item.get("due_at") else None
    due_local = f"{due.astimezone(F.zone(tz)):%a %d %b %H:%M}" if due else None
    out = RD.draft(engine, org_id=p.org_id, item=item, due_local=due_local)
    if not out:
        return Response(status_code=_NO_CONTENT)
    return {"text": out}


@router.get("/v1/seats/me/weekly-report")
def weekly_report(request: Request, week_start: date | None = None):
    from genios_engine.reason.moments import followups as F
    from genios_engine.reason.moments import screen_insight as SI
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    return F.weekly_report(cstore.engine, org_id=p.org_id, seat_id=p.seat_id,
                           capability_id=SI.CAPABILITY_ID, week_start=week_start, now=_now())


# ── §2.3 device-local moments ─────────────────────────────────────────────────────────────────
@router.post("/v1/moments")
def post_device_moment(body: DeviceMoment, request: Request):
    dstore, cstore = D.stores()
    p = principal(request, dstore, device_only=True)
    if isinstance(p, JSONResponse):
        return p
    subjects = body.subject_node_ids or [e["node_id"] for e in body.evidence
                                         if isinstance(e, dict) and isinstance(e.get("node_id"), str)]
    moment = body.model_dump(exclude={"origin", "subject_node_ids"})
    # Identical advice within its TTL is shown once. A reminder is time-triggered and never
    # deduplicated (a snoozed reminder re-fires on purpose).
    key = None if body.kind == "reminder" else M.cache_key(
        seat_id=p.seat_id, capability_id=body.capability_id, subject_ids=subjects,
        trigger=M.trigger_digest(body.kind, body.headline, body.body), subject_version="device")
    try:
        out = M.persist(cstore.engine, org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id,
                        origin="device", moment=moment, subject_ids=subjects, key=key)
    except M.MomentConflict:
        return _err(409, "MOMENT_ID_CONFLICT", "That moment id belongs to another seat.")
    return {"moment_id": body.moment_id, "display": out["display"], "reason": out["reason"]}


# ── §2.4 feedback ─────────────────────────────────────────────────────────────────────────────
@router.post("/v1/moments/{moment_id}/feedback")
def post_feedback(moment_id: str, body: FeedbackRequest, request: Request):
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    at = body.at or _now()
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    res = M.record_feedback(cstore.engine, org_id=p.org_id, seat_id=p.seat_id,
                            actor=viewer_key(p.email), moment_id=moment_id, action=body.action,
                            reason=body.reason, at=at)
    if res is None:
        return _err(404, "MOMENT_NOT_FOUND", "No such moment for this seat.")
    # P9 K4: "Not useful" / "Mute chat" on a screen insight mutes that thread's popups.
    try:
        from genios_engine.reason.moments import followups as F
        from genios_engine.reason.moments import screen_insight as SI
        F.learn_from_feedback(cstore.engine, org_id=p.org_id, seat_id=p.seat_id,
                              moment_id=moment_id, action=body.action, reason=body.reason,
                              capability_id=SI.CAPABILITY_ID, now=_now())
    except Exception:      # noqa: BLE001 — learning never fails the feedback itself
        _log.exception("screen insight mute failed org=%s moment=%s", p.org_id, moment_id)
    return res


# ── §2.6 history ──────────────────────────────────────────────────────────────────────────────
@router.get("/v1/moments")
def list_moments(request: Request, limit: int = Query(default=50, ge=1, le=200),
                 before: datetime | None = None, kind: str | None = None):
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    if kind is not None and kind not in KINDS:
        return _err(422, "INVALID_KIND", f"kind must be one of {', '.join(KINDS)}")
    if before is not None and before.tzinfo is None:
        before = before.replace(tzinfo=timezone.utc)
    return M.history(cstore.engine, org_id=p.org_id, seat_id=p.seat_id, limit=limit,
                     before=before, kind=kind)


__all__ = ["Principal", "principal", "router"]
