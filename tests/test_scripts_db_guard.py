"""A maintenance script that picks its own database picks production.

`tests/test_tests_never_touch_production.py` closed this hole for the test suite. The scripts
directory has the same hole and a worse blast radius: `rebuild_graph.py` backs up, WIPES and
replays eight projection tables, and it asks global settings for its target — which on any
machine with a `.env` is the live tenant database. Nothing in the invocation says
"production" — you get it by running the script.

`scripts/_db.py` is the answer: a target must be NAMED (`--database-url` or
`GENIOS_TARGET_DATABASE_URL`), a Supabase host needs `GENIOS_ALLOW_PROD_WRITE=1` on top of that,
and whatever survives is printed before the first statement runs. This file is what keeps that
true — for the five gate scripts the L1 v2 plan adds as much as for the ones here today.
"""
from __future__ import annotations

import argparse
import pathlib

import pytest

from scripts._db import (ALLOW_PROD_ENV, TARGET_URL_ENV, UnsafeDatabaseTarget,
                         add_database_argument, describe, is_production_url, redact,
                         resolve_database_url)

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"

#: The implicit-production ledger, and it may only ever SHRINK.
#:
#: `rebuild_graph.py` still resolves its engine from the configured setting
#: (`rebuild_graph.py:107`). Migrating it is a one-line change — `add_database_argument(ap)` and
#: `resolve_database_url(args, purpose=...)` in place of that call — and is deliberately not done
#: here, so that the guard lands without touching the rebuild's semantics.
#:
#: The assertion below is EQUALITY, not "no new offenders": a script added to this set fails
#: review, and a script migrated off it fails until its name is deleted here. An open-ended
#: allowlist would have absorbed the next five gate scripts silently, which is exactly the failure
#: this file exists to prevent.
_KNOWN_UNMIGRATED = {"rebuild_graph.py"}

#: Spelled in halves on purpose. `tests/test_tests_never_touch_production.py` greps every
#: `test_*.py` for this exact expression, and a guard that trips the neighbouring guard is a guard
#: someone eventually silences by adding a name to an allowlist.
_SETTINGS_DB = "get_settings()" + ".database_url"


def _script_modules() -> list[pathlib.Path]:
    return sorted(p for p in SCRIPTS.glob("*.py") if p.name != "_db.py")


def test_no_script_resolves_its_database_from_production_settings():
    offenders = {p.name for p in _script_modules() if _SETTINGS_DB in p.read_text()}
    assert offenders == _KNOWN_UNMIGRATED, (
        "scripts must take their target from scripts/_db.resolve_database_url, not from the "
        f"configured (production) database_url.\n  unexpected: {sorted(offenders - _KNOWN_UNMIGRATED)}"
        f"\n  already migrated, delete from the ledger: {sorted(_KNOWN_UNMIGRATED - offenders)}")


def test_the_resolver_itself_has_no_production_fallback():
    """The guard above is only worth having while the thing it points at is safe. If `_db.py`
    ever learns to ask `Settings` for a URL, every migrated script starts reaching production
    again and this file would still pass. Checked against the module SOURCE, because the whole
    module is small enough that an import of `genios_engine` anywhere in it is the defect."""
    source = (SCRIPTS / "_db.py").read_text()
    code = source[source.index('"""', source.index('"""') + 3) + 3:]     # past the module docstring
    assert "genios_engine" not in code, (
        "scripts/_db.py must not import from genios_engine — that is where the settings fallback "
        "would come back in:\n" + code)


def test_resolver_refuses_when_no_target_is_named(monkeypatch, capsys):
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    with pytest.raises(UnsafeDatabaseTarget) as exc:
        resolve_database_url(argparse.Namespace(database_url=None), purpose="wipe org graph")
    assert TARGET_URL_ENV in str(exc.value)
    assert "--database-url" in str(exc.value)
    assert capsys.readouterr().out == ""          # refused before it announced anything


def test_resolver_refuses_with_no_args_object_at_all(monkeypatch):
    """A script that forgets to wire the flag must still fail closed rather than inherit."""
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    with pytest.raises(UnsafeDatabaseTarget):
        resolve_database_url(purpose="probe")


def test_resolver_refuses_a_blank_or_whitespace_target(monkeypatch):
    monkeypatch.setenv(TARGET_URL_ENV, "   ")
    with pytest.raises(UnsafeDatabaseTarget):
        resolve_database_url(argparse.Namespace(database_url=None), purpose="probe")


def test_explicit_flag_is_accepted_and_the_target_is_printed(monkeypatch, capsys):
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    ap = add_database_argument(argparse.ArgumentParser())
    args = ap.parse_args(["--database-url", "postgresql://u:secret@localhost:5432/genios_scratch"])
    url = resolve_database_url(args, purpose="rebuild org graph")
    assert url == "postgresql://u:secret@localhost:5432/genios_scratch"
    out = capsys.readouterr().out
    assert "rebuild org graph" in out
    assert "localhost:5432" in out and "genios_scratch" in out
    assert "non-production" in out
    assert "secret" not in out                     # printed, but never the password


