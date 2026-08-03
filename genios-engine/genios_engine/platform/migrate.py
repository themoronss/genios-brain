from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import text

from genios_engine.platform.config import get_settings
from genios_engine.platform.db import get_engine

_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def apply_migrations(database_url: str | None = None) -> list[str]:
    """Apply every migrations/*.sql to the DB. Run once after setting DATABASE_URL:
        cd genios-engine && .venv/bin/python -m genios_engine.platform.migrate
    (Or paste the SQL into the Supabase SQL editor.)"""
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("Set GENIOS_DATABASE_URL (in .env) before applying migrations.")
    engine = get_engine(url)
    applied: list[str] = []
    for sql_file in sorted(_MIGRATIONS.glob("*.sql")):
        # strip `-- ...` line comments (which may contain ';') before splitting
        sql = re.sub(r"--[^\n]*", "", sql_file.read_text())
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
        applied.append(sql_file.name)
    return applied


if __name__ == "__main__":
    print("Applied migrations:", apply_migrations())
