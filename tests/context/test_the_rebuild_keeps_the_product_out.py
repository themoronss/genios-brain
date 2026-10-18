"""STEP-04 · the correlation rebuild keeps GeniOS's own mail out of the anchors, as the live path does.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_the_rebuild_keeps_the_product_out.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U22`, found by U09's own report. The live pipeline keeps the
company of a platform address (`settings.platform_domains`, `thegenios.com`) out of every anchor
(`pipeline._works_at` — `is_platform_sender`), for every tenant. The rebuild
(`backfill_correlations(rebuild=True)`) asked only `platform/self_identity` — who the TENANT is — so a
tenant that never declared the product's domain had situations re-derived onto `thegenios.com` from
the product's own onboarding mail. The repair after STEP-04 runs that rebuild.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.backfill import backfill_correlations
from genios_engine.platform.config import get_settings

pytestmark = pytest.mark.pg

ORG = "rebuild_keeps_product_out_org"
NOW = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
FOUNDER = "founder.rebuild@gmail.com"
PRODUCT = get_settings().platform_domains.split(",")[0].strip().lower()
INVITE = f"invite@{PRODUCT}"
INVESTOR, THEIRS = "priya@northwind.test", "northwind.test"


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
    with pg_store.engine.begin() as c:       # a tenant that declared nothing
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": ORG, "e": FOUNDER})
    yield pg_store
    _reset(pg_store)


def _event(store, event_id: str, *nodes: tuple[str, str]) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, outcome, parent_object_id) "
            "values (:e, :o, 'conn_u22', 'gmail', 'email_message', :e, :e, '{}'::jsonb, :t, "
            "'emitted', :thr)"), {"e": event_id, "o": ORG, "t": NOW, "thr": f"thr_{event_id}"})
        for kind, key in nodes:
            store.find_or_create_node(c, org_id=ORG, node_type=kind, canonical_key=key,
                                      display_name=key, event_id=event_id)


def _anchors(store, event_id: str) -> set[str]:
    with store.engine.connect() as c:
        return {r.canonical_key for r in c.execute(text(
            "select n.canonical_key from context_correlation_members m "
            "  join context_correlations k on k.org_id = m.org_id "
            "       and k.correlation_id = m.correlation_id "
            "  join graph_nodes n on n.org_id = k.org_id and n.node_id = k.anchor_node_id "
            "       and n.valid_to is null "
            " where m.org_id = :o and m.event_id = :e"), {"o": ORG, "e": event_id})}


def test_the_products_own_mail_anchors_nothing_on_a_rebuild(store):
    _event(store, "evt_u22_invite", ("service", INVITE), ("company", PRODUCT))
    backfill_correlations(store, ORG, rebuild=True)
    anchors = _anchors(store, "evt_u22_invite")
    assert PRODUCT not in anchors, f"the rebuild anchored on the product itself: {sorted(anchors)}"


def test_a_counterparty_still_anchors_on_a_rebuild(store):
    _event(store, "evt_u22_investor", ("person", INVESTOR), ("company", THEIRS),
           ("company", PRODUCT))
    backfill_correlations(store, ORG, rebuild=True)
    assert _anchors(store, "evt_u22_investor") == {THEIRS}