def test_the_flag_beats_the_environment(monkeypatch, capsys):
    """A shell exported for one database must not silently steer a command aimed at another."""
    monkeypatch.setenv(TARGET_URL_ENV, "postgresql://u:p@other-host:5432/other")
    args = argparse.Namespace(database_url="postgresql://u:p@localhost:5432/chosen")
    assert resolve_database_url(args, purpose="probe").endswith("/chosen")
    assert "--database-url" in capsys.readouterr().out


def test_environment_target_is_accepted_when_no_flag_is_given(monkeypatch, capsys):
    monkeypatch.setenv(TARGET_URL_ENV, "postgresql://u:p@127.0.0.1:5432/genios_scratch")
    assert resolve_database_url(argparse.Namespace(database_url=None), purpose="probe")
    assert TARGET_URL_ENV in capsys.readouterr().out


@pytest.mark.parametrize("url", [
    "localhost:5432/genios",          # urlsplit reads this as scheme="localhost", host=None
    "postgresql:///genios",           # a real scheme, no host at all
    "mysql://u:p@localhost:3306/x",   # a database, but not the one any of these scripts opens
    "/var/run/postgresql",
])
def test_a_target_that_is_not_a_postgres_url_is_refused(url, monkeypatch):
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    with pytest.raises(UnsafeDatabaseTarget) as exc:
        resolve_database_url(argparse.Namespace(database_url=url), purpose="probe")
    assert "not a Postgres URL" in str(exc.value)


def test_a_driver_qualified_postgres_url_is_accepted(monkeypatch):
    """`platform/db.py` normalizes to `postgresql+psycopg://`; an operator pasting the normalized
    form must not be refused for it."""
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    url = "postgresql+psycopg://u:p@localhost:5432/genios_scratch"
    assert resolve_database_url(argparse.Namespace(database_url=url), purpose="probe") == url


@pytest.mark.parametrize("url", [
    "postgresql://postgres:p@db.abcdefghijklmno.supabase.co:5432/postgres",
    "postgresql://postgres.abcdef:p@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
])
def test_production_hosts_are_refused_without_the_second_lock(url, monkeypatch, capsys):
    monkeypatch.delenv(ALLOW_PROD_ENV, raising=False)
    assert is_production_url(url)
    with pytest.raises(UnsafeDatabaseTarget) as exc:
        resolve_database_url(argparse.Namespace(database_url=url), purpose="wipe org graph")
    assert ALLOW_PROD_ENV in str(exc.value)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "TRUE"])
def test_only_the_exact_value_1_unlocks_production(value, monkeypatch):
    """"Deliberate" is the property being enforced, so near-misses do not count."""
    monkeypatch.setenv(ALLOW_PROD_ENV, value)
    with pytest.raises(UnsafeDatabaseTarget):
        resolve_database_url(
            argparse.Namespace(database_url="postgresql://u:p@db.ref.supabase.co:5432/postgres"),
            purpose="wipe org graph")


def test_production_is_reachable_only_with_both_acts_and_says_so(monkeypatch, capsys):
    url = "postgresql://postgres:p@db.ref.supabase.co:5432/postgres"
    monkeypatch.setenv(ALLOW_PROD_ENV, "1")
    assert resolve_database_url(argparse.Namespace(database_url=url), purpose="wipe org graph") == url
    assert "PRODUCTION" in capsys.readouterr().out


@pytest.mark.parametrize("host,production", [
    ("db.ref.supabase.co", True),
    ("aws-0-ap-south-1.pooler.supabase.com", True),
    ("supabase.co", True),
    ("localhost", False),
    ("127.0.0.1", False),
    ("not-supabase.co.example.com", False),        # suffix match, not substring
    ("mysupabase.com", False),                     # ".supabase.com", not any ...supabase.com
])
def test_production_detection_matches_the_host_suffix_only(host, production):
    assert is_production_url(f"postgresql://u:p@{host}:5432/postgres") is production


def test_redaction_keeps_what_identifies_the_target_and_drops_the_password():
    url = "postgresql://postgres:sup3r-s3cret@db.ref.supabase.co:5432/postgres"
    masked = redact(url)
    assert "sup3r-s3cret" not in masked
    assert "postgres:***@db.ref.supabase.co:5432/postgres" in masked
    assert "sup3r-s3cret" not in describe(url)


def test_redaction_survives_a_url_with_no_credentials():
    assert redact("postgresql://localhost:5432/genios") == "postgresql://localhost:5432/genios"
