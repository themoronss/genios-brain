"""STEP-16 · the one writer of a verdict — both doors write `card_feedback_verdicts` through it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_one_writer_of_a_verdict.py

Tree `yc2_w27_s16` M46.C2.L-data.V1.U02 (`deliver/verdicts`; `s16-F1`). ⛔ WHY. The extension's door
(`POST /v1/intelligence/feedback`) wrote the verdict ledger with two statements of its own, and the
dashboard's (`deliver/actions.ingest_action`) wrote `card_events` only — so the reason you give on a card
reached calibration and nothing else of the eight readers that read the ledger. One writer is the
precondition for the dashboard's door writing it too (M46.C2.L-integration.V2.U03): the route's two
statements moved here byte for byte — the verdict and its revision, idempotent per card, `occurred_at` the
request's one instant — bound to the card's audited authority, a decision's or a question's.
`run_play`, `do_it_myself` and `wrong` with one of the eleven reasons are verdicts; `snooze` and `requeue`
never are.
"""
from __future__ import annotations

import ast
import os
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.contracts.learning_attribution import ALL_REASONS
from genios_engine.deliver import verdicts as V
from genios_engine.platform import table_coverage as tc
from tests.reason.expert.test_a_covered_file_decides_once import NOW, world  # noqa: F401 — fixtures
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

_REPO = Path(__file__).resolve().parents[2]
ROUTE = "genios_engine/api/intelligence_routes.py"
WRITER = "genios_engine/deliver/verdicts.py"
_AT = NOW + timedelta(minutes=5)


# =================================================================================================
# 1 · one writer — read from the code
# =================================================================================================
@pytest.mark.parametrize("ledger", ["card_feedback_verdicts", "card_feedback_revisions"])
def test_the_engine_writes_the_verdict_ledger_in_one_place(ledger):
    engine_writers = {w for w in tc.writers_of(ledger) if w.startswith("genios_engine/")}
    assert engine_writers == {WRITER}, sorted(engine_writers)


def test_the_extensions_door_calls_the_one_writer():
    tree = ast.parse((_REPO / ROUTE).read_text(encoding="utf-8"))
    route = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "intelligence_feedback")
    calls = [n for n in ast.walk(route) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "record"
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "verdicts"]
    assert len(calls) == 1, "the route records its verdict through deliver/verdicts.record, once"
    lease = [n for n in ast.walk(route) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "lease_from_card_feedback"]
    assert len(lease) == 1, "the route still evaluates the adaptive lease in its own transaction"


# =================================================================================================
# 2 · what a verdict is — pure, before any statement
# =================================================================================================
def test_a_verdict_is_a_taken_card_or_a_wrong_one():
    assert V.VERDICT_CAUSES == frozenset({"run_play", "do_it_myself", "wrong"})
    assert V.NEVER_VERDICTS == frozenset({"snooze", "requeue"})
    assert V.WRONG_REASONS == frozenset(ALL_REASONS) and len(V.WRONG_REASONS) == 11


class _Unreachable:
    def execute(self, *_a, **_k):                                    # pragma: no cover - the point
        raise AssertionError("a refused verdict reached the database")


_BINDING = V.Binding(pack_id="general", pack_version="1.0.0", authority_pack_revision=3,
                     capability_id="expert.file_review", capability_version="1.0.0",
                     rule_id="file_review", of=V.OF_DECISION)


@pytest.mark.parametrize("cause, reason", [
    ("snooze", None), ("requeue", None), ("answer", None), ("thumbs_up", None),
    ("wrong", None), ("wrong", "not_a_reason"), ("run_play", "not_relevant"),
])
def test_what_is_not_a_verdict_is_refused_before_any_write(cause, reason):
    with pytest.raises(ValueError):
        V.record(_Unreachable(), org_id="org_1", card_id="card_1", binding=_BINDING, cause=cause,
                 reason=reason, detail={}, actor="seat_1", as_of=_AT)


def test_one_card_has_one_feedback_id_whichever_door():
    assert V.feedback_id_of("org_1", "card_1") == V.feedback_id_of("org_1", "card_1")
    assert V.feedback_id_of("org_1", "card_1") != V.feedback_id_of("org_1", "card_2")
    # The extension's id since it was written (`stable_id("fb", …)` with an empty decision id), kept so a
    # verdict already in the ledger is the same verdict whichever door changes it next.
    from genios_engine.platform.canonical import stable_id
    assert V.feedback_id_of("org_1", "card_1") == stable_id(
        "fb", {"org_id": "org_1", "card_id": "card_1", "decision_id": ""})


# =================================================================================================
# 3 · on Postgres — bound to the card's own authority, idempotent per card
# =================================================================================================
def _db():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the ledger and the authority it binds are Postgres's")


