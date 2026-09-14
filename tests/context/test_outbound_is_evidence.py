"""What WE send is evidence about the person we sent it to.

THE DEFECT THIS PINS. `write_event_presence` gave every outbound recipient exactly one
`event_presence` row — a marker saying "an event touched this node" and nothing else. So a
founder who wrote to Peak XV twice produced, on Peak XV's node, two content-free markers, while
every commitment, question and observation in those mails was filed against the founder's OWN
node. Measured on the pilot: 398 of 1001 observations sit on the mailbox owner, and 30 of 60
people carry zero — the exact people who never replied, i.e. the subject of every "they have gone
quiet" card.

`evidence_score` counts observations on the situation's anchor. An anchor about somebody we have
only ever WRITTEN to therefore scored zero, and the publisher held it. The work we did was not
counted as knowledge about the relationship it was done in.

WHAT THIS DOES NOT CHANGE, and the distinction is the whole design. A recipient still never
becomes the SPEAKER of words they did not write. `test_outbound_recipient_observations.py` exists
to protect that and its intent is correct; this unit keeps it by carrying the content under a
`received:` kind that can never be read as something they said, with `speaker_node_id` naming who
actually wrote it. "They were told this" and "they said this" stay different rows.
"""
import json

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from genios_engine.context.graph_store import GraphStore

from .test_event_presence_store import presence_schema
from .test_support_derived_provenance import NOW

OWNER = "owner@gmail.com"
THEM = "vidushi@peakxv.com"
ALSO = "harshita@peakxv.com"


def _store(monkeypatch, engine):
    store = object.__new__(GraphStore)
    store._engine = engine
    with engine.begin() as c:
        presence_schema(c)
    for method in ("write_fact", "write_edge", "write_change"):
        monkeypatch.setattr(store, method, lambda *a, **kw: None)
    monkeypatch.setattr(store, "bump_version", lambda *a: 1)
    monkeypatch.setattr(store, "find_or_create_node", lambda *a, **kw: kw["canonical_key"])
    monkeypatch.setattr(pipeline, "correlate_event", lambda *a, **kw: [])
    monkeypatch.setattr(pipeline, "close_loops_for_reply", lambda *a, **kw: None)
    monkeypatch.setattr(pipeline, "record_ask", lambda *a, **kw: "loop")
    monkeypatch.setattr(pipeline, "resolve_canon_mention", lambda *a, **kw: None)
    return store


def _send(store, ex, body, *, recipients=(THEM, ALSO), inbound=False):
    return dict(org_id="o", event_id="e", source="gmail", content=body,
                sender_email=OWNER, recipient_emails=list(recipients),
                internal_emails=frozenset({OWNER}), occurred_at=NOW,
                llm=None, store=store, qualified_extraction=ex, is_inbound=inbound)


def _rows(engine, subject):
    with engine.connect() as c:
        return c.execute(text(
            "select ob.observation_id, ob.kind, r.evidence from graph_observations ob "
            "left join graph_source_refs r on r.observation_id = ob.observation_id "
            "where ob.subject_node_id = :s order by ob.kind"), {"s": subject}).mappings().all()


BODY = "We would love your view on the deck — could you take a look this week?"


def _extraction(path):
    ex = Extraction(ok=True, relevance=0.9, noise_type="none", domains=[], entity_mentions=[],
                    fact_candidates=[], commitments=[], questions=[], observations=[])
    if path == "observation":
        ex.observations = [{"kind": "review_requested", "evidence_text": BODY}]
    if path == "question":
        ex.questions = [{"evidence_text": BODY, "directed_at": THEM}]
    return ex


@pytest.mark.parametrize("path", ["observation", "question"])
def test_the_content_we_sent_reaches_the_person_we_sent_it_to(monkeypatch, path):
    """Every recipient carries the substance of our mail, not merely a marker that one arrived."""
    engine = create_engine("sqlite://")
    store = _store(monkeypatch, engine)
    pipeline.process_event(**_send(store, _extraction(path), BODY))

    for who in (THEM, ALSO):
        kinds = {r["kind"] for r in _rows(engine, who)}
        assert any(k.startswith("received:") for k in kinds), (
            f"{who} carries only {kinds} — the substance of a mail we sent them is still "
            "filed against our own node, so an anchor about them scores zero evidence")
    engine.dispose()


@pytest.mark.parametrize("path", ["observation", "question"])
def test_a_recipient_is_never_made_the_speaker(monkeypatch, path):
    """The protected half: they were TOLD this, they did not SAY it."""
    engine = create_engine("sqlite://")
    store = _store(monkeypatch, engine)
    pipeline.process_event(**_send(store, _extraction(path), BODY))

    for who in (THEM, ALSO):
        for row in _rows(engine, who):
            assert row["kind"] == "event_presence" or row["kind"].startswith("received:"), (
                f"{who} carries {row['kind']!r}, which reads as something they said")
            evidence = json.loads(row["evidence"]) if row["evidence"] else {}
            if row["kind"].startswith("received:"):
                assert evidence.get("speaker_node_id") == OWNER, (
                    "a received row must name who actually wrote the words")
    engine.dispose()


def test_an_inbound_mail_gives_its_recipients_nothing_new(monkeypatch):
    """Only OUR sending is our work. A mail they sent is already evidence about them."""
    engine = create_engine("sqlite://")
    store = _store(monkeypatch, engine)
    ex = _extraction("observation")
    pipeline.process_event(**_send(store, ex, BODY, recipients=[OWNER], inbound=True))

    with engine.connect() as c:
        received = c.execute(text(
            "select count(*) from graph_observations where kind like 'received:%'")).scalar()
    assert received == 0, "an inbound mail must not mint received rows for its recipients"
    engine.dispose()


def test_replay_writes_each_received_row_once(monkeypatch):
    """A re-sync must not inflate the evidence count it feeds."""
    engine = create_engine("sqlite://")
    store = _store(monkeypatch, engine)
    kwargs = _send(store, _extraction("observation"), BODY)
    pipeline.process_event(**kwargs)
    first = len(_rows(engine, THEM))
    pipeline.process_event(**kwargs)
    assert len(_rows(engine, THEM)) == first, "replay duplicated the recipient's evidence"
    engine.dispose()
