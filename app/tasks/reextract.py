"""
Re-extraction Pipeline
──────────────────────
Re-runs LLM extraction on existing interactions without deleting data.
Two tiers:
  Tier 1 (recompute): Rebuild scores/stages/graph from stored interactions. No LLM calls.
  Tier 2 (reextract): Re-fetch email bodies from Gmail, re-run LLM extraction, then recompute.

Idempotency: ON CONFLICT (gmail_message_id, contact_id) DO UPDATE handles dedup.
Batching: Processes BATCH_SIZE interactions per commit to avoid long transactions.
Versioning: Only reprocesses rows where processed_version < PROCESSING_VERSION.
"""

import time
import json
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import text

from app.database import SessionLocal
from app.config import PROCESSING_VERSION
from app.ingestion.gmail_connector import build_gmail_service, fetch_full_message, get_user_email
from app.ingestion.email_parser import parse_headers, extract_email_body, detect_attachments
from app.ingestion.attachment_extractor import extract_attachment_text
from app.ingestion.email_classifier import classify_email
from app.ingestion.entity_extractor import extract_email_intelligence
from app.ingestion.graph_builder import (
    upsert_contact,
    create_interaction,
    _calculate_interaction_weight,
)
from app.tasks.gmail_sync import (
    build_thread_context,
    quick_sentiment_heuristic,
    is_automated_email,
    is_internal_email,
)
from app.graph.relationship_calculator import recalculate_all_relationships


BATCH_SIZE = 50


def _update_recompute_status(db, org_id: str, **kwargs):
    """Update recompute job status. Tries dedicated columns, silently skips if not migrated."""
    try:
        set_parts = []
        params = {"org_id": org_id}
        for key, value in kwargs.items():
            set_parts.append(f"recompute_{key} = :recompute_{key}")
            params[f"recompute_{key}"] = value if not isinstance(value, datetime) else value.isoformat()
        if set_parts:
            db.execute(
                text(f"UPDATE orgs SET {', '.join(set_parts)} WHERE id = :org_id"),
                params,
            )
            db.commit()
    except Exception:
        db.rollback()  # Columns don't exist yet — skip silently


# ── Tier 1: Recompute (no LLM, no API calls) ────────────────────────────────


def run_recompute(org_id: str):
    """
    Tier 1: Rebuild all scores, stages, and graph from existing interaction data.
    This is the nightly_refresh pipeline triggered on demand.
    Safe to run anytime — no external calls, purely recalculation.
    """
    db = SessionLocal()
    try:
        _update_recompute_status(db, org_id, status="running",
                                 started_at=datetime.now(timezone.utc))

        from app.tasks.nightly_refresh import run_nightly_refresh
        run_nightly_refresh(org_id)

        _update_recompute_status(db, org_id, status="completed",
                                 completed_at=datetime.now(timezone.utc),
                                 error=None)
        print(f"✅ Recompute completed for org {org_id}")
    except Exception as e:
        _update_recompute_status(db, org_id, status="error", error=str(e)[:500])
        print(f"❌ Recompute failed for org {org_id}: {e}")
        raise
    finally:
        db.close()


# ── Tier 2: Re-extract with LLM ─────────────────────────────────────────────


