"""STEP-14 · the card store versions a file's card — under the new signal's lease, on its authority, its words in place.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_a_card_is_versioned_not_replaced.py -q

Tree `yc2_w27_s14` M42.C3.L-data.V1.U02 (`deliver/store.CardStore.version_card`; STEP-14 §8.4 items 1-2). A file's
next decision or question is a VERSION of its card (`migrations/0220`): under the new signal's build lease, its
authority re-proven as an insert's is (the decision's predicate, or the question's), the card moved onto the new
signal by the one writer of a card's signal (`platform/card_lifecycle.version_card`), and the new words written in
place — the founder's side of the row (its state, snooze, history, verdicts) kept. The words before are read from
the card's own last version (its `card.created` or `card.versioned` event), so what changed is named exactly. A
lost lease, an authority that no longer holds, a blank card, or a card the founder decided version nothing.
"""
from __future__ import annotations

import json
import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.contracts.card_version import VersionWords
from genios_engine.deliver.card_builder import BUILDER_VERSION
from genios_engine.deliver.store import CardStore
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _open_signals, _write, admitted, world)
from tests.reason.expert.test_a_file_hands_its_card_on import _carded
from tests.reason.expert.test_a_file_keeps_one_decision import OTHER_MOVE, SECOND

pytestmark = pytest.mark.pg

LATER = NOW + timedelta(hours=6)
V2 = VersionWords(headline="Ask Arjun when the partner meeting is", situation="a fund preparing a partner meeting",
                  move="Ask Arjun when the partner meeting is", lane="decision", mode="act", ask="for:Arjun")


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _second(world):
    """The file's first card built, then a second review with other advice decided: its new signal, uncarded."""
    store, org, registry, _ = world
    anchor, events, first, card = _carded(store, org, registry)
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    _compile(store, org, registry, covered={anchor: SECOND}, at=LATER)
    [new] = _open_signals(store, org, anchor)
    with store.engine.connect() as c:
        row = dict(c.execute(text("select * from cards where card_id = :c"), {"c": card.card_id}).mappings().one())
        sig = dict(c.execute(text("select * from signals where signal_id = :s"), {"s": new.signal_id}).mappings().one())
    return store, org, anchor, row, sig


def _draft(row, sig, **over) -> tuple[dict, dict]:
    """The new signal's card as the pipeline composes it: the row's presentation, the new signal's authority."""
    card = {k: row[k] for k in ("org_id", "assignee", "domain", "level", "urgency_band", "score", "score_block",
                                "actions", "why", "context_tags", "surfaces", "output_lane", "lane_reason")}
    card.update(signal_id=sig["signal_id"], builder_version=BUILDER_VERSION, file_id=row["file_id"],
                expires_at=sig["authority_expires_at"], capability_key=sig["capability_id"],
                _authority_time=LATER, _words=V2.as_mapping(),
                _authority={"reasoning_run_id": sig["reasoning_run_id"],
                            "reasoning_candidate_id": sig["reasoning_candidate_id"],
                            "reasoning_decision_hash": sig["reasoning_decision_hash"],
                            "config_snapshot_id": sig["config_snapshot_id"]})
    card.update(over)
    copy = {"headline": V2.headline, "situation": V2.situation, "artifact": {"kind": "none", "body": ""},
            "render_mode": "review"}
    return card, copy


def _version(cards, org, card, copy, token=None):
    token = token or cards.claim_build(org, card["signal_id"], eval_time=LATER, builder_version=BUILDER_VERSION)
    found = cards.file_card(org, card["file_id"])
    return cards.version_card(card, copy, build_claim_token=token, file_card=found)


def _events(store, card_id, kind):
    with store.engine.connect() as c:
        return [r.detail for r in c.execute(text("select detail from card_events where card_id = :c and kind = :k "
                                                 "order by occurred_at, id"), {"c": card_id, "k": kind})]


