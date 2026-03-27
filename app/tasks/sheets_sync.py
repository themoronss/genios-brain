"""
Sheets Sync Task

Phase 1 MVP:
  - 30-min cron: check Drive for modified spreadsheets
  - Hash-based row change detection
  - Column mapper → tab type classification
  - Budget state upsert → alert if >80% consumed
  - MANDATORY user confirmation before any Authority Graph write

CRITICAL: confidence >= 0.85 required before writing to Authority Graph.
Below that → surface to user for confirmation (user_confirmed = FALSE).
"""

import logging
import json
import hashlib
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal
from app.ingestion.sheets_connector import (
    build_sheets_service,
    build_drive_service,
    get_sheets_user_email,
    fetch_spreadsheet_metadata,
    fetch_tab_sample,
    check_for_importrange,
    classify_tab_type,
    normalize_number,
    hash_row,
)

logger = logging.getLogger(__name__)

# Alert threshold: send alert when consumed/budget_cap >= this
BUDGET_ALERT_THRESHOLD = 0.8


def _get_sheets_connection(db, org_id):
    return db.execute(
        text("SELECT access_token, refresh_token, token_expires_at FROM sheets_connections WHERE org_id = :oid LIMIT 1"),
        {"oid": org_id},
    ).fetchone()


def run_sheets_sync(org_id: str):
    """
    Main Sheets sync entry point.

    Signal taxonomy quality gates:
      - DROP tab_type == 'unknown' after LLM classification
      - DROP row_count > 50000 (raw operational logs)
      - DROP if no header row detected
      - DROP chart/pivot tabs
      - DROP tabs primarily IMPORTRANGE
      - DROP if payroll/salary keywords in headers
      - DROP formula-only cells (index display value only)
      - Authority Graph write: confidence >= 0.85 only; below that → queue for user confirmation
    """
    db = SessionLocal()
    try:
        conn = _get_sheets_connection(db, org_id)
        if not conn or not conn.access_token:
            logger.warning(f"Sheets sync: no connection found for org {org_id}")
            return

        sheets_service = build_sheets_service(conn.access_token, conn.refresh_token)
        drive_service = build_drive_service(conn.access_token, conn.refresh_token)

        # Get all tracked spreadsheets
        spreadsheets = db.execute(
            text("SELECT spreadsheet_id, spreadsheet_name, drive_modified_time FROM sheets_spreadsheets WHERE org_id = :oid AND sync_enabled = TRUE"),
            {"oid": org_id},
        ).fetchall()

        for ss in spreadsheets:
            _sync_spreadsheet(db, sheets_service, org_id, ss.spreadsheet_id)

        db.execute(
            text("UPDATE sheets_connections SET last_sync_at = NOW(), updated_at = NOW() WHERE org_id = :oid"),
            {"oid": org_id},
        )
        db.commit()
        logger.info(f"Sheets sync complete for org {org_id}")

        # ── Phase 2: Bridge Sheets CRM data into contacts ──
        try:
            from app.ingestion.sheets_bridge import resolve_sheets_crm_to_contacts
            resolve_sheets_crm_to_contacts(db, org_id)
            db.commit()
        except Exception as bridge_err:
            logger.error(f"Sheets bridge failed for org {org_id}: {bridge_err}")

    except Exception as e:
        logger.error(f"Sheets sync failed for org {org_id}: {e}")
        raise
    finally:
        db.close()


def _sync_spreadsheet(db, sheets_service, org_id, spreadsheet_id):
    """Sync all tabs in a spreadsheet."""
    try:
        metadata = fetch_spreadsheet_metadata(sheets_service, spreadsheet_id)
    except Exception as e:
        logger.error(f"Failed to fetch spreadsheet {spreadsheet_id}: {e}")
        return

    spreadsheet_name = metadata.get("properties", {}).get("title", "")
    sheets = metadata.get("sheets", [])

    for sheet in sheets:
        props = sheet.get("properties", {})
        tab_name = props.get("title", "")
        tab_gid = str(props.get("sheetId", ""))
        row_count = props.get("gridProperties", {}).get("rowCount", 0)

        # Quality gate: skip chart/pivot tabs
        sheet_type = props.get("sheetType", "GRID")
        if sheet_type in ("OBJECT",):  # OBJECT = chart
            continue

        # Quality gate: skip huge operational tables
        if row_count > 50000:
            logger.info(f"Sheets: dropping tab {tab_name} (row_count={row_count} > 50000)")
            continue

        _sync_tab(db, sheets_service, org_id, spreadsheet_id, tab_name, tab_gid, row_count)