def run_reextract(org_id: str, batch_size: int = BATCH_SIZE):
    """
    Tier 2: Re-fetch email bodies from Gmail API, re-run LLM extraction,
    update interactions via ON CONFLICT, then trigger Tier 1 recompute.

    Only processes interactions where processed_version < PROCESSING_VERSION.
    """
    db = SessionLocal()
    try:
        _update_recompute_status(
            db, org_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            progress=json.dumps({"tier": 2, "phase": "counting"}),
        )

        # Count stale interactions
        total_stale = db.execute(
            text("""
                SELECT COUNT(*) FROM interactions
                WHERE org_id = :org_id
                  AND source = 'gmail'
                  AND COALESCE(processed_version, 1) < :target_version
            """),
            {"org_id": org_id, "target_version": PROCESSING_VERSION},
        ).scalar()

        if total_stale == 0:
            print(f"✅ All interactions already at version {PROCESSING_VERSION}. Running recompute only.")
            _update_recompute_status(db, org_id, status="completed",
                                     completed_at=datetime.now(timezone.utc))
            db.close()
            run_recompute(org_id)
            return

        print(f"🔄 Re-extracting {total_stale} stale interactions for org {org_id}")

        # Get Gmail service credentials
        tokens = db.execute(
            text("""
                SELECT access_token, refresh_token,
                       COALESCE(account_email, 'default') AS account_email
                FROM oauth_tokens
                WHERE org_id = :org_id
            """),
            {"org_id": org_id},
        ).fetchall()

        if not tokens:
            raise ValueError("No Gmail tokens found for org")

        # Build services per account
        services = {}
        user_emails = {}
        for token_row in tokens:
            try:
                svc = build_gmail_service(token_row[0], token_row[1])
                email = get_user_email(svc)
                services[token_row[2]] = svc
                user_emails[token_row[2]] = email
            except Exception as e:
                print(f"⚠️ Could not build service for {token_row[2]}: {e}")

        if not services:
            raise ValueError("No valid Gmail services could be built")

        # Pick a default service for fallback
        default_account = list(services.keys())[0]

        processed = 0
        failed = 0
        skipped = 0

        while processed + failed + skipped < total_stale:
            # Fetch a batch of stale interactions
            batch = db.execute(
                text("""
                    SELECT i.id, i.gmail_message_id, i.subject, i.contact_id,
                           i.direction, i.interaction_at, i.account_email,
                           c.email AS contact_email, c.name AS contact_name
                    FROM interactions i
                    JOIN contacts c ON c.id = i.contact_id
                    WHERE i.org_id = :org_id
                      AND i.source = 'gmail'
                      AND COALESCE(i.processed_version, 1) < :target_version
                    ORDER BY i.interaction_at DESC
                    LIMIT :batch_size
                """),
                {
                    "org_id": org_id,
                    "target_version": PROCESSING_VERSION,
                    "batch_size": batch_size,
                },
            ).fetchall()

            if not batch:
                break

            for row in batch:
                interaction_id = str(row[0])
                gmail_id = row[1]
                subject = row[2]
                contact_id = str(row[3])
                direction = row[4]
                interaction_at = row[5]
                account_email = row[6] or default_account
                contact_email = row[7]
                contact_name = row[8]

                # Pick the right Gmail service
                service = services.get(account_email, services[default_account])
                user_email = user_emails.get(account_email, user_emails[default_account])

                try:
                    # Re-fetch full message from Gmail
                    msg = fetch_full_message(service, gmail_id)
                    payload = msg.get("payload", {})
                    body_text = extract_email_body(payload)
                    attachment_info = detect_attachments(payload)

                    # Phase 2 Task 2.1 — pull attachment text on reextract too,
                    # not just on fresh Gmail sync. Old messages with PDFs/DOCX
                    # attachments need this re-run pass to surface their content.
                    if attachment_info.get("has_attachment"):
                        try:
                            attach_text = extract_attachment_text(service, gmail_id, payload)
                            if attach_text:
                                body_text = (body_text + "\n\n" + attach_text)[:8000]
                        except Exception as _ae:
                            # Fail-soft — never block reextract on attachment errors
                            print(f"  ⚠ attachment extract failed for {gmail_id}: {_ae}")

                    # Classify
                    headers = {
                        h["name"]: h["value"]
                        for h in payload.get("headers", [])
                    }
                    category = classify_email(
                        subject=subject or "",
                        sender_email=contact_email or "",
                        body=body_text or "",
                        headers=headers,
                    )

                    if category == "TIER_0":
                        # Mark as processed so we don't re-visit
                        db.execute(
                            text("UPDATE interactions SET processed_version = :v WHERE id = :id"),
                            {"v": PROCESSING_VERSION, "id": interaction_id},
                        )
                        skipped += 1
                        continue

                    if category == "TIER_1":
                        heuristic = quick_sentiment_heuristic(body_text or "")
                        weight = _calculate_interaction_weight(
                            "email_reply" if direction == "inbound" else "email_one_way",
                            "low", heuristic * 0.3, direction,
                        )
                        db.execute(
                            text("""
                                UPDATE interactions SET
                                    sentiment = :sentiment,
                                    weight_score = :weight,
                                    signal_score = 0.1,
                                    engagement_level = 'low',
                                    processed_version = :v
                                WHERE id = :id
                            """),
                            {
                                "sentiment": heuristic * 0.3,
                                "weight": weight,
                                "v": PROCESSING_VERSION,
                                "id": interaction_id,
                            },
                        )
                        processed += 1
                        continue

                    if category == "SYSTEM":
                        db.execute(
                            text("UPDATE interactions SET processed_version = :v WHERE id = :id"),
                            {"v": PROCESSING_VERSION, "id": interaction_id},
                        )
                        skipped += 1
                        continue

                    # STRONG: Full LLM re-extraction
                    intelligence = extract_email_intelligence(
                        subject,
                        body_text,
                        sender_name=contact_name,
                        is_reply=bool(subject and "re:" in subject.lower()),
                        thread_context="",  # Thread context not stored; accept minor quality loss
                        org_id=org_id,
                    )

                    signal = None  # Signal computed at query time only (CLM spec)
                    weight = _calculate_interaction_weight(
                        intelligence.get("interaction_type", "email_one_way"),
                        intelligence.get("engagement_level", "medium"),
                        intelligence.get("sentiment", 0.0),
                        direction,
                    )

                    # Build comm_style_signals
                    comm_style = None
                    if intelligence.get("what_works") or intelligence.get("what_to_avoid"):
                        comm_style = json.dumps({
                            "what_works": intelligence.get("what_works"),
                            "what_to_avoid": intelligence.get("what_to_avoid"),
                        })

                    # Update interaction in-place (no duplication — keyed by id)
                    db.execute(
                        text("""
                            UPDATE interactions SET
                                summary = :summary,
                                sentiment = :sentiment,
                                intent = :intent,
                                interaction_type = :interaction_type,
                                weight_score = :weight_score,
                                signal_score = :signal_score,
                                topics = :topics,
                                mentioned_people = :mentioned_people,
                                comm_style_signals = :comm_style,
                                has_attachment = :has_attachment,
                                processed_version = :version
                            WHERE id = :id
                        """),
                        {
                            "summary": intelligence.get("summary", ""),
                            "sentiment": intelligence.get("sentiment", 0.0),
                            "intent": intelligence.get("intent", "other"),
                            "interaction_type": intelligence.get("interaction_type", "email_one_way"),
                            "weight_score": weight,
                            "signal_score": signal,
                            "topics": intelligence.get("topics", []),
                            "mentioned_people": intelligence.get("mentioned_people", []),
                            "comm_style": comm_style,
                            "has_attachment": attachment_info.get("has_attachment", False),
                            "version": PROCESSING_VERSION,
                            "id": interaction_id,
                        },
                    )

                    # Update contact entity_type if LLM found a better role
                    contact_role = intelligence.get("contact_role")
                    if contact_role and contact_role != "other":
                        upsert_contact(
                            db, org_id, contact_email, contact_name,
                            entity_type=contact_role,
                            thread_topics=intelligence.get("topics", []),
                            email_body=body_text or "",
                        )

                    processed += 1

                    # Rate limit: Groq allows ~30 req/min
                    time.sleep(2)

                except Exception as e:
                    # Mark as processed to avoid infinite retry loop
                    db.execute(
                        text("UPDATE interactions SET processed_version = :v WHERE id = :id"),
                        {"v": PROCESSING_VERSION, "id": interaction_id},
                    )
                    failed += 1
                    print(f"  ⚠️ Failed to re-extract {gmail_id}: {e}")

            # Commit after each batch
            db.commit()

            _update_recompute_status(
                db, org_id,
                progress=json.dumps({
                    "tier": 2,
                    "phase": "extracting",
                    "processed": processed,
                    "failed": failed,
                    "skipped": skipped,
                    "total": total_stale,
                }),
            )

            print(f"  📦 Batch done: {processed} processed, {failed} failed, {skipped} skipped / {total_stale} total")

        db.commit()
        print(f"✅ Re-extraction done: {processed} processed, {failed} failed, {skipped} skipped")

        # Tier 1: Recompute all scores from updated interactions
        _update_recompute_status(
            db, org_id,
            progress=json.dumps({"tier": 1, "phase": "recomputing"}),
        )
        db.close()

        run_recompute(org_id)

    except Exception as e:
        try:
            _update_recompute_status(db, org_id, status="error", error=str(e)[:500])
        except Exception:
            pass
        print(f"❌ Re-extraction failed for org {org_id}: {e}")
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass
