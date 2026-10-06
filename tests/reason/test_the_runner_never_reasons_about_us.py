"""STEP-04 · U02 — the runner never reasons about us.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_the_runner_never_reasons_about_us.py -q

`reason/runner.run` kept the account owner out of the subjects it reasons about by re-writing the
tenant SQL itself (`orgs.email` ∪ the active seats ∪ `connections.external_account_id`) and matching
a node's key against those addresses alone. So an address of ours that is none of the three — the
founder's declared `ceo@thegenios.com` — an address at the domain we declared, and the company node
whose domain is ours were all reasoned about as counterparties: the cards that tell the founder to
chase himself (`speedrun008/YC-II W27/` STEP-04 §8.2).

It asks the one answer now — `platform/self_identity.identity_for(...).is_us_node(node_type,
canonical_key)` (tree `yc2_w27_s04/M22.C2.L-logic.V2.U02`). The witness is the runner's own: a
subject it reasons about has its context loaded (`_load_context`); one it refuses as us is counted
`self_excluded`.
"""
from __future__ import annotations

import ast
import inspect
import os
import textwrap
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg

ORG = "s04_runner_never_us"
NOW = datetime(2026, 10, 6, 9, tzinfo=timezone.utc)
#: `orgs.email` is UNIQUE across the scratch database: an address no other test seeds.
OWNER = "Founder.S04Runner@gmail.com"

#: node_id → (node_type, canonical_key). Ours: the runner must refuse every one of them as a subject.
OURS = {
    "nd_s04_owner": ("person", "founder.s04runner@gmail.com"),  # orgs.email — excluded before STEP-04
    "nd_s04_ceo": ("person", "ceo@thegenios.com"),              # a declared address, in no seat
    "nd_s04_cofounder": ("person", "harsh@thegenios.com"),      # an address at the declared domain
    "nd_s04_company": ("company", "thegenios.com"),             # the company whose domain is ours
}
#: Theirs: still subjects. `gmail.com` is the owner's mail host — a Gmail founder is not gmail.com.
THEIRS = {
    "nd_s04_priya": ("person", "priya@acme.test"),
    "nd_s04_acme": ("company", "acme.test"),
    "nd_s04_gmail": ("company", "gmail.com"),
}


@pytest.fixture(scope="module")
def swept(pg_store):
    """One real sweep of the default pack over a tenant that declared `ceo@thegenios.com` and
    `thegenios.com`; returns the run's result and every node id whose context was loaded."""
    from genios_engine.packs.wiring import make_registry
    from genios_engine.reason import runner
    from tests.test_e2e_all_layers import _fresh_tenant, _seed_org

    _seed_org(pg_store, ORG)
    _fresh_tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        c.execute(text("update orgs set email = :e where id = :o"), {"o": ORG, "e": OWNER})
        for table in ("org_seats", "connections", "org_self_identities"):   # kept by /reset
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', 'ceo@thegenios.com', 'test'), "
                       "(:o, 'domain', 'thegenios.com', 'test')"), {"o": ORG})
        for node_id, (node_type, key) in {**OURS, **THEIRS}.items():
            c.execute(text("insert into graph_nodes (org_id, node_id, node_type, canonical_key) "
                           "values (:o, :n, :t, :k)"),
                      {"o": ORG, "n": node_id, "t": node_type, "k": key})

    evaluated: set[str] = set()
    original = runner._load_context

    def _recording(store, org_id, node_id, *args, **kwargs):
        evaluated.add(node_id)
        return original(store, org_id, node_id, *args, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(runner, "_load_context", _recording)
        result = runner.run(org_id=ORG, store=pg_store, eval_time=NOW,
                            registry=make_registry(os.environ["GENIOS_TEST_DATABASE_URL"]))
    with pg_store.engine.begin() as c:          # release the unique address for the next run
        c.execute(text("update orgs set email = null where id = :o"), {"o": ORG})
    assert result["nodes"] == len(OURS) + len(THEIRS), result     # the sweep ran, not a retry
    return result, evaluated


def test_a_declared_address_is_never_a_subject(swept):
    _, evaluated = swept
    assert "nd_s04_ceo" not in evaluated, (
        "ceo@thegenios.com is declared ours and was reasoned about as a counterparty")


def test_an_address_at_our_declared_domain_is_never_a_subject(swept):
    _, evaluated = swept
    assert "nd_s04_cofounder" not in evaluated, (
        "harsh@thegenios.com sits at the domain we declared and was reasoned about as a counterparty")


def test_the_owner_is_still_never_a_subject(swept):
    _, evaluated = swept
    assert "nd_s04_owner" not in evaluated


def test_every_node_of_ours_and_only_ours_is_counted_as_us(swept):
    """The company whose domain is ours is refused as us, not walked past as "no expertise"; the
    counterparty company and the owner's public mail host are not us."""
    result, _ = swept
    assert result["outcomes"].get("self_excluded", 0) == len(OURS), result["outcomes"]


def test_a_counterparty_is_still_reasoned_about(swept):
    """The negative control: the witness sees a subject the runner does reason about."""
    _, evaluated = swept
    assert "nd_s04_priya" in evaluated, evaluated


def test_the_runner_asks_the_one_answer_and_keeps_no_copy_of_it():
    """`run` reads who we are from `identity_for`; the seats/orgs/connections union is not written
    again here, so the runner and every other caller cannot disagree about who the tenant is."""
    from genios_engine.reason import runner

    tree = ast.parse(textwrap.dedent(inspect.getsource(runner.run)))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "identity_for" in called, "run() does not ask platform/self_identity who we are"
    sql = [n.value for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [s for s in sql if "external_account_id" in s], (
        "run() still carries its own copy of the tenant identity SQL")