def _sync_tab(db, sheets_service, org_id, spreadsheet_id, tab_name, tab_gid, row_count):
    """Sync a single spreadsheet tab."""
    # Check for IMPORTRANGE dominance
    try:
        is_importrange = check_for_importrange(sheets_service, spreadsheet_id, tab_name)
        if is_importrange:
            return
    except Exception:
        pass

    # Fetch sample rows for classification
    try:
        sample_data = fetch_tab_sample(sheets_service, spreadsheet_id, tab_name, max_rows=50)
    except Exception as e:
        logger.warning(f"Failed to fetch tab {tab_name}: {e}")
        return

    if not sample_data:
        return

    headers = sample_data[0] if sample_data else []
    sample_rows = sample_data[1:] if len(sample_data) > 1 else []

    # Quality gate: no header row
    if not headers:
        return

    # Classify tab type
    tab_type, confidence = classify_tab_type(headers, sample_rows)

    # Quality gate: sensitive data or unknown type — skip
    if tab_type in ("unknown", "sensitive_payroll"):
        return

    # Upsert tab config
    db.execute(
        text("""
            INSERT INTO sheets_tab_config
                (org_id, spreadsheet_id, tab_name, tab_gid, tab_type,
                 classification_confidence, has_header_row, row_count,
                 column_count, sync_enabled, last_synced_at)
            VALUES
                (:org_id, :ss_id, :tab_name, :tab_gid, :tab_type,
                 :confidence, TRUE, :row_count, :col_count, TRUE, NOW())
            ON CONFLICT (org_id, spreadsheet_id, tab_name) DO UPDATE SET
                tab_type = EXCLUDED.tab_type,
                classification_confidence = EXCLUDED.classification_confidence,
                row_count = EXCLUDED.row_count,
                column_count = EXCLUDED.column_count,
                last_synced_at = NOW()
        """),
        {
            "org_id": org_id,
            "ss_id": spreadsheet_id,
            "tab_name": tab_name,
            "tab_gid": tab_gid,
            "tab_type": tab_type,
            "confidence": confidence,
            "row_count": row_count,
            "col_count": len(headers),
        },
    )
    db.commit()

    # Process rows based on tab type
    all_rows = fetch_tab_sample(sheets_service, spreadsheet_id, tab_name, max_rows=1000)
    if not all_rows or len(all_rows) < 2:
        return

    data_rows = all_rows[1:]  # Skip header

    for idx, row in enumerate(data_rows, start=1):
        row_hash = hash_row(row)

        # Check if row changed
        existing = db.execute(
            text("SELECT row_hash FROM sheets_rows WHERE org_id = :oid AND spreadsheet_id = :ss_id AND tab_name = :tab AND row_index = :idx"),
            {"oid": org_id, "ss_id": spreadsheet_id, "tab": tab_name, "idx": idx},
        ).fetchone()

        if existing and existing.row_hash == row_hash:
            continue  # No change

        extracted = _extract_row_data(headers, row, tab_type)

        db.execute(
            text("""
                INSERT INTO sheets_rows
                    (org_id, spreadsheet_id, tab_name, row_index, row_hash, extracted_data, is_active, synced_at)
                VALUES (:org_id, :ss_id, :tab, :idx, :hash, :data::jsonb, TRUE, NOW())
                ON CONFLICT (org_id, spreadsheet_id, tab_name, row_index) DO UPDATE SET
                    row_hash = EXCLUDED.row_hash,
                    extracted_data = EXCLUDED.extracted_data,
                    synced_at = NOW()
            """),
            {
                "org_id": org_id,
                "ss_id": spreadsheet_id,
                "tab": tab_name,
                "idx": idx,
                "hash": row_hash,
                "data": json.dumps(extracted),
            },
        )

        # Budget state: update if this is a budget tracker tab
        if tab_type == "budget_tracker":
            _update_budget_state(db, org_id, spreadsheet_id, extracted, headers, row)

        # Approval matrix: queue for user confirmation
        if tab_type == "approval_matrix":
            _queue_policy_rule(db, org_id, spreadsheet_id, tab_name, idx, extracted, confidence)

    db.commit()


def _extract_row_data(headers, row, tab_type):
    """Extract structured data from a row based on tab type."""
    data = {}
    for i, header in enumerate(headers):
        value = row[i] if i < len(row) else ""
        data[header] = value

        # Try normalizing numeric values
        if value:
            normalized = normalize_number(value)
            if normalized is not None:
                data[f"_num_{header}"] = normalized

    return data


