"""
Google Docs Sync Task

Phase 1 MVP:
  - Drive modifiedTime cursor for incremental sync
  - Parallel body + comments fetch (ALWAYS both, never one without the other)
  - Semantic chunking (H1/H2 boundaries, 400-600 tokens)
  - Contract extraction → gdocs_contracts
  - Unresolved comment → State Graph open loop signal

CRITICAL:
  - Always use suggestionsViewMode=PREVIEW_WITHOUT_SUGGESTIONS
  - Always fetch body AND comments as two parallel operations
  - Never fetch revision history body
  - Paginate comments fully (loop nextPageToken until null)
"""

import logging
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.database import SessionLocal
from app.ingestion.docs_connector import (
    build_docs_service,
    build_drive_service,
    get_docs_user_email,
    fetch_document_and_comments_parallel,
    traverse_structural_elements,
    chunk_document,
    classify_document,
    count_words_in_elements,
    MIN_WORD_COUNT,
)

logger = logging.getLogger(__name__)


def _get_docs_connection(db, org_id):
    return db.execute(
        text("""
            SELECT access_token, refresh_token, token_expires_at,
                   last_sync_cursor, last_full_sync_at, backfill_status
            FROM gdocs_connections WHERE org_id = :oid LIMIT 1
        """),
        {"oid": org_id},
    ).fetchone()


