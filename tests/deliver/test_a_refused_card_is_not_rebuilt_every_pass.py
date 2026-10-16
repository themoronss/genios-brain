"""STEP-14 fix · a refused card is not rebuilt on every pass — tried again once a day, its file's card kept meanwhile.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_a_refused_card_is_not_rebuilt_every_pass.py -q

Tree `yc2_w27_s14` M43.C4.L-integration.V1.U09 (the STEP-14 crosscheck, finding 14). A signal the card contract refused
stays open with no card, so every pass selected it again, built it again, NARRATED it again (a model call on a card no
review wrote — `render_copy` runs before the contract, and the renderer has no cache) and refused it again. Now a signal
the pipeline refused within `REFUSAL_RETRY` (a day, by the pass's own clock) is not built — counted
`skipped_refused_recently` — and its file's card stays as it was (`_close_the_files_pass` reads the refusal from
`card_refusals`, not only from the pass). After the day it is tried once more; refused again, its one row per rule says
when it last was (`refused_at` moves; `found` is the first).
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import pipeline
from genios_engine.deliver.store import CardStore
from tests.deliver.test_a_refused_version_leaves_the_card_where_it_was import _a_card_then_a_refused_decision, _state
from tests.reason.expert.test_a_covered_file_decides_once import admitted, world  # noqa: F401 — fixtures

pytestmark = pytest.mark.pg


def _refusal(store, org):
    with store.engine.connect() as c:
        return c.execute(text("select count(*), max(refused_at) from card_refusals where org_id = :o"),
                         {"o": org}).one()


def test_a_refused_signal_is_not_built_again_the_same_day(world, monkeypatch):
    store, org, cards, card_id, before, later = _a_card_then_a_refused_decision(world)
    first = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=later)
    assert first["refused_contract:internal"] == 1, first
    built: list = []
    real = pipeline.build_draft
    monkeypatch.setattr(pipeline, "build_draft", lambda *a, **k: built.append(a[2]["signal_id"]) or real(*a, **k))
    again = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org,
                                         eval_time=later + timedelta(hours=6))
    assert again["skipped_refused_recently"] == 1 and again["refused_contract:internal"] == 0, again
    assert built == [], "not built, not narrated"
    assert again["file_cards_replaced"] == 0, "its file's card stays as it was"
    row, events, n, kept = _state(store, org, card_id)
    assert (row, events, n, kept) == (before, [], 1, 1)


def test_after_a_day_it_is_tried_again_and_its_refusal_says_when(world):
    store, org, cards, card_id, before, later = _a_card_then_a_refused_decision(world)
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=later)
    n1, at1 = _refusal(store, org)
    tomorrow = later + pipeline.REFUSAL_RETRY + timedelta(minutes=1)
    out = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=tomorrow)
    assert out["refused_contract:internal"] == 1 and out["skipped_refused_recently"] == 0, out
    n2, at2 = _refusal(store, org)
    assert (n1, n2) == (1, 1) and at1 == later and at2 == tomorrow, (at1, at2)
    assert _state(store, org, card_id)[0] == before


def test_a_signal_never_refused_is_built_as_ever(world):
    """⛔ THE NEGATIVE CONTROL: nothing refused, nothing skipped."""
    from tests.reason.expert.test_a_covered_file_decides_once import NOW, _compile, _fund, _write
    from tests.reason.expert.test_a_file_keeps_one_decision import FIRST
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    out = pipeline.build_cards_for_org(graph=store, card_store=CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]),
                                       org_id=org, eval_time=NOW)
    assert (out["built"], out["skipped_refused_recently"]) == (1, 0), out


def test_a_refused_question_is_not_built_again_the_same_day(world):
    from tests.reason.expert.test_a_covered_file_decides_once import NOW, _compile, _fund
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, _ = world
    cards = CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events, question="Is the party.role still open?")
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    first = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    assert first["refused_contract:internal"] == 1, first
    again = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW + timedelta(hours=2))
    assert (again["skipped_refused_recently"], again["refused_contract:internal"]) == (1, 0), again
