#!/usr/bin/env python3
"""
Capped reextract — same logic as app.tasks.reextract.run_reextract but:
  - Hard ceiling on rows processed (default 40)
  - Token budget watchdog — abort if running total approaches the daily
    Groq free-tier limit (default 80K out of 100K, leaving 20K headroom)
  - Per-row console output so progress is visible
  - Safe to interrupt — every row commits independently

Usage:
  python scripts/_reextract_capped.py [max_rows] [token_budget]
"""
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force programmatic narrative — don't waste tokens on cosmetic headlines
os.environ.setdefault("GENIOS_NARRATIVE_USE_LLM", "false")

from sqlalchemy import text
from app.database import SessionLocal
from app.config import PROCESSING_VERSION
from app.ingestion.gmail_connector import build_gmail_service, fetch_full_message
from app.ingestion.email_parser import parse_headers, extract_email_body, detect_attachments
from app.ingestion.attachment_extractor import extract_attachment_text
from app.ingestion.email_classifier import classify_email
from app.ingestion.entity_extractor import extract_email_intelligence

ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"

MAX_ROWS = int(sys.argv[1]) if len(sys.argv) > 1 else 40
TOKEN_BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 80_000


_RUN_STARTED_AT = datetime.now(timezone.utc)


def get_used_tokens_this_run(db) -> int:
    """Tokens consumed since this script started — not historical 24h.
    Lets us track usage on a freshly-rotated Groq key without being
    blocked by the previous key's exhausted quota in DB history."""
    r = db.execute(text("""
        SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS used
        FROM llm_usage
        WHERE provider = 'groq'
          AND called_at >= :since
    """), {"since": _RUN_STARTED_AT}).scalar()
    return int(r or 0)


def pick_stale_rows(db, limit):
    """The same WHERE clause run_reextract uses, plus our cap."""
    return db.execute(text("""
        SELECT i.id, i.gmail_message_id, i.subject, i.direction,
               i.contact_id, i.account_email,
               c.name AS contact_name, c.email AS contact_email
        FROM interactions i
        JOIN contacts c ON c.id = i.contact_id
        WHERE i.org_id = :oid
          AND i.source = 'gmail'
          AND COALESCE(i.processed_version, 1) < :v
          AND i.gmail_message_id IS NOT NULL
        ORDER BY i.interaction_at DESC NULLS LAST
        LIMIT :n
    """), {"oid": ORG_ID, "v": PROCESSING_VERSION, "n": limit}).fetchall()


def gmail_service_for_account(db, account_email: str | None):
    """Build Gmail client from stored OAuth token (per account if multi)."""
    row = db.execute(text("""
        SELECT access_token, refresh_token, account_email
        FROM oauth_tokens
        WHERE org_id = :oid
          AND (:acct IS NULL OR account_email = :acct OR account_email IS NULL)
        ORDER BY (account_email = :acct) DESC NULLS LAST
        LIMIT 1
    """), {"oid": ORG_ID, "acct": account_email}).fetchone()
    if not row:
        raise RuntimeError("no oauth token row")
    return build_gmail_service(row.access_token, row.refresh_token)


