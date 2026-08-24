from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from genios_engine.api import account_routes


MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def _org_tables_and_direct_cascades() -> tuple[set[str], set[str], set[str]]:
    """Replay every migration statement IN ORDER and track the net state of each table's org
    cascade. Order matters: a constraint that is dropped and re-added in the same wave is still
    protected, while one dropped and never re-added is not — a set of "ever added" names cannot
    tell those apart, and would report a table as erasable long after it stopped being so.

    Returns (tables carrying org_id, tables whose cascade is live now, tables whose cascade was
    dropped and left off)."""
    org_tables: set[str] = set()
    live: dict[str, bool] = {}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        for statement in path.read_text().split(";"):
            created = re.search(r"create\s+table\s+if\s+not\s+exists\s+(\w+)\s*\((.*)",
                                statement, flags=re.IGNORECASE | re.DOTALL)
            if created:
                table, body = created.groups()
                if re.search(r"\borg_id\b", body, flags=re.IGNORECASE):
                    org_tables.add(table)
                if re.search(r"\borg_id\b.*?references\s+orgs\s*\(\s*id\s*\).*?on\s+delete\s+cascade",
                             body, flags=re.IGNORECASE | re.DOTALL):
                    live[table] = True
                continue
            altered = re.search(r"alter\s+table\s+(\w+)", statement, flags=re.IGNORECASE)
            if not altered:
                continue
            if re.search(r"foreign\s+key\s*\(\s*org_id\s*\)\s*references\s+orgs\s*"
                         r"\(\s*id\s*\)\s*on\s+delete\s+cascade",
                         statement, flags=re.IGNORECASE | re.DOTALL):
                live[altered.group(1)] = True
            elif re.search(r"drop\s+constraint\s+(if\s+exists\s+)?\w*org\w*",
                           statement, flags=re.IGNORECASE):
                live[altered.group(1)] = False
    cascades = {t for t, ok in live.items() if ok}
    dropped = {t for t, ok in live.items() if not ok}
    return org_tables, cascades, dropped


# Deliberately NOT erased with the account (0058). These are GeniOS's own accounting records —
# what we spent on models and what the customer paid us — not the tenant's personal data. Losing
# them on deletion would make our own cost and revenue history silently wrong, so the org cascade
# was dropped and the tenant's identity is preserved in orgs_archive purely to keep those rows
# attributable. Adding a table here is a business decision, never a convenience.
RETAINED_FINANCIAL_TABLES = {"llm_costs", "credit_ledger", "subscriptions", "orgs_archive"}


def test_financial_tables_are_retained_and_everything_else_still_cascades():
    """The retained set is exactly what we intend: no content table can quietly join it."""
    _org_tables, _cascades, dropped = _org_tables_and_direct_cascades()
    # every cascade we dropped must be an intentional financial retention
    assert dropped - RETAINED_FINANCIAL_TABLES == set()
    # and none of the retained tables may be wiped by the org-scoped erasure sweep either
    assert RETAINED_FINANCIAL_TABLES & set(account_routes._ORG_SCOPED_TABLES) == set()


def test_every_org_scoped_table_has_a_proven_account_delete_cascade():
    org_tables, direct_cascades, _dropped = _org_tables_and_direct_cascades()
    org_tables -= RETAINED_FINANCIAL_TABLES
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
