"""STEP-04 · a company whose domain is ours never anchors, in any event.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_our_company_never_anchors.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U16`. `context/pipeline._works_at` mints a `company` node for
every non-personal address domain, and kept it out of the anchors only when the address that
reached it was in the self set or was a platform address. So the tenant's OWN company — a domain it
declared (`org_self_identities`, 06 D6) — anchored a situation in every event where a colleague's
address at it was not individually known: a Gmail founder copying `ops@nimbuslabs.test` filed an
investor's thread under his own company.

Now a declared domain, or a subdomain of one, is ours in every event: its company is excluded from
the anchors, and so is the person at it — `correlate_event` lifts each remaining person to the company
of their address's domain, so a colleague left in the pool would bring the company straight back.
The drain reads the identity once per sweep and hands it to the pipeline, the declared domains with
the addresses.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.context import pipeline, runner
from genios_engine.context.extract.extractor import Extraction
from genios_engine.platform.self_identity import identity_for

pytestmark = pytest.mark.pg

ORG = "our_company_never_anchors_org"
NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
FOUNDER = "founder.nimbus@gmail.com"        # orgs.email — a Gmail founder
OURS = "nimbuslabs.test"                    # the company domain the tenant declared
COLLEAGUE = "ops@nimbuslabs.test"           # at our domain; neither a seat nor declared
SUB_COLLEAGUE = "team@eu.nimbuslabs.test"   # at a subdomain of ours
INVESTOR = "priya@northwind.test"
THEIRS = "northwind.test"
BODY = "Following up on the seed round — can we find time this week?"


def _reset(store) -> None:
    """An empty graph and no correlations for this tenant, through the production erasure list."""
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


def _nothing_extracted() -> Extraction:
    return Extraction(ok=True, relevance=0.9, noise_type="none", domains=[], entity_mentions=[],
                      fact_candidates=[], commitments=[], questions=[], observations=[])


def _process(store, *, event_id: str, sender: str, recipients: list[str], inbound: bool):
    """One mail, handed over the way the drain hands it: the identity read once, its addresses as
    the self set, and the identity itself."""
    us = identity_for(store, ORG)
    return pipeline.process_event(
        org_id=ORG, event_id=event_id, source="gmail", content=BODY, sender_email=sender,
        recipient_emails=recipients, occurred_at=NOW, llm=None, store=store,
        is_inbound=inbound, internal_emails=us.addresses, self_identity=us,
        thread_id=f"thr_{event_id}", qualified_extraction=_nothing_extracted())


def _anchors(store, event_id: str) -> set[str]:
    """The canonical keys of the nodes this event's situations are anchored on."""
    with store.engine.connect() as c:
        return {r.canonical_key for r in c.execute(text(
            "select n.canonical_key from context_correlation_members m "
            "  join context_correlations k on k.org_id = m.org_id "
            "       and k.correlation_id = m.correlation_id "
            "  join graph_nodes n on n.org_id = k.org_id and n.node_id = k.anchor_node_id "
            "       and n.valid_to is null "
            " where m.org_id = :o and m.event_id = :e"), {"o": ORG, "e": event_id})}


def test_a_colleague_at_our_domain_does_not_file_the_thread_under_us(store):
    """The investor writes to the founder and copies a colleague the engine does not know by
    address. The investor's company is the anchor; ours is not one, directly or through the lift."""
    _process(store, event_id="evt_u16_colleague", sender=INVESTOR,
             recipients=[FOUNDER, COLLEAGUE], inbound=True)
    anchors = _anchors(store, "evt_u16_colleague")
    assert OURS not in anchors, f"the thread was anchored on our own company: {sorted(anchors)}"
    assert anchors == {THEIRS}


def test_a_subdomain_of_ours_is_ours(store):
    """`eu.nimbuslabs.test` is a subdomain of a declared domain, and the identity says so."""
    _process(store, event_id="evt_u16_subdomain", sender=FOUNDER,
             recipients=[INVESTOR, SUB_COLLEAGUE], inbound=False)
    anchors = _anchors(store, "evt_u16_subdomain")
    assert not {OURS, "eu.nimbuslabs.test"} & anchors, (
        f"a company at a subdomain of ours anchored: {sorted(anchors)}")
    assert anchors == {THEIRS}


def test_a_lookalike_domain_is_not_ours(store):
    """Only our domain and its subdomains: `notnimbuslabs.test` is somebody else's company."""
    _process(store, event_id="evt_u16_lookalike", sender="ceo@notnimbuslabs.test",
             recipients=[FOUNDER], inbound=True)
    assert _anchors(store, "evt_u16_lookalike") == {"notnimbuslabs.test"}


def test_the_drain_hands_the_identity_to_the_pipeline(store, monkeypatch):
    """The production path: `process_pending` reads the identity once and every event's
    `process_event` receives it — the declared domains included, which the self set cannot carry."""
    from genios_engine.platform.config import get_settings

    row = SimpleNamespace(
        event_id="evt_u16_drain", source="gmail", object_type="email_message", sender=INVESTOR,
        sender_name=None, occurred_at=NOW, source_object_id="obj_u16_drain", triage_lane=None,
        internal_kind=None, parent_object_id="thr_u16_drain", domain_hints=None,
        qes_confidence_bp=9000, qes_signal_types=[], qes_domain_hints=[],
        qes_output={"stub": "replaced by the adapter double"}, enc_content=None,
        prepared_text=None)
    batches = [[row]]
    received: list[dict] = []

    def _process_event(**kwargs):
        received.append(kwargs)
        return pipeline.L2Result(kwargs["event_id"], "committed")

    monkeypatch.setattr(runner, "_pull", lambda *a, **kw: batches.pop(0) if batches else [])
    monkeypatch.setattr(runner, "adapt_qes_extraction", lambda *a, **kw: _nothing_extracted())
    monkeypatch.setattr(runner, "process_event", _process_event)
    monkeypatch.setattr(runner, "_record_done", lambda *a, **kw: None)

    runner.process_pending(org_id=ORG, store=store, llm=None,
                           crypto_key=get_settings().crypto_key, max_total=1)

    assert len(received) == 1, "the event never reached the pipeline"
    us = received[0].get("self_identity")
    assert us is not None and us == identity_for(store, ORG), (
        "the pipeline was not handed the identity, so it cannot know our declared domains")
    assert us.domains == frozenset({OURS})
    assert received[0]["internal_emails"] == us.addresses
