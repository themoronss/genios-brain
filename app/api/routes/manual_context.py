"""
Manual Context & File Upload API — Supports the Resources page.
Endpoints: manual context CRUD, file upload with LLM extraction.
"""
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.plan_enforcer import require_integration, require_operation, check_contact_limit
from typing import Optional
import logging
import uuid
import os

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Manual Context Entry ─────────────────────────────────────────────────

class ManualContextEntry(BaseModel):
    contact_name: str
    contact_email: Optional[str] = None
    context_type: str  # Meeting, Phone Call, WhatsApp, In-Person, Conference, Other
    discussion: str
    commitments: Optional[str] = None
    interaction_date: Optional[str] = None


@router.post("/api/org/{org_id}/manual-context")
def add_manual_context(org_id: str, entry: ManualContextEntry, db: Session = Depends(get_db)):
    """Add a manual context entry — authority_weight=1.0, no decay. Hustler+ only."""
    require_operation(db, org_id, "manual_context")
    try:
        # Find or create the contact
        contact = db.execute(
            text("""
                SELECT id FROM contacts
                WHERE org_id = :org_id AND (
                    LOWER(name) = LOWER(:name)
                    OR LOWER(email) = LOWER(:email)
                )
                LIMIT 1
            """),
            {"org_id": org_id, "name": entry.contact_name, "email": entry.contact_email or ""},
        ).fetchone()

        contact_id = None
        if contact:
            contact_id = str(contact[0])
        else:
            limit_check = check_contact_limit(db, org_id)
            if not limit_check["allowed"]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "CONTACT_LIMIT_REACHED",
                        "message": limit_check["message"],
                        "upgrade_required": True,
                    },
                )
            # Create new contact
            contact_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO contacts (id, org_id, name, email, entity_type, authority_score)
                    VALUES (:id, :org_id, :name, :email, 'other', 1.0)
                """),
                {
                    "id": contact_id,
                    "org_id": org_id,
                    "name": entry.contact_name,
                    "email": entry.contact_email,
                },
            )

        # Create interaction record
        interaction_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO interactions (id, org_id, contact_id, direction, subject, summary, sentiment, interaction_at, intent, source, interaction_type, weight_score, signal_score)
                VALUES (:id, :org_id, :contact_id, 'outbound', :subject, :summary, 0.5, COALESCE(:date::timestamp, NOW()), :intent, 'manual', 'manual', 1.0, 0.8)
            """),
            {
                "id": interaction_id,
                "org_id": org_id,
                "contact_id": contact_id,
                "subject": f"Manual: {entry.context_type}",
                "summary": entry.discussion[:500],
                "intent": entry.context_type.lower(),
                "date": entry.interaction_date,
            },
        )

        # Update contact authority score to 1.0 (manual = highest)
        db.execute(
            text("""
                UPDATE contacts
                SET authority_score = GREATEST(COALESCE(authority_score, 0), 1.0),
                    last_interaction_at = COALESCE(:date::timestamp, NOW()),
                    interaction_count = COALESCE(interaction_count, 0) + 1
                WHERE id = :contact_id
            """),
            {"contact_id": contact_id, "date": entry.interaction_date},
        )

        # Create commitment if provided
        if entry.commitments:
            db.execute(
                text("""
                    INSERT INTO commitments (id, org_id, contact_id, commit_text, owner, status)
                    VALUES (:id, :org_id, :contact_id, :text, 'user', 'OPEN')
                """),
                {
                    "id": str(uuid.uuid4()),
                    "org_id": org_id,
                    "contact_id": contact_id,
                    "text": entry.commitments[:500],
                },
            )

        # Log activity
        db.execute(
            text("""
                INSERT INTO activity_log (id, org_id, event_type, event_data, created_at)
                VALUES (:id, :org_id, 'manual_context_added', :data, NOW())
            """),
            {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "data": f"Manual context added for {entry.contact_name}: {entry.context_type}",
            },
        )

        db.commit()

        return {
            "success": True,
            "contact_id": contact_id,
            "interaction_id": interaction_id,
        }
    except Exception as e:
        logger.error(f"Manual context error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/org/{org_id}/manual-context")
