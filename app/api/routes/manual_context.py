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
    """List recent manual context entries."""
    try:
        results = db.execute(
            text("""
                SELECT i.id, c.name, c.email, i.subject, i.summary, i.interaction_at, i.intent
                FROM interactions i
                JOIN contacts c ON i.contact_id = c.id
                WHERE i.org_id = :org_id
                AND i.subject LIKE 'Manual:%'
                ORDER BY i.interaction_at DESC NULLS LAST
                LIMIT :limit
            """),
            {"org_id": org_id, "limit": limit},
        ).fetchall()

        return {
            "entries": [
                {
                    "id": str(r[0]),
                    "contact_name": r[1],
                    "contact_email": r[2],
                    "context_type": (r[3] or "").replace("Manual: ", ""),
                    "discussion": r[4],
                    "date": str(r[5]) if r[5] else None,
                    "intent": r[6],
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error(f"List manual context error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/org/{org_id}/manual-context/{entry_id}")
def delete_manual_context(org_id: str, entry_id: str, db: Session = Depends(get_db)):
    """Delete a manual context entry."""
    try:
        db.execute(
            text("DELETE FROM interactions WHERE id = :id AND org_id = :org_id"),
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
        if text_content and len(text_content) > 20:
            try:
                from app.ingestion.entity_extractor import extract_email_intelligence
                # Use LLM to extract entities from the document
                intelligence = extract_email_intelligence(text_content[:3000], f"Document: {file.filename}")
                entities_found = len(intelligence.get("entities", []))

                # Create interactions for each detected entity
                for entity_info in intelligence.get("entities", []):
                    entity_name = entity_info if isinstance(entity_info, str) else entity_info.get("name", "")
                    if not entity_name:
                        continue

                    # Find existing contact or skip
                    existing = db.execute(
                        text("SELECT id FROM contacts WHERE org_id = :org_id AND LOWER(name) = LOWER(:name) LIMIT 1"),
                        {"org_id": org_id, "name": entity_name},
                    ).fetchone()

                    if existing:
                        db.execute(
                            text("""
                                INSERT INTO interactions (id, org_id, contact_id, direction, subject, summary, sentiment, interaction_at, weight_score, signal_score)
                                VALUES (:id, :org_id, :contact_id, 'inbound', :subject, :summary, 0.5, NOW(), 0.7, 0.5)
                            """),
                            {
                                "id": str(uuid.uuid4()),
                                "org_id": org_id,
                                "contact_id": str(existing[0]),
                                "subject": f"Upload: {file.filename}",
                                "summary": intelligence.get("summary", text_content[:200]),
                            },
                        )
                        db.commit()

            except Exception as extract_err:
                logger.warning(f"Entity extraction from uploaded file failed: {extract_err}")

        return {
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "file_type": file_ext,
            "tag": tag,
            "size_bytes": len(content),
            "text_extracted": len(text_content) > 0,
            "entities_found": entities_found,
            "status": "indexed" if text_content else "queued",
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
        results = db.execute(
            text("""
                SELECT id, event_data, created_at
                FROM activity_log
                WHERE org_id = :org_id AND event_type = 'file_uploaded'
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"org_id": org_id, "limit": limit},
        ).fetchall()

        uploads = []
        for r in results:
            data = r[1] if isinstance(r[1], dict) else {}
            size_bytes = data.get("size_bytes", 0)
            size_str = (
                f"{size_bytes / (1024*1024):.1f}MB" if size_bytes > 1024*1024
                else f"{size_bytes // 1024}KB" if size_bytes > 0
                else "—"
            )
            uploads.append({
                "id": str(r[0]),
                "file_name": data.get("filename", "unknown"),
                "file_type": (data.get("file_ext", "").lstrip(".") or "txt").upper(),
                "size": size_str,
                "size_bytes": size_bytes,
                "tag": data.get("tag", "Other"),
                "status": "indexed",
                "uploaded_at": str(r[2]) if r[2] else None,
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


# ── Delete Upload ────────────────────────────────────────────────────────

@router.delete("/api/org/{org_id}/uploads/{file_id}")
def delete_upload(org_id: str, file_id: str, db: Session = Depends(get_db)):
    """Delete an uploaded file and its activity log entry."""
    try:
        for fname in os.listdir(UPLOAD_DIR):
            if fname.startswith(file_id):
                os.remove(os.path.join(UPLOAD_DIR, fname))
                break
        db.execute(
            text("DELETE FROM activity_log WHERE id = :id AND org_id = :org_id AND event_type = 'file_uploaded'"),
            {"id": file_id, "org_id": org_id},
        )
        db.commit()
        return {"deleted": True}
    except Exception as e:
        logger.error(f"Delete upload error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── Re-tag Upload ────────────────────────────────────────────────────────

class RetagRequest(BaseModel):
    tag: str

@router.patch("/api/org/{org_id}/uploads/{file_id}/tag")
def retag_upload(org_id: str, file_id: str, body: RetagRequest, db: Session = Depends(get_db)):
    """Re-tag an uploaded file."""
    try:
        row = db.execute(
            text("SELECT event_data FROM activity_log WHERE id = :id AND org_id = :org_id AND event_type = 'file_uploaded'"),
            {"id": file_id, "org_id": org_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Upload not found")
        data = row[0] if isinstance(row[0], dict) else {}
        data["tag"] = body.tag
        db.execute(
            text("UPDATE activity_log SET event_data = CAST(:data AS jsonb) WHERE id = :id AND org_id = :org_id"),
            {"data": json.dumps(data), "id": file_id, "org_id": org_id},
        )
        db.commit()
        return {"retagged": True, "tag": body.tag}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retag upload error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


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
