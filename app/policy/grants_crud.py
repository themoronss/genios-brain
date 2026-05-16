"""
Per-agent → workspace-account access grants (Phase 12).

Architecture pivot: tools (Gmail / Calendar / Inkbox / IMAP / Phone / SMS)
are now connected ONCE at workspace level on the Integrations page.
Each connection produces an "account" — multiple accounts allowed per tool.

Agents are NOT connected to tools directly. Instead, an agent's "Tools
access" tab in the dashboard records GRANTS — a checkbox-style list of
workspace accounts the agent is allowed to read from.

Account identity is split across two tables for back-compat:
  * `oauth_tokens.id`            → Google OAuth (Gmail, Calendar)
  * `connector_credentials.id`   → Inkbox, IMAP, Phone, SMS
The `account_kind` column ('oauth' or 'connector') tells which table to join.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


# ── Mutations ────────────────────────────────────────────────────────────────
def list_for_agent(db: Session, org_id: str, agent_uuid: str):
    """Returns the rows the agent has access to, joined with account display
    info from oauth_tokens / connector_credentials."""
    return db.execute(
        text("""
            SELECT g.id::text         AS grant_id,
                   g.account_id::text AS account_id,
                   g.account_kind     AS account_kind,
                   g.granted_at,
                   COALESCE(ot.account_email, cc.metadata->>'mailbox_address',
                            cc.metadata->>'phone_number', cc.metadata->>'account')
                                       AS account_label,
                   COALESCE(
                       CASE WHEN ot.account_email IS NOT NULL THEN
                            CASE WHEN ot.account_email LIKE 'tool:gcal:%' THEN 'calendar'
                                 ELSE 'gmail' END
                       END,
                       cc.metadata->>'provider', cc.source) AS tool
            FROM agent_account_grants g
            LEFT JOIN oauth_tokens ot
                   ON g.account_kind = 'oauth' AND ot.id = g.account_id
            LEFT JOIN connector_credentials cc
                   ON g.account_kind = 'connector' AND cc.id = g.account_id
            WHERE g.org_id = :o AND g.agent_uuid = :a
            ORDER BY g.granted_at DESC
        """),
        {"o": org_id, "a": agent_uuid},
    ).fetchall()


def list_account_ids_for_agent(db: Session, agent_uuid: str) -> list[tuple[str, str]]:
    """Tight return for read-time scope filter: [(account_id, account_kind), ...]"""
    rows = db.execute(
        text("""
            SELECT account_id::text, account_kind
            FROM agent_account_grants
            WHERE agent_uuid = :a
        """),
        {"a": agent_uuid},
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def replace_grants(
    db: Session, org_id: str, agent_uuid: str,
    accounts: list[dict],
    granted_by: Optional[str] = None,
) -> int:
    """Atomic replace — clears all existing grants for the agent, inserts new set.
    `accounts` shape: [{"account_id": "...", "account_kind": "oauth|connector"}, ...]
    Returns number of grants now active."""
    db.execute(
        text("DELETE FROM agent_account_grants WHERE org_id = :o AND agent_uuid = :a"),
        {"o": org_id, "a": agent_uuid},
    )
    for acct in accounts or []:
        kind = (acct.get("account_kind") or "").strip().lower()
        if kind not in ("oauth", "connector"):
            continue
        if not acct.get("account_id"):
            continue
        db.execute(
            text("""
                INSERT INTO agent_account_grants
                    (org_id, agent_uuid, account_id, account_kind, granted_by)
                VALUES (:o, :a, :acct, :k, :gb)
                ON CONFLICT (agent_uuid, account_id, account_kind) DO NOTHING
            """),
            {"o": org_id, "a": agent_uuid, "acct": acct["account_id"], "k": kind, "gb": granted_by},
        )
    return db.execute(
        text("SELECT COUNT(*) FROM agent_account_grants WHERE agent_uuid = :a"),
        {"a": agent_uuid},
    ).scalar() or 0


def add_grant(db: Session, org_id: str, agent_uuid: str,
              account_id: str, account_kind: str, granted_by: Optional[str] = None) -> bool:
    res = db.execute(
        text("""
            INSERT INTO agent_account_grants (org_id, agent_uuid, account_id, account_kind, granted_by)
            VALUES (:o, :a, :acct, :k, :gb)
            ON CONFLICT (agent_uuid, account_id, account_kind) DO NOTHING
            RETURNING id
        """),
        {"o": org_id, "a": agent_uuid, "acct": account_id, "k": account_kind, "gb": granted_by},
    ).fetchone()
    return res is not None


def remove_grant(db: Session, org_id: str, agent_uuid: str,
                 account_id: str, account_kind: str) -> bool:
    res = db.execute(
        text("""
            DELETE FROM agent_account_grants
            WHERE org_id = :o AND agent_uuid = :a AND account_id = :acct AND account_kind = :k
            RETURNING id
        """),
        {"o": org_id, "a": agent_uuid, "acct": account_id, "k": account_kind},
    ).fetchone()
    return res is not None


def list_workspace_accounts(db: Session, org_id: str):
    """All connected accounts at workspace level. Returns rows with
    (id, kind, tool, channel, label, last_event_at, sync_status, sync_error,
    last_sync_at, consecutive_failures) — UI uses status fields to render
    badges (green Synced / red Auth failed / yellow Syncing / gray Stale)
    and `channel` to render the right icon (📧 email / 💬 sms / 📞 voice)."""
    return db.execute(
        text("""
            SELECT id::text,
                   'oauth' AS kind,
                   CASE WHEN account_email LIKE 'tool:gcal:%' THEN 'calendar'
                        WHEN account_email LIKE 'tool:%' THEN
                             SPLIT_PART(account_email, ':', 2)
                        ELSE 'gmail' END                AS tool,
                   CASE WHEN account_email LIKE 'tool:gcal:%' THEN 'calendar'
                        ELSE 'email' END                AS channel,
                   CASE WHEN account_email LIKE 'tool:%' THEN
                             SPLIT_PART(account_email, ':', 3)
                        ELSE account_email END           AS label,
                   last_synced_at                       AS last_event_at,
                   sync_status                          AS sync_status,
                   NULL                                 AS sync_error,
                   last_synced_at                       AS last_sync_at,
                   0                                    AS consecutive_failures
            FROM oauth_tokens
            WHERE org_id = :o
            UNION ALL
            SELECT id::text,
                   'connector' AS kind,
                   COALESCE(metadata->>'provider', source) AS tool,
                   source                               AS channel,
                   COALESCE(metadata->>'mailbox_address',
                            metadata->>'phone_number',
                            metadata->>'account', source) AS label,
                   last_event_at,
                   last_sync_status,
                   last_sync_error,
                   last_sync_at,
                   COALESCE(consecutive_failures, 0)
            FROM connector_credentials
            WHERE org_id = :o AND is_active = TRUE AND agent_uuid IS NULL
            ORDER BY tool, channel, label
        """),
        {"o": org_id},
    ).fetchall()
