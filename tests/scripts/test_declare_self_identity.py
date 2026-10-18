"""STEP-04 · the tenant declares what is its own — an address, a domain — and nothing public.

    pytest tests/scripts/test_declare_self_identity.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_declare_self_identity.py -q

`scripts/declare_self_identity.py` (tree `yc2_w27_s04/M22.C1.L-interface.V2.U04`). Until a brief can
carry it (STEP-07), this is how a tenant says "this address and this domain are us": Harsh runs it
for the design partner with `06` D6's values — `ceo@thegenios.com` and `thegenios.com`. Dry run by
default. A public mail domain is refused before anything is written: declared, gmail.com would make
every Gmail sender one of us, the defect STEP-04 removes.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "declare_self_identity.py"
ORG = "declare_identity_org"


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("declare_self_identity", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_target_is_resolved_through_the_guard_with_no_fallback():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "resolve_database_url" in called and "get_settings" not in called


def test_the_org_and_at_least_one_value_are_required():
    mod = _module()
    with pytest.raises(SystemExit):
        mod.parse_args([])
    with pytest.raises(SystemExit):
        mod.main(["--org", ORG, "--database-url", "postgresql+psycopg://x@127.0.0.1/none"])


@pytest.mark.parametrize("value", ["gmail.com", "@Gmail.com", "outlook.com"])
def test_a_public_mail_domain_is_refused_before_anything_is_written(value):
    mod = _module()
    with pytest.raises(ValueError, match="public"):
        mod.declarations(addresses=[], domains=[value])


def test_values_are_normalised_as_the_identity_reads_them():
    mod = _module()
    assert mod.declarations(addresses=["CEO+x@TheGenios.com"], domains=["@TheGenios.COM."]) == [
        ("address", "ceo@thegenios.com"), ("domain", "thegenios.com")]


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'mrrohitswerashi@gmail.com')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.mark.pg
def test_a_dry_run_writes_nothing_and_apply_writes_once(engine):
    from sqlalchemy import text

    from genios_engine.platform.self_identity import identity_for
    mod = _module()
    rows = mod.declarations(addresses=["ceo@thegenios.com"], domains=["thegenios.com"])
    assert mod.declare(engine, ORG, rows, by="D6", apply=False) == 2
    assert not identity_for(engine, ORG).is_us("ceo@thegenios.com"), "a dry run wrote"
    assert mod.declare(engine, ORG, rows, by="D6", apply=True) == 2
    assert mod.declare(engine, ORG, rows, by="D6", apply=True) == 0, "declared twice"
    us = identity_for(engine, ORG)
    assert us.is_us("ceo@thegenios.com") and us.is_us("invite@thegenios.com")
    with engine.connect() as c:
        assert c.execute(text("select distinct declared_by from org_self_identities where org_id = :o"),
                         {"o": ORG}).scalar() == "D6"
