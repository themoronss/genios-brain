"""File uploads — PDF/DOCX/TXT/CSV ingest.

Flow per g-i-1:
  1. Save file bytes to UPLOAD_DIR (status=queued)
  2. Parse to text (handler per type)
  3. Chunk (~2000 chars per chunk so a single Haiku extract stays cheap)
  4. emit() one MemoryItem per chunk; ingest_subscriber upserts entities
     + facts keyed by source_item_id = "upload:<file_id>:chunk_<n>"
  5. Update resource_uploads row to status=indexed (or failed) + counts

Parsing is best-effort: missing parser deps degrade to plaintext (txt).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO

from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi import HTTPException

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.memory.emit import emit as emit_memory_item
from core.memory.types import MemoryItem, MemoryItemMetadata
from core.resources.billing import deduct_or_raise
from core.resources.connection import (
    ensure_resource_connection,
    synthetic_source_id,
)

log = get_logger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
CHUNK_CHARS = 2000  # per-chunk char budget — keeps Haiku extract <1k tokens

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


@dataclass(frozen=True)
class UploadInput:
    file_name: str
    file_type: str  # 'pdf' | 'docx' | 'txt' | 'csv' | 'json'
    raw: bytes
    tag: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────


def _parse_to_text(file_path: str, file_type: str) -> str:
    """Extract plaintext from the saved file. Returns "" on unsupported types."""
    t = file_type.lower().lstrip(".")
    if t in ("txt", "md", "csv", "tsv", "json"):
        with open(file_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    if t == "pdf":
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(file_path)
            return "\n\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:  # missing dep or malformed pdf
            log.warning("pdf_parse_failed", file=file_path, error=str(e))
            return ""
    if t in ("docx", "doc"):
        try:
            import docx  # type: ignore  # python-docx
            d = docx.Document(file_path)
            return "\n".join(p.text for p in d.paragraphs)
        except Exception as e:
            log.warning("docx_parse_failed", file=file_path, error=str(e))
            return ""
    log.info("unsupported_file_type", type=t)
    return ""


def _chunk(text_body: str, budget: int = CHUNK_CHARS) -> list[str]:
    """Split text into ~budget-char pieces on sentence boundaries when possible."""
    text_body = text_body.strip()
    if not text_body:
        return []
    if len(text_body) <= budget:
        return [text_body]
    out: list[str] = []
    start = 0
    while start < len(text_body):
        end = min(start + budget, len(text_body))
        # try to break at a paragraph; else newline; else hard cut
        slice_ = text_body[start:end]
        if end < len(text_body):
            for sep in ("\n\n", "\n", ". "):
                idx = slice_.rfind(sep)
                if idx > budget // 2:
                    end = start + idx + len(sep)
                    slice_ = text_body[start:end]
                    break
        out.append(slice_.strip())
        start = end
    return [s for s in out if s]


# ─────────────────────────────────────────────────────────────────────────────
# Write
# ─────────────────────────────────────────────────────────────────────────────


def create_upload(
    session: Session,
    *,
    org_id: str,
    actor_email: str,
    upload: UploadInput,
    agent_id: str | None = None,
) -> dict:
    """Save the file, run extraction synchronously, return the row.

    Synchronous extraction is fine at this scale (files capped at 10MB,
    chunks ≤2000 chars). A background worker can be added later if needed.
    """
    if len(upload.raw) > MAX_UPLOAD_BYTES:
        raise ValueError(f"file too large ({len(upload.raw)} > {MAX_UPLOAD_BYTES})")

    ensure_resource_connection(session, org_id=org_id, source_type="upload")
    source_id = synthetic_source_id(source_type="upload", org_id=org_id)

    file_id = str(uuid.uuid4())
    ext = upload.file_type.lower().lstrip(".") or "bin"
    safe_name = "".join(c for c in upload.file_name if c.isalnum() or c in "._-") or file_id
    storage_path = os.path.join(UPLOAD_DIR, f"{file_id}_{safe_name}")
    with open(storage_path, "wb") as f:
        f.write(upload.raw)

    source_item_prefix = f"upload_{file_id}"
    uploaded_at = datetime.now(UTC)

    session.execute(
        text(
            """
            INSERT INTO resource_uploads
                (id, org_id, agent_id, file_name, file_type, file_size_bytes,
                 storage_path, tag, status, source_item_prefix,
                 uploaded_by, uploaded_at)
            VALUES
                (:id, :org, :agent, :fname, :ftype, :fsize,
                 :path, :tag, 'queued', :pfx,
                 :actor, :uploaded)
            """
        ),
        {
            "id": file_id, "org": org_id, "agent": agent_id,
            "fname": upload.file_name, "ftype": ext,
            "fsize": len(upload.raw), "path": storage_path,
            "tag": upload.tag, "pfx": source_item_prefix,
            "actor": actor_email, "uploaded": uploaded_at,
        },
    )
    session.commit()

    # Parse + emit chunks. Wrapped so a failure flips status to 'failed'
    # rather than 500-ing back to the dashboard upload form.
    _set_status(session, file_id, "extracting")
    chunks_n = 0
    insufficient_at_chunk: int | None = None

    # CSV gets a deterministic, LLM-free path — see csv_ingest.py for the
    # rationale. It still flows through the g-i-1 memory bus (one
    # MemoryItem per row, structured_facts hint set) so the single-pipeline
    # invariant holds: the g-i-3 subscriber sees the hint, persists
    # directly, no Haiku call. Same bus, two modes.
    if ext == "csv":
        try:
            from core.resources import csv_ingest

            columns, raw_rows = csv_ingest.parse_csv_bytes(upload.raw)
            mapping, unmapped = csv_ingest.infer_column_mapping(columns)
            structured = csv_ingest.process_rows(raw_rows, mapping)

            # Emit one MemoryItem per row → the registered subscriber writes
            # nodes + edges + facts inside its own DB session. We use a
            # fresh session here only to roll up post-emission counts for
            # the resource_uploads row.
            csv_ingest.emit_rows_to_bus(
                org_id=org_id,
                rows=structured,
                file_id=file_id,
                source_id=source_id,
            )

            # Roll up stored counts from facts / nodes — what actually landed
            # in the graph, not what we tried to emit.
            facts_n = session.execute(
                text(
                    "SELECT COUNT(*) FROM facts WHERE org_id = :org "
                    "AND source_item_id LIKE :prefix"
                ),
                {"org": org_id, "prefix": f"upload:{file_id}:%"},
            ).scalar() or 0
            # JSON-text LIKE keeps the SQL portable (avoids ::jsonb cast
            # parameter binding clash with Postgres ::). For the entities
            # count we want every Client/Invoice node tied to this upload's
            # source_item_ids — file_id is unique per upload so the LIKE
            # over the JSON text is sufficient.
            entities_n = session.execute(
                text(
                    "SELECT COUNT(*) FROM graph_nodes WHERE org_id = :org "
                    "AND type IN ('client', 'invoice') "
                    "AND source_item_ids::text LIKE :like_probe"
                ),
                {"org": org_id, "like_probe": f"%upload:{file_id}:%"},
            ).scalar() or 0

            mapped_summary = (
                f"Auto-mapped {len(mapping)}/{len(columns)} columns. "
                f"Skipped: {', '.join(unmapped[:5])}"
                if unmapped
                else f"Auto-mapped all {len(columns)} columns."
            )
            session.execute(
                text(
                    """
                    UPDATE resource_uploads
                    SET status = 'indexed',
                        facts_count = :fn,
                        entities_count = :en,
                        error = :err,
                        processed_at = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "id": file_id,
                    "fn": int(facts_n),
                    "en": int(entities_n),
                    "err": mapped_summary,
                },
            )
            session.commit()
            audit.record(
                org_id=org_id, actor_type="user", actor_id=actor_email,
                action="data_accessed", target_type="upload",
                target_id=file_id,
                metadata={
                    "op": "create_csv",
                    "file_name": upload.file_name,
                    "rows": len(structured),
                    "columns_mapped": len(mapping),
                    "columns_skipped": len(unmapped),
                    "facts_persisted": int(facts_n),
                    "entities_persisted": int(entities_n),
                },
            )
            return _row_to_dict(session, org_id=org_id, file_id=file_id)
        except ValueError as ve:
            _set_status(session, file_id, "failed", error=f"CSV parse failed: {ve}")
            log.warning("upload_csv_parse_failed", file_id=file_id, error=str(ve))
            return _row_to_dict(session, org_id=org_id, file_id=file_id)
        except Exception as e:
            _set_status(session, file_id, "failed", error=str(e)[:500])
            log.exception("upload_csv_ingest_failed", file_id=file_id, error=str(e))
            return _row_to_dict(session, org_id=org_id, file_id=file_id)

    try:
        body = _parse_to_text(storage_path, ext)
        chunks = _chunk(body)
        for i, ch in enumerate(chunks):
            item_id = f"{source_item_prefix}_chunk_{i}"
            # Per-chunk billing: 1 credit per chunk so a 50-page contract
            # costs proportionally more than a 1-page note. If the org
            # runs out mid-file, we stop emitting (don't burn more
            # Haiku calls) but keep the partial extract already on disk
            # and the chunks that did process — the row is flagged so
            # the user knows it was truncated.
            try:
                deduct_or_raise(
                    org_id=org_id,
                    reason="resources:upload_chunk",
                    idempotency_key=f"upload:{file_id}:chunk:{i}",
                    related_kind="upload",
                    related_id=file_id,
                    agent_uuid=agent_id,
                    actor_email=actor_email,
                )
            except HTTPException as he:
                if he.status_code == 402:
                    insufficient_at_chunk = i
                    break
                raise
            item = MemoryItem(
                item_id=item_id,
                source_id=source_id,
                source_type="upload",
                content=ch,
                content_ref=f"file://{storage_path}",
                metadata=MemoryItemMetadata(
                    timestamp=uploaded_at,
                    owner=actor_email,
                    source_confidence=1.0,
                    tags=[t for t in [upload.tag, ext] if t],
                ),
            )
            emit_memory_item(item, org_id=org_id)
            chunks_n += 1
        # Roll up counts from facts table (ingest subscriber already wrote).
        facts_n = session.execute(
            text("SELECT COUNT(*) FROM facts WHERE org_id = :org "
                 "AND source_item_id LIKE :prefix"),
            {"org": org_id, "prefix": f"upload:{source_item_prefix}%"},
        ).scalar() or 0
        # 'indexed' = whole file ran. 'partial' = credits ran out mid-
        # file; we keep what we extracted, flag the error so the UI
        # surfaces it, and the customer top-ups + re-uploads the rest.
        final_status = "indexed"
        partial_err: str | None = None
        if insufficient_at_chunk is not None:
            final_status = "partial"
            partial_err = (
                f"Out of credits at chunk {insufficient_at_chunk + 1} of "
                f"{len(chunks)}. Top up to extract the rest of this file."
            )
        session.execute(
            text(
                """
                UPDATE resource_uploads
                SET status = :status, facts_count = :fn,
                    error = :err, processed_at = NOW()
                WHERE id = :id
                """
            ),
            {"id": file_id, "fn": facts_n, "status": final_status, "err": partial_err},
        )
        session.commit()
    except Exception as e:
        _set_status(session, file_id, "failed", error=str(e))
        log.warning("upload_ingest_failed", file_id=file_id, error=str(e))

    audit.record(
        org_id=org_id, actor_type="user", actor_id=actor_email,
        action="data_accessed", target_type="upload",
        target_id=file_id,
        metadata={"op": "create", "file_name": upload.file_name,
                  "size_bytes": len(upload.raw), "chunks": chunks_n},
    )
    return _row_to_dict(session, org_id=org_id, file_id=file_id)


