"""GeniOS-011 S34.U3 · the card writer's copy on a real card: written by the pass, served, and cleared by a version.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_the_card_copy_is_stored_pg.py -q

`deliver/card_copy` words a NEW card version once (`deliver/pipeline.build_cards_for_org`, R-10, the tenant's
`card_copy` switch) and `deliver/store.CardStore.set_copy` stores it in `cards.copy` (migration 0252) for the version
and the headline it was written from. The queue serves its subject and two lines beside today's headline; the card
detail (`get_authoritative_card`, `k.*`) returns all of it. A version rewrites the card's words and clears the copy in
the same statement, so a copy never shows over words it was not made from. Off — the default — nothing is written
and the card reads as it does today. The model is a fake: no live call.
"""
from __future__ import annotations

import json
import os
import re

import pytest
from sqlalchemy import text

from genios_engine.context.llm.client import LLMResult
from genios_engine.deliver import card_copy as CC
from genios_engine.deliver import pipeline
from genios_engine.deliver.store import CardStore
from genios_engine.platform import l4_activation as ACT
from tests.deliver.test_a_card_is_versioned_not_replaced import LATER, _draft, _second, _version
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _write, admitted, world)
from tests.reason.expert.test_a_file_hands_its_card_on import _cards
from tests.reason.expert.test_a_file_keeps_one_decision import FIRST

pytestmark = pytest.mark.pg


class Echo:
    """A fake model that words the card from its own move: the subject is the move's first clause, resting on it."""

    model = "claude-haiku-4-5"
    supports_thinking = True

    def __init__(self):
        self.calls = 0

    def call(self, prompt, *, max_tokens, **kw):
        self.calls += 1
        move = re.search(r"^\[line:move\] \(line\) (.+)$", prompt, re.M).group(1)
        subject = " ".join(re.split(r"[,;]", move)[0].split()[:8])
        payload = {"subject": {"text": subject, "rests_on": ["line:move"]},
                   "summary": {"text": move[:200], "rests_on": ["line:move"]},
                   "steps": [{"text": subject, "rests_on": ["line:move"]}],
                   "result": {"text": "Ring Priya Kapoor", "rests_on": []},        # rests on nothing: dropped
                   "goal": None}
        return LLMResult(parsed=payload, raw=json.dumps(payload), ok=True, model=self.model, input_tokens=900,
                         output_tokens=200)


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _arm(store, org):
    ACT.activate(store.engine, org, feature=ACT.FEATURE_CARD_COPY, by="s34u3_test", notes="GeniOS-011 S34.U3")


def _build(store, org, monkeypatch, client):
    monkeypatch.setattr(CC, "make_site_client", lambda tier: client)
    pipeline.build_cards_for_org(graph=store, card_store=CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]),
                                 org_id=org, eval_time=NOW)


def _row(store, card_id):
    with store.engine.connect() as c:
        return dict(c.execute(text("select version, headline, copy from cards where card_id = :c"),
                              {"c": card_id}).mappings().one())


def _calls(store, org):
    with store.engine.connect() as c:
        return [tuple(r) for r in c.execute(text(
            "select site, outcome from l4_r_site_calls where org_id = :o and site = 'R-10' order by created_at"),
            {"o": org})]


def test_copywrite_the_pass_words_a_new_card_once_and_the_queue_serves_it(world, cards, monkeypatch):
    store, org, registry, _ = world
    _arm(store, org)
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    client = Echo()
    _build(store, org, monkeypatch, client)
    [card] = _cards(store, org)
    row = _row(store, card.card_id)
    copy = row["copy"]
    assert client.calls == 1 and _calls(store, org) == [("R-10", "ran")]
    assert copy["card_version"] == row["version"] == 1
    assert copy["subject"] and copy["rests_on"]["subject"] == ["line:move"]
    assert copy["result"] is None and copy["dropped"]["result"] == "rests_on_nothing", "said, never shipped"
    [served] = [r for r in cards.queue(org, admin=True, record_impressions=False, eval_time=NOW)
                if r["card_id"] == card.card_id]
    assert served["copy"] == {"subject": copy["subject"], "summary": copy["summary"]}
    assert served["headline"] == row["headline"], "today's headline stands beside it"
    full = cards.get_authoritative_card(card.card_id, org, eval_time=NOW)
    assert full["copy"]["steps"] == copy["steps"]
    # A second pass over the same card writes no new version, so it asks nothing.
    _build(store, org, monkeypatch, client)
    assert client.calls == 1


def test_copyoff_no_switch_no_call_no_copy(world, cards, monkeypatch):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    client = Echo()
    _build(store, org, monkeypatch, client)
    [card] = _cards(store, org)
    assert client.calls == 0 and _calls(store, org) == []
    assert _row(store, card.card_id)["copy"] is None
    [served] = [r for r in cards.queue(org, admin=True, record_impressions=False, eval_time=NOW)
                if r["card_id"] == card.card_id]
    assert served["copy"] is None, "fails closed: the card reads as it does today"


def test_copyversion_a_version_clears_the_copy_and_an_old_copy_cannot_land(world, cards):
    store, org, _anchor, row, sig = _second(world)
    stored = {"copy_version": CC.COPY_VERSION, "subject": "Ask Arjun about the meeting", "card_version": 1}
    assert cards.set_copy(org, row["card_id"], stored, version=1, headline=row["headline"])
    assert _row(store, row["card_id"])["copy"]["subject"] == "Ask Arjun about the meeting"
    card, copy = _draft(row, sig)
    assert _version(cards, org, card, copy)[1] == 2
    after = _row(store, row["card_id"])
    assert after["copy"] is None, "the words moved, so their copy went with them"
    # The copy written for version 1, or for the old headline, never lands on version 2.
    assert not cards.set_copy(org, row["card_id"], stored, version=1, headline=after["headline"])
    assert not cards.set_copy(org, row["card_id"], stored, version=2, headline=row["headline"])
    assert cards.set_copy(org, row["card_id"], {**stored, "card_version": 2}, version=2, headline=after["headline"])
    assert cards.get_authoritative_card(row["card_id"], org, eval_time=LATER)["copy"]["card_version"] == 2


def test_copyshape_the_column_holds_an_object_or_nothing(world, cards):
    store, org, _anchor, row, _sig = _second(world)
    with pytest.raises(Exception, match="cards_copy_is_an_object"):
        with store.engine.begin() as c:
            c.execute(text("update cards set copy = '[1]'::jsonb where card_id = :c"), {"c": row["card_id"]})
