"""Audit trail writer. Append-only, refs+counts only (no content). `record()` is a side effect —
it NEVER raises into the caller: a failed audit write must not break the action it's auditing. Read
side lives in api/audit_routes.py. Ported from genios-brain (core/foundations/audit).
"""
from __future__ import annotations

import json

from sqlalchemy import text

from genios_engine.platform.config import get_settings
from genios_engine.platform.db import get_engine
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.audit")

# The action vocabulary the dashboard's Audit filter knows how to label.
ACTIONS = [
    "user_signed_up", "user_logged_in", "user_logged_out", "login_failed",
    "decision_made", "data_accessed", "permission_changed", "override_captured",
    "module_activated", "module_deactivated", "scope_granted", "scope_revoked",
    "secret_accessed", "config_changed", "data_subject_access", "data_subject_erasure",
    "retention_swept",
]


def record(org_id: str, action: str, *, actor_type: str = "system", actor_id: str | None = None,
           target_type: str | None = None, target_id: str | None = None,
           metadata: dict | None = None) -> None:
    """Append one audit event for `org_id`. Swallows all errors (logs them)."""
    if not org_id or not action:
        return
    try:
        eng = get_engine(get_settings().database_url)
        with eng.begin() as c:
            c.execute(text(
                "insert into audit_log (org_id, actor_type, actor_id, action, target_type, "
                "target_id, metadata_jsonb) values (:o,:at,:aid,:ac,:tt,:tid,cast(:m as jsonb))"),
                {"o": org_id, "at": actor_type, "aid": actor_id, "ac": action, "tt": target_type,
                 "tid": target_id, "m": json.dumps(metadata or {}, default=str)})
    except Exception:                                          # noqa: BLE001 - audit never breaks callers
        _log.exception("audit record failed action=%s org=%s", action, org_id)
