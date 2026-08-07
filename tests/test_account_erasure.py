from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from genios_engine.api import account_routes


MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def _org_tables_and_direct_cascades() -> tuple[set[str], set[str]]:
    org_tables: set[str] = set()
    cascades: set[str] = set()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        sql = path.read_text()
        for match in re.finditer(
                r"create\s+table\s+if\s+not\s+exists\s+(\w+)\s*\((.*?)\n\);",
                sql, flags=re.IGNORECASE | re.DOTALL):
            table, body = match.groups()
            if re.search(r"\borg_id\b", body, flags=re.IGNORECASE):
                org_tables.add(table)
            if (re.search(r"\borg_id\b.*?references\s+orgs\s*\(\s*id\s*\)"
                          r".*?on\s+delete\s+cascade", body,
                          flags=re.IGNORECASE | re.DOTALL)):
                cascades.add(table)
        for statement in sql.split(";"):
            table_match = re.search(r"alter\s+table\s+(\w+)", statement,
                                    flags=re.IGNORECASE)
            if (table_match and re.search(
                    r"foreign\s+key\s*\(\s*org_id\s*\)\s*references\s+orgs\s*"
                    r"\(\s*id\s*\)\s*on\s+delete\s+cascade",
                    statement, flags=re.IGNORECASE | re.DOTALL)):
                cascades.add(table_match.group(1))
    return org_tables, cascades


def test_every_org_scoped_table_has_a_proven_account_delete_cascade():
    org_tables, direct_cascades = _org_tables_and_direct_cascades()
    # These rows have composite FKs with ON DELETE CASCADE to one of the direct org-owned
    # reasoning parents, so deleting the org still has a complete, schema-enforced path.
    indirect_reasoning_children = {
        "reasoning_context_payloads",
        "reasoning_reasoner_results",
        "reasoning_candidates",
        "reasoning_candidate_checks",
        "reasoning_run_outputs",
    }

    assert org_tables - direct_cascades - indirect_reasoning_children == set()


def test_upload_file_erasure_accepts_only_the_owned_upload_root(tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    owned = upload_root / "upl_1_notes.txt"
    owned.write_text("sensitive")
    outside = tmp_path / "do-not-delete.txt"
    outside.write_text("keep")
    monkeypatch.setattr(account_routes, "_UPLOAD_ROOT", upload_root.resolve())

    assert account_routes._remove_upload_files([str(owned), str(owned)]) == 1
    assert not owned.exists()

    with pytest.raises(HTTPException) as exc:
        account_routes._remove_upload_files([str(outside)])

    assert exc.value.status_code == 503
    assert outside.read_text() == "keep"
