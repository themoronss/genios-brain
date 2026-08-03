"""Resource uploads (dashboard → Resources → Uploads). A file becomes a data source: stored to disk,
parsed to text, chunked, and each chunk injected as a source_events row (source='upload') so the SAME
L2 extraction path a connector sync uses (`process_pending`) pulls entities + facts into the graph.
No user credits are charged (upload isn't /v1/intelligence/query); the LLM extraction cost lands in
llm_costs like any sync. These endpoints lived only in the old genios-brain; ported to the engine's
raw-SQL + `_org` conventions.
"""
from __future__ import annotations

import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.config import get_settings
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store, make_llm_client, make_payload_store

router = APIRouter()
_log = get_logger("genios.uploads")
_graph = make_graph_store()
_llm = make_llm_client()
_payloads = make_payload_store()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"   # genios-engine/uploads/
MAX_BYTES = 10 * 1024 * 1024                                    # 10 MiB
CHUNK_CHARS = 2000
MAX_CHUNKS = 60                                                 # cap per file so one upload can't runaway
_PROGRESS = {"queued": 10, "extracting": 55, "indexed": 100, "failed": 0}


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    """Resolve the tenant from the credential; refuse a path that names a different org."""
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _ext(name: str) -> str:
    return (name.rsplit(".", 1)[-1] if "." in name else "").lower()


def _extract_text(name: str, data: bytes) -> str:
    """Native text extraction — no OCR binary. pdf→pypdf, docx→python-docx, else utf-8 decode."""
    ext = _ext(name)
    try:
        if ext == "pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        if ext == "docx":
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:                                       # noqa: BLE001
        _log.warning("parse failed for %s (%s): %s", name, ext, e)
        return ""
    return data.decode("utf-8", errors="ignore")                # txt / md / csv / json / other


def _chunk(text_content: str) -> list[str]:
    t = (text_content or "").strip()
    if not t:
        return []
    return [t[i:i + CHUNK_CHARS] for i in range(0, len(t), CHUNK_CHARS)][:MAX_CHUNKS]


def _emit_chunk(org_id: str, file_id: str, idx: int, subject: str, body: str, uploader_email: str) -> None:
    """One upload chunk → a source_events (outcome='emitted') + encrypted raw_payloads row, the exact
    shape L2's process_pending consumes. source/object_type ('upload','document') miss the structured
    registry, so the chunk takes the LLM extraction lane."""
    eid = new_id("evt")
    dedup = f"upload:{file_id}:chunk_{idx}"
    actor = json.dumps({"type": "internal_user", "email": uploader_email})
    now = datetime.now(timezone.utc)
    with _graph.engine.begin() as c:
        row = c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, outcome) values "
            "(:eid,:o,'upload','upload','document',:soid,:dk,cast(:actor as jsonb),:now,'emitted') "
            "on conflict (org_id, dedup_key) do nothing returning event_id"),
            {"eid": eid, "o": org_id, "soid": dedup, "dk": dedup, "actor": actor, "now": now}).first()
    if row is None:                                             # dedup collision (re-upload) — skip payload
        return
    _payloads.put(payload_id=new_id("pay"), org_id=org_id, event_id=eid,
                  content=json.dumps({"subject": subject, "body": body}))


def _ingest(org_id: str, file_id: str, prefix: str) -> None:
    """Background: drain L2 extraction for the org (same entry point as a sync), then reconcile this
    file's real fact/entity counts + flip status to 'indexed'. Best-effort, per-org isolated."""
    like = f"{prefix}:%"
    try:
        if _llm is not None:
            from genios_engine.context.runner import process_pending
            process_pending(org_id=org_id, store=_graph, llm=_llm, crypto_key=get_settings().crypto_key)
    except Exception:
        _log.exception("upload L2 extraction failed org=%s file=%s", org_id, file_id)
    try:
        with _graph.engine.begin() as c:
            facts = c.execute(text(
                "select count(*) from graph_facts where org_id=:o and valid_to is null and status='active' "
                "and created_by_event_id in (select event_id from source_events where org_id=:o "
                "and dedup_key like :p)"), {"o": org_id, "p": like}).scalar()
            ents = c.execute(text(
                "select count(*) from graph_nodes where org_id=:o and valid_to is null "
                "and created_by_event_id in (select event_id from source_events where org_id=:o "
                "and dedup_key like :p)"), {"o": org_id, "p": like}).scalar()
            note = None
            if _llm is None:
                note = "Stored — AI extraction is currently disabled (no model configured)."
            c.execute(text(
                "update resource_uploads set status='indexed', facts_count=:f, entities_count=:e, "
                "error=:err, processed_at=now() where org_id=:o and file_id=:fid"),
                {"f": int(facts or 0), "e": int(ents or 0), "err": note, "o": org_id, "fid": file_id})
    except Exception:
        _log.exception("upload count/status update failed org=%s file=%s", org_id, file_id)


def _row(r) -> dict:
    return {
        "id": r.file_id, "file_name": r.file_name, "file_type": r.file_type,
        "file_size": int(r.file_size_bytes or 0),
        "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        "tag": r.tag, "status": r.status,
        "facts_count": int(r.facts_count or 0),
        "entities_count": int(r.entities_count or 0),
        "contacts_count": int(r.entities_count or 0),   # UI maps contacts→entities
        "progress": _PROGRESS.get(r.status, 0),
        "error": r.error, "authority": 1.0,
    }


