"""
Policy store — CRUD for policy_rules.

Thin wrapper around SQL. Keeps the route layer slim.
"""

import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def list_rules(db: Session, org_id: str, enabled_only: bool = False) -> list:
    sql = """
        SELECT id, name, description, action_type, risk_tier, rule_json, priority,
               enabled, mode, version, created_at, updated_at, created_by
        FROM policy_rules
        WHERE org_id = :org
    """
    if enabled_only:
        sql += " AND enabled = TRUE"
    sql += " ORDER BY priority ASC, created_at ASC"
    rows = db.execute(text(sql), {"org": org_id}).fetchall()
    return [_serialize(r) for r in rows]


def get_rule(db: Session, org_id: str, rule_id: str) -> Optional[dict]:
    row = db.execute(
        text("""
            SELECT id, name, description, action_type, risk_tier, rule_json, priority,
                   enabled, mode, version, created_at, updated_at, created_by
            FROM policy_rules
            WHERE org_id = :org AND id = :id
        """),
        {"org": org_id, "id": rule_id},
    ).fetchone()
    return _serialize(row) if row else None


def create_rule(
    db: Session,
    org_id: str,
    name: str,
    action_type: str,
    rule_json: dict,
    description: Optional[str] = None,
    risk_tier: Optional[str] = None,
    priority: int = 100,
    mode: str = "enforce",
    created_by: Optional[str] = None,
) -> dict:
    row = db.execute(
        text("""
            INSERT INTO policy_rules
                (org_id, name, description, action_type, risk_tier, rule_json,
                 priority, mode, created_by)
            VALUES
                (:org, :name, :desc, :atype, :rtier, CAST(:rj AS jsonb),
                 :prio, :mode, :by)
            RETURNING id, name, description, action_type, risk_tier, rule_json,
                      priority, enabled, mode, version, created_at, updated_at, created_by
        """),
        {
            "org": org_id, "name": name, "desc": description,
            "atype": action_type, "rtier": risk_tier,
            "rj": json.dumps(rule_json or {}), "prio": priority,
            "mode": mode, "by": created_by,
        },
    ).fetchone()
    db.commit()
    return _serialize(row)


def update_rule(
    db: Session,
    org_id: str,
    rule_id: str,
    **fields,
) -> Optional[dict]:
    # Whitelist the columns callers can touch.
    allowed = {"name", "description", "action_type", "risk_tier",
               "rule_json", "priority", "enabled", "mode"}
    sets, params = [], {"org": org_id, "id": rule_id}
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "rule_json":
            sets.append(f"{k} = CAST(:{k} AS jsonb)")
            params[k] = json.dumps(v)
        else:
            sets.append(f"{k} = :{k}")
            params[k] = v
    if not sets:
        return get_rule(db, org_id, rule_id)

    sets.append("version = version + 1")
    sets.append("updated_at = NOW()")
    sql = f"""
        UPDATE policy_rules SET {', '.join(sets)}
        WHERE org_id = :org AND id = :id
        RETURNING id, name, description, action_type, risk_tier, rule_json,
                  priority, enabled, mode, version, created_at, updated_at, created_by
    """
    row = db.execute(text(sql), params).fetchone()
    db.commit()
    return _serialize(row) if row else None


def delete_rule(db: Session, org_id: str, rule_id: str) -> bool:
    result = db.execute(
        text("DELETE FROM policy_rules WHERE org_id = :org AND id = :id"),
        {"org": org_id, "id": rule_id},
    )
    db.commit()
    return (result.rowcount or 0) > 0


def _serialize(row) -> Optional[dict]:
    if not row:
        return None
    return {
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "action_type": row.action_type,
        "risk_tier": row.risk_tier,
        "rule_json": row.rule_json,
        "priority": row.priority,
        "enabled": row.enabled,
        "mode": row.mode,
        "version": row.version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "created_by": row.created_by,
    }