def main():
    print("=" * 70)
    print(f"  Capped reextract — Rohit's org")
    print(f"  Max rows      : {MAX_ROWS}")
    print(f"  Token budget  : {TOKEN_BUDGET:,}")
    print("=" * 70)

    db = SessionLocal()
    try:
        used_today = get_used_tokens_this_run(db)
        print(f"\nGroq tokens used (this run baseline): {used_today:,}")
        print(f"Token budget for this run: {TOKEN_BUDGET:,}")

        rows = pick_stale_rows(db, MAX_ROWS)
        print(f"Stale rows to process: {len(rows)}")
        if not rows:
            print("Nothing to do.")
            return 0

        # Build Gmail service once
        service = gmail_service_for_account(db, rows[0].account_email)

        ok = fail = skip = 0
        budget_hit = False
        start = time.time()

        for i, r in enumerate(rows, 1):
            # Check token budget before each row
            used_now = get_used_tokens_this_run(db)
            if used_now >= TOKEN_BUDGET:
                print(f"\n⚠ Token budget reached ({used_now:,}/{TOKEN_BUDGET:,}). Stopping.")
                budget_hit = True
                break

            label = f"[{i}/{len(rows)}]"
            try:
                msg = fetch_full_message(service, r.gmail_message_id)
                payload = msg.get("payload", {})
                body = extract_email_body(payload)
                attach_info = detect_attachments(payload)

                if attach_info.get("has_attachment"):
                    try:
                        atext = extract_attachment_text(service, r.gmail_message_id, payload)
                        if atext:
                            body = (body + "\n\n" + atext)[:8000]
                    except Exception as ae:
                        print(f"  {label} attach extract warn: {ae}")

                # Tier 0/1 classifier — skip noise
                headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
                category = classify_email(
                    subject=r.subject or "",
                    sender_email=r.contact_email or "",
                    body=body or "",
                    headers=headers,
                )
                if category == "TIER_0":
                    db.execute(text(
                        "UPDATE interactions SET processed_version = :v WHERE id = :id"
                    ), {"v": PROCESSING_VERSION, "id": str(r.id)})
                    db.commit()
                    skip += 1
                    print(f"  {label} skipped (TIER_0): {r.contact_email}")
                    continue

                intel = extract_email_intelligence(
                    subject=r.subject or "",
                    body=body,
                    sender_name=r.contact_name or "",
                    is_reply=bool(r.subject and "re:" in (r.subject or "").lower()),
                    org_id=ORG_ID,
                )

                summary = (intel.get("summary") or "")[:500]
                sentiment = float(intel.get("sentiment", 0.0))
                intent = (intel.get("intent") or "other")[:50]
                topics = intel.get("topics") or []
                interaction_type = (intel.get("interaction_type") or "email_one_way")[:50]

                db.execute(text("""
                    UPDATE interactions
                    SET summary = :summary,
                        sentiment = :sentiment,
                        intent = :intent,
                        topics = :topics,
                        interaction_type = :itype,
                        extraction_status = 'extracted',
                        processed_version = :v,
                        raw_body = LEFT(COALESCE(raw_body, :fallback), 1000)
                    WHERE id = :id
                """), {
                    "summary": summary, "sentiment": sentiment, "intent": intent,
                    "topics": topics, "itype": interaction_type,
                    "v": PROCESSING_VERSION, "id": str(r.id),
                    "fallback": (body or "")[:1000],
                })
                db.commit()

                ok += 1
                print(f"  {label} ✅ {r.contact_email[:40]:40} → {summary[:60]}")

            except Exception as e:
                fail += 1
                # Mark version anyway to avoid infinite retry
                try:
                    db.rollback()
                    db.execute(text(
                        "UPDATE interactions SET processed_version = :v WHERE id = :id"
                    ), {"v": PROCESSING_VERSION, "id": str(r.id)})
                    db.commit()
                except Exception:
                    db.rollback()
                print(f"  {label} ❌ {r.contact_email[:40]:40}: {type(e).__name__}: {str(e)[:80]}")

            # Groq 30 RPM cap
            time.sleep(2)

        elapsed = time.time() - start
        used_after = get_used_tokens_this_run(db)

        print()
        print("=" * 70)
        print(f"  Results")
        print("=" * 70)
        print(f"  processed ok    : {ok}")
        print(f"  failed          : {fail}")
        print(f"  skipped (TIER_0): {skip}")
        print(f"  budget hit      : {budget_hit}")
        print(f"  elapsed         : {elapsed:.1f}s")
        print(f"  tokens used     : +{used_after - used_today:,}  (cumul today: {used_after:,})")
        print()

        # How many still stale?
        remaining = db.execute(text("""
            SELECT COUNT(*) FROM interactions
            WHERE org_id = :oid AND source = 'gmail'
              AND COALESCE(processed_version, 1) < :v
        """), {"oid": ORG_ID, "v": PROCESSING_VERSION}).scalar()
        print(f"  rows still stale: {remaining}")
        if remaining and not budget_hit:
            print(f"  → run again to process more")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
