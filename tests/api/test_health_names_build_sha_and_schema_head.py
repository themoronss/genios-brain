"""`/health` names the build SHA and the schema head (GeniOS-011 S03.U1).

Audit item `process-live-sha-not-observable`: which commit production runs could not be read from
outside. `/health` answered `{status, layer}` and nothing else, `GENIOS_BUILD_SHA` was read only by
`/v1/benchmarks/scorecard`, and no route exposed `schema_migrations` — so a deploy check (08 §0.2
step 9) could not tell which SHA was live or which migration the database stood at, and the claim
that production received c501eec9 on 18 Oct could not be checked from the running service.

What these tests hold:

* `build_sha` is `GENIOS_BUILD_SHA`, and `'dev'` when it is unset (or blank) — read per request,
  so the value is the process's environment and not whatever an import happened to see;
* `schema_head` is the latest `schema_migrations` filename — the ledger `apply_migrations` writes —
  and `null` when there is no database or the read fails; the read never raises, because `/health`
  is the liveness signal and a liveness check that 500s on a database fault is the outage it exists
  to report;
* the degraded (read-only boot) shape keeps both keys — that is exactly the moment a deploy check
  most needs to know which code is up and how far its schema got;
* the head is read at most once per TTL, success or failure, so an uptime monitor polling `/health`
  is not a query per poll, and a database outage costs one bounded wait per TTL rather than one per
  probe.

Hermetic: the ledger is a sqlite file written by the real `apply_migrations`. The one Postgres test
below SKIPS without `GENIOS_TEST_DATABASE_URL`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import routes
from genios_engine.platform.db import get_engine
from genios_engine.platform.migrate import apply_migrations

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _fresh_head_cache(monkeypatch):
    """Each test starts with no cached head: the cache is process state and would leak across."""
    monkeypatch.setattr(routes, "_SCHEMA_HEAD_CACHE", None, raising=False)


def _client() -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(routes.router)
    return app, TestClient(app)


def _ledger(tmp_path, *names) -> str:
    """A sqlite database whose `schema_migrations` was written by the real migration runner."""
    mdir = tmp_path / "migs"
    mdir.mkdir(exist_ok=True)
    for i, n in enumerate(names, start=1):
        (mdir / n).write_text(f"create table if not exists t{i} (id text);")
    url = f"sqlite:///{tmp_path}/ledger.db"
    apply_migrations(url, migrations_dir=mdir)
    return url


class _CountingEngine:
    """An engine that counts how many times `/health` opened a connection."""

    def __init__(self, engine):
        self._engine = engine
        self.connects = 0

    def connect(self):
        self.connects += 1
        return self._engine.connect()


class _DeadEngine:
    """An engine whose every connection fails — the database is unreachable."""

    def __init__(self):
        self.connects = 0

    def connect(self):
        self.connects += 1
        raise ConnectionError("database unreachable")


# ── build_sha ────────────────────────────────────────────────────────────────────────────────────
def test_health_names_the_build_sha_it_was_deployed_with(monkeypatch):
    monkeypatch.setenv("GENIOS_BUILD_SHA", "0cc8d83c4f1e")
    monkeypatch.setattr(routes, "_graph", None)
    _, client = _client()
    with client:
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["build_sha"] == "0cc8d83c4f1e"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_build_sha_is_dev_when_the_environment_does_not_name_one(monkeypatch, value):
    """Unset and blank both mean "nobody bound the commit" — `'dev'`, never an empty string that a
    deploy check would read as a SHA it could not match."""
    if value is None:
        monkeypatch.delenv("GENIOS_BUILD_SHA", raising=False)
    else:
        monkeypatch.setenv("GENIOS_BUILD_SHA", value)
    monkeypatch.setattr(routes, "_graph", None)
    _, client = _client()
    with client:
        body = client.get("/health").json()
    assert body["build_sha"] == "dev"


# ── schema_head ──────────────────────────────────────────────────────────────────────────────────
def test_health_names_the_latest_migration_in_the_ledger(tmp_path, monkeypatch):
    url = _ledger(tmp_path, "0001_first.sql", "0002_second.sql", "0010_tenth.sql")
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=get_engine(url)))
    _, client = _client()
    with client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["schema_head"] == "0010_tenth.sql"


def test_schema_head_is_null_without_a_database(monkeypatch):
    """In-memory dev has no ledger to read: the key is there and says so, it is not left out."""
    monkeypatch.setattr(routes, "_graph", None)
    _, client = _client()
    with client:
        body = client.get("/health").json()
    assert "schema_head" in body
    assert body["schema_head"] is None


def test_an_unreachable_database_reads_as_null_and_health_still_answers(monkeypatch):
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_DeadEngine()))
    _, client = _client()
    with client:
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["schema_head"] is None
    assert "build_sha" in body


def test_a_database_with_no_ledger_reads_as_null(tmp_path, monkeypatch):
    """A schema that never ran a migration has no `schema_migrations`: an error, read as null."""
    eng = get_engine(f"sqlite:///{tmp_path}/empty.db")
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=eng))
    _, client = _client()
    with client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["schema_head"] is None


# ── the degraded shape ───────────────────────────────────────────────────────────────────────────
def test_the_degraded_shape_keeps_both_keys(tmp_path, monkeypatch):
    """A read-only boot is when a deploy check most needs to know which code is up and how far its
    schema got: the pending migrations the boot could not apply are exactly the gap to the head."""
    monkeypatch.setenv("GENIOS_BUILD_SHA", "21b7ae10")
    url = _ledger(tmp_path, "0001_first.sql", "0249_l2_admissions.sql")
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=get_engine(url)))
    app, client = _client()
    with client:
        app.state.degraded_read_only = "1 migration(s) pending and the database is read-only"
        body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert body["writes"] == "unavailable"
    assert "read-only" in body["reason"]
    assert body["build_sha"] == "21b7ae10"
    assert body["schema_head"] == "0249_l2_admissions.sql"


def test_the_degraded_shape_keeps_both_keys_when_the_read_fails(monkeypatch):
    monkeypatch.delenv("GENIOS_BUILD_SHA", raising=False)
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_DeadEngine()))
    app, client = _client()
    with client:
        app.state.degraded_read_only = "1 migration(s) pending and the database is read-only"
        body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert body["build_sha"] == "dev"
    assert "schema_head" in body
    assert body["schema_head"] is None


# ── the read is bounded ──────────────────────────────────────────────────────────────────────────
def test_the_head_is_read_once_per_ttl_not_once_per_probe(tmp_path, monkeypatch):
    url = _ledger(tmp_path, "0001_first.sql")
    eng = _CountingEngine(get_engine(url))
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=eng))
    _, client = _client()
    with client:
        heads = [client.get("/health").json()["schema_head"] for _ in range(3)]
        assert heads == ["0001_first.sql"] * 3
        assert eng.connects == 1, "every probe read the ledger — an uptime monitor is a query per poll"

        monkeypatch.setattr(routes, "_SCHEMA_HEAD_TTL_S", -1.0)     # the TTL has run out
        assert client.get("/health").json()["schema_head"] == "0001_first.sql"
    assert eng.connects == 2, "an expired head was not re-read"


def test_a_failed_read_is_held_for_the_ttl_too(monkeypatch):
    """During an outage each read waits out the connect timeout. Not caching the failure would make
    every probe pay it, and consecutive slow probes are what an orchestrator restarts a box for."""
    eng = _DeadEngine()
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=eng))
    _, client = _client()
    with client:
        for _ in range(3):
            assert client.get("/health").json()["schema_head"] is None
    assert eng.connects == 1


# ── Postgres ─────────────────────────────────────────────────────────────────────────────────────
def test_on_postgres_the_head_is_not_behind_this_codes_migrations(monkeypatch):
    """The real ledger on a real server: the head names a migration file, and it is not older than
    the newest one this checkout ships (a database migrated by this code is AT least its head)."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the real-Postgres schema head is not read")
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=get_engine(url)))
    _, client = _client()
    with client:
        head = client.get("/health").json()["schema_head"]
    assert isinstance(head, str) and re.fullmatch(r"\d{4}_[\w.-]+\.sql", head), head
    newest_here = max(p.name for p in (_REPO / "migrations").glob("*.sql"))
    assert head >= newest_here, f"schema head {head} is behind this code's {newest_here}"