@pytest.fixture
def decision_card(request):
    _db()
    world = request.getfixturevalue("world")
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
    return store, org, card


@pytest.fixture
def question_card(request):
    _db()
    world = request.getfixturevalue("world")
    from genios_engine.deliver.store import CardStore
    from tests.deliver.test_a_question_card import _asked, _build, _cards
    store, org, _registry, _anchor, _events = _asked(world)
    _build(store, CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]), org)
    [card] = _cards(store, org)
    return store, org, card


def _ledger(store, org, card_id):
    with store.engine.connect() as c:
        verdict = c.execute(text(
            "select feedback_id, pack_id, pack_version, authority_pack_revision, capability_id, "
            "capability_version, rule_id, cause, reason, detail, actor_id, verdict_version, occurred_at "
            "from card_feedback_verdicts where org_id = :o and card_id = :k"),
            {"o": org, "k": card_id}).first()
        revisions = c.execute(text(
            "select verdict_version, cause, reason from card_feedback_revisions where org_id = :o "
            "and card_id = :k order by verdict_version"), {"o": org, "k": card_id}).all()
    return verdict, [tuple(r) for r in revisions]


def _record(store, org, card_id, *, cause="wrong", reason="not_relevant", at=_AT, detail=None):
    with store.engine.begin() as c:
        binding = V.binding_of(c, org_id=org, card_id=card_id, at=at)
        assert binding is not None
        return binding, V.record(c, org_id=org, card_id=card_id, binding=binding, cause=cause,
                                 reason=reason, detail=detail or {}, actor="founder@meridian.test",
                                 as_of=at)


@pytest.mark.pg
def test_a_verdict_on_a_decision_card_is_bound_to_the_decisions_authority(decision_card):
    store, org, card = decision_card
    binding, recorded = _record(store, org, card.card_id, reason="misread_source")
    assert binding.of == V.OF_DECISION
    assert (binding.capability_id, binding.rule_id) == ("expert.file_review", "file_review")
    assert binding.authority_pack_revision > 0
    verdict, revisions = _ledger(store, org, card.card_id)
    assert recorded == V.Recorded(feedback_id=V.feedback_id_of(org, card.card_id), verdict_version=1,
                                  changed=True)
    assert (verdict.pack_id, verdict.pack_version, verdict.authority_pack_revision, verdict.capability_id,
            verdict.capability_version, verdict.rule_id) == (
        binding.pack_id, binding.pack_version, binding.authority_pack_revision, binding.capability_id,
        binding.capability_version, binding.rule_id)
    assert (verdict.cause, verdict.reason, verdict.actor_id, verdict.occurred_at) == (
        "wrong", "misread_source", "founder@meridian.test", _AT), "occurred_at is the request's one instant"
    assert revisions == [(1, "wrong", "misread_source")]


@pytest.mark.pg
def test_the_same_verdict_again_changes_nothing_and_a_new_one_is_a_revision(decision_card):
    store, org, card = decision_card
    _record(store, org, card.card_id, reason="bad_timing")
    _b, again = _record(store, org, card.card_id, reason="bad_timing", at=_AT + timedelta(minutes=1))
    assert again == V.Recorded(feedback_id=V.feedback_id_of(org, card.card_id), verdict_version=1,
                               changed=False)
    later = _AT + timedelta(minutes=2)
    _b, changed = _record(store, org, card.card_id, reason="wrong_person", at=later)
    assert changed.verdict_version == 2 and changed.changed is True
    verdict, revisions = _ledger(store, org, card.card_id)
    assert (verdict.reason, verdict.verdict_version, verdict.occurred_at) == ("wrong_person", 2, later)
    assert revisions == [(1, "wrong", "bad_timing"), (2, "wrong", "wrong_person")]


@pytest.mark.pg
@pytest.mark.parametrize("cause", ["run_play", "do_it_myself"])
def test_a_taken_card_is_a_verdict_with_no_reason(decision_card, cause):
    store, org, card = decision_card
    _record(store, org, card.card_id, cause=cause, reason=None)
    verdict, revisions = _ledger(store, org, card.card_id)
    assert (verdict.cause, verdict.reason) == (cause, None) and revisions == [(1, cause, None)]


@pytest.mark.pg
def test_a_verdict_on_a_question_card_is_bound_to_the_questions_own_authority(question_card):
    """A question passes its own authority (`reason/authority.QUESTION_SIGNAL_PREDICATE`), never the
    decision's: its rule is `founder_question` — a rule of no pack, so calibration never scores it — and its
    pack revision is none (0): a question binds no pack revision, and calibration joins only cards that do."""
    store, org, card = question_card
    binding, recorded = _record(store, org, card.card_id, reason="not_relevant")
    assert binding.of == V.OF_QUESTION
    assert (binding.capability_id, binding.rule_id, binding.authority_pack_revision) == (
        "expert.file_review", "founder_question", 0)
    verdict, revisions = _ledger(store, org, card.card_id)
    assert recorded.changed and (verdict.rule_id, verdict.reason) == ("founder_question", "not_relevant")
    assert revisions == [(1, "wrong", "not_relevant")]


