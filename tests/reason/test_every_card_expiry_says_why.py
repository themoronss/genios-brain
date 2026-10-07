"""STEP-06 · every place that expires a card goes through the one writer, with its own reason.

    pytest tests/reason/test_every_card_expiry_says_why.py -q -k <site>
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_every_card_expiry_says_why.py -q

Tree `yc2_w27_s06 · M24.C1` (one `-k` per unit). Twelve places set a card `expired`; nine of them wrote
nothing (`speedrun008/YC-II W27/` STEP-06 §8.2). Each now calls `platform/card_lifecycle`, which writes
the event (`tests/platform/test_card_lifecycle.py` proves the writer). This file proves, site by site:

  · STRUCTURALLY, for every site — read by the AST: the call sits in the function it replaced and
    passes that site's own cause (and kind). `SITES` is the whole list; a site gone or added fails it.
  · BY RUNNING IT, where the site can be driven in isolation on Postgres — the legacy lane's
    `_emit`, the publisher, the lapse sweep: the old card is `expired` and carries its event.
    The others sit deep inside a sweep (`run`, `compose_deal_health`, `_emit_capability_signal`,
    `run_calibration`, a route); for them the structural check plus the writer's own test plus the
    guard that no other SQL sets `expired` (`tests/platform/test_one_way_to_expire_a_card.py`) are the
    proof, said here rather than implied.
"""
from __future__ import annotations

import ast
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: (file, function) → the (helper, cause, kind) calls it makes, in source order. The whole list.
SITES: dict[tuple[str, str], list[tuple[str, str | None, str | None]]] = {
    ("genios_engine/reason/runner.py", "_emit"): [("expire_cards", "REPLACED", None)],
    ("genios_engine/reason/runner.py", "run"): [("expire_cards", "RULE_CLEARED", None)],
    ("genios_engine/reason/composer.py", "compose_deal_health"): [
        ("expire_cards", "BUDGET_HELD", None), ("expire_cards", "NOT_AUTHORIZED", None),
        ("expire_cards", "REPLACED", None), ("expire_cards", "PLAN_GONE", None)],
    ("genios_engine/reason/publication.py", "publish_native_signal"): [
        ("expire_cards", "REPLACED", None)],
    ("genios_engine/reason/domain_shadow.py", "_emit_capability_signal"): [
        ("expire_cards", "REPLACED", None)],
    ("genios_engine/feedback/calibrate.py", "run_calibration"): [
        ("expire_cards", "RULE_MUTED", None)],
    ("genios_engine/deliver/store.py", "sweep_lifecycle"): [("expire_lapsed", None, None)],
    ("genios_engine/api/intelligence_routes.py", "dismiss_insight"): [
        ("expire_cards", "EXTENSION", "DISMISSED")],
    ("scripts/repair_self_identity.py", "apply"): [("expire_cards", "SUBJECT_IS_US", "RETIRED")],
}


def _calls(rel: str) -> dict[str, list[tuple[str, str | None, str | None]]]:
    """Every `card_lifecycle.<helper>(…)` call in `rel`, by enclosing function, in line order."""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    out: dict[str, list[tuple[int, tuple[str, str | None, str | None]]]] = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "card_lifecycle"):
                kw = {k.arg: k.value for k in node.keywords}

                def _name(v):
                    return v.attr if isinstance(v, ast.Attribute) else None
                out.setdefault(fn.name, []).append(
                    (node.lineno, (node.func.attr, _name(kw.get("cause")), _name(kw.get("kind")))))
    return {name: [call for _, call in sorted(calls)] for name, calls in out.items()}


def _site(rel: str, function: str):
    return _calls(rel).get(function, [])


#: The `-k` word of each site's tree unit (`yc2_w27_s06 · M24.C1`).
_UNIT_WORD = {"runner": "runner", "composer": "composer", "publication": "publication",
              "domain_shadow": "domain_shadow", "calibrate": "calibrate", "store": "lapse",
              "intelligence_routes": "dismiss", "repair_self_identity": "repair"}


@pytest.mark.parametrize("site", sorted(SITES),
                         ids=lambda s: f"{_UNIT_WORD[Path(s[0]).stem]}-{Path(s[0]).stem}.{s[1]}")
def test_each_site_calls_the_writer_with_its_own_reason(site):
    assert _site(*site) == SITES[site], f"{site}: {_site(*site)}"


def test_no_other_function_in_these_files_calls_the_writer():
    expected = {(rel, fn) for rel, fn in SITES}
    found = {(rel, fn) for rel in {r for r, _ in SITES} for fn in _calls(rel)}
    assert found == expected, sorted(found ^ expected)


