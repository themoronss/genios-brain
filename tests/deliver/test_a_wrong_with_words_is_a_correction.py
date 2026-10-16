"""STEP-16 · your *wrong* in your own words is a correction of the card's file — and a bare click is only a verdict.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_a_wrong_with_words_is_a_correction.py

Tree `yc2_w27_s16` M46.C3.L-integration.V3.U04 (`deliver/actions.ingest_action`, `POST /cards/{id}/action` with `words`
and `scope`; S16-D1, S16-D4). With words, the correction is kept on the card's file in the verdict's transaction —
an expert card's file is its own (`cards.file_id`), any other card's the file its subject belongs to — with its
scope: this file, every file of its kind of work (the kind the brief gives the file), or how your company works
(your own preferences line of the brief). Without words it stays a verdict: one click generalises nothing. Words
that are no correction, and a kind correction on a file the brief names no kind for, are refused before anything
is written. A kind or a company correction is the account owner's alone (`06` D27's rule).
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import founder_corrections as C
from genios_engine.deliver import actions
from genios_engine.deliver import verdicts as V
from tests.reason.expert.test_a_covered_file_decides_once import NOW, world  # noqa: F401 — fixtures
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

AT = NOW + timedelta(minutes=5)
FOUNDER = "founder@meridian.test"
WORDS = "Banyan asked for news only on real milestones — don't push them."


@pytest.fixture
def decided(world):
    """A covered file, decided by the expert: its one card, through the decision's own door."""
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the card, its file and the ledger are Postgres's")
    from genios_engine.deliver.store import CardStore
    from tests.deliver.test_a_question_card import _build, _cards
    from tests.reason.expert.test_a_covered_file_decides_once import _compile, _fund
    from tests.reason.expert.test_a_covered_file_decides_once import _write as _write_act
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write_act(store, org, anchor, "ffp-fund-act-review-000000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"})
    _build(store, CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]), org)
    [card] = _cards(store, org)
    return store, org, anchor, card


def _press(store, org, card, action="wrong", **kw):
    kw.setdefault("reason", "not_relevant" if action == "wrong" else None)
    return actions.ingest_action(card_store=None, graph=store, org_id=org, card_id=card.card_id, actor=FOUNDER,
                                 action=action, eval_time=AT, allow_any_assignee=True, **kw)


def _kept(store, org):
    with store.engine.connect() as c:
        return c.execute(text(
            "select correction_id, file_id, card_id, feedback_id, reason, words, scope, kind, brief_line_id, "
            "corrected_by, corrected_at from founder_corrections where org_id = :o order by corrected_at"),
            {"o": org}).all()


def _state(store, org, card_id):
    with store.engine.connect() as c:
        return c.execute(text("select state from cards where org_id = :o and card_id = :c"),
                         {"o": org, "c": card_id}).scalar()


# =================================================================================================
# 1 · with words, a correction of the card's file — in the verdict's transaction
# =================================================================================================
@pytest.mark.pg
def test_your_words_are_kept_on_the_cards_file_beside_the_verdict(decided):
    store, org, anchor, card = decided
    out = _press(store, org, card, words=f"  {WORDS}  ")
    assert out["ok"] is True and out["state"] == "acted", out
    [kept] = _kept(store, org)
    assert out["correction_id"] == kept.correction_id == C.correction_id_for(org, anchor, WORDS, C.FILE)
    assert (kept.file_id, kept.card_id, kept.feedback_id, kept.reason, kept.words, kept.scope, kept.kind) == (
        anchor, card.card_id, V.feedback_id_of(org, card.card_id), "not_relevant", WORDS, C.FILE, None)
    assert (kept.corrected_by, kept.corrected_at) == (FOUNDER, AT)
    with store.engine.connect() as c:
        assert [k.correction_id for k in C.standing_for(c, org, anchor).corrections] == [kept.correction_id]
        assert c.execute(text("select reason from card_feedback_verdicts where org_id = :o and card_id = :c"),
                         {"o": org, "c": card.card_id}).scalar() == "not_relevant", "and the verdict beside it"


