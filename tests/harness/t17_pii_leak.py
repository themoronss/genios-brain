"""T-17 — RLS cross-tenant leak test.

Connects as a non-BYPASSRLS role (authenticated) and confirms:
  a) Missing `app.tenant_id` session var → 0 rows visible in contacts
  b) Setting tenant A's id → only A's rows returned, never B's

Threshold: 100% blocked.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_tenant.json"


def run() -> dict:
    data = json.loads(_FIXTURE.read_text())
    org_a = data.get("rls_org_a")
    org_b = data.get("rls_org_b")
    if not org_a or not org_b:
        return {"test": "T-17", "skipped": "no fixture orgs"}

    violations = []

    db = SessionLocal()
    try:
        # (a) No tenant context → expect zero rows (RLS active).
        try:
            db.execute(text("SELECT set_config('app.tenant_id', '', true)"))
            n = db.execute(text("SELECT COUNT(*) FROM contacts")).scalar()
            if n and n > 0:
                violations.append(f"no_tenant_ctx_returned_{n}_rows")
        except Exception as e:
            violations.append(f"no_tenant_ctx_error: {e}")

        # (b) Tenant A context → must not see B's rows.
        try:
            db.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": org_a})
            bleed = db.execute(
                text("SELECT COUNT(*) FROM contacts WHERE org_id = :b"), {"b": org_b}
            ).scalar()
            if bleed and bleed > 0:
                violations.append(f"tenant_a_saw_{bleed}_of_b")
        except Exception as e:
            violations.append(f"tenant_a_error: {e}")
    finally:
        db.close()

    return {
        "test": "T-17", "metric": "rls_violations", "value": len(violations),
        "threshold": 0, "passed": len(violations) == 0, "detail": violations,
    }
