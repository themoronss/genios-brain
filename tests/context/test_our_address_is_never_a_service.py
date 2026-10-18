"""STEP-04 · an address of ours is a person, never a `service`.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_our_address_is_never_a_service.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U15`. `context/pipeline._person` typed every
`is_platform_sender` address a `service`, and `settings.platform_domains` is `thegenios.com` —
GeniOS's own product domain, which is ALSO the design partner's company domain. So
`ceo@thegenios.com`, an address of the founder's that only ever receives his own mail, became a
service node, and `find_or_create_node` never re-types a node, so it stayed one.

The rule, as the plan decides it (`STEP-04` §8.5): an exact address of ours — a seat, `orgs.email`, a
connected account, a declared address; `runner._internal_emails`, the identity's addresses — is a
person. The product's own mail (`invite@thegenios.com`) stays a `service` even though the declared
domain makes it "us": only declared addresses are re-typed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from genios_engine.context.runner import _internal_emails
from genios_engine.platform.self_identity import identity_for

pytestmark = pytest.mark.pg

ORG = "our_address_never_a_service_org"
NOW = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
FOUNDER = "mrrohitswerashi@gmail.com"      # orgs.email — the connected Gmail
DECLARED = "ceo@thegenios.com"             # 06 D6: only ever receives the founder's own mail
COFOUNDER = "harsh@thegenios.com"          # a seat, on the same domain
PRODUCT = "invite@thegenios.com"           # GeniOS's own product mail, never declared
INVESTOR = "priya@northwind.test"
BODY = "Sharing our seed deck ahead of Thursday."


def _reset(store) -> None:
    """An empty graph for this tenant — through the production erasure list, because a node left by
    an earlier run would be found, not created, and `find_or_create_node` never re-types it."""
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
        c.execute(text("insert into org_seats (org_id, seat_id, email, active) "
                       "values (:o, 'seat_cofounder', :e, true)"), {"o": ORG, "e": COFOUNDER})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', :a, 'D6'), (:o, 'domain', 'thegenios.com', 'D6')"),
                  {"o": ORG, "a": DECLARED})
    yield pg_store
    _reset(pg_store)


def _nothing_extracted() -> Extraction:
    return Extraction(ok=True, relevance=0.9, noise_type="none", domains=[], entity_mentions=[],
                      fact_candidates=[], commitments=[], questions=[], observations=[])


def _process(store, *, event_id: str, sender: str, recipients: list[str], inbound: bool):
    """One mail, handed to the pipeline the way the drain hands it: "us" is `_internal_emails`."""
    return pipeline.process_event(
        org_id=ORG, event_id=event_id, source="gmail", content=BODY, sender_email=sender,
        recipient_emails=recipients, occurred_at=NOW, llm=None, store=store,
        is_inbound=inbound, internal_emails=_internal_emails(store, ORG),
        thread_id=f"thr_{event_id}", qualified_extraction=_nothing_extracted())


def _type_of(store, address: str) -> str | None:
    with store.engine.connect() as c:
        return c.execute(text("select node_type from graph_nodes where org_id = :o "
                              "and canonical_key = :k and valid_to is null"),
                         {"o": ORG, "k": address}).scalar()


def test_the_premise_our_company_domain_is_the_platform_domain():
    """Why the defect exists at all: both addresses are platform senders by configuration."""
    assert pipeline.is_platform_sender(DECLARED) and pipeline.is_platform_sender(PRODUCT)


def test_a_declared_address_on_the_platform_domain_is_a_person(store):
    """The production case: the founder writes to an investor and copies his own second address."""
    _process(store, event_id="evt_u15_declared", sender=FOUNDER,
             recipients=[INVESTOR, DECLARED], inbound=False)
    assert _type_of(store, DECLARED) == "person", (
        "an address the tenant declared as its own was typed a service because its domain is "
        "also the platform's")
    assert _type_of(store, INVESTOR) == "person"


def test_a_seat_on_the_platform_domain_is_a_person(store):
    """Whatever the source of the address — a seat here — an exact address of ours is a person."""
    _process(store, event_id="evt_u15_seat", sender=COFOUNDER, recipients=[INVESTOR],
             inbound=False)
    assert _type_of(store, COFOUNDER) == "person"


def test_the_products_own_mail_stays_a_service(store):
    """`invite@thegenios.com` is "us" by the declared domain, and still a service: it is GeniOS's
    onboarding mail, not a person, and only declared addresses are re-typed (§8.5)."""
    assert identity_for(store, ORG).is_us(PRODUCT)
    _process(store, event_id="evt_u15_product", sender=PRODUCT, recipients=[FOUNDER],
             inbound=True)
    assert _type_of(store, PRODUCT) == "service"
