"""STEP-04 · the backfill reads the identity — live and rebuild stop disagreeing about our company.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_backfill_reads_the_identity.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U09`. Two passes in `context/backfill` decided "us" on their
own, each from a narrower source than the live pipeline:

  * the correlation rebuild excluded ACTIVE SEATS only — so on a rebuild the founder's own
    `orgs.email` node, and the tenant's own company, anchored situations the live path keeps out;
  * the deal backfill took the domains of the active seats as our company — never a declared one.

Both now read `platform/self_identity.identity_for`: a node of ours is a person by its address (or a
declared domain), a company by a declared domain (`SelfIdentity.is_us_node`).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.backfill import backfill_correlations, backfill_deal_nodes

pytestmark = pytest.mark.pg

ORG = "backfill_reads_identity_org"
NOW = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
FOUNDER = "founder.backfill@gmail.com"       # orgs.email — not a seat
OURS = "nimbusbackfill.test"                 # the declared company domain
COLLEAGUE = "ops@nimbusbackfill.test"        # at our domain; not a seat, not declared
INVESTOR = "priya@northwind.test"
THEIRS = "northwind.test"
ANGEL = "angel.investor@gmail.com"           # a person with no company


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        _wipe(c, ORG)
        for tbl in ("context_correlation_members", "context_situations", "context_correlations"):
            c.execute(text(f"delete from {tbl} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def store(pg_store):
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": ORG, "e": FOUNDER})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'domain', :d, 'test')"), {"o": ORG, "d": OURS})
    yield pg_store
    _reset(pg_store)


def _event(store, event_id: str, *nodes: tuple[str, str]) -> dict[str, str]:
    """An emitted event and the nodes it created — the material the rebuild reads back."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, outcome, parent_object_id) "
            "values (:e, :o, 'conn_u09', 'gmail', 'email_message', :e, :e, '{}'::jsonb, :t, "
            "'emitted', :thr)"), {"e": event_id, "o": ORG, "t": NOW, "thr": f"thr_{event_id}"})
        return {key: store.find_or_create_node(c, org_id=ORG, node_type=kind, canonical_key=key,
                                               display_name=key, event_id=event_id)
                for kind, key in nodes}


def _anchors(store, event_id: str) -> set[str]:
    with store.engine.connect() as c:
        return {r.canonical_key for r in c.execute(text(
            "select n.canonical_key from context_correlation_members m "
            "  join context_correlations k on k.org_id = m.org_id "
            "       and k.correlation_id = m.correlation_id "
            "  join graph_nodes n on n.org_id = k.org_id and n.node_id = k.anchor_node_id "
            "       and n.valid_to is null "
            " where m.org_id = :o and m.event_id = :e"), {"o": ORG, "e": event_id})}


def test_the_rebuild_never_anchors_on_our_company(store):
    """The live pipeline keeps a declared domain's company out of the anchors; the rebuild did
    not, and re-derived every such situation onto us."""
    _event(store, "evt_u09_company", ("person", INVESTOR), ("company", THEIRS),
           ("person", COLLEAGUE), ("company", OURS))
    backfill_correlations(store, ORG, rebuild=True)
    anchors = _anchors(store, "evt_u09_company")
    assert OURS not in anchors, f"the rebuild anchored on our own company: {sorted(anchors)}"
    assert anchors == {THEIRS}


def test_the_rebuild_never_anchors_on_the_founder(store):
    """The founder is `orgs.email`, not a seat: the live path's self set always held him, the
    rebuild's did not."""
    _event(store, "evt_u09_founder", ("person", FOUNDER), ("person", ANGEL))
    backfill_correlations(store, ORG, rebuild=True)
    anchors = _anchors(store, "evt_u09_founder")
    assert FOUNDER not in anchors, f"the rebuild anchored on the founder: {sorted(anchors)}"
    assert anchors == {ANGEL}


def test_the_deal_backfill_puts_no_deal_on_our_company(store):
    """A `deal.*` fact misfiled on one of our own people must not become `<our company> — deal`.
    The outside account in the same history still gets its deal."""
    ids = _event(store, "evt_u09_deal", ("person", COLLEAGUE), ("company", OURS),
                 ("person", INVESTOR), ("company", THEIRS))
    with store.engine.begin() as c:
        for person, company in ((COLLEAGUE, OURS), (INVESTOR, THEIRS)):
            store.write_edge(c, org_id=ORG, edge_type="works_at", from_node_id=ids[person],
                             to_node_id=ids[company], confidence=0.9, occurred_at=NOW,
                             event_id="evt_u09_deal", evidence={"derived": "email domain"},
                             source="gmail")
            store.write_fact(c, org_id=ORG, subject_node_id=ids[person], field="deal.status",
                             value="open", value_type="string", confidence=0.9,
                             occurred_at=NOW, event_id="evt_u09_deal",
                             evidence={"text": "the deal is open"}, source="gmail",
                             authority_rank=2)

    out = backfill_deal_nodes(store, ORG)

    with store.engine.connect() as c:
        deals = {r.canonical_key for r in c.execute(text(
            "select canonical_key from graph_nodes where org_id = :o and node_type = 'deal' "
            "and valid_to is null"), {"o": ORG})}
    assert f"deal:{ids[OURS]}" not in deals, "the backfill minted a deal on our own company"
    assert deals == {f"deal:{ids[THEIRS]}"}
    assert out["deal_facts_orphaned"] == 1, "the fact on our own person stays where it was"