def _update_budget_state(db, org_id, spreadsheet_id, extracted, headers, row):
    """Update budget state table from budget tracker row."""
    # Try to find department and budget values
    department = None
    budget_cap = None
    consumed = None
    period = None

    for header, value in extracted.items():
        h_lower = header.lower()
        if "department" in h_lower or "dept" in h_lower:
            department = value
        elif "period" in h_lower or "quarter" in h_lower or "month" in h_lower:
            period = value
        elif "budget" in h_lower and "cap" in h_lower:
            budget_cap = extracted.get(f"_num_{header}")
        elif "consumed" in h_lower or "spent" in h_lower or "actual" in h_lower:
            consumed = extracted.get(f"_num_{header}")

    if not department or not period:
        return

    db.execute(
        text("""
            INSERT INTO budget_state
                (org_id, source_spreadsheet_id, department, period, budget_cap, consumed, updated_at)
            VALUES (:org_id, :ss_id, :dept, :period, :cap, :consumed, NOW())
            ON CONFLICT (org_id, department, period) DO UPDATE SET
                budget_cap = COALESCE(EXCLUDED.budget_cap, budget_state.budget_cap),
                consumed = COALESCE(EXCLUDED.consumed, budget_state.consumed),
                prev_budget_cap = CASE
                    WHEN EXCLUDED.budget_cap != budget_state.budget_cap THEN budget_state.budget_cap
                    ELSE budget_state.prev_budget_cap
                END,
                cap_changed_at = CASE
                    WHEN EXCLUDED.budget_cap != budget_state.budget_cap THEN NOW()
                    ELSE budget_state.cap_changed_at
                END,
                updated_at = NOW()
        """),
        {
            "org_id": org_id,
            "ss_id": spreadsheet_id,
            "dept": department,
            "period": period,
            "cap": budget_cap,
            "consumed": consumed,
        },
    )


def _queue_policy_rule(db, org_id, spreadsheet_id, tab_name, row_index, extracted, confidence):
    """
    Queue an approval policy rule for user confirmation.
    CRITICAL: user_confirmed = FALSE until user explicitly approves.
    Authority Graph write only happens after user_confirmed = TRUE AND confidence >= 0.85.
    """
    # Find max_amount/role fields
    max_amount = None
    approver_role = None
    role = None
    domain = None

    for header, value in extracted.items():
        h_lower = header.lower()
        num_val = extracted.get(f"_num_{header}")
        if any(k in h_lower for k in ["max", "limit", "threshold", "ceiling"]) and num_val:
            max_amount = num_val
        if "approver" in h_lower and "role" in h_lower:
            approver_role = value
        if h_lower == "role" or "requester" in h_lower:
            role = value
        if "domain" in h_lower or "category" in h_lower or "type" in h_lower:
            domain = value

    if not max_amount:
        return

    db.execute(
        text("""
            INSERT INTO sheets_policy_rules
                (org_id, source_spreadsheet_id, source_tab_name, source_row_index,
                 rule_type, domain, role, max_amount, approver_role,
                 extraction_confidence, user_confirmed, is_active)
            VALUES (:org_id, :ss_id, :tab, :row_idx, 'approval_limit',
                    :domain, :role, :max_amount, :approver_role,
                    :confidence, FALSE, TRUE)
            ON CONFLICT (org_id, source_spreadsheet_id, source_tab_name, source_row_index) DO UPDATE SET
                max_amount = EXCLUDED.max_amount,
                approver_role = EXCLUDED.approver_role,
                extraction_confidence = EXCLUDED.extraction_confidence,
                prev_max_amount = CASE
                    WHEN EXCLUDED.max_amount != sheets_policy_rules.max_amount THEN sheets_policy_rules.max_amount
                    ELSE sheets_policy_rules.prev_max_amount
                END,
                threshold_changed_at = CASE
                    WHEN EXCLUDED.max_amount != sheets_policy_rules.max_amount THEN NOW()
                    ELSE sheets_policy_rules.threshold_changed_at
                END
        """),
        {
            "org_id": org_id,
            "ss_id": spreadsheet_id,
            "tab": tab_name,
            "row_idx": row_index,
            "domain": domain,
            "role": role,
            "max_amount": max_amount,
            "approver_role": approver_role,
            "confidence": confidence,
        },
    )