def test_every_cause_a_site_names_is_in_the_closed_vocabulary():
    from genios_engine.platform import card_lifecycle as cl
    for calls in SITES.values():
        for _helper, cause, kind in calls:
            assert cause is None or getattr(cl, cause) in cl.CAUSES
            assert kind is None or getattr(cl, kind) in cl.KINDS


# ── by running it, on Postgres ──────────────────────────────────────────────────────────────────
ORG = "every_expiry_org"
AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


def _reset(eng):
    from sqlalchemy import text
    with eng.begin() as c:
        for table in ("card_events", "cards", "signals"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text
    eng = create_engine(url)
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'f@every.test')"),
                  {"o": ORG})
    yield eng
    _reset(eng)


def _open_signal_with_card(eng, *, signal_id, card_id, rule_id, node_id, pack="pk", version="1",
                           state="queued", expires=None):
    from sqlalchemy import text
    with eng.begin() as c:
        c.execute(text("insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, "
                       "subject_node_id, score, reason_code, eval_time) "
                       "values (:s, :o, :p, :v, :r, :n, 50, 'rc', :t)"),
                  {"s": signal_id, "o": ORG, "p": pack, "v": version, "r": rule_id, "n": node_id,
                   "t": AT})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, why, actions, artifact, state, expires_at) values "
            "(:c, :s, :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), "
            "cast('[]' as jsonb), cast('{}' as jsonb), :st, :exp)"),
            {"c": card_id, "s": signal_id, "o": ORG, "st": state,
             "exp": expires or AT + timedelta(days=3)})


def _without_references():
    """An engine whose sessions skip FOREIGN KEY triggers (`session_replication_role = replica`).

    The new signal a site writes binds a reasoning run (`signals_reasoning_run_fk`), and persisting a
    whole decision is not what these tests are about. CHECK constraints still run; only the
    references to rows a real decision would have written are not looked up. Scratch database only.
    """
    from sqlalchemy import create_engine
    return create_engine(os.environ["GENIOS_TEST_DATABASE_URL"],
                         connect_args={"options": "-c session_replication_role=replica"})


def _card(eng, card_id):
    from sqlalchemy import text
    with eng.connect() as c:
        state = c.execute(text("select state from cards where card_id = :c"),
                          {"c": card_id}).scalar()
        events = [(r.kind, r.cause) for r in c.execute(text(
            "select kind, cause from card_events where card_id = :c order by occurred_at, id"),
            {"c": card_id})]
    return state, events


def test_runner_emit_replacing_a_signal_leaves_its_card_a_reason(engine):
    from genios_engine.reason.runner import _emit
    _open_signal_with_card(engine, signal_id="sig_old", card_id="c_old", rule_id="r_emit",
                           node_id="n1")
    rule = SimpleNamespace(id="r_emit", version=1, level="prescriptive", reason_code="rc")
    # the authority binding a real decision carries (`signals_authority_binding_shape`, 0031)
    new_id = _emit(SimpleNamespace(engine=_without_references()), ORG, rule, "n1", 60, {}, [],
                   AT, "cs_1",
                   "run_1", "cand_1", "hash_1", AT + timedelta(days=2), "play", 1, "pk", "1")
    assert new_id and new_id != "sig_old"
    assert _card(engine, "c_old") == ("expired", [("card.expired", "replaced")])


def test_publication_replacing_a_claim_leaves_its_card_a_reason(engine):
    from genios_engine.reason.publication import publish_native_signal
    _open_signal_with_card(engine, signal_id="sig_pub", card_id="c_pub", rule_id="r_pub",
                           node_id="n2")
    publication = SimpleNamespace(
        rule_id="r_pub", rule_version=1, level="prescriptive", subject_node_id="n2", score=60,
        score_inputs={}, reason_code="rc", evidence=(), play="play", reasoning_run_id="run_2",
        reasoning_candidate_id="cand_2", reasoning_decision_hash="hash_2",
        authority_expires_at=AT + timedelta(days=2))
    new_id = publish_native_signal(SimpleNamespace(engine=_without_references()), org_id=ORG,
                                   publication=publication, eval_time=AT, config_snapshot_id="cs_2",
                                   pack_id="pk", pack_version="1", authority_pack_revision=1)
    assert new_id and new_id != "sig_pub"
    assert _card(engine, "c_pub") == ("expired", [("card.expired", "replaced")])


def test_lapse_the_sweep_keeps_window_lapsed(engine):
    from genios_engine.deliver.store import CardStore
    _open_signal_with_card(engine, signal_id="sig_lapse", card_id="c_lapse", rule_id="r_l",
                           node_id="n3", state="surfaced", expires=AT - timedelta(minutes=5))
    CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]).sweep_lifecycle(eval_time=AT)
    assert _card(engine, "c_lapse") == ("expired", [("window.lapsed", "expired")])