@pytest.mark.pg
def test_a_card_no_authority_binds_has_no_binding(decision_card):
    """The negative control: the decision card's signal no longer open — neither door's authority holds."""
    store, org, card = decision_card
    with store.engine.begin() as c:
        c.execute(text("update signals set status = 'expired' where org_id = :o and signal_id = :s"),
                  {"o": org, "s": card.signal_id})
        assert V.binding_of(c, org_id=org, card_id=card.card_id, at=_AT) is None
        assert V.binding_of(c, org_id=org, card_id="card_nobody", at=_AT) is None


@pytest.mark.pg
def test_a_question_whose_signal_is_gone_has_no_binding(question_card):
    """The question's negative control: its signal expired — its own authority no longer holds."""
    store, org, card = question_card
    with store.engine.begin() as c:
        c.execute(text("update signals set status = 'expired' where org_id = :o and signal_id = :s"),
                  {"o": org, "s": card.signal_id})
        assert V.binding_of(c, org_id=org, card_id=card.card_id, at=_AT) is None


@pytest.mark.pg
def test_a_verdict_kept_under_another_id_stays_that_verdict(decision_card):
    """Whatever id a caller offers, a card's verdict is the one already in the ledger — its id is returned."""
    store, org, card = decision_card
    _record(store, org, card.card_id, reason="bad_timing")
    with store.engine.begin() as c:
        binding = V.binding_of(c, org_id=org, card_id=card.card_id, at=_AT)
        again = V.record(c, org_id=org, card_id=card.card_id, binding=binding, cause="wrong",
                         reason="bad_timing", detail={}, actor="founder@meridian.test", as_of=_AT,
                         feedback_id="fb_another_door")
    assert again == V.Recorded(feedback_id=V.feedback_id_of(org, card.card_id), verdict_version=1,
                               changed=False)


@pytest.mark.pg
@pytest.mark.parametrize("which", ["decision_card", "question_card"])
def test_a_card_past_its_window_has_no_binding(request, which):
    """Bound at the request's instant: past the card's window, neither authority holds."""
    store, org, card = request.getfixturevalue(which)
    with store.engine.connect() as c:
        assert V.binding_of(c, org_id=org, card_id=card.card_id, at=_AT) is not None
        assert V.binding_of(c, org_id=org, card_id=card.card_id,
                            at=card.expires_at + timedelta(seconds=1)) is None


def test_the_extensions_door_binds_its_verdict_to_the_authority_it_just_proved(monkeypatch):
    """Hermetic, through the route: what `record` is handed is the route's own authority SELECT's row —
    the pack, its revision, the capability and its rule — your cause and reason, the request's instant."""
    from types import SimpleNamespace

    from genios_engine.api import intelligence_routes as routes
    from genios_engine.platform.auth import AuthCtx
    from tests.test_intelligence_authority_routes import _FeedbackEngine

    seen = []

    def _record(conn, **kw):
        seen.append(kw)
        return V.Recorded(feedback_id=V.feedback_id_of(kw["org_id"], kw["card_id"]), verdict_version=1,
                          changed=False)

    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_FeedbackEngine()))
    monkeypatch.setattr(routes.verdicts, "record", _record)
    out = routes.intelligence_feedback(
        routes.FeedbackBody(action="thumbs_down", insight_id="card_1", reason="wrong_person"),
        ctx=AuthCtx(org_id="org_1", actor_id="seat_1", scopes=["feedback.write"]))
    [kw] = seen
    assert kw["binding"] == V.Binding(pack_id="sales", pack_version="1.0.0", authority_pack_revision=3,
                                      capability_id="legacy.sales.cooling_deal", capability_version="1.0.0",
                                      rule_id="cooling_deal", of=V.OF_DECISION)
    assert (kw["org_id"], kw["card_id"], kw["cause"], kw["reason"], kw["actor"]) == (
        "org_1", "card_1", "wrong", "wrong_person", "seat_1")
    assert kw["detail"] == {"reason": "wrong_person"} and kw["as_of"].tzinfo is not None
    assert kw["feedback_id"] == V.feedback_id_of("org_1", "card_1")
    assert (out["feedback_id"], out["verdict_version"], out["changed"]) == (
        V.feedback_id_of("org_1", "card_1"), 1, False)