def run_docs_sync(org_id: str):
    """
    Main Docs sync entry point.

    Signal taxonomy quality gates:
      - DROP title == "Untitled document" (draft)
      - DROP trashed: true
      - DROP word_count < MIN_WORD_COUNT (150)
      - DROP auto-generated template docs
      - DROP personal/private docs (only owner access — require opt-in)
      - DROP Docs from Google Forms
      - Always fetch with suggestionsViewMode=PREVIEW_WITHOUT_SUGGESTIONS
      - Always parallel fetch: body + comments
    """
    db = SessionLocal()
    try:
        conn = _get_docs_connection(db, org_id)
        if not conn or not conn.access_token:
            logger.warning(f"Docs sync: no connection found for org {org_id}")
            return

        docs_service = build_docs_service(conn.access_token, conn.refresh_token)
        drive_service = build_drive_service(conn.access_token, conn.refresh_token)

        # Mark as running
        db.execute(
            text("UPDATE gdocs_connections SET backfill_status = 'running', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()

        # Fetch all Google Docs from Drive since last cursor
        last_cursor = conn.last_sync_cursor
        docs_fetched = _get_docs_from_drive(drive_service, since=last_cursor)

        docs_processed = 0
        for doc_file in docs_fetched:
            try:
                # Quality gate: classify based on Drive metadata first
                classification = classify_document(doc_file)
                if classification is None:
                    continue

                processed = _process_document(db, docs_service, drive_service, org_id, doc_file, classification)
                if processed:
                    docs_processed += 1

            except Exception as e:
                logger.error(f"Docs: failed to process doc {doc_file.get('id')}: {e}")

        # Update cursor
        db.execute(
            text("""
                UPDATE gdocs_connections
                SET last_sync_cursor = NOW(),
                    last_full_sync_at = COALESCE(last_full_sync_at, NOW()),
                    backfill_status = 'complete',
                    updated_at = NOW()
                WHERE org_id = :oid
            """),
            {"oid": org_id},
        )
        db.commit()
        logger.info(f"Docs sync complete: org={org_id} processed {docs_processed} documents")

        # ── Phase 2: Bridge Docs data into relationship graph ──
        try:
            from app.ingestion.docs_bridge import resolve_docs_people_to_contacts, create_docs_interactions
            from app.graph.relationship_calculator import recalculate_all_relationships
            resolve_docs_people_to_contacts(db, org_id)
            db.commit()
            created = create_docs_interactions(db, org_id)
            db.commit()
            if created > 0:
                recalculate_all_relationships(db, org_id)
        except Exception as bridge_err:
            logger.error(f"Docs bridge failed for org {org_id}: {bridge_err}")

    except Exception as e:
        db.execute(
            text("UPDATE gdocs_connections SET backfill_status = 'error', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()
        logger.error(f"Docs sync failed for org {org_id}: {e}")
        raise
    finally:
        db.close()


def _get_docs_from_drive(drive_service, since=None, max_results=100):
    """
    Fetch Google Docs files from Drive modified since cursor.
    Returns list of Drive file metadata dicts.
    """
    query = "mimeType='application/vnd.google-apps.document' and trashed=false"
    if since:
        cursor_str = since.isoformat() if hasattr(since, "isoformat") else str(since)
        query += f" and modifiedTime > '{cursor_str}'"

    try:
        result = drive_service.files().list(
            q=query,
            pageSize=min(max_results, 100),
            fields="files(id,name,mimeType,trashed,owners,modifiedTime,createdTime,description,capabilities)",
            orderBy="modifiedTime desc",
        ).execute()
        return result.get("files", [])
    except Exception as e:
        logger.error(f"Failed to list docs from Drive: {e}")
        return []


def _process_document(db, docs_service, drive_service, org_id, doc_file, classification):
    """
    Process a single Google Doc:
    1. Check staleness
    2. Parallel fetch body + comments (CRITICAL: always both)
    3. Quality gate on word count
    4. Chunk and upsert
    5. Contract extraction
    6. Unresolved comment signals
    """
    doc_id = doc_file.get("id")
    title = classification.get("title", "")
    modified_time = doc_file.get("modifiedTime")

    # Check if already indexed and unchanged
    existing = db.execute(
        text("SELECT id, last_modified_time FROM gdocs_documents WHERE org_id = :oid AND document_id = :did"),
        {"oid": org_id, "did": doc_id},
    ).fetchone()

    if existing and existing.last_modified_time:
        existing_str = existing.last_modified_time.isoformat()[:19]
        new_str = (modified_time or "")[:19]
        if existing_str >= new_str:
            return False  # No change

    # CRITICAL: Parallel fetch body + comments
    try:
        doc_body, comments = fetch_document_and_comments_parallel(docs_service, drive_service, doc_id)
    except Exception as e:
        logger.error(f"Docs: failed to fetch doc {doc_id} + comments: {e}")
        return False

    # Parse structural elements
    elements = traverse_structural_elements(doc_body)
    word_count = count_words_in_elements(elements)

    # Quality gate: too short
    if word_count < MIN_WORD_COUNT:
        return False

    # Upsert document record
    owners = doc_file.get("owners", [{}])
    owner_email = owners[0].get("emailAddress") if owners else None

    db.execute(
        text("""
            INSERT INTO gdocs_documents (
                org_id, document_id, title, owned_by_us, owner_email,
                last_modified_time, last_indexed_at, word_count,
                comment_count, index_status
            )
            VALUES (
                :org_id, :doc_id, :title, :owned_by_us, :owner_email,
                :modified_time, NOW(), :word_count,
                :comment_count, 'indexed'
            )
            ON CONFLICT (org_id, document_id) DO UPDATE SET
                title = EXCLUDED.title,
                last_modified_time = EXCLUDED.last_modified_time,
                last_indexed_at = NOW(),
                word_count = EXCLUDED.word_count,
                comment_count = EXCLUDED.comment_count,
                index_status = 'indexed'
        """),
        {
            "org_id": org_id,
            "doc_id": doc_id,
            "title": title,
            "owned_by_us": doc_file.get("capabilities", {}).get("canEdit", False),
            "owner_email": owner_email,
            "modified_time": modified_time,
            "word_count": word_count,
            "comment_count": len(comments),
        },
    )
    db.commit()

    # Get document UUID
    doc_row = db.execute(
        text("SELECT id FROM gdocs_documents WHERE org_id = :oid AND document_id = :did"),
        {"oid": org_id, "did": doc_id},
    ).fetchone()
    if not doc_row:
        return False

    doc_uuid = doc_row.id

    # Semantic chunking
    chunks = chunk_document(elements, max_tokens=500, min_tokens=50)
    db.execute(
        text("DELETE FROM gdocs_chunks WHERE org_id = :oid AND document_id = :did"),
        {"oid": org_id, "did": doc_uuid},
    )

    for idx, chunk in enumerate(chunks):
        db.execute(
            text("""
                INSERT INTO gdocs_chunks
                    (org_id, document_id, chunk_index, section_heading, text_content, token_count)
                VALUES (:org_id, :doc_id, :idx, :heading, :text, :tokens)
                ON CONFLICT (org_id, document_id, chunk_index) DO UPDATE SET
                    section_heading = EXCLUDED.section_heading,
                    text_content = EXCLUDED.text_content,
                    token_count = EXCLUDED.token_count
            """),
            {
                "org_id": org_id,
                "doc_id": doc_uuid,
                "idx": idx,
                "heading": chunk.get("section_heading", ""),
                "text": chunk.get("text_content", ""),
                "tokens": chunk.get("estimated_tokens"),
            },
        )

    db.execute(
        text("UPDATE gdocs_documents SET chunk_count = :count WHERE id = :id"),
        {"count": len(chunks), "id": doc_uuid},
    )

    # Upsert comments
    unresolved_count = 0
    for comment in comments:
        resolved = comment.get("resolved", False)
        if not resolved:
            unresolved_count += 1

        author = comment.get("author", {})
        db.execute(
            text("""
                INSERT INTO gdocs_comments (
                    org_id, document_id, comment_id, author_email, content,
                    quoted_text, resolved, created_at
                )
                VALUES (
                    :org_id, :doc_id, :comment_id, :author_email, :content,
                    :quoted_text, :resolved, :created_at
                )
                ON CONFLICT (org_id, document_id, comment_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    resolved = EXCLUDED.resolved
            """),
            {
                "org_id": org_id,
                "doc_id": doc_uuid,
                "comment_id": comment.get("id"),
                "author_email": author.get("emailAddress"),
                "content": comment.get("content", ""),
                "quoted_text": comment.get("quotedFileContent", {}).get("value"),
                "resolved": resolved,
                "created_at": comment.get("createdTime"),
            },
        )

    db.execute(
        text("UPDATE gdocs_documents SET unresolved_comment_count = :count WHERE id = :id"),
        {"count": unresolved_count, "id": doc_uuid},
    )
    db.commit()

    # Heuristic contract detection (by title keywords)
    _try_detect_contract(db, org_id, doc_uuid, title, chunks)

    return True


def _try_detect_contract(db, org_id, doc_uuid, title, chunks):
    """Heuristic contract detector based on title + content keywords."""
    title_lower = title.lower()
    contract_keywords = ["agreement", "contract", "msa", "sow", "nda", "terms", "addendum", "amendment"]
    is_contract = any(kw in title_lower for kw in contract_keywords)

    if not is_contract:
        # Check first chunk content
        if chunks:
            first_text = (chunks[0].get("text_content") or "").lower()
            is_contract = any(kw in first_text for kw in contract_keywords)

    if not is_contract:
        return

    # Infer contract type from title
    contract_type = "other"
    if "nda" in title_lower or "non-disclosure" in title_lower:
        contract_type = "nda"
    elif "employment" in title_lower or "offer letter" in title_lower:
        contract_type = "employment"
    elif "vendor" in title_lower or "supplier" in title_lower:
        contract_type = "vendor"
    elif "client" in title_lower or "customer" in title_lower:
        contract_type = "client"
    elif "saas" in title_lower or "subscription" in title_lower:
        contract_type = "saas"
    elif "msa" in title_lower or "master" in title_lower:
        contract_type = "vendor"

    db.execute(
        text("""
            INSERT INTO gdocs_contracts
                (org_id, document_id, contract_type, extraction_confidence, status)
            VALUES (:org_id, :doc_id, :contract_type, 0.6, 'active')
            ON CONFLICT (org_id, document_id) DO UPDATE SET
                contract_type = EXCLUDED.contract_type
        """),
        {"org_id": org_id, "doc_id": doc_uuid, "contract_type": contract_type},
    )
    db.commit()
