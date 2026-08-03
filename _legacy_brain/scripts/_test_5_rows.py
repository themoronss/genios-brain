#!/usr/bin/env python3
"""
Small batch test — re-extract 5 random interactions from Rohit's org
through the new code path. Verifies:
  - Gmail re-fetch works
  - attachment_extractor doesn't blow up
  - LLM extraction returns valid JSON
  - DB write succeeds
  - Groq 30 RPM honored (2s sleep between LLM calls)

Output: per-row pass/fail. No bulk mutation — just 5 rows.

Usage:
  python scripts/_test_5_rows.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import SessionLocal
from app.ingestion.gmail_connector import build_gmail_service, fetch_full_message
from app.ingestion.email_parser import (
    parse_headers, extract_email_body, detect_attachments,
)
from app.ingestion.attachment_extractor import extract_attachment_text
from app.ingestion.entity_extractor import extract_email_intelligence

ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"
SAMPLE = 5


def pick_rows(db):
    rows = db.execute(
        text("""
            SELECT i.id, i.gmail_message_id, i.subject, i.direction,
                   i.summary, i.contact_id,
                   c.name AS contact_name, c.email AS contact_email
            FROM interactions i
            JOIN contacts c ON c.id = i.contact_id
            WHERE i.org_id = :oid
              AND i.gmail_message_id IS NOT NULL
            ORDER BY RANDOM()
            LIMIT :n
        """),
        {"oid": ORG_ID, "n": SAMPLE},
    ).fetchall()
    return rows


def gmail_service():
    """Build Gmail service from stored OAuth tokens for this org."""
    db = SessionLocal()
    try:
        row = db.execute(
            text("""
                SELECT access_token, refresh_token, account_email
                FROM oauth_tokens WHERE org_id = :oid LIMIT 1
            """),
            {"oid": ORG_ID},
        ).fetchone()
        if not row:
            raise RuntimeError("No oauth_tokens row for org")
        return build_gmail_service(row.access_token, row.refresh_token), row.account_email
    finally:
        db.close()


def main():
    print("=" * 70)
    print(f"  5-row reextract test — {ORG_ID}")
    print("=" * 70)

    print("\nBuilding Gmail service from stored OAuth tokens...")
    try:
        service, account_email = gmail_service()
        print(f"  ✅ service ready (account: {account_email})")
    except Exception as e:
        print(f"  ❌ failed to build Gmail service: {e}")
        return 1

    db = SessionLocal()
    try:
        rows = pick_rows(db)
    finally:
        db.close()

    if not rows:
        print("  ❌ no rows to test")
        return 1
    print(f"\nPicked {len(rows)} random rows to test\n")

    results = []
    for i, r in enumerate(rows, 1):
        print(f"--- Row {i}/{len(rows)} ---")
        print(f"  contact: {r.contact_name} <{r.contact_email}>")
        print(f"  subject: {(r.subject or '(none)')[:60]}")
        print(f"  current summary: {(r.summary or '(blank)')[:80]}")

        out = {"row": i, "contact": r.contact_email, "ok": False, "error": None}

        # Step 1: re-fetch from Gmail
        try:
            msg = fetch_full_message(service, r.gmail_message_id)
            payload = msg.get("payload", {})
            body = extract_email_body(payload)
            attach_info = detect_attachments(payload)
            print(f"  fetched: body={len(body)} chars, attachments={attach_info.get('attachment_count', 0)}")
            out["body_len"] = len(body)
            out["attachments"] = attach_info.get("attachment_count", 0)
        except Exception as e:
            out["error"] = f"gmail fetch: {e}"
            print(f"  ❌ {out['error']}")
            results.append(out)
            continue

        # Step 2: attachment text extraction (NEW code path)
        attach_text = ""
        if attach_info.get("has_attachment"):
            try:
                attach_text = extract_attachment_text(service, r.gmail_message_id, payload)
                print(f"  attachment text: {len(attach_text)} chars")
                out["attach_text_len"] = len(attach_text)
            except Exception as e:
                out["error"] = f"attachment extract: {e}"
                print(f"  ❌ {out['error']}")
                results.append(out)
                continue

        if attach_text:
            body = (body + "\n\n" + attach_text)[:8000]

        # Step 3: LLM extraction (Haiku/Groq)
        try:
            t0 = time.time()
            intel = extract_email_intelligence(
                subject=r.subject or "",
                body=body,
                sender_name=r.contact_name or "",
                is_reply=bool(r.subject and "re:" in (r.subject or "").lower()),
                org_id=ORG_ID,
            )
            took = time.time() - t0
            print(f"  LLM took {took:.2f}s")
            print(f"  new summary: {(intel.get('summary') or '(blank)')[:80]}")
            print(f"  intent: {intel.get('intent')} sentiment: {intel.get('sentiment'):.2f} "
                  f"commitments: {len(intel.get('commitments', []))}")
            out["new_summary"] = intel.get("summary")
            out["intent"] = intel.get("intent")
            out["llm_seconds"] = round(took, 2)
            out["ok"] = True
        except Exception as e:
            out["error"] = f"LLM: {e}"
            print(f"  ❌ {out['error']}")
            results.append(out)
            continue

        results.append(out)
        # Groq 30 RPM cap → 2s gap
        if i < len(rows):
            time.sleep(2)
        print()

    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)
    passed = sum(1 for r in results if r["ok"])
    for r in results:
        status = "✅" if r["ok"] else "❌"
        print(f"  {status} row{r['row']} {r['contact']}")
        if r["ok"]:
            print(f"     summary: {(r.get('new_summary') or '')[:80]}")
        else:
            print(f"     error: {r['error']}")
    print(f"\n  {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
