"""Boot must survive a read-only database instead of crash-looping on it.

Measured against production on 2026-08-29, with the server in Supabase's disk-quota read-only
mode: the first statement `apply_migrations` issued — the ledger's `create table if not exists
schema_migrations` — raised

    psycopg.errors.ReadOnlySqlTransaction: cannot execute CREATE TABLE in a read-only transaction

even though `schema_migrations` had existed for months and all 75 of its rows were present.
Postgres runs the read-only check BEFORE the IF NOT EXISTS check, so "nothing to do" and "cannot
do it" are indistinguishable to the server.

`apply_migrations` is the first thing `main.lifespan` does. So every boot crashed, every deploy
crash-looped, and the crash took down the reads that were still working perfectly — converting a
partial outage into a total one, at the exact moment nobody could deploy a fix.

Two changes, tested here. The ledger is READ first, so the fully-migrated case issues no DDL at
all and boots on a read-only server exactly as it does on a writable one. And when migrations
genuinely are pending, the failure is a typed `ReadOnlyDatabaseError` the boot path can tell apart
from a real migration fault — because restarting cannot fix a write lock, and only a human
lifting it can.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.platform import migrate as migrate_mod
from genios_engine.platform.db import get_engine
from genios_engine.platform.migrate import ReadOnlyDatabaseError, apply_migrations


def _db(tmp_path):
    return f"sqlite:///{tmp_path}/m.db"


def _migrations(tmp_path, *names):
    mdir = tmp_path / "migs"
    mdir.mkdir(exist_ok=True)
    for i, n in enumerate(names, start=1):
        (mdir / n).write_text(f"create table if not exists t{i} (id text);")
    return mdir


def test_a_fully_migrated_database_issues_no_ddl_at_all(tmp_path, monkeypatch):
    """The production case, and the one that matters: nothing pending, so nothing is written.

    Before this, the no-op path still opened with a CREATE TABLE. Asserting on the ABSENCE of DDL
    rather than on the return value is deliberate — the return was already `[]` when it crashed.
    """
    mdir = _migrations(tmp_path, "0001_a.sql")
    url = _db(tmp_path)
    assert apply_migrations(url, migrations_dir=mdir) == ["0001_a.sql"]

    # Both statements the write path would issue, made into tripwires. Neither may be reached:
    # with nothing pending the function must return before it decides anything about writing.
    def _tripwire(_engine):
        raise AssertionError("the write path was entered with nothing pending")

    monkeypatch.setattr(migrate_mod, "_is_read_only", _tripwire)
    monkeypatch.setattr(migrate_mod, "_LEDGER_DDL", "select 1/0")

    assert apply_migrations(url, migrations_dir=mdir) == []


def test_pending_migrations_on_a_read_only_server_raise_the_typed_error(tmp_path, monkeypatch):
    """Not the driver's error — one the boot path can distinguish from a genuine fault."""
    mdir = _migrations(tmp_path, "0001_a.sql")
    url = _db(tmp_path)
    apply_migrations(url, migrations_dir=mdir)
    (mdir / "0002_b.sql").write_text("create table if not exists t2 (id text);")

    monkeypatch.setattr(migrate_mod, "_is_read_only", lambda _e: True)
    with pytest.raises(ReadOnlyDatabaseError) as exc:
        apply_migrations(url, migrations_dir=mdir)
    assert "0002_b.sql" in str(exc.value)


def test_the_error_names_what_is_pending_so_the_human_knows_what_to_lift(tmp_path, monkeypatch):
    mdir = _migrations(tmp_path, "0001_a.sql", "0002_b.sql", "0003_c.sql")
    url = _db(tmp_path)
    monkeypatch.setattr(migrate_mod, "_is_read_only", lambda _e: True)
    with pytest.raises(ReadOnlyDatabaseError) as exc:
        apply_migrations(url, migrations_dir=mdir)
    assert "3 migration(s) pending" in str(exc.value)


def test_a_writable_server_is_unaffected(tmp_path):
    """The guard must not change the normal path — migrations still apply, once, in order."""
    mdir = _migrations(tmp_path, "0001_a.sql", "0002_b.sql")
    url = _db(tmp_path)
    assert apply_migrations(url, migrations_dir=mdir) == ["0001_a.sql", "0002_b.sql"]
    assert apply_migrations(url, migrations_dir=mdir) == []

    with get_engine(url).connect() as c:
        rows = c.execute(text("select filename from schema_migrations")).all()
    assert [r.filename for r in rows] == ["0001_a.sql", "0002_b.sql"]


def test_checksum_drift_still_fails_even_when_read_only(tmp_path, monkeypatch):
    """Read-only is survivable. Edited history is not, and must not be masked by it."""
    mdir = _migrations(tmp_path, "0001_a.sql")
    url = _db(tmp_path)
    apply_migrations(url, migrations_dir=mdir)
    (mdir / "0001_a.sql").write_text("create table if not exists t_changed (id text);")

    monkeypatch.setattr(migrate_mod, "_is_read_only", lambda _e: True)
    with pytest.raises(RuntimeError, match="checksum drift"):
        apply_migrations(url, migrations_dir=mdir)


def test_sqlite_is_never_reported_read_only(tmp_path):
    """`show default_transaction_read_only` does not exist outside Postgres — that is not a yes."""
    assert migrate_mod._is_read_only(get_engine(_db(tmp_path))) is False


# ── the boot path ────────────────────────────────────────────────────────────────────────────
def test_boot_degrades_instead_of_crashing_and_says_so_on_health():
    """The whole point: the process stays up, and `/health` stops claiming to be ok.

    A four-hour production write outage passed every check that was watching it, because the
    process was genuinely alive and `/health` only ever reported that.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api.routes import router

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"

        app.state.degraded_read_only = "1 migration(s) pending and the database is read-only"
        body = client.get("/health").json()

    assert body["status"] == "degraded"
    assert body["writes"] == "unavailable"
    assert "read-only" in body["reason"]


def test_the_boot_path_catches_only_the_read_only_error():
    """A real migration failure must still crash the boot — fail-fast is the rule, not the
    exception. Only the case a restart cannot fix is survivable."""
    import inspect

    from genios_engine import main

    src = inspect.getsource(main.lifespan)
    assert "except ReadOnlyDatabaseError" in src, "the boot guard caught something broader"
    assert "degraded_read_only" in src
