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


# ── the two ROUTES, executed end to end against real PostgreSQL ───────────────────────────────
#
# `_wipe` is exercised elsewhere (tests/capture/semantic/test_extraction_cache.py). The two
# routes that WRAP it are not, and they carry raw SQL of their own that no other test executes:
# `_lock_erasure_authority`'s two `for update` reads, the `resource_uploads` projection, the
# `tenant_packs` reset, the `orgs_archive` insert-select's hand-written column list, and the
# `delete from orgs`. Every one of those names a table or a column, so every one of them is a
# stale-name away from raising inside a `with engine.begin()` block that has no try/except —
# and, exactly like the l2_extraction_results rename, nothing would say so until a customer
# asked to be deleted.
#
# The route FUNCTIONS are called, not transcribed: a copy of the statements here would drift
# from the route the first time somebody edits one. `_graph` is swapped for a shim whose
# `engine.begin()` hands back a SAVEPOINT on the test's own connection, so the real code runs
# and the outer transaction still rolls the whole thing back.

@pytest.fixture()
def erasure_conn(live_db_url, monkeypatch):
    """A real connection, a disposable org of our own, and `_graph` pointed at both.

    A dedicated org rather than the shared scratch one because `delete_account` DELETES it, and
    a test that removes the row every other real-Postgres fixture selects would turn nine files
    into skips the moment it committed. It never commits — but the org is disposable anyway, so
    the two protections are independent.
    """
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres erasure tests skipped")
    import uuid
    from contextlib import contextmanager

    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    conn = get_engine(live_db_url).connect()
    outer = conn.begin()
    try:
        template = conn.execute(text("select id from orgs limit 1")).scalar()
        if not template:
            pytest.skip("no org in the scratch database")
        org = f"org_erasure_{uuid.uuid4().hex[:12]}"
        # Cloned from whatever org the scratch database already holds, so a migration that
        # adds a NOT NULL column to `orgs` does not turn these three tests into errors. Only the
        # columns carrying a UNIQUE constraint are overridden — the clone must be a different
        # tenant, not a second copy of the same one.
        columns = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_schema='public' and table_name='orgs'")).all()]
        unique = {r.column_name for r in conn.execute(text(
            "select a.attname as column_name from pg_index i "
            "join pg_attribute a on a.attrelid=i.indrelid and a.attnum = any(i.indkey) "
            "where i.indrelid='public.orgs'::regclass and i.indisunique")).all()}
        projection = ", ".join(f":clone_{c} as {c}" if c in unique else c for c in columns)
        params = {"t": template}
        params.update({f"clone_{c}": (org if c == "id" else f"{org}@erasure.invalid")
                       for c in unique})
        conn.execute(text(f"insert into orgs ({', '.join(columns)}) select {projection} "
                          "from orgs where id=:t"), params)

        class _Shim:
            """`engine.begin()` as a SAVEPOINT, so the route's own transaction block runs."""

            def __init__(self, c):
                self._c = c

            @contextmanager
            def begin(self):
                nested = self._c.begin_nested()
                try:
                    yield self._c
                except Exception:
                    nested.rollback()
                    raise
                else:
                    nested.commit()

        monkeypatch.setattr(account_routes, "_graph", type("G", (), {"engine": _Shim(conn)})())
        yield conn, org
    finally:
        outer.rollback()
        conn.close()


def test_the_reset_route_runs_every_statement_it_names_against_real_postgres(erasure_conn,
                                                                            monkeypatch):
    """POST /reset end to end: the two locks, the uploads projection, `_wipe`, the pack reset."""
    from sqlalchemy import text

    from genios_engine.platform import audit

    conn, org = erasure_conn
    recorded: list[tuple] = []
    monkeypatch.setattr(audit, "record", lambda *a, **k: recorded.append((a, k)))
    conn.execute(text(
        "insert into tenant_packs (org_id, pack_id, version, lvl3_config, authority_revision) "
        "values (:o, 'sales', '1.0.0', '{\"learned\": 1}'::jsonb, 3) "
        "on conflict do nothing"), {"o": org})
    before = conn.execute(text("select authority_revision from tenant_packs where org_id=:o"),
                          {"o": org}).scalar()

    body = account_routes.reset_graph(org, org=org)

    assert body["wiped"] is True
    assert set(body["rows"]) == set(account_routes._ORG_SCOPED_TABLES)
    assert conn.execute(text("select lvl3_config from tenant_packs where org_id=:o"),
                        {"o": org}).scalar() == {}
    assert conn.execute(text("select authority_revision from tenant_packs where org_id=:o"),
                        {"o": org}).scalar() == before + 1
    assert conn.execute(text("select count(*) from orgs where id=:o"), {"o": org}).scalar() == 1
    assert recorded, "the erasure must be audited"


def test_the_delete_account_route_archives_and_removes_the_org_against_real_postgres(
        erasure_conn):
    """DELETE /account end to end: `_wipe`, then the archive insert-select and the org delete.

    The archive projection is the half `_wipe`'s own test cannot reach — it names seven columns
    of `orgs` and seven of `orgs_archive` by hand, and a rename on either side raises inside the
    same un-guarded transaction block.
    """
    from sqlalchemy import text

    conn, org = erasure_conn
    conn.execute(text(
        f"insert into {'l1_extraction_results'} (processing_key, org_id, event_id, output, "
        "profile_id, tier) values (:k, :o, 'evt_del', '{}'::jsonb, 'email', 'T1')"),
        {"k": f"pytest_delete_{org}", "o": org})

    body = account_routes.delete_account(org, org=org)

    assert body["deleted"] is True
    assert conn.execute(text("select count(*) from orgs where id=:o"), {"o": org}).scalar() == 0
    assert conn.execute(text("select count(*) from orgs_archive where org_id=:o"),
                        {"o": org}).scalar() == 1
    assert conn.execute(text("select count(*) from l1_extraction_results where org_id=:o"),
                        {"o": org}).scalar() == 0


def test_delete_account_refuses_an_org_that_is_already_gone(erasure_conn):
    """The `for update` guard: a second deletion is a 404, never a silent success that reports
    rows wiped from a tenant that no longer exists."""
    conn, org = erasure_conn
    account_routes.delete_account(org, org=org)
    with pytest.raises(HTTPException) as raised:
        account_routes.delete_account(org, org=org)
    assert raised.value.status_code == 404
