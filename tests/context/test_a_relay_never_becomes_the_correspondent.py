"""What Sehan wrote is Sehan's, even when Boardy delivered it.

`sender_node` answered two different questions at once — which address carried this, and who
spoke — and every content write in `process_event` took the second meaning from a variable that
only ever held the first. For an intro network that is not a rounding error: the reply is the most
valuable mail in the mailbox, and `thread.last_inbound` plus `thread.ball_in_court` landed on the
network, so the follow-up readings built on them said it was our turn WITH BOARDY and left the
person who actually wrote looking like somebody who never had.

`is_noise` does not cover this. It routes everything `_is_automated_sender` matches out of the
network graph and out of correlation — right for a newsletter, wrong for a relay, and it matches
an intro network's `hello@` local-part not at all.
"""
import pytest
from sqlalchemy import create_engine, text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from genios_engine.context.graph_store import GraphStore
from .test_event_presence_store import presence_schema
from .test_support_derived_provenance import NOW

OWNER = "owner@gmail.com"
RELAY = "hello@boardy.ai"
PARTY = "sehan@sanjula.io"


@pytest.fixture
def inbound(monkeypatch):
    """Drive one INBOUND message and hand back (observations, facts)."""
    def _run(*, sender, sender_name=None, headers=None, question=True):
        engine = create_engine("sqlite://")
        store = object.__new__(GraphStore)
        store._engine = engine
        facts: list[tuple] = []
        with engine.begin() as c:
            presence_schema(c)
        monkeypatch.setattr(store, "write_fact",
                            lambda *a, **kw: facts.append((kw.get("subject_node_id"),
                                                           kw.get("field"), kw.get("value"))))
        # `name_person_node` joins the list for the same reason the other two are on it: this
        # fixture stubs every store WRITE and asserts on the facts, and `find_or_create_node` is
        # stubbed to return the address itself as the node id — so a naming call would query
        # `graph_nodes` for a row that this schema never creates. What the relay tests are about
        # is which node the CONTENT lands on, which no label can change.
        for method in ("write_edge", "write_change", "name_person_node"):
            monkeypatch.setattr(store, method, lambda *a, **kw: None)
        monkeypatch.setattr(store, "bump_version", lambda *a: 1)
        monkeypatch.setattr(store, "find_or_create_node", lambda *a, **kw: kw["canonical_key"])
        monkeypatch.setattr(pipeline, "correlate_event", lambda *a, **kw: [])
        monkeypatch.setattr(pipeline, "close_loops_for_reply", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline, "close_loops_awaited_from", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline, "record_ask", lambda *a, **kw: "loop")
        monkeypatch.setattr(pipeline, "resolve_canon_mention", lambda *a, **kw: None)
        body = "Great to connect — could you share the deck?"
        ex = Extraction(ok=True, relevance=0.9, noise_type="none", domains=[],
                        entity_mentions=[], fact_candidates=[], commitments=[],
                        questions=[{"evidence_text": body}] if question else [],
                        observations=[])
        pipeline.process_event(
            org_id="o", event_id="e", source="gmail", content=body,
            sender_email=sender, sender_name=sender_name, recipient_emails=[OWNER],
            internal_emails=frozenset({OWNER}), occurred_at=NOW, thread_id="t1",
            llm=None, store=store, is_inbound=True,
            canon_meta={"headers": dict(headers or {})},
            qualified_extraction=ex)
        with engine.connect() as c:
            obs = c.execute(text(
                "select subject_node_id, kind from graph_observations")).all()
        return obs, facts
    return _run


def _subjects(obs, kind):
    return {row[0] for row in obs if row[1] == kind}


def _fact(facts, field):
    """Person-level writes only.

    The same block mirrors both facts onto the THREAD node ("and the same state on the THREAD,
    where it does not collide"). That write is not what this unit changed — a thread is a thread
    whoever delivered the message — so it is filtered out rather than asserted around, which
    would make these tests fail the day the thread substrate changes for reasons of its own.
    """
    return {(subject, value) for subject, f, value in facts
            if f == field and not str(subject or "").startswith("thread:")}


# ── the control: an ordinary correspondent is untouched ──────────────────────────────────────

def test_an_ordinary_sender_still_owns_everything_they_say(inbound) -> None:
    """The overwhelming majority of mail. Nothing about this path may change."""
    obs, facts = inbound(sender="harshita@peakxv.com", sender_name="Harshita Kaul")
    assert _subjects(obs, "question") == {"harshita@peakxv.com"}
    assert _fact(facts, "thread.ball_in_court") == {("harshita@peakxv.com", "us")}
    assert ("harshita@peakxv.com", "thread.last_inbound", NOW.isoformat()) in facts


# ── a relay that names its party ─────────────────────────────────────────────────────────────

def test_a_reply_to_moves_the_words_onto_the_person_who_wrote_them(inbound) -> None:
    obs, facts = inbound(sender=RELAY, sender_name="Sehan Sanjula via Boardy",
                         headers={"Reply-To": f"Sehan <{PARTY}>"})
    assert _subjects(obs, "question") == {PARTY}, "the question is Sehan's"
    assert RELAY not in _subjects(obs, "question")


def test_the_ball_lands_in_our_court_with_the_person_not_the_network(inbound) -> None:
    """The write this unit exists for: `waiting.py` derives `thread.last_heard_days` from
    `thread.last_inbound`, so putting it on the relay is what made a founder owe a reply to a
    mailing service and made the person look like somebody who never wrote."""
    _, facts = inbound(sender=RELAY, sender_name="Sehan Sanjula via Boardy",
                       headers={"Reply-To": PARTY})
    assert _fact(facts, "thread.ball_in_court") == {(PARTY, "us")}
    assert _fact(facts, "thread.last_inbound") == {(PARTY, NOW.isoformat())}


# ── a relay that names nobody ────────────────────────────────────────────────────────────────

def test_a_relay_with_no_reply_to_claims_nothing_rather_than_claiming_wrongly(inbound) -> None:
    """The display name proves the From address did not write this; with nothing naming who did,
    there is no honest subject. A missing card beats a card addressed to a mailing service."""
    obs, facts = inbound(sender=RELAY, sender_name="Sehan Sanjula via Boardy")
    assert _subjects(obs, "question") == set(), "no question is attributed to anyone"
    assert _fact(facts, "thread.ball_in_court") == set()
    assert _fact(facts, "thread.last_inbound") == set()


def test_the_relay_still_keeps_its_own_delivery_record(inbound) -> None:
    """`store-and-score, not delete`. The message's own relevance is a fact about the message,
    and the address that delivered it is the honest subject of that one."""
    obs, _ = inbound(sender=RELAY, sender_name="Sehan Sanjula via Boardy")
    assert _subjects(obs, "email_relevance") == {RELAY}


# ── the boundary ─────────────────────────────────────────────────────────────────────────────

def test_a_reply_to_equal_to_the_sender_is_not_a_relay(inbound) -> None:
    """Plenty of ordinary mailers set Reply-To to the From address."""
    obs, facts = inbound(sender="harshita@peakxv.com", sender_name="Harshita Kaul",
                         headers={"Reply-To": "harshita@peakxv.com"})
    assert _subjects(obs, "question") == {"harshita@peakxv.com"}
    assert _fact(facts, "thread.ball_in_court") == {("harshita@peakxv.com", "us")}


def test_a_message_with_no_headers_and_a_plain_name_is_ordinary(inbound) -> None:
    """Absence is never evidence of a relay."""
    _, facts = inbound(sender="theresa@antler.co", sender_name=None)
    assert _fact(facts, "thread.ball_in_court") == {("theresa@antler.co", "us")}
