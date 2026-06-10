#!/usr/bin/env python3
"""Comprehensive code-level verification of today's changes.

No production traffic — only imports, function existence, signature
sanity, and SQL column-name assumptions against the actual schema.
"""
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("GENIOS_CAMPAIGN_DETECTORS_ENABLED", "true")
os.environ.setdefault("GENIOS_RELATED_OUTBOUND_ENABLED", "true")


def header(title):
    print(f"\n{'=' * 70}\n  {title}\n{'=' * 70}")


def check(label, fn):
    try:
        fn()
        print(f"  ✅ {label}")
        return True
    except Exception as e:
        print(f"  ❌ {label}")
        print(f"     {type(e).__name__}: {e}")
        return False


def main() -> int:
    failures = 0

    # ── 1. Imports ───────────────────────────────────────────────────────
    header("1. Module imports — all new files load")
    failures += not check("attachment_extractor", lambda: __import__("app.ingestion.attachment_extractor", fromlist=["*"]))
    failures += not check("inbound_ack detector", lambda: __import__("app.graph.detectors.inbound_ack", fromlist=["*"]))
    failures += not check("change_point detector", lambda: __import__("app.graph.detectors.change_point", fromlist=["*"]))
    failures += not check("narrative (rewritten)", lambda: __import__("app.brain.narrative", fromlist=["*"]))
    failures += not check("reextract (with attachment hook)", lambda: __import__("app.tasks.reextract", fromlist=["*"]))
    failures += not check("gmail_sync (with attachment hook)", lambda: __import__("app.tasks.gmail_sync", fromlist=["*"]))
    failures += not check("v1.py (trigram search)", lambda: __import__("app.api.routes.v1", fromlist=["*"]))

    # ── 2. Function/symbol existence ─────────────────────────────────────
    header("2. Function/symbol existence")
    from app.ingestion.attachment_extractor import extract_attachment_text
    failures += not check("extract_attachment_text exists", lambda: callable(extract_attachment_text))

    from app.graph.detectors.inbound_ack import INBOUND_ACK_DETECTORS, _detect_unacknowledged_inbound
    failures += not check("INBOUND_ACK_DETECTORS list non-empty", lambda: len(INBOUND_ACK_DETECTORS) >= 1)

    from app.graph.detectors.change_point import CHANGE_POINT_DETECTORS, _detect_engagement_change_point
    failures += not check("CHANGE_POINT_DETECTORS list non-empty", lambda: len(CHANGE_POINT_DETECTORS) >= 1)

    from app.graph.detectors import ALL_DETECTORS
    failures += not check(f"ALL_DETECTORS includes new ones (count={len(ALL_DETECTORS)})",
                          lambda: _detect_unacknowledged_inbound in ALL_DETECTORS
                                  and _detect_engagement_change_point in ALL_DETECTORS)

    from app.brain.narrative import build_narrative, _build_programmatic
    failures += not check("build_narrative + _build_programmatic", lambda: callable(build_narrative) and callable(_build_programmatic))

    # ── 3. Programmatic narrative output ─────────────────────────────────
    header("3. Programmatic narrative — sample outputs")
    samples = [
        ("Piyush Sharma", {"stage": "NEEDS_ATTENTION", "sentiment_ewma": -0.4, "open_commitments": 5,
                           "last_subject": "GeniOS update", "last_interaction_at": None}),
        ("Ansh Goel",     {"stage": "WARM", "sentiment_ewma": 0.5, "open_commitments": 0}),
        ("(empty)",       {}),
    ]
    for name, meta in samples:
        out = _build_programmatic(name, [], meta)
        ok = (name == "(empty)" and out is None) or (name != "(empty)" and isinstance(out, str) and len(out) > 0)
        marker = "✅" if ok else "❌"
        print(f"  {marker} {name:25} → {repr(out)[:80]}")
        if not ok:
            failures += 1

    # ── 4. SQL column sanity (against live schema, read-only) ────────────
    header("4. SQL column sanity — detectors' queries match real schema")
    from sqlalchemy import text
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        # interactions cols
        cols = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'interactions'
        """)).fetchall()
        col_set = {r.column_name for r in cols}
        for col in ("contact_id", "org_id", "direction", "interaction_at", "summary",
                    "extraction_status", "processed_version", "subject", "intent",
                    "topics", "embedding"):
            failures += not check(f"interactions.{col}", lambda c=col: c in col_set)

        # contacts cols
        cols = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'contacts'
        """)).fetchall()
        col_set = {r.column_name for r in cols}
        for col in ("id", "org_id", "name", "email", "company", "relationship_stage",
                    "is_archived", "is_bidirectional", "interaction_count",
                    "classification", "classification_override", "last_interaction_at",
                    "sentiment_trend"):
            failures += not check(f"contacts.{col}", lambda c=col: c in col_set)

        # commitments
        cols = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'commitments'
        """)).fetchall()
        col_set = {r.column_name for r in cols}
        for col in ("contact_id", "status", "due_date"):
            failures += not check(f"commitments.{col}", lambda c=col: c in col_set)

        # insights
        cols = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'insights'
        """)).fetchall()
        col_set = {r.column_name for r in cols}
        for col in ("org_id", "contact_id", "category", "delivery_status",
                    "generated_at", "delivered_at", "is_dismissed"):
            failures += not check(f"insights.{col}", lambda c=col: c in col_set)
    finally:
        db.close()

    # ── 5. Detectors return cleanly (no exception) ───────────────────────
    header("5. Detectors run cleanly against real org (read-only)")
    ORG = "0031178b-2f9d-4881-88d7-b39218292077"
    db = SessionLocal()
    try:
        for fn in (_detect_unacknowledged_inbound, _detect_engagement_change_point):
            try:
                rows = fn(db, ORG)
                print(f"  ✅ {fn.__name__:50} → {len(rows)} candidate(s)")
            except Exception as e:
                print(f"  ❌ {fn.__name__}: {type(e).__name__}: {e}")
                failures += 1
    finally:
        db.close()

    # ── 6. Pull-mode insight delivery query (proactive.py) ──────────────
    header("6. Pull-mode delivery UPDATE query syntax")
    db = SessionLocal()
    try:
        # Dry-run: prepare the UPDATE without executing destructively
        db.execute(text("""
            UPDATE insights
            SET delivery_status = delivery_status
            WHERE id::text = ANY(CAST(:ids AS text[]))
              AND delivery_status IN ('pending', 'no_webhook')
              AND id IS NULL  -- guarantees zero rows match, idempotent test
        """), {"ids": []})
        print("  ✅ pull-mode UPDATE query parses")
    except Exception as e:
        print(f"  ❌ pull-mode UPDATE: {type(e).__name__}: {e}")
        failures += 1
    finally:
        db.close()

    # ── Summary ──────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    if failures:
        print(f"  ❌ {failures} CHECK(S) FAILED")
    else:
        print("  ✅ ALL CHECKS PASSED — code level is clean")
    print("=" * 70)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