def test_a_files_card_is_versioned_onto_its_new_signal_its_words_in_place(world, cards):
    store, org, anchor, row, sig = _second(world)
    assert row["file_id"] == anchor and row["version"] == 1
    card, copy = _draft(row, sig)
    assert _version(cards, org, card, copy) == (row["card_id"], 2, True, "updated")
    now = cards.get_card(row["card_id"])
    assert (now["signal_id"], now["version"], now["headline"], now["state"]) == (
        sig["signal_id"], 2, V2.headline, row["state"])
    assert cards.get_authoritative_card(row["card_id"], org, eval_time=LATER) is not None, "its door shows it"
    [created] = _events(store, row["card_id"], "card.created")
    [versioned] = _events(store, row["card_id"], "card.versioned")
    assert versioned["before"] == created["words"] and versioned["words"] == V2.as_mapping()
    assert versioned["from_signal"] == row["signal_id"] and versioned["changed"][0] == "headline"
    with store.engine.connect() as c:          # dated by its decision (the pass's instant), never the database's clock
        assert c.execute(text("select occurred_at from card_events where card_id = :c and kind = 'card.versioned'"),
                         {"c": row["card_id"]}).scalar() == LATER
    with store.engine.connect() as c:
        assert c.execute(text("select count(*) from cards where org_id = :o"), {"o": org}).scalar() == 1


def test_the_next_version_reads_the_last_versions_words(world, cards):
    store, org, _anchor, row, sig = _second(world)
    card, copy = _draft(row, sig)
    _version(cards, org, card, copy)
    with store.engine.begin() as c:            # the next decision: the same advice, its signal renewed
        c.execute(text("update signals set status = 'expired' where signal_id = :s"), {"s": sig["signal_id"]})
        c.execute(text(
            "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, rule_version, level, "
            " subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, config_snapshot_id, "
            " reasoning_run_id, reasoning_candidate_id, reasoning_decision_hash, authority_expires_at, "
            " authority_binding_version, authority_pack_revision, capability_id, capability_version, "
            " capability_review_state, output_lane, lane_reason, situation_id) "
            "select 'sig_renewed', org_id, pack_id, pack_version, rule_id, rule_version, level, subject_node_id, "
            " score, score_inputs, reason_code, evidence, play, eval_time, config_snapshot_id, reasoning_run_id, "
            " reasoning_candidate_id, reasoning_decision_hash, authority_expires_at, authority_binding_version, "
            " authority_pack_revision, capability_id, capability_version, capability_review_state, output_lane, "
            " lane_reason, situation_id from signals where signal_id = :s"), {"s": sig["signal_id"]})
    renewed, copy = _draft(row, {**sig, "signal_id": "sig_renewed"})
    assert _version(cards, org, renewed, copy) == (row["card_id"], 3, False, "renewed")


@pytest.mark.parametrize("why", ["lease", "authority", "blank"])
def test_a_version_needs_its_lease_its_authority_and_words(world, cards, why):
    store, org, _anchor, row, sig = _second(world)
    card, copy = _draft(row, sig)
    token = None
    if why == "lease":
        cards.claim_build(org, card["signal_id"], eval_time=LATER, builder_version=BUILDER_VERSION)
        token = "cbuild_not_mine"
    elif why == "authority":
        card["_authority"] = {**card["_authority"], "reasoning_decision_hash": "0" * 64}
    else:
        copy = {**copy, "headline": "  "}
    assert _version(cards, org, card, copy, token=token) is None
    assert cards.get_card(row["card_id"])["signal_id"] == row["signal_id"]
    assert _events(store, row["card_id"], "card.versioned") == []


def test_the_founders_side_of_the_row_is_kept(world, cards):
    store, org, _anchor, row, sig = _second(world)
    snooze = LATER + timedelta(hours=4)
    with store.engine.begin() as c:
        c.execute(text("update cards set state = 'snoozed', snooze_until = :t where card_id = :c"),
                  {"t": snooze, "c": row["card_id"]})
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id) values "
                       "('cev_kept', :c, :o, 'human.card_action', 'snooze', 'seat_1')"),
                  {"c": row["card_id"], "o": org})
    card, copy = _draft(row, sig)
    assert _version(cards, org, card, copy)[1] == 2
    now = cards.get_card(row["card_id"])
    assert (now["state"], now["snooze_until"], now["created_at"]) == ("snoozed", snooze, row["created_at"])
    assert [e["kind"] for e in cards.timeline(org, row["card_id"])].count("human.card_action") == 1