# ─────────────────────────────────────────────────────────────────────────────
# Read
# ─────────────────────────────────────────────────────────────────────────────


def list_uploads(
    session: Session, *, org_id: str, limit: int = 100, offset: int = 0,
) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT id, file_name, file_type, file_size_bytes, tag, status,
                   error, facts_count, entities_count, uploaded_by,
                   uploaded_at, processed_at
            FROM resource_uploads
            WHERE org_id = :org
            ORDER BY uploaded_at DESC
            LIMIT :lim OFFSET :off
            """
        ),
        {"org": org_id, "lim": limit, "off": offset},
    ).fetchall()
    return [_dict_from_row(r) for r in rows]


def _row_to_dict(session: Session, *, org_id: str, file_id: str) -> dict:
    row = session.execute(
        text(
            """
            SELECT id, file_name, file_type, file_size_bytes, tag, status,
                   error, facts_count, entities_count, uploaded_by,
                   uploaded_at, processed_at
            FROM resource_uploads WHERE id = :id AND org_id = :org
            """
        ),
        {"id": file_id, "org": org_id},
    ).fetchone()
    return _dict_from_row(row) if row else {}


def _dict_from_row(r) -> dict:
    return {
        "id": str(r.id),
        "file_name": r.file_name,
        "file_type": (r.file_type or "").upper(),
        "file_size_bytes": r.file_size_bytes,
        "tag": r.tag,
        "status": r.status,
        "error": r.error,
        "facts_count": r.facts_count or 0,
        "entities_count": r.entities_count or 0,
        "uploaded_by": r.uploaded_by,
        "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        "processed_at": r.processed_at.isoformat() if r.processed_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Update / Delete
# ─────────────────────────────────────────────────────────────────────────────


def retag_upload(
    session: Session, *, org_id: str, file_id: str, tag: str, actor_email: str,
) -> dict | None:
    session.execute(
        text("UPDATE resource_uploads SET tag = :tag "
             "WHERE id = :id AND org_id = :org"),
        {"tag": tag, "id": file_id, "org": org_id},
    )
    session.commit()
    audit.record(
        org_id=org_id, actor_type="user", actor_id=actor_email,
        action="config_changed", target_type="upload",
        target_id=file_id, metadata={"op": "retag", "tag": tag},
    )
    return _row_to_dict(session, org_id=org_id, file_id=file_id) or None


def delete_upload(
    session: Session, *, org_id: str, file_id: str, actor_email: str,
) -> bool:
    """Wipe row + extracted facts/nodes + the saved file on disk."""
    row = session.execute(
        text("SELECT source_item_prefix, storage_path FROM resource_uploads "
             "WHERE id = :id AND org_id = :org"),
        {"id": file_id, "org": org_id},
    ).fetchone()
    if row is None:
        return False
    tagged_like = f"upload:{row.source_item_prefix}%"
    facts_n = session.execute(
        text("DELETE FROM facts WHERE org_id = :org AND source_item_id LIKE :p "
             "RETURNING id"),
        {"org": org_id, "p": tagged_like},
    ).rowcount or 0

    session.execute(
        text("DELETE FROM resource_uploads WHERE id = :id AND org_id = :org"),
        {"id": file_id, "org": org_id},
    )
    session.commit()

    # Best-effort file unlink — never raise.
    try:
        if row.storage_path and os.path.exists(row.storage_path):
            os.remove(row.storage_path)
    except OSError as e:
        log.warning("upload_unlink_failed",
                    file_id=file_id, path=row.storage_path, error=str(e))

    audit.record(
        org_id=org_id, actor_type="user", actor_id=actor_email,
        action="data_subject_erasure", target_type="upload",
        target_id=file_id, metadata={"facts_deleted": facts_n},
    )
    log.info("upload_deleted", file_id=file_id, facts_n=facts_n)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _set_status(session: Session, file_id: str, status: str, *, error: str | None = None) -> None:
    session.execute(
        text("UPDATE resource_uploads SET status = :s, error = :e WHERE id = :id"),
        {"s": status, "e": error, "id": file_id},
    )
    session.commit()
