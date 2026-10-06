"""STEP-04 · a thread is named after its OTHER side — never after us.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_thread_is_named_after_the_other_side.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U17` ⛔. `context/pipeline` names a thread
`"<who> — <what it is for>"` at the one moment both are in hand — the message carrying its
`thread.objective` claim — and it took `<who>` from that message's SENDER whatever the direction.
So the founder's own outbound pitch named the thread after the founder, and `name_thread_node`
never renames a label it did not generate: production holds threads frozen as
"Mr Rohit Swerashi — <the pitch>" (STEP-04 §8.2).

Now `<who>` is the first party of the message who is not us — the sender of an inbound mail, the
first outside recipient of an outbound one — and a conversation only among us is named by what it is
for alone (`graph_store.thread_label` without a counterparty).
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

ORG = "thread_named_after_other_side_org"
NOW = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
FOUNDER, FOUNDER_NAME = "mrrohitswerashi@gmail.com", "Mr Rohit Swerashi"   # orgs.email
SECOND = "ceo@thegenios.com"                     # declared: only receives the founder's mail
COLLEAGUE, COLLEAGUE_NAME = "harsh@thegenios.com", "Harsh"   # at the declared domain only
INVESTOR, INVESTOR_NAME = "priya@northwind.test", "Priya Sharma"
QUOTE = "this thread is about our seed round"
BODY = f"Hi, {QUOTE}. The deck is attached."
OBJECTIVE = "Seed round for GeniOS"


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
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', :a, 'D6'), (:o, 'domain', 'thegenios.com', 'D6')"),
                  {"o": ORG, "a": SECOND})
    yield pg_store
    _reset(pg_store)


def _what_it_is_for() -> Extraction:
    """The claim L1 hands over: a `thread.objective`, with a span verified against the body."""
    start = BODY.index(QUOTE)
    span = EvidenceSpan(source_ref="evt", quote=QUOTE, start_offset=start,
                        end_offset=start + len(QUOTE), verified=True)
    claim = {"subject": "thread", "field": "thread.objective", "value": OBJECTIVE,
             "standing": "observed", "business_fact": True, "evidence_text": QUOTE,
             "evidence_spans": [span.model_dump(mode="json")]}
    return Extraction(ok=True, relevance=0.9, noise_type="none", domains=[], entity_mentions=[],
                      fact_candidates=[claim], commitments=[], questions=[], observations=[])


def _label(store, *, sender: str, sender_name: str | None, recipients: list[str],
           inbound: bool, thread: str) -> str:
    """One message, handed over the way the drain hands it; returns the thread's name."""
    us = identity_for(store, ORG)
    pipeline.process_event(
        org_id=ORG, event_id=f"evt_{thread}", source="gmail", content=BODY,
        sender_email=sender, sender_name=sender_name, recipient_emails=recipients,
        occurred_at=NOW, llm=None, store=store, is_inbound=inbound,
        internal_emails=us.addresses, self_identity=us, thread_id=thread,
        qualified_extraction=_what_it_is_for())
    with store.engine.connect() as c:
        return c.execute(text("select display_name from graph_nodes where org_id = :o "
                              "and canonical_key = :k and valid_to is null"),
                         {"o": ORG, "k": f"thread:{thread}"}).scalar()


def test_the_founders_own_pitch_is_named_after_the_investor(store):
    """The production defect: an outbound pitch named the thread after the founder."""
    label = _label(store, sender=FOUNDER, sender_name=FOUNDER_NAME, recipients=[INVESTOR],
                   inbound=False, thread="thr_u17_pitch")
    assert label == f"{INVESTOR} — {OBJECTIVE}", f"named after us: {label!r}"


def test_an_inbound_ask_is_named_after_its_sender(store):
    """Unchanged where it was right: the other side of an inbound mail is the one who wrote it."""
    label = _label(store, sender=INVESTOR, sender_name=INVESTOR_NAME, recipients=[FOUNDER],
                   inbound=True, thread="thr_u17_ask")
    assert label == f"{INVESTOR_NAME} — {OBJECTIVE}"


def test_the_first_party_who_is_not_us_names_it(store):
    """Our own second address first on the To line is skipped, not taken as the other side."""
    label = _label(store, sender=FOUNDER, sender_name=FOUNDER_NAME,
                   recipients=[SECOND, INVESTOR], inbound=False, thread="thr_u17_cc")
    assert label == f"{INVESTOR} — {OBJECTIVE}", f"named after us: {label!r}"


def test_a_colleague_at_our_domain_never_names_it(store):
    """A colleague we know only by the declared domain is still us."""
    label = _label(store, sender=COLLEAGUE, sender_name=COLLEAGUE_NAME, recipients=[INVESTOR],
                   inbound=False, thread="thr_u17_colleague")
    assert label == f"{INVESTOR} — {OBJECTIVE}", f"named after us: {label!r}"


def test_a_thread_only_among_us_is_named_by_what_it_is_for(store):
    """No other side: the objective alone, which is a true name — ours would be a false one."""
    label = _label(store, sender=FOUNDER, sender_name=FOUNDER_NAME, recipients=[SECOND],
                   inbound=False, thread="thr_u17_internal")
    assert label == OBJECTIVE, f"named after us: {label!r}"
