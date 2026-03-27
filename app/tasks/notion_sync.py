"""
Notion Sync Task

Phase 1 MVP:
  - 30-min cron: search pages edited since last_sync_cursor
  - Page quality gate → recursive block fetch (max 4 levels)
  - Semantic chunking (H1/H2 boundaries, 400-600 tokens)
  - Upsert notion_pages + notion_page_chunks
  - Meeting notes extraction → notion_meeting_notes
"""

import logging
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.database import SessionLocal
from app.ingestion.notion_connector import (
    fetch_pages_since,
    fetch_page,
    fetch_blocks,
    classify_page,
    chunk_blocks,
)

logger = logging.getLogger(__name__)


def _get_notion_connection(db, org_id):
    return db.execute(
        text("""
            SELECT workspace_id, access_token, last_sync_cursor, last_full_sync_at
            FROM notion_connections WHERE org_id = :oid LIMIT 1
        """),
        {"oid": org_id},
    ).fetchone()


def run_notion_sync(org_id: str):
    """
    Main Notion sync entry point. Called after OAuth connect and by 30-min cron.

    Signal taxonomy quality gates applied BEFORE any DB writes:
      - DROP archived: true
      - DROP is_template: true
      - DROP title == "Untitled" (drafts)
      - DROP block_count < 3 (blank/stub pages)
      - SKIP embed, image, video, audio, file, code, equation blocks
      - On synced_block: skip copies, only index originals
      - Hard recursion limit: 4 levels
    """
    db = SessionLocal()
    try:
        conn = _get_notion_connection(db, org_id)
        if not conn or not conn.access_token:
            logger.warning(f"Notion sync: no connection found for org {org_id}")
            return

        # Mark as running
        db.execute(
            text("UPDATE notion_connections SET backfill_status = 'running', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()

        cursor = None
        pages_processed = 0

        while True:
            pages, next_cursor = fetch_pages_since(
                conn.access_token,
                last_sync_cursor=cursor,
                page_size=100,
            )

            for page in pages:
                # Quality gate
                classification = classify_page(page)
                if classification is None:
                    continue

                processed = _process_page(db, org_id, conn.access_token, page, classification)
                if processed:
                    pages_processed += 1

            if not next_cursor:
                break
            cursor = next_cursor

        # Update sync cursor
        db.execute(
            text("""
                UPDATE notion_connections
                SET last_sync_cursor = NOW(),
                    last_full_sync_at = COALESCE(last_full_sync_at, NOW()),
                    backfill_status = 'complete',
                    updated_at = NOW()
                WHERE org_id = :oid
            """),
            {"oid": org_id},
        )
        db.commit()
        logger.info(f"Notion sync complete: org={org_id} processed {pages_processed} pages")

    except Exception as e:
        db.execute(
            text("UPDATE notion_connections SET backfill_status = 'error', updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()
        logger.error(f"Notion sync failed for org {org_id}: {e}")
        raise
    finally:
        db.close()


def _process_page(db, org_id, access_token, page, classification):
    """
    Process a single Notion page: upsert metadata, fetch blocks, chunk, upsert chunks.
    Returns True if successfully processed.
    """
    page_id = page.get("id")
    if not page_id:
        return False

    title = classification.get("title", "")
    last_edited_time = page.get("last_edited_time")
    url = page.get("url")
    parent = page.get("parent", {})
    parent_id = parent.get("page_id") or parent.get("database_id")

    # Infer page type
    parent_type = parent.get("type", "")
    page_type = "database_item" if parent_type == "database_id" else "page"

    # Check if page needs re-indexing (freshness check)
    existing = db.execute(
        text("SELECT id, last_indexed_at, last_edited_time FROM notion_pages WHERE org_id = :oid AND page_id = :pid"),
        {"oid": org_id, "pid": page_id},
    ).fetchone()

    if existing and existing.last_edited_time and last_edited_time:
        if existing.last_edited_time.isoformat()[:19] >= last_edited_time[:19]:
            return False  # No changes since last index

    # Fetch blocks (max 4 levels deep)
    try:
        blocks = fetch_blocks(access_token, page_id, max_depth=4)
    except Exception as e:
        logger.warning(f"Failed to fetch blocks for page {page_id}: {e}")
        blocks = []

    block_count = len(blocks)

    # Quality gate: drop pages with too few blocks
    if block_count < 3:
        return False

    # Upsert page record
    db.execute(
        text("""
            INSERT INTO notion_pages (
                org_id, page_id, parent_id, page_type, title, url,
                is_archived, block_count, last_edited_time, last_indexed_at,
                index_status
            )
            VALUES (
                :org_id, :page_id, :parent_id, :page_type, :title, :url,
                FALSE, :block_count, :last_edited_time, NOW(),
                'indexed'
            )
            ON CONFLICT (org_id, page_id) DO UPDATE SET
                title = EXCLUDED.title,
                block_count = EXCLUDED.block_count,
                last_edited_time = EXCLUDED.last_edited_time,
                last_indexed_at = NOW(),
                index_status = 'indexed'
        """),
        {
            "org_id": org_id,
            "page_id": page_id,
            "parent_id": parent_id,
            "page_type": page_type,
            "title": title,
            "url": url,
            "block_count": block_count,
            "last_edited_time": last_edited_time,
        },
    )
    db.commit()

    # Get the page's UUID
    page_row = db.execute(
        text("SELECT id FROM notion_pages WHERE org_id = :oid AND page_id = :pid"),
        {"oid": org_id, "pid": page_id},
    ).fetchone()
    if not page_row:
        return False

    page_uuid = page_row.id

    # Semantic chunking
    chunks = chunk_blocks(blocks, max_tokens=500, min_tokens=50)

    # Delete old chunks and re-insert
    db.execute(
        text("DELETE FROM notion_page_chunks WHERE org_id = :oid AND page_id = :pid"),
        {"oid": org_id, "pid": page_uuid},
    )

    for idx, chunk in enumerate(chunks):
        db.execute(
            text("""
                INSERT INTO notion_page_chunks
                    (org_id, page_id, chunk_index, section_heading, text_content, token_count)
                VALUES (:org_id, :page_id, :idx, :heading, :text, :tokens)
                ON CONFLICT (org_id, page_id, chunk_index) DO UPDATE SET
                    section_heading = EXCLUDED.section_heading,
                    text_content = EXCLUDED.text_content,
                    token_count = EXCLUDED.token_count
            """),
            {
                "org_id": org_id,
                "page_id": page_uuid,
                "idx": idx,
                "heading": chunk.get("section_heading", ""),
                "text": chunk.get("text_content", ""),
                "tokens": chunk.get("estimated_tokens"),
            },
        )

    db.execute(
        text("UPDATE notion_pages SET chunk_count = :count WHERE id = :id"),
        {"count": len(chunks), "id": page_uuid},
    )
    db.commit()
    return True
