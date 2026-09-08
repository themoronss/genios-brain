"""`scripts/activate_tenant.py` — nine switches, one order, one command.

    pytest tests/test_activate_tenant.py -q      (the pg tests need GENIOS_TEST_DATABASE_URL)

Four layers ship four independent switch tables, and each is right to be separate. What was missing
is the thing that knows their ORDER: Layer 1's lane is the only producer of the verified evidence
spans Layer 2's admission gate requires, so a tenant switched on from the top down has every layer
above L1 fed held situations — the console reads green and the pipeline stays empty. That failure
has a name in every one of those modules' docstrings: *"activation would LOOK successful while
producing generic output."*

What is pinned here is the part a reviewer cannot see by reading the output: the ORDER, the
refusal to write anything without `--apply`, and that a re-run is a no-op rather than a second
pilot with a fresh start date.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.platform.db import get_engine
from scripts import activate_tenant as script

ORG = "org_activate_script"


# =============================================================================================
# The order — the whole reason this file exists
# =============================================================================================
def test_layer_one_is_first_and_layer_four_is_last():
    """Not alphabetical, not by table name. L1 supplies the evidence L2 admits on; L4 ranks what
    L3 compiled. Any other order switches something on with nothing to work on."""
    layers = [layer for layer, _kind, _name in script.PLAN]
    assert layers == sorted(layers), "the plan is out of layer order"
    assert layers[0] == "L1" and layers[-1] == "L4"


def test_the_layer_four_features_are_in_wave_order():
    """`roster_v2` decides which units run, `ranking_v2` ranks what they produced, `bundle`
    narrates what was ranked. Reversed, each has nothing to speak about."""
    features = [name for layer, kind, name in script.PLAN if kind == "feature"]
    assert features == ["roster_v2", "ranking_v2", "bundle", "critique", "brief"]


def test_analytic_precedes_patterns():
    switches = [name for _l, kind, name in script.PLAN if kind == "switch"]
    assert switches == ["analytic", "patterns"]


def test_every_switch_name_is_one_its_own_layer_accepts():
    """A typo here would write a row that reads as an activated tenant and turns nothing on. Each
    layer owns its vocabulary, so each name is validated by the module that owns it."""
    from genios_engine.platform.l2_activation import require_switch
    from genios_engine.platform.l3_activation import require_domain
    from genios_engine.platform.l4_activation import require_feature

    for _layer, kind, name in script.PLAN:
        if kind == "switch":
            assert require_switch(name) == name
        elif kind == "domain":
            assert require_domain(name) == name
        elif kind == "feature":
            assert require_feature(name) == name


def test_every_switch_says_what_it_does():
    """An operator who can see a switch and not its effect assumes it turned on everything."""
    for layer, kind, name in script.PLAN:
        key = (layer, "semantic" if kind == "semantic" else name)
        assert script.EFFECT.get(key), f"{layer} {name} has no stated effect"


def test_the_two_that_spend_say_so():
    """Layer 1 puts a model call on every message; `bundle` writes a narrative per decision. Both
    are spend decisions and the line an operator reads has to say that before they type --apply."""
    assert "SPENDS" in script.EFFECT[("L1", "semantic")]
    assert "SPENDS" in script.EFFECT[("L4", "bundle")]


def test_the_selection_keeps_the_plan_order():
    """A caller asking for two domains and one feature still gets L1 -> L2 -> L3 -> L4."""
    chosen = script._plan_for(("admin", "sales"), ("ranking_v2",))
    assert [(layer, name) for layer, _k, name in chosen] == [
        ("L1", "semantic"), ("L2", "analytic"), ("L2", "patterns"),
        ("L3", "admin"), ("L3", "sales"), ("L4", "ranking_v2")]


def test_the_default_feature_set_stops_before_the_narrative():
    """`--features` defaults to the pair that makes the formula decide. `bundle` is opt-in because
    it is the second thing here that spends money per item."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default="roster_v2,ranking_v2")
    assert parser.parse_args([]).features == "roster_v2,ranking_v2"


# =============================================================================================
# Against a real database
# =============================================================================================
@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — activation writes real rows")
    return live_db_url


@pytest.fixture
def tenant(pg_url):
    engine = get_engine(pg_url)

    def wipe(conn):
        for table in ("l1_semantic_activation", "l2_v2_activation", "l3_activation",
                      "l4_activation", "audit_log"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})

    with engine.begin() as conn:
        wipe(conn)
        names = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                          f"({', '.join(':' + c for c in cols)})"),
                     {"id": ORG, **{n: "scratch" for n in names}})
    yield engine, pg_url
    with engine.begin() as conn:
        wipe(conn)


def _run(pg_url: str, *extra: str) -> int:
    import sys

    argv = ["activate_tenant.py", "--database-url", pg_url, "--org", ORG, *extra]
    old, sys.argv = sys.argv, argv
    try:
        return script.main()
    finally:
        sys.argv = old


def test_a_dry_run_writes_nothing(tenant, capsys):
    engine, pg_url = tenant
    assert _run(pg_url) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert not any(script._state(engine, ORG).values()), "the dry run flipped something"


def test_apply_switches_the_requested_set_on(tenant):
    engine, pg_url = tenant
    assert _run(pg_url, "--apply") == 0

    live = script._state(engine, ORG)
    assert live[("L1", "semantic")] and live[("L2", "analytic")] and live[("L2", "patterns")]
    assert live[("L3", "admin")] and live[("L4", "roster_v2")] and live[("L4", "ranking_v2")]
    # The two that spend per item, and the domains nobody asked for, stay off.
    assert not live[("L4", "bundle")] and not live[("L4", "critique")]
    assert not live[("L3", "sales")]


def test_running_it_twice_is_a_no_op(tenant, capsys):
    """Not merely harmless — each layer's `activate` keeps the ORIGINAL `enabled_at`, because
    'since when has this tenant been on' is the question the pilot diff is read against."""
    engine, pg_url = tenant
    _run(pg_url, "--apply")
    with engine.connect() as conn:
        first = conn.execute(text("select enabled_at from l1_semantic_activation "
                                  "where org_id = :o"), {"o": ORG}).scalar()
    capsys.readouterr()

    _run(pg_url, "--apply")
    assert "nothing to do" in capsys.readouterr().out
    with engine.connect() as conn:
        again = conn.execute(text("select enabled_at from l1_semantic_activation "
                                  "where org_id = :o"), {"o": ORG}).scalar()
    assert again == first, "a re-run restarted the pilot window"


def test_status_reports_without_writing(tenant, capsys):
    engine, pg_url = tenant
    assert _run(pg_url, "--status") == 0
    out = capsys.readouterr().out
    assert "L1 semantic" in out and "WOULD FLIP" not in out
    assert not any(script._state(engine, ORG).values())


def test_a_typo_in_a_domain_is_refused_before_anything_is_written(tenant):
    """Fail on the NAME, not on the row. `admn` would otherwise be a tenant that reads as
    activated and compiles nothing."""
    engine, pg_url = tenant
    with pytest.raises(ValueError):
        _run(pg_url, "--apply", "--domains", "admn")
    # L1 and L2 come first in the plan, so the refusal must not leave them half-flipped: the
    # selection is resolved before any write.
    assert not any(script._state(engine, ORG).values())