@pytest.mark.pg
def test_a_bare_wrong_is_only_a_verdict_one_click_generalises_nothing(decided):
    store, org, _anchor, card = decided
    out = _press(store, org, card, words="   ")
    assert out["ok"] is True and "correction_id" not in out
    assert _kept(store, org) == []


@pytest.mark.pg
def test_words_with_a_taken_card_are_no_correction(decided):
    store, org, _anchor, card = decided
    assert _press(store, org, card, "run_play", words=WORDS)["ok"] is True
    assert _kept(store, org) == []


@pytest.mark.pg
def test_a_correction_for_the_kind_of_work_records_the_files_kind(decided):
    """The fund's file is `investor` by the brief's in-motion line (`_tenant`)."""
    store, org, anchor, card = decided
    out = _press(store, org, card, words="Investors get nothing before a milestone lands.", scope=C.KIND)
    assert out["ok"] is True, out
    [kept] = _kept(store, org)
    assert (kept.file_id, kept.scope, kept.kind) == (anchor, C.KIND, "investor")


@pytest.mark.pg
def test_a_kind_correction_on_a_file_with_no_kind_is_refused_and_writes_nothing(decided):
    store, org, _anchor, card = decided
    with store.engine.begin() as c:
        c.execute(text("update company_brief_lines set status = 'removed', removed_at = :at "
                       "where org_id = :o and section = 'in_motion' and status = 'accepted'"), {"o": org, "at": NOW})
    from genios_engine.platform import company_brief
    company_brief.invalidate(org)
    out = _press(store, org, card, words="Investors get nothing before a milestone lands.", scope=C.KIND)
    assert out["ok"] is False and out["error"] == "no_kind_of_work", out
    assert _kept(store, org) == [] and _state(store, org, card.card_id) != "acted", "nothing written, the card open"
    with store.engine.connect() as c:
        assert c.execute(text("select count(*) from card_feedback_verdicts where org_id = :o"),
                         {"o": org}).scalar() == 0


@pytest.mark.pg
def test_a_correction_of_the_company_is_your_preferences_line_of_the_brief(decided):
    store, org, _anchor, card = decided
    out = _press(store, org, card, words="Never push a follow-up on a Friday.", scope=C.COMPANY)
    assert out["ok"] is True, out
    [kept] = _kept(store, org)
    with store.engine.connect() as c:
        line = c.execute(text("select section, text, status from company_brief_lines where org_id = :o "
                              "and line_id = :l"), {"o": org, "l": kept.brief_line_id}).one()
    assert kept.scope == C.COMPANY and tuple(line) == ("preferences", "Never push a follow-up on a Friday.",
                                                        "accepted")


@pytest.mark.pg
@pytest.mark.parametrize("words, scope", [("two\nlines", C.FILE), ("x" * (C.MAX_WORDS + 1), C.FILE),
                                          (WORDS, "team"), ("y" * 250, C.COMPANY)])
def test_words_that_are_no_correction_are_refused_before_anything_is_written(decided, words, scope):
    store, org, _anchor, card = decided
    out = _press(store, org, card, words=words, scope=scope)
    assert out["ok"] is False and out["error"] == "invalid_correction" and out["why"], out
    assert _kept(store, org) == [] and _state(store, org, card.card_id) != "acted"