def list_manual_context(org_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """List recent manual context entries — v2 reads from facts where the
    source_item_id was tagged 'manual:' on insert.

    v1 stored manual notes in `interactions` with subject LIKE 'Manual:%'.
    Mig 0015 dropped that table; v2 routes the same payload through
    emit() → graph, so manual notes show up as ordinary S-P-O facts.
    """
    rows = db.execute(
        text("""
            SELECT id, subject, predicate, object, created_at
            FROM facts
            WHERE org_id = :oid
              AND source_item_id LIKE 'manual:%'
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"oid": org_id, "limit": limit},
    ).fetchall()
    return {
        "entries": [
            {
                "id": str(r[0]),
                "contact_name": r[1],
                "contact_email": None,
                "context_type": "manual",
                "discussion": f"{r[2]}: {r[3]}",
                "date": r[4].isoformat() if r[4] else None,
                "intent": None,
            }
            for r in rows
        ],
    }


@router.delete("/api/org/{org_id}/manual-context/{entry_id}")
def delete_manual_context(org_id: str, entry_id: str, db: Session = Depends(get_db)):
    """Delete a manual context fact (v2: facts row, not v1 interactions)."""
    try:
        db.execute(
            text("DELETE FROM facts WHERE id = :id AND org_id = :org_id"),
            {"id": entry_id, "org_id": org_id},
        )
        db.commit()
        return {"deleted": True}
    except Exception as e:
        logger.error(f"Delete manual context error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# ── File Upload ──────────────────────────────────────────────────────────

@router.post("/api/org/{org_id}/upload")
async def upload_context_file(
    org_id: str,
    file: UploadFile = File(...),
    tag: str = Form(default="other"),
    db: Session = Depends(get_db),
):
    """Upload a document (PDF, DOCX, TXT, CSV) for context extraction. Startup only."""
    require_integration(db, org_id, "documents")
    try:
        # Validate file type
        allowed_extensions = {".pdf", ".docx", ".txt", ".csv", ".doc"}
        file_ext = os.path.splitext(file.filename or "")[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}",
            )

        # Save file
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 10 MB.")
        with open(file_path, "wb") as f:
            f.write(content)

        # Record upload in DB (status: queued)
        db.execute(
            text("""
                INSERT INTO activity_log (id, org_id, event_type, event_data, created_at)
                VALUES (:id, :org_id, 'file_uploaded', :data, NOW())
            """),
            {
                "id": file_id,
                "org_id": org_id,
                "data": json.dumps({
                    "filename": file.filename,
                    "tag": tag,
                    "size_bytes": len(content),
                    "file_ext": file_ext,
                }),
            },
        )
        db.commit()

        # Extract text content
        text_content = ""
        if file_ext == ".txt":
            text_content = content.decode("utf-8", errors="ignore")
        elif file_ext == ".csv":
            text_content = content.decode("utf-8", errors="ignore")
        elif file_ext == ".pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                text_content = "\n".join(page.get_text() for page in doc)
                doc.close()
            except ImportError:
                text_content = "[PDF extraction requires PyMuPDF. Install with: pip install PyMuPDF]"
        elif file_ext in (".docx", ".doc"):
            try:
                import docx
                doc = docx.Document(file_path)
                text_content = "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                text_content = "[DOCX extraction requires python-docx. Install with: pip install python-docx]"

        # Extract entities via LLM if content available
        entities_found = 0
        commitments_found = 0
        if text_content and len(text_content) > 20:
            try:
                from app.ingestion.entity_extractor import extract_email_intelligence
                # Use LLM to extract intelligence from the document.
                # NOTE: signature is (subject, body, ..., org_id) — the doc
                # text must go in `body`, and org_id is required or _log_usage
                # (and the llm_call analytics event) silently skips.
                intelligence = extract_email_intelligence(
                    subject=f"Document: {file.filename}",
                    body=text_content[:3000],
                    org_id=org_id,
                )
                # extract_email_intelligence returns `mentioned_people` (not `entities`)
                people = intelligence.get("mentioned_people", [])
                entities_found = len(people)
                commitments_found = len(intelligence.get("commitments", []))

                # Resolve or create a contact for each detected person.
                # Documents identify people by name — no email needed
                # (source-agnostic model — see app/core/identity.py).
                from app.core.identity import resolve_or_create_person, NAME
                for entity_info in people:
                    entity_name = entity_info if isinstance(entity_info, str) else entity_info.get("name", "")
                    if not entity_name:
                        continue

                    contact_id = resolve_or_create_person(
                        db, org_id, identifiers=[(NAME, entity_name)],
                    )
                    if not contact_id:
                        continue

                    db.execute(
                        text("""
                            INSERT INTO interactions (id, org_id, contact_id, direction, subject, summary, sentiment, interaction_at, weight_score, signal_score)
                            VALUES (:id, :org_id, :contact_id, 'inbound', :subject, :summary, 0.5, NOW(), 0.7, 0.5)
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "org_id": org_id,
                            "contact_id": contact_id,
                            "subject": f"Upload: {file.filename}",
                            "summary": intelligence.get("summary", text_content[:200]),
                        },
                    )
                    db.commit()

            except Exception as extract_err:
                logger.warning(f"Entity extraction from uploaded file failed: {extract_err}")

        # Persist real status + extraction counts onto the upload record so the
        # Resources page shows per-file results instead of a hardcoded badge.
        upload_status = "indexed" if text_content else "failed"
        try:
            db.execute(
                text("""
                    UPDATE activity_log
                    SET event_data = event_data || CAST(:stats AS jsonb)
                    WHERE id = :id AND org_id = :org_id
                """),
                {
                    "id": file_id, "org_id": org_id,
                    "stats": json.dumps({
                        "status": upload_status,
                        "contacts_count": entities_found,
                        "commitments_count": commitments_found,
                    }),
                },
            )
            db.commit()
        except Exception as _stat_err:
            logger.warning(f"Could not persist upload stats: {_stat_err}")
            db.rollback()

        return {
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "file_type": file_ext,
            "tag": tag,
            "size_bytes": len(content),
            "text_extracted": len(text_content) > 0,
            "entities_found": entities_found,
            "commitments_found": commitments_found,
            "status": upload_status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/org/{org_id}/uploads")
def list_uploads(org_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """List recently uploaded files with parsed metadata."""
    try:
        # v1 stored uploads as activity_log rows (dropped). v2 path: an
        # upload becomes a 'document' node in graph_nodes whose source_item_id
        # is prefixed 'document:<file_id>'. Surface those as the uploads list.
        rows = db.execute(
            text("""
                SELECT id, canonical_name, attributes, first_seen,
                       jsonb_array_elements_text(
                         CASE jsonb_typeof(source_item_ids::jsonb)
                              WHEN 'array' THEN source_item_ids::jsonb
                              ELSE '[]'::jsonb END
                       ) AS item
                FROM graph_nodes
                WHERE org_id = :org_id
                  AND type = 'entity'
                  AND source_item_ids::text LIKE '%document:%'
                ORDER BY first_seen DESC
                LIMIT :limit
            """),
            {"org_id": org_id, "limit": limit},
        ).fetchall()
        seen: set[str] = set()
        uploads: list[dict] = []
        for r in rows:
            if not r[4] or not r[4].startswith("document:"):
                continue
            file_id = r[4][len("document:"):]
            if file_id in seen:
                continue
            seen.add(file_id)
            attrs = r[2] if isinstance(r[2], dict) else {}
            uploads.append({
                "id": file_id,
                "file_name": r[1] or "document",
                "file_type": (attrs.get("file_ext") or "TXT").upper(),
                "size": "—",
                "size_bytes": 0,
                "tag": attrs.get("tag", "Other"),
                "status": "indexed",
                "contacts_count": None,
                "commitments_count": None,
                "uploaded_at": r[3].isoformat() if r[3] else None,
                "authority": 1.0,
            })
        return {"uploads": uploads}
    except Exception as e:
        logger.error(f"List uploads error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# ── Delete / Re-tag Upload ───────────────────────────────────────────────
# v2 docs live in graph_nodes (tagged source_item_id = 'document:<file_id>').
# Delete/tag operate via source_item_ids JSONB rather than the dropped
# activity_log row.

@router.delete("/api/org/{org_id}/uploads/{file_id}")
def delete_upload(org_id: str, file_id: str, db: Session = Depends(get_db)):
    """Remove uploaded file's bytes from disk + drop nodes tagged with it."""
    try:
        for fname in os.listdir(UPLOAD_DIR):
            if fname.startswith(file_id):
                os.remove(os.path.join(UPLOAD_DIR, fname))
                break
        tag = f"document:{file_id}"
        db.execute(
            text("""
                DELETE FROM graph_nodes
                WHERE org_id = :org_id
                  AND EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(
                      CASE jsonb_typeof(source_item_ids::jsonb)
                           WHEN 'array' THEN source_item_ids::jsonb
                           ELSE '[]'::jsonb END
                    ) AS i WHERE i = :tag)
            """),
            {"org_id": org_id, "tag": tag},
        )
        db.execute(
            text("DELETE FROM facts WHERE org_id = :org_id AND source_item_id = :tag"),
            {"org_id": org_id, "tag": tag},
        )
        db.commit()
        return {"deleted": True}
    except Exception as e:
        logger.error(f"Delete upload error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


class RetagRequest(BaseModel):
    tag: str

@router.patch("/api/org/{org_id}/uploads/{file_id}/tag")
def retag_upload(org_id: str, file_id: str, body: RetagRequest, db: Session = Depends(get_db)):
    """v2 doesn't store per-upload metadata — retag is a no-op echo so the UI
    doesn't break. Real per-document attribute editing is a future feature."""
    return {"retagged": True, "tag": body.tag, "note": "tag is informational only in v2"}


# ── Edit Manual Context ──────────────────────────────────────────────────

class ManualContextUpdate(BaseModel):
    discussion: Optional[str] = None
    commitments: Optional[str] = None
    context_type: Optional[str] = None

@router.patch("/api/org/{org_id}/manual-context/{entry_id}")
def update_manual_context(org_id: str, entry_id: str, body: ManualContextUpdate, db: Session = Depends(get_db)):
    """Update a manual context entry."""
    try:
        sets = []
        params: dict = {"id": entry_id, "org_id": org_id}
        if body.discussion is not None:
            sets.append("summary = :summary")
            params["summary"] = body.discussion[:500]
        if body.context_type is not None:
            sets.append("subject = :subject")
            params["subject"] = f"Manual: {body.context_type}"
        if not sets:
            return {"updated": False}
        db.execute(
            text(f"UPDATE interactions SET {', '.join(sets)} WHERE id = :id AND org_id = :org_id"),
            params,
        )
        db.commit()
        return {"updated": True}
    except Exception as e:
        logger.error(f"Update manual context error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── Correct Context ───────────────────────────────────────────────────────

_VALID_STAGES = {"ACTIVE", "WARM", "NEEDS_ATTENTION", "DORMANT", "COLD", "AT_RISK"}

class ContextCorrection(BaseModel):
    relationship_stage: Optional[str] = None
    topics: Optional[list] = None
    notes: Optional[str] = None

@router.patch("/api/org/{org_id}/contacts/{contact_id}/correct")
def correct_context(org_id: str, contact_id: str, body: ContextCorrection, db: Session = Depends(get_db)):
    """Correct a contact's context fields — relationship stage, topics, notes. Hustler+ only."""
    require_operation(db, org_id, "correct_context")
    try:
        if body.relationship_stage and body.relationship_stage.upper() not in _VALID_STAGES:
            raise HTTPException(status_code=400, detail=f"Invalid stage. Valid values: {sorted(_VALID_STAGES)}")

        sets = []
        params: dict = {"id": contact_id, "org_id": org_id}
        if body.relationship_stage is not None:
            sets.append("relationship_stage = :stage")
            params["stage"] = body.relationship_stage.upper()
        if body.topics is not None:
            sets.append("topics_aggregate = :topics")
            params["topics"] = json.dumps(body.topics)
        if body.notes is not None:
            sets.append("context_notes = :notes")
            params["notes"] = body.notes[:1000]
        if not sets:
            return {"updated": False}

        result = db.execute(
            text(f"UPDATE contacts SET {', '.join(sets)} WHERE id = :id AND org_id = :org_id"),
            params,
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contact not found")
        db.commit()
        return {"updated": True, "contact_id": contact_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Correct context error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── Override Relationship Stage ───────────────────────────────────────────

class StageOverride(BaseModel):
    stage: str

@router.patch("/api/org/{org_id}/contacts/{contact_id}/stage")
def override_stage(org_id: str, contact_id: str, body: StageOverride, db: Session = Depends(get_db)):
    """Manually override the auto-computed relationship stage for a contact. Hustler+ only."""
    require_operation(db, org_id, "override_stage")
    stage = body.stage.upper()
    if stage not in _VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Valid values: {sorted(_VALID_STAGES)}")
    try:
        row = db.execute(
            text("SELECT relationship_stage FROM contacts WHERE id = :id AND org_id = :org_id"),
            {"id": contact_id, "org_id": org_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        previous_stage = row[0]
        db.execute(
            text("UPDATE contacts SET relationship_stage = :stage WHERE id = :id AND org_id = :org_id"),
            {"stage": stage, "id": contact_id, "org_id": org_id},
        )
        db.commit()
        return {"contact_id": contact_id, "previous_stage": previous_stage, "new_stage": stage}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Override stage error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
