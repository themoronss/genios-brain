"""P5 transcript API (SCREEN_INTEL_P5 §3) — seat-scoped.

    GET  /v1/transcripts                       the transcripts this seat may read
    GET  /v1/transcripts/{id}                  one (404 when not a principal)
    PUT  /v1/transcripts/{id}/speakers         {"<label>": "<person_node_id|email|null>"} →
                                               re-ingests as a new content version
    GET  /v1/meetings/recent?q&date            the seat's meetings (last 14 d) for the upload picker

A transcript is its attendees' conversation: a seat reads one only when its address is among the
principals — an admin or the owner is not an exception. Auth is the P3 principal (a seat session
or a device token); an API key has no seat and is refused.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse

from genios_engine.api.moment_routes import principal
from genios_engine.capture.transcripts import link as L
from genios_engine.capture.transcripts.ingest import (TranscriptError, ingest_transcript,
                                                      load_row, may_read, view, visible_rows)
from genios_engine.capture.transcripts.speakers import manual_candidate
from genios_engine.platform import devices as D
from genios_engine.platform.config import get_settings

router = APIRouter(tags=["transcripts"])


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _who(request: Request):
    dstore, cstore = D.stores()
    return principal(request, dstore), cstore.engine


@router.get("/v1/transcripts")
def list_transcripts(request: Request):
    p, engine = _who(request)
    if isinstance(p, JSONResponse):
        return p
    with engine.connect() as c:
        rows = visible_rows(c, p.org_id, p.email)
    return {"transcripts": [view(r) for r in rows]}


@router.get("/v1/transcripts/{transcript_id}")
def get_transcript(transcript_id: str, request: Request):
    p, engine = _who(request)
    if isinstance(p, JSONResponse):
        return p
    with engine.connect() as c:
        row = load_row(c, p.org_id, transcript_id)
    if row is None or not may_read(row, p.email):
        return _err(404, "not_found", "transcript not found")
    return view(row)


@router.put("/v1/transcripts/{transcript_id}/speakers")
async def put_speakers(transcript_id: str, request: Request, background_tasks: BackgroundTasks):
    p, engine = _who(request)
    if isinstance(p, JSONResponse):
        return p
    try:
        body = await request.json()
    except ValueError:
        return _err(422, "invalid_body", "body must be a JSON object of label → person")
    if not isinstance(body, dict) or not body:
        return _err(422, "invalid_body", "body must be a non-empty JSON object of label → person")
    with engine.connect() as c:
        row = load_row(c, p.org_id, transcript_id)
        if row is None or not may_read(row, p.email):
            return _err(404, "not_found", "transcript not found")
        labels = {s.get("label") for s in (view(row)["speakers"] or [])}
        unknown = sorted(str(k) for k in body if k not in labels)
        if unknown:
            return _err(422, "unknown_label", f"not a speaker in this transcript: {unknown}")
        manual = {}
        for label, value in body.items():
            if value is not None and not isinstance(value, str):
                return _err(422, "invalid_value", f"{label!r}: a person node id, an email or null")
            try:
                manual[label] = manual_candidate(c, p.org_id, value)
            except ValueError as exc:
                return _err(422, "unknown_person", str(exc))
    s = get_settings()
    if row.enc_text is None or not s.crypto_key:
        return _err(409, "text_unavailable",
                    "this transcript's text is not stored; upload it again to re-map speakers")
    from genios_engine.api.upload_routes import _ingest_transcript_bg, _transcript_doors
    from genios_engine.platform.crypto import decrypt
    try:
        out = ingest_transcript(
            engine, org_id=p.org_id, text_content=decrypt(bytes(row.enc_text), s.crypto_key),
            source=row.source, source_ref=row.source_ref, uploader_email=row.uploader_email,
            seat_id=row.seat_id, doors=_transcript_doors(p.org_id), provider_hint=row.provider,
            meeting_node_id=row.meeting_node_id, calendar_event_id=row.calendar_event_id,
            meeting_title=row.title, meeting_date=row.started_at.date() if row.started_at else None,
            scope=row.scope, file_id=row.file_id, manual=manual, crypto_key=s.crypto_key)
    except TranscriptError as exc:
        return _err(422, exc.code, str(exc))
    if not out.duplicate:
        background_tasks.add_task(_ingest_transcript_bg, p.org_id, transcript_id, row.file_id,
                                  tuple(out.emitted_ids))
    from genios_engine.platform.audit import record
    record(p.org_id, "data_accessed", actor_type="user", actor_id=p.email,
           target_type="transcript", target_id=transcript_id,
           metadata={"speakers_remapped": sorted(manual)})
    return out.transcript


@router.get("/v1/meetings/recent")
def meetings_recent(request: Request, q: str | None = Query(default=None, max_length=200),
                    date_: str | None = Query(default=None, alias="date")):
    p, engine = _who(request)
    if isinstance(p, JSONResponse):
        return p
    day = None
    if date_:
        try:
            day = date.fromisoformat(date_)
        except ValueError:
            return _err(422, "invalid_date", "date must be YYYY-MM-DD")
    with engine.connect() as c:
        refs = L.recent_meetings(c, p.org_id, seat_email=p.email or "", q=q, day=day)
    return {"meetings": [r.view() for r in refs]}
