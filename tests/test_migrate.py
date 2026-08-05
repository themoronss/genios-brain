"""Migration ledger: each file applies exactly once; edited history fails loudly."""
from __future__ import annotations

from sqlalchemy import text

from genios_engine.platform.db import get_engine
from genios_engine.platform.migrate import apply_migrations


def _db(tmp_path):
    return f"sqlite:///{tmp_path}/m.db"


def test_applies_once_then_skips(tmp_path):
    mdir = tmp_path / "migs"
    mdir.mkdir()
    (mdir / "0001_a.sql").write_text("create table if not exists t1 (id text);")
    url = _db(tmp_path)

    assert apply_migrations(url, migrations_dir=mdir) == ["0001_a.sql"]
    assert apply_migrations(url, migrations_dir=mdir) == []          # second run: no-op

    with get_engine(url).connect() as c:
        rows = c.execute(text("select filename from schema_migrations")).all()
    assert [r.filename for r in rows] == ["0001_a.sql"]


def test_new_file_applies_incrementally(tmp_path):
    mdir = tmp_path / "migs"
    mdir.mkdir()
    (mdir / "0001_a.sql").write_text("create table if not exists t1 (id text);")
    url = _db(tmp_path)
    apply_migrations(url, migrations_dir=mdir)

    (mdir / "0002_b.sql").write_text("create table if not exists t2 (id text);")
    assert apply_migrations(url, migrations_dir=mdir) == ["0002_b.sql"]


def test_checksum_drift_fails_loudly(tmp_path):
    mdir = tmp_path / "migs"
    mdir.mkdir()
    f = mdir / "0001_a.sql"
    f.write_text("create table if not exists t1 (id text);")
    url = _db(tmp_path)
    apply_migrations(url, migrations_dir=mdir)

    f.write_text("create table if not exists t1_edited (id text);")   # history edited
    try:
        apply_migrations(url, migrations_dir=mdir)
        raise AssertionError("edited applied migration must be rejected")
    except RuntimeError as e:
        assert "checksum drift" in str(e)


def test_failed_file_records_nothing(tmp_path):
    """A file that raises mid-way must NOT be marked applied (file + ledger row share a tx)."""
    mdir = tmp_path / "migs"
    mdir.mkdir()
    (mdir / "0001_bad.sql").write_text(
        "create table if not exists ok1 (id text); this is not sql;")
    url = _db(tmp_path)
    try:
        apply_migrations(url, migrations_dir=mdir)
        raise AssertionError("bad sql must raise")
    except Exception:
        pass
    with get_engine(url).connect() as c:
        rows = c.execute(text("select filename from schema_migrations")).all()
    assert rows == []                                    # not recorded → retried next run
