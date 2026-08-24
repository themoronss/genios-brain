"""Resource uploads (dashboard → Resources → Uploads). A file becomes a data source: stored to disk,
parsed to text, chunked, and each chunk injected as a source_events row (source='upload') so the SAME
L2 extraction path a connector sync uses (`process_pending`) pulls entities + facts into the graph.
No user credits are charged (upload isn't /v1/intelligence/query); the LLM extraction cost lands in
llm_costs like any sync. These endpoints lived only in the old genios-brain; ported to the engine's
raw-SQL + `_org` conventions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.capture.documents.chunking import chunk_text
from genios_engine.capture.documents.native import extract_text_best_effort
from genios_engine.capture.internal_knowledge import (authority_rank_for, is_canon,
                                                      normalize_kind)
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import (make_graph_store, make_llm_client, make_ocr,
                                           make_payload_store, make_prepared_store,
                                           make_repo, make_trace_repo)

router = APIRouter()
_log = get_logger("genios.uploads")
_graph = make_graph_store()
_llm = make_llm_client()
_payloads = make_payload_store()
_repo = make_repo()
_prepared = make_prepared_store()
_trace_repo = make_trace_repo()
_ocr = make_ocr()                                              # scanned PDFs/images → same OCR as email/Drive

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"   # genios-engine/uploads/
MAX_BYTES = 10 * 1024 * 1024                                    # 10 MiB
CHUNK_CHARS = 2000
MAX_CHUNKS = 300                                               # cap per file so one upload can't runaway
                                                               # (~300 pages); if exceeded it is REPORTED, never silently dropped
_PROGRESS = {"queued": 10, "extracting": 55, "indexed": 100, "failed": 0}


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    """Resolve the tenant from the credential; refuse a path that names a different org."""
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _ext(name: str) -> str:
    return (name.rsplit(".", 1)[-1] if "." in name else "").lower()


def _extract_text(name: str, data: bytes, content_type: str = "") -> str:
    """Native extraction + OCR fallback — the SAME document path email/Drive attachments use, so a
    scanned PDF/image uploaded here reads exactly like one that arrived by email. (The upload door
    was pypdf-only before, so a scanned file returned "" even with OCR enabled.) Plain-text formats
    still decode to utf-8; a binary that yields nothing returns "" → honest 'no extractable text'."""
    return extract_text_best_effort(mime=content_type or "", data=data, filename=name, ocr=_ocr)


def _chunk(text_content: str) -> list[str]:
    """Boundary-aware chunking (capture.documents.chunking) — a fact is never sliced
    mid-sentence. Returns ALL chunks; the caller applies MAX_CHUNKS and reports any
    truncation, so a big file is never silently cut off while status reports success."""
    return chunk_text(text_content, max_chars=CHUNK_CHARS)


def _emit_chunk(org_id: str, file_id: str, idx: int, subject: str, body: str,
                uploader_email: str, internal_kind: str | None = None) -> None:
    """One upload chunk → THE ONE DOOR (capture_event via intake): deduped, traced,
    W-05-whitelisted, payload + prepared text persisted — identical to a connector sync.
    (Was a hand-rolled SQL insert that skipped the gate, the trace and the seam.)
    source/object_type ('upload','document_chunk') miss the structured registry, so the
    chunk takes the LLM extraction lane.

    A tag that names one of INTERNAL_KINDS makes the file COMPANY CANON: the chunks land
    in the `internal` family at authority rank 4, so an uploaded price list outranks what
    a billing system inferred. An unrecognised tag stays an ordinary label and the chunk
    keeps observed authority — the id shape is untouched either way, so `_ingest`'s
    reconciliation prefix still matches."""
    from genios_engine.capture.intake import ingest_manual
    ingest_manual(org_id=org_id, source="upload", object_type="document_chunk",
                  source_object_id=f"{file_id}:chunk_{idx}", body=body, subject=subject,
                  actor_type="internal_user", actor_email=uploader_email,
                  internal_kind=internal_kind,
                  # One canon node per FILE, not per chunk. Keying on the event would give
                  # a 30-chunk pricing PDF thirty separate "Pricing" entities, each holding
                  # a slice of one document — the graph would look like thirty price lists.
                  raw_extra=({"knowledge_key": file_id, "title": subject}
                             if internal_kind else None),
                  repo=_repo, payload_store=_payloads, prepared_store=_prepared,
                  trace_repo=_trace_repo, connection_id="upload")


def _ingest(org_id: str, file_id: str, prefix: str, truncated: int = 0) -> None:
    """Background: drain L2 extraction for the org (same entry point as a sync), then reconcile this
    file's real fact/entity counts + flip status to 'indexed'. Best-effort, per-org isolated.
    Two dedup shapes are matched: the one-door key 'upload:document_chunk:{file}:…' and the
    legacy pre-door key 'upload:{file}:…'."""
    like_new = f"upload:document_chunk:{file_id}:%"
    like_old = f"{prefix}:%"
    try:
        if _llm is not None:
            from genios_engine.context.runner import process_pending
            from genios_engine.packs.wiring import make_registry
            process_pending(org_id=org_id, store=_graph, llm=_llm,
                            registry=make_registry(),
                            crypto_key=get_settings().crypto_key)
    except Exception:
        _log.exception("upload L2 extraction failed org=%s file=%s", org_id, file_id)
    try:
        with _graph.engine.begin() as c:
            facts = c.execute(text(
                "select count(*) from graph_facts where org_id=:o and valid_to is null and status='active' "
                "and created_by_event_id in (select event_id from source_events where org_id=:o "
                "and (dedup_key like :p or dedup_key like :p2))"),
                {"o": org_id, "p": like_old, "p2": like_new}).scalar()
            ents = c.execute(text(
                "select count(*) from graph_nodes where org_id=:o and valid_to is null "
                "and created_by_event_id in (select event_id from source_events where org_id=:o "
                "and (dedup_key like :p or dedup_key like :p2))"),
                {"o": org_id, "p": like_old, "p2": like_new}).scalar()
            notes = []
            if _llm is None:
                notes.append("Stored — AI extraction is currently disabled (no model configured).")
            if truncated:
                # Honest partial-index report — the old path silently dropped everything past
                # the cap and still flipped status to 'indexed', so the user believed the whole
                # file was read. Never claim full coverage we did not deliver.
                notes.append(
                    f"Indexed the first {MAX_CHUNKS} sections; {truncated} more were not indexed "
                    f"(this file is larger than the current {MAX_CHUNKS}-section limit).")
            note = " ".join(notes) or None
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
        "error": r.error,
        # Reported, not asserted. This was a hardcoded 1.0 on every row while the facts
        # underneath all landed at rank 2 — the UI claimed an authority the graph did not
        # honour, on a 0–1 scale nothing else in the API uses. Now it is the real rank,
        # matching /entity and the fact read models (2 observed · 4 company canon).
        "authority": authority_rank_for(r.tag),
        "internal_kind": normalize_kind(r.tag),
        "is_canon": is_canon(r.tag),
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
    # Content-addressed id → re-uploading the SAME file is idempotent: identical bytes → same file_id
    # → same chunk dedup keys → no duplicate events (MD Part 3.4). Org-scoped so two tenants uploading
    # the same file never collide.
    content_hash = hashlib.sha256(org.encode() + b":" + data).hexdigest()
    file_id = "upl_" + content_hash[:24]
    prefix = f"upload:{file_id}"

    with _graph.engine.connect() as c:                 # already have this exact file? → idempotent
        existing = c.execute(text(
            "select status, chunks from resource_uploads where org_id=:o and file_id=:f"),
            {"o": org, "f": file_id}).first()
    if existing is not None:
        return {"file_id": file_id, "status": existing.status,
                "chunks": int(existing.chunks or 0), "duplicate": True}

    all_chunks = _chunk(_extract_text(name, data, file.content_type or ""))
    chunks = all_chunks[:MAX_CHUNKS]
    truncated = len(all_chunks) - len(chunks)          # >0 → reported in _ingest, never silent
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

    try:
        with _graph.engine.begin() as c:
            c.execute(text(
                "insert into resource_uploads (file_id, org_id, file_name, file_type, "
                "file_size_bytes, storage_path, tag, status, source_item_prefix, chunks, error, "
                "uploaded_by) values (:fid,:o,:fn,:ft,:sz,:sp,:tag,:st,:pref,:ch,:err,:by) "
                "on conflict do nothing"),                # race safety; the pre-check handles the common case
                {"fid": file_id, "o": org, "fn": name, "ft": _ext(name), "sz": len(data),
                 "sp": storage_path, "tag": tag, "st": status, "pref": prefix, "ch": len(chunks),
                 "err": err, "by": uploader})
    except Exception:
        # In particular, an account deletion may revoke the org while this upload waits on its FK
        # lock. Never leave the bytes orphaned when the metadata insert cannot commit.
        if storage_path:
            try:
                Path(storage_path).unlink(missing_ok=True)
            except OSError:
                _log.exception("failed to clean upload after metadata insert failure: %s", file_id)
        raise

    kind = normalize_kind(tag)          # a canon tag promotes the whole file to rank 4
    for i, ch in enumerate(chunks):
        _emit_chunk(org, file_id, i, name, ch, uploader, internal_kind=kind)
    if chunks:
        background_tasks.add_task(_ingest, org, file_id, prefix, truncated)

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
    like_old = f"upload:{file_id}:%"                      # pre-door key shape
    like_new = f"upload:document_chunk:{file_id}:%"       # one-door key shape
    with _graph.engine.begin() as c:
        rec = c.execute(text("select storage_path from resource_uploads where org_id=:o and file_id=:f"),
                        {"o": org, "f": file_id}).first()
        if rec is None:
            raise HTTPException(404, {"error": "not_found", "message": "upload not found"})
        evids = [r.event_id for r in c.execute(text(
            "select event_id from source_events where org_id=:o "
            "and (dedup_key like :p or dedup_key like :p2)"),
            {"o": org, "p": like_old, "p2": like_new})]
        if evids:
            # remove the facts learned from THIS file + its capture artifacts (raw payload,
            # prepared text, observations). Shared graph_nodes are left in place (they may
            # be referenced by other sources).
            # Lock/bump the tenant graph version in this SAME transaction before changing
            # graph state. Layer 4 holds a shared lock on this row while publishing decisions,
            # so an erasure can never commit halfway through a reasoning emission window.
            _graph.bump_version(c, org)
            c.execute(text("delete from graph_facts where org_id=:o and created_by_event_id = any(:e)"),
                      {"o": org, "e": evids})
            c.execute(text("delete from graph_observations where org_id=:o "
                           "and created_by_event_id = any(:e)"), {"o": org, "e": evids})
            c.execute(text("delete from raw_payloads where org_id=:o and event_id = any(:e)"),
                      {"o": org, "e": evids})
            c.execute(text("delete from prepared_content where org_id=:o and event_id = any(:e)"),
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