# =================================================================================================
# 2 · the card's file: its own, or the file its subject belongs to
# =================================================================================================
@pytest.mark.pg
def test_a_cards_file_is_its_own_or_the_one_its_subject_belongs_to(pg_store):
    org = "org_s16_file_of_card"
    store = pg_store
    at = NOW
    with store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": org})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'foc@s16.test')"), {"o": org})
        c.execute(text("insert into context_correlations (correlation_id, org_id, anchor_node_id) values "
                       "('cor_s16_a', :o, 'node_company'), ('cor_s16_b', :o, 'node_anchored_person')"), {"o": org})
        c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, from_node_id, "
                       "to_node_id) values ('ev_s16_w', 'e_s16_w', :o, 'works_at', 'node_partner', 'node_company'), "
                       "('ev_s16_x', 'e_s16_x', :o, 'works_at', 'node_anchored_person', 'node_company')"),
                  {"o": org})
        for card_id, subject, file_id in (("card_file", "node_whatever", "node_the_file"),
                                          ("card_anchored", "node_anchored_person", None),
                                          ("card_partner", "node_partner", None),
                                          ("card_loner", "node_loner", None)):
            c.execute(text("insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, subject_node_id, "
                           "score, reason_code, eval_time) values (:s, :o, 'general', '1.0.0', 'unanswered_email', :n, "
                           "10, 'unanswered_email', :at)"),
                      {"s": f"sig_{card_id}", "o": org, "n": subject, "at": at})
            c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                           "score, expires_at, file_id) values (:c, :s, :o, 'prescriptive', 'standard', 'h', 's', "
                           "10, :exp, :f)"),
                      {"c": card_id, "s": f"sig_{card_id}", "o": org, "exp": at + timedelta(days=7), "f": file_id})
        files = {k: C.file_of_card(c, org_id=org, card_id=k)
                 for k in ("card_file", "card_anchored", "card_partner", "card_loner", "card_nobody")}
        c.execute(text("delete from graph_edges where org_id = :o"), {"o": org})
        c.execute(text("delete from context_correlations where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})
    assert files == {"card_file": "node_the_file", "card_anchored": "node_anchored_person",
                     "card_partner": "node_company", "card_loner": "node_loner", "card_nobody": None}


# =================================================================================================
# 3 · the route carries your words and their scope; a kind or a company correction is the owner's
# =================================================================================================
def test_the_route_carries_your_words_and_their_scope(monkeypatch):
    from tests.test_card_history_routes import FakeStore, client
    seen: list[dict] = []
    monkeypatch.setattr(actions, "ingest_action", lambda **kw: seen.append(kw) or {"ok": True, "state": "acted"})
    api = client(monkeypatch, FakeStore())
    assert api.post("/cards/card_1/action", json={"action": "wrong", "reason": "not_relevant", "words": WORDS,
                                                   "scope": "kind"}).status_code == 200
    assert (seen[0]["words"], seen[0]["scope"]) == (WORDS, "kind")


@pytest.mark.parametrize("scope", ["kind", "company"])
def test_a_kind_or_company_correction_from_an_admin_is_refused_at_the_route(monkeypatch, scope):
    from genios_engine.platform.auth import AuthCtx
    from tests.test_card_history_routes import ORG, FakeStore, client
    monkeypatch.setattr(actions, "ingest_action", lambda **kw: pytest.fail("refused before the press"))
    admin = AuthCtx(org_id=ORG, actor_id="seat_admin", seat_id="seat_admin", role="admin", source="jwt")
    answer = client(monkeypatch, FakeStore(), admin).post(
        "/cards/card_1/action", json={"action": "wrong", "reason": "not_relevant", "words": WORDS, "scope": scope})
    assert answer.status_code == 403 and answer.json()["detail"]["error"] == "owner_only"


def test_an_admins_file_correction_and_bare_wrong_reach_the_press(monkeypatch):
    from genios_engine.platform.auth import AuthCtx
    from tests.test_card_history_routes import ORG, FakeStore, client
    seen: list[dict] = []
    monkeypatch.setattr(actions, "ingest_action", lambda **kw: seen.append(kw) or {"ok": True, "state": "acted"})
    admin = AuthCtx(org_id=ORG, actor_id="seat_admin", seat_id="seat_admin", role="admin", source="jwt")
    api = client(monkeypatch, FakeStore(), admin)
    assert api.post("/cards/card_1/action", json={"action": "wrong", "reason": "not_relevant", "words": WORDS,
                                                   "scope": "file"}).status_code == 200
    assert api.post("/cards/card_1/action", json={"action": "wrong", "reason": "not_relevant",
                                                   "scope": "company"}).status_code == 200, "no words, no correction"
    assert len(seen) == 2