def test_a_card_the_founder_decided_is_never_versioned(world, cards):
    store, org, _anchor, row, sig = _second(world)
    with store.engine.begin() as c:
        c.execute(text("update cards set state = 'acted' where card_id = :c"), {"c": row["card_id"]})
    card, copy = _draft(row, sig)
    assert cards.file_card(org, row["file_id"]) is None
    token = cards.claim_build(org, card["signal_id"], eval_time=LATER, builder_version=BUILDER_VERSION)
    with store.engine.connect() as c:
        from genios_engine.platform.card_lifecycle import FileCard
        stale = FileCard(card_id=row["card_id"], signal_id=row["signal_id"], version=1, state="acted", held=False)
    assert cards.version_card(card, copy, build_claim_token=token, file_card=stale) is None
    assert cards.get_card(row["card_id"])["signal_id"] == row["signal_id"]


def test_a_new_files_card_says_its_words_when_it_is_created(world, cards):
    store, org, _anchor, row, _sig = _second(world)
    [created] = _events(store, row["card_id"], "card.created")
    assert set(created["words"]) == set(V2.as_mapping()) and created["words"]["headline"] == row["headline"]
    assert created["version"] == 1
    json.dumps(created)


def test_the_words_shown_are_the_copys_whatever_the_builder_named(world, cards):
    store, org, _anchor, row, sig = _second(world)
    card, copy = _draft(row, sig, _words={**V2.as_mapping(), "headline": "a builder's word"})
    _version(cards, org, card, copy)
    [versioned] = _events(store, row["card_id"], "card.versioned")
    assert versioned["words"]["headline"] == copy["headline"] == V2.headline


def test_a_card_the_clock_closed_is_reopened_by_its_files_next_version(world, cards):
    store, org, _anchor, row, sig = _second(world)
    with store.engine.begin() as c:
        c.execute(text("update cards set state = 'expired' where card_id = :c"), {"c": row["card_id"]})
    card, copy = _draft(row, sig)
    assert _version(cards, org, card, copy)[3] == "reopened"
    assert cards.get_card(row["card_id"])["state"] == "queued"


def test_a_card_an_agent_holds_waits(world, cards):
    from genios_engine.platform.card_lifecycle import FileCard
    store, org, _anchor, row, sig = _second(world)
    card, copy = _draft(row, sig)
    token = cards.claim_build(org, card["signal_id"], eval_time=LATER, builder_version=BUILDER_VERSION)
    held = FileCard(card_id=row["card_id"], signal_id=row["signal_id"], version=1, state="claimed", held=True)
    assert cards.version_card(card, copy, build_claim_token=token, file_card=held) is None
    assert cards.get_card(row["card_id"])["signal_id"] == row["signal_id"]


def test_a_card_with_no_authority_named_is_never_versioned(world, cards):
    store, org, _anchor, row, sig = _second(world)
    card, copy = _draft(row, sig)
    card.pop("_authority")
    assert _version(cards, org, card, copy) is None


