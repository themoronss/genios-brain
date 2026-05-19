"""
HubSpot Sync Task
Fetches all contacts + deals from HubSpot and bridges them into the graph.
Uses stored OAuth tokens from the oauth_tokens table.
Refreshes access token automatically if expired.

Post-bridge: calls recalculate_all_relationships so graph scores (confidence,
relationship stage, edge weights) reflect the new CRM data — same as all other tools.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _get_hubspot_token(db: Session, org_id: str) -> dict | None:
    """Retrieve HubSpot OAuth token row for org. Returns None if not connected."""
    row = db.execute(
        text("""
            SELECT id, access_token, refresh_token, expires_at
            FROM oauth_tokens
            WHERE org_id = :oid
              AND account_email LIKE 'hubspot:%'
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"oid": org_id},
    ).fetchone()
    return row._mapping if row else None


def _ensure_fresh_token(db: Session, token_row: dict) -> str:
    """
    Return a valid access token, refreshing if needed.
    Updates the DB row with new tokens on refresh.
    """
    from app.ingestion.hubspot_connector import refresh_access_token

    expires_at = token_row.get("expires_at")
    now = datetime.now(timezone.utc)

    needs_refresh = (
        not token_row.get("access_token") or
        (expires_at and expires_at.replace(tzinfo=timezone.utc) <= now)
    )

    if not needs_refresh:
        return token_row["access_token"]

    if not token_row.get("refresh_token"):
        raise ValueError("HubSpot refresh token missing — re-connect required")

    refreshed = refresh_access_token(token_row["refresh_token"])
    new_access = refreshed["access_token"]
    new_refresh = refreshed.get("refresh_token", token_row["refresh_token"])
    expires_in = refreshed.get("expires_in", 1800)

    from datetime import timedelta
    new_expiry = now + timedelta(seconds=expires_in)

    db.execute(
        text("""
            UPDATE oauth_tokens
            SET access_token = :at, refresh_token = :rt, expires_at = :exp
            WHERE id = :tid
        """),
        {
            "at": new_access,
            "rt": new_refresh,
            "exp": new_expiry,
            "tid": token_row["id"],
        },
    )
    db.commit()
    return new_access


def run_hubspot_sync(org_id: str):
    """
    Full incremental HubSpot sync for an org.
    1. Load OAuth token
    2. Refresh if expired
    3. Fetch all contacts + deals
    4. Run bridge (upsert into contacts + commitments)
    5. Update last_synced_at
    """
    from app.database import SessionLocal
    from app.ingestion.hubspot_connector import fetch_all_contacts, fetch_all_deals
    from app.ingestion.hubspot_bridge import run_hubspot_bridge

    db = SessionLocal()
    try:
        token_row = _get_hubspot_token(db, org_id)
        if not token_row:
            logger.info(f"HubSpot not connected for org {org_id} — skipping")
            return

        # Mark sync as running
        db.execute(
            text("UPDATE oauth_tokens SET sync_status = 'running' WHERE id = :tid"),
            {"tid": token_row["id"]},
        )
        db.commit()

        try:
            access_token = _ensure_fresh_token(db, token_row)

            logger.info(f"[HubSpot] Fetching contacts for org {org_id}")
            contacts = fetch_all_contacts(access_token)
            logger.info(f"[HubSpot] Fetching deals for org {org_id}")
            deals = fetch_all_deals(access_token)

            # ── Bulk sync credit deduct (HubSpot is batched, not streamed) ──
            # Charge per record fetched. If the org doesn't have enough sync
            # credits for the full batch, we truncate to what they can afford
            # rather than fail the whole sync — partial sync is more useful
            # than zero sync. The bridge upserts in deterministic order so
            # truncation is stable across retries.
            from app.credits import deduct as _credit_deduct, InsufficientCredits as _Ins
            total_records = len(contacts) + len(deals)
            if total_records > 0:
                try:
                    _credit_deduct(
                        db, org_id=org_id, bucket="sync",
                        reason="sync:hubspot_record",
                        units=total_records,
                        idempotency_key=f"sync:hubspot:{org_id}:{int(datetime.now(timezone.utc).timestamp())}",
                        related_kind="interaction",
                    )
                    db.commit()
                except _Ins as e:
                    # Truncate to affordable. e.available is remaining credits.
                    db.rollback()
                    affordable = max(0, e.available)
                    logger.warning(
                        f"[HubSpot] Sync credits short: have {e.available}, need {total_records}. "
                        f"Truncating to {affordable} records."
                    )
                    # Split: prioritise contacts (more useful), then deals.
                    if affordable >= len(contacts):
                        deals = deals[: affordable - len(contacts)]
                    else:
                        contacts = contacts[:affordable]
                        deals = []
                    if affordable > 0:
                        try:
                            _credit_deduct(
                                db, org_id=org_id, bucket="sync",
                                reason="sync:hubspot_record",
                                units=affordable,
                                idempotency_key=f"sync:hubspot:{org_id}:trunc:{int(datetime.now(timezone.utc).timestamp())}",
                            )
                            db.commit()
                        except Exception:
                            db.rollback()

            logger.info(
                f"[HubSpot] Running bridge: {len(contacts)} contacts, {len(deals)} deals for org {org_id}"
            )
            summary = run_hubspot_bridge(db, org_id, contacts, deals)

            # Mark sync complete
            db.execute(
                text("""
                    UPDATE oauth_tokens
                    SET sync_status = 'completed',
                        last_synced_at = NOW(),
                        sync_total = :total,
                        sync_processed = :processed,
                        sync_error = NULL
                    WHERE id = :tid
                """),
                {
                    "tid": token_row["id"],
                    "total": len(contacts) + len(deals),
                    "processed": summary["contacts_upserted"] + summary["deals_upserted"],
                },
            )
            db.commit()

            # ── Phase 2: Recalculate relationship graph (same as Gmail/Slack/Jira) ──
            if summary["contacts_upserted"] > 0:
                try:
                    from app.graph.relationship_calculator import recalculate_all_relationships
                    updated = recalculate_all_relationships(db, org_id)
                    logger.info(f"[HubSpot] Graph recalculated: {updated} contacts updated for org {org_id}")
                except Exception as graph_err:
                    logger.warning(f"[HubSpot] Graph recalc failed (non-critical): {graph_err}")

            # Log sync activity
            try:
                db.execute(
                    text("""
                        INSERT INTO activity_log (id, org_id, event_type, event_data, created_at)
                        VALUES (:id, :org_id, 'hubspot_sync_complete', :data, NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "org_id": org_id,
                        "data": (
                            f"HubSpot sync: {summary['contacts_upserted']} contacts, "
                            f"{summary['deals_upserted']} deals"
                        ),
                    },
                )
                db.commit()
            except Exception:
                pass

            logger.info(
                f"[HubSpot] Sync complete for org {org_id}: "
                f"{summary['contacts_upserted']} contacts, {summary['deals_upserted']} deals"
            )

        except Exception as e:
            logger.error(f"[HubSpot] Sync failed for org {org_id}: {e}")
            try:
                db.execute(
                    text("""
                        UPDATE oauth_tokens
                        SET sync_status = 'error', sync_error = :err
                        WHERE id = :tid
                    """),
                    {"err": str(e)[:500], "tid": token_row["id"]},
                )
                db.commit()
            except Exception:
                pass
            raise

    finally:
        db.close()
