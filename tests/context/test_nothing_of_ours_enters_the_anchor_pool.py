"""STEP-04 · nothing of ours enters the anchor pool, whichever door it came through.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_nothing_of_ours_enters_the_anchor_pool.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U20`, found by U16's own probe. `_person` and `_works_at` ask
who we are as they make a node, because they hold an address. Three other doors put an EXISTING node
in the pool with no address in hand, and asked nobody:

  * a company named in prose — `resolve_company_mention`: a Gmail founder's pitch that names his own
    company anchored the thread on it;
  * a claim's subject — `_business_subject`: an investor's "a term sheet for Nimbus Labs" minted
    "<our company> — deal" instead of a deal with the investor;
  * a person known only by name (`resolve_person_name`) and a transcript speaker take the same road;
    no case here reaches them, because one observation of a name does not make it resolvable — the
    check below is the pool's, so it covers them without one.

Now the pool is checked once more, by each node's own key, before it is handed to correlation; and a
deal claim whose subject is ours is re-targeted to the one outside company in the event, which
`_deal_for` already does for an internal subject — or to nobody when that is ambiguous.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.platform.self_identity import identity_for

pytestmark = pytest.mark.pg

ORG = "nothing_of_ours_anchors_org"
NOW = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
FOUNDER = "founder.kite@gmail.com"          # orgs.email — a Gmail founder
OURS, OUR_NAME = "kitebirdlabs.test", "Kitebird Labs"   # the domain the tenant declared, and its name
COLLEAGUE, COLLEAGUE_NAME = "ops@kitebirdlabs.test", "Devika Rao"
INVESTOR = "ira@northwind.test"
THEIRS = "northwind.test"


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


def _mention(kind: str, name: str, email: str | None = None) -> dict:
    """An entity mention as L1 hands it: grounded by its own words in the body (`keep_grounded`)."""
    return {"type": kind, "name": name, "evidence_text": name, **({"email": email} if email else {})}


def _extraction(*, mentions=(), claims=()) -> Extraction:
    return Extraction(ok=True, relevance=0.9, noise_type="none", domains=[],
                      entity_mentions=list(mentions), fact_candidates=list(claims), commitments=[],
                      questions=[], observations=[])


def _claim(body: str, quote: str, *, subject: str, field: str, value: str) -> dict:
    start = body.index(quote)
    span = EvidenceSpan(source_ref="evt", quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=True)
    return {"subject": subject, "field": field, "value": value, "standing": "observed",
            "business_fact": True, "evidence_text": quote,
            "evidence_spans": [span.model_dump(mode="json")]}


def _process(store, *, event_id: str, sender: str, recipients: list[str], inbound: bool,
             body: str, extraction: Extraction) -> None:
    """One mail, handed over the way the drain hands it."""
    us = identity_for(store, ORG)
    pipeline.process_event(
        org_id=ORG, event_id=event_id, source="gmail", content=body, sender_email=sender,
        recipient_emails=recipients, occurred_at=NOW, llm=None, store=store,
        is_inbound=inbound, internal_emails=us.addresses, self_identity=us,
        thread_id=f"thr_{event_id}", qualified_extraction=extraction)


def _our_company_exists(store) -> None:
    """An earlier mail copies a colleague at our domain: our company node exists, and the colleague
    is known by name — so later prose can reach both."""
    body = "Looping in Devika from our side for the diligence call."
    _process(store, event_id="evt_u20_seed", sender=INVESTOR, recipients=[FOUNDER, COLLEAGUE],
             inbound=True, body=body, extraction=_extraction(mentions=[
                 _mention("person", COLLEAGUE_NAME, COLLEAGUE)]))


def _anchors(store, event_id: str) -> set[str]:
    with store.engine.connect() as c:
        return {r.canonical_key for r in c.execute(text(
            "select n.canonical_key from context_correlation_members m "
            "  join context_correlations k on k.org_id = m.org_id "
            "       and k.correlation_id = m.correlation_id "
            "  join graph_nodes n on n.org_id = k.org_id and n.node_id = k.anchor_node_id "
            "       and n.valid_to is null "
            " where m.org_id = :o and m.event_id = :e"), {"o": ORG, "e": event_id})}


def _deal_on(store, domain: str) -> bool:
    with store.engine.connect() as c:
        return c.execute(text(
            "select 1 from graph_nodes d join graph_nodes c "
            "    on c.org_id = d.org_id and d.canonical_key = 'deal:' || c.node_id "
            " where d.org_id = :o and d.node_type = 'deal' and d.valid_to is null "
            "   and c.node_type = 'company' and c.canonical_key = :k"),
            {"o": ORG, "k": domain}).first() is not None


def test_a_company_of_ours_named_in_prose_does_not_anchor(store):
    """The founder's own pitch names his company; the investor's firm is the only anchor."""
    _our_company_exists(store)
    body = f"Sharing the {OUR_NAME} deck ahead of our call."
    _process(store, event_id="evt_u20_prose", sender=FOUNDER, recipients=[INVESTOR],
             inbound=False, body=body,
             extraction=_extraction(mentions=[_mention("company", OUR_NAME)]))
    anchors = _anchors(store, "evt_u20_prose")
    assert OURS not in anchors, f"our own company, named in prose, anchored: {sorted(anchors)}"
    assert anchors == {THEIRS}


def test_a_claim_about_our_company_puts_the_deal_on_the_counterparty(store):
    """"A term sheet for Kitebird Labs" is a deal WITH the investor, not one on us."""
    _our_company_exists(store)
    quote = f"a term sheet for {OUR_NAME}"
    body = f"We are preparing {quote} this week."
    _process(store, event_id="evt_u20_deal", sender=INVESTOR, recipients=[FOUNDER], inbound=True,
             body=body, extraction=_extraction(claims=[
                 _claim(body, quote, subject=OUR_NAME, field="deal.stage", value="term sheet")]))
    assert not _deal_on(store, OURS), "a deal was minted on our own company"
    assert _deal_on(store, THEIRS), "the claim found no deal with the investor's firm"
    anchors = _anchors(store, "evt_u20_deal")
    assert OURS not in anchors, f"our own company anchored the deal thread: {sorted(anchors)}"


def test_an_outside_company_named_in_prose_still_anchors(store):
    """The check removes only us: a firm we know, named in prose, is still a counterparty."""
    _our_company_exists(store)           # also makes northwind.test a known company
    body = "Northwind asked for the updated deck."
    _process(store, event_id="evt_u20_theirs", sender=FOUNDER, recipients=["sam@lumen.test"],
             inbound=False, body=body,
             extraction=_extraction(mentions=[_mention("company", "Northwind")]))
    assert THEIRS in _anchors(store, "evt_u20_theirs")