@pytest.mark.parametrize("held", [True, False], ids=["its-authority", "another-question"])
def test_a_question_versions_the_files_card_on_its_own_authority(world, cards, held):
    from genios_engine.deliver import pipeline
    from genios_engine.deliver.store import QUESTION_CARD_BUILDER
    from tests.reason.expert.test_a_file_hands_its_card_on import _asked_and_carded
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, _ = world
    anchor, events, _question, first = _asked_and_carded(store, org, registry)
    with store.engine.begin() as c:            # the question card names its file (its builder does from U03 on)
        c.execute(text("update cards set file_id = :f where card_id = :c"), {"f": anchor, "c": first.card_id})
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question="Who at the fund decides?")
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"}, at=LATER)
    [row] = pipeline._open_questions_without_cards(store, org, LATER)
    card, copy = pipeline.question_card(store, org, row, LATER)
    card["file_id"] = anchor
    if not held:
        card["_question_authority"] = {**card["_question_authority"], "question_id": "fq_not_this_one"}
    token = cards.claim_build(org, card["signal_id"], eval_time=LATER, builder_version=QUESTION_CARD_BUILDER)
    got = cards.version_card(card, copy, build_claim_token=token, file_card=cards.file_card(org, anchor))
    if held:
        assert got[0] == first.card_id and got[1] == 2
        assert cards.get_card(first.card_id)["headline"] == "Who at the fund decides?"
    else:
        assert got is None and cards.get_card(first.card_id)["signal_id"] == first.signal_id


# ── STEP-14 · the gold columns, on the card and on every version (`yc2_w27_s14` M43.C3.L-data.V4.U02, 0221) ──

GOLD = {"recommended": {"who": "You", "what": "Send Arjun the deck and the quarter's metrics before the partner meeting",
                        "for_whom": "Arjun", "by_when": None, "to": "Arjun"},
        "alternative": "Offer Arjun a short call to walk through them instead",
        "wait_or_stop": "If no reply comes within a week, ask once, then stop"}


def _gold_row(store, card_id):
    with store.engine.connect() as c:
        return c.execute(text("select recommended, alternative, wait_or_stop from cards where card_id = :c"),
                         {"c": card_id}).one()


def test_a_new_card_writes_its_gold_columns(world, cards):
    """The pipeline's expert card (`deliver/card_builder`, the decision's `gold`) lands its move whole."""
    store, _org, _anchor, row, _sig = _second(world)
    recommended, _alternative, wait_or_stop = _gold_row(store, row["card_id"])
    assert recommended and recommended["what"] and recommended["who"]
    assert wait_or_stop, "the review's stop rule, as its check held it"


def test_every_version_writes_its_gold_columns_and_its_event_carries_them(world, cards):
    store, org, _anchor, row, sig = _second(world)
    card, copy = _draft(row, sig, **GOLD)
    assert _version(cards, org, card, copy) is not None
    recommended, alternative, wait_or_stop = _gold_row(store, row["card_id"])
    assert (recommended, alternative, wait_or_stop) == (GOLD["recommended"], GOLD["alternative"], GOLD["wait_or_stop"])
    [versioned] = _events(store, row["card_id"], "card.versioned")
    assert (versioned["words"]["alternative"], versioned["words"]["wait_or_stop"]) == (GOLD["alternative"],
                                                                                       GOLD["wait_or_stop"])
    assert "alternative" in versioned["changed"] and "wait_or_stop" in versioned["changed"]


def test_a_version_with_no_gold_lines_clears_them_never_keeps_the_last_ones(world, cards):
    """A version's columns are ITS words: a card no review wrote names none, so none are left from before."""
    store, org, _anchor, row, sig = _second(world)
    card, copy = _draft(row, sig)
    _version(cards, org, card, copy)
    assert tuple(_gold_row(store, row["card_id"])) == (None, None, None)


def test_a_card_an_older_builder_wrote_is_rebuilt_in_place_with_its_gold_columns(world, cards):
    """`BUILDER_VERSION` moved (v7): an untouched card from before is rebuilt in place — and gains its gold columns."""
    from genios_engine.deliver import pipeline
    store, org, registry, _ = world
    _anchor, _events_, _first, card = _carded(store, org, registry)
    with store.engine.begin() as c:
        c.execute(text("update cards set builder_version = 'card-builder.v6-lane-and-eleven-reasons', "
                       "recommended = null, alternative = null, wait_or_stop = null where card_id = :c"),
                  {"c": card.card_id})
    out = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    assert out["refreshed"] == 1, out
    recommended, _alternative, wait_or_stop = _gold_row(store, card.card_id)
    assert recommended and recommended["what"] and wait_or_stop