@router.post("/api/org/{org_id}/upload")
async def upload_resource(org_id: str, background_tasks: BackgroundTasks,
                          file: UploadFile = File(...), tag: str | None = Form(None),
                          org: str = Depends(_org)) -> dict:
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    data = await file.read()
    if not data:
        raise HTTPException(422, {"error": "empty_file", "message": "file is empty"})
    if len(data) > MAX_BYTES:
        raise HTTPException(413, {"error": "too_large", "message": "file exceeds 10 MiB"})

    name = file.filename or "upload"
    file_id = new_id("upl")
    prefix = f"upload:{file_id}"
    chunks = _chunk(_extract_text(name, data))
    status = "extracting" if chunks else "failed"
    err = None if chunks else "No extractable text found in this file."

    storage_path = None
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]
        p = UPLOAD_DIR / f"{file_id}_{safe}"
        p.write_bytes(data)
        storage_path = str(p)
    except Exception:                                           # noqa: BLE001 — disk record is a nicety
        _log.warning("upload disk write failed for %s", file_id)

    with _graph.engine.connect() as c:
        uploader = c.execute(text("select email from orgs where id=:o"), {"o": org}).scalar()
    uploader = uploader or f"owner@{org}"

    with _graph.engine.begin() as c:
        c.execute(text(
            "insert into resource_uploads (file_id, org_id, file_name, file_type, file_size_bytes, "
            "storage_path, tag, status, source_item_prefix, chunks, error, uploaded_by) "
            "values (:fid,:o,:fn,:ft,:sz,:sp,:tag,:st,:pref,:ch,:err,:by)"),
            {"fid": file_id, "o": org, "fn": name, "ft": _ext(name), "sz": len(data),
             "sp": storage_path, "tag": tag, "st": status, "pref": prefix, "ch": len(chunks),
             "err": err, "by": uploader})

    for i, ch in enumerate(chunks):
        _emit_chunk(org, file_id, i, name, ch, uploader)
    if chunks:
        background_tasks.add_task(_ingest, org, file_id, prefix)

    from genios_engine.platform.audit import record
    record(org, "data_accessed", actor_type="user", actor_id=uploader, target_type="upload",
           target_id=file_id, metadata={"file_name": name, "bytes": len(data), "chunks": len(chunks)})
    return {"file_id": file_id, "status": status, "chunks": len(chunks)}


@router.get("/api/org/{org_id}/uploads")
def list_uploads(org_id: str, org: str = Depends(_org)) -> dict:
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select file_id, file_name, file_type, file_size_bytes, uploaded_at, tag, status, "
            "facts_count, entities_count, error from resource_uploads where org_id=:o "
            "order by uploaded_at desc"), {"o": org}).fetchall()
    return {"uploads": [_row(r) for r in rows]}


@router.delete("/api/org/{org_id}/uploads/{file_id}")
def delete_upload(org_id: str, file_id: str, org: str = Depends(_org)) -> dict:
    like = f"upload:{file_id}:%"
    with _graph.engine.begin() as c:
        rec = c.execute(text("select storage_path from resource_uploads where org_id=:o and file_id=:f"),
                        {"o": org, "f": file_id}).first()
        if rec is None:
            raise HTTPException(404, {"error": "not_found", "message": "upload not found"})
        evids = [r.event_id for r in c.execute(text(
            "select event_id from source_events where org_id=:o and dedup_key like :p"),
            {"o": org, "p": like})]
        if evids:
            # remove the facts learned from THIS file + its capture artifacts. Shared graph_nodes are
            # left in place (they may be referenced by other sources).
            c.execute(text("delete from graph_facts where org_id=:o and created_by_event_id = any(:e)"),
                      {"o": org, "e": evids})
            c.execute(text("delete from raw_payloads where org_id=:o and event_id = any(:e)"),
                      {"o": org, "e": evids})
            c.execute(text("delete from source_events where org_id=:o and event_id = any(:e)"),
                      {"o": org, "e": evids})
        c.execute(text("delete from resource_uploads where org_id=:o and file_id=:f"),
                  {"o": org, "f": file_id})
    try:
        if rec.storage_path and os.path.exists(rec.storage_path):
            os.remove(rec.storage_path)
    except Exception:                                           # noqa: BLE001
        pass
    from genios_engine.platform.audit import record
    record(org, "data_subject_erasure", actor_type="user", target_type="upload", target_id=file_id,
           metadata={"events_removed": len(evids)})
    return {"deleted": True}


class TagUpdate(BaseModel):
    tag: str


@router.patch("/api/org/{org_id}/uploads/{file_id}/tag")
def retag_upload(org_id: str, file_id: str, body: TagUpdate, org: str = Depends(_org)) -> dict:
    with _graph.engine.begin() as c:
        res = c.execute(text("update resource_uploads set tag=:t where org_id=:o and file_id=:f"),
                        {"t": body.tag, "o": org, "f": file_id})
    if res.rowcount == 0:
        raise HTTPException(404, {"error": "not_found", "message": "upload not found"})
    return {"retagged": True}
