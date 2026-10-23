"""STEP-12 M33 · a pack rule stands down for a file its review decided — no second card, no decider.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_pack_rule_stands_down_for_a_decided_file.py -q

Tree `yc2_w27_s12` M33.C1.L-integration.V0.U14 (`reason/runner.run`), `03` F173. The golden set's first
decided re-record measured the general pack's `unanswered_email` beside the file's card on 15 cases — the
same mail, the same matter, the decider asked again. `run` is handed what the files decided on the live
lane explain (`explained`, `reason/expert/cover.Covers`): a rule on one of a decided file's nodes whose
every stored fact came from events the review saw is not reasoned; the open signal it left is replaced,
its cards `replaced`; the stand-down is a suppression row (`covered_by_review`) and a count. A rule
resting on an event the review never saw, or on a fact with no source event, or on a person another
file's review saw, is reasoned as before.

The world is `test_no_new_evidence_keeps_signal`'s: one person we owe a reply — the ball in our court,
their last message five days old — each fact written by a mail.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.reason import runner
from genios_engine.reason.expert.cover import Covers, FileCover

pytestmark = pytest.mark.pg

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
ORG = "m33u14_pack_rule"
PERSON, COMPANY = "m33u14_p1", "m33u14_acme"
MAILS = ("evt_m33u14_asked", "evt_m33u14_nudged")


def _seed_org(store) -> None:
    with store.engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": ORG}
        for r in reqd:
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else f"{ORG}@x.test" if "email" in r.column_name else ORG)
        conn.execute(text(f"insert into orgs ({','.join(cols)}) values ({','.join(ph)}) "
                          "on conflict do nothing"), vals)


@pytest.fixture
def world(pg_store):
    """Ada at Acme, owed a reply: `thread.ball_in_court` written by her ask, `thread.last_inbound` by
    her nudge — each fact with its source event (`graph_source_refs`)."""
    from genios_engine.api.account_routes import _wipe
    from genios_engine.packs.wiring import ensure_defaults, make_registry

    _seed_org(pg_store)
    stale = NOW - timedelta(days=5)
    with pg_store.engine.begin() as conn:
        _wipe(conn, ORG)
        conn.execute(text("delete from signals where org_id=:o"), {"o": ORG})
        conn.execute(text("delete from reasoning_publication_watermarks where org_id=:o"), {"o": ORG})
        conn.execute(text("delete from signal_suppression_log where org_id=:o"), {"o": ORG})
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
            "values (:p, :o, 'person', 'Ada Buyer', 'ada@acme.test'), "
            "       (:c, :o, 'company', 'Acme', 'acme.test')"), {"o": ORG, "p": PERSON, "c": COMPANY})
        for i, (field, value, event_id) in enumerate((
                ("thread.ball_in_court", "us", MAILS[0]),
                ("thread.last_inbound", stale.isoformat(), MAILS[1]))):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, occurred_at) values "
                "(:fv, :f, :o, :p, :field, cast(:v as jsonb), 'string', 'active', :t)"),
                {"fv": f"m33u14_fv{i}", "f": f"m33u14_f{i}", "o": ORG, "p": PERSON, "field": field,
                 "v": json.dumps(value), "t": stale})
            conn.execute(text(
                "insert into graph_source_refs (source_ref_id, org_id, fact_version_id, event_id, source) "
                "values (:id, :o, :fv, :e, 'gmail')"),
                {"id": f"m33u14_sr{i}", "o": ORG, "fv": f"m33u14_fv{i}", "e": event_id})
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, ORG)
    try:
        yield pg_store, registry
    finally:
        with pg_store.engine.begin() as conn:
            _wipe(conn, ORG)


def _cover(seen=MAILS, members=(COMPANY, PERSON)) -> Covers:
    return Covers([FileCover(file_id=COMPANY, fingerprint="ffp-acme", seen=frozenset(seen),
                             members=frozenset(members))])


def _run(store, registry, *, explained, at=NOW):
    return runner.run(org_id=ORG, store=store, eval_time=at, registry=registry, pack_id="general",
                      explained=explained)["outcomes"]


def _signals(store) -> dict[str, str]:
    with store.engine.connect() as c:
        return dict(c.execute(text("select signal_id, status from signals where org_id = :o "
                                   "and rule_id = 'unanswered_email' and subject_node_id = :p"),
                              {"o": ORG, "p": PERSON}).all())


def _suppressed(store) -> list:
    with store.engine.connect() as c:
        return c.execute(text("select rule_id, detail from signal_suppression_log where org_id = :o "
                              "and reason_code = 'covered_by_review' order by id"), {"o": ORG}).all()


@pytest.fixture
def reasoned(monkeypatch):
    """Every (rule, subject) the pack lane reasons — where the decider and R-1 sit."""
    seen: list[tuple[str, str]] = []
    original = runner.reason_legacy_rule

    def _spy(**kw):
        seen.append((kw["rule"].id, kw["context"].node_id))
        return original(**kw)
    monkeypatch.setattr(runner, "reason_legacy_rule", _spy)
    return seen


def test_without_a_decided_file_the_rule_fires_as_before(world, reasoned):
    """⛔ THE NEGATIVE CONTROL: the same world, nothing decided — the reply owed is carded."""
    store, registry = world
    out = _run(store, registry, explained=None)
    assert list(_signals(store).values()) == ["open"], out
    assert ("unanswered_email", PERSON) in reasoned and out.get("covered_by_review", 0) == 0


def test_a_rule_its_files_review_saw_is_not_reasoned_and_says_so(world, reasoned):
    store, registry = world
    out = _run(store, registry, explained=_cover())
    assert _signals(store) == {} and out.get("covered_by_review", 0) >= 1, out
    assert ("unanswered_email", PERSON) not in reasoned, "the decider's path was asked about it"
    stood = [r for r in _suppressed(store) if r.rule_id == "unanswered_email"]
    assert stood and stood[0].detail["file_id"] == COMPANY and stood[0].detail["fingerprint"] == "ffp-acme"


def test_the_open_signal_it_left_is_replaced_by_the_files_decision(world, monkeypatch):
    from genios_engine.platform import card_lifecycle
    store, registry = world
    _run(store, registry, explained=None)
    [before] = list(_signals(store))
    causes: list[tuple[str, tuple]] = []
    original = card_lifecycle.expire_cards

    def _spy(conn, *, org_id, cause, signal_ids=(), **kw):
        causes.append((cause, tuple(signal_ids)))
        return original(conn, org_id=org_id, cause=cause, signal_ids=signal_ids, **kw)
    monkeypatch.setattr(card_lifecycle, "expire_cards", _spy)
    out = _run(store, registry, explained=_cover(), at=NOW + timedelta(hours=6))
    assert _signals(store) == {before: "expired"} and out.get("covered_signals_replaced") == 1, out
    assert causes == [("replaced", (before,))]


def test_an_event_the_review_never_saw_keeps_the_rule_on_its_path(world, reasoned):
    store, registry = world
    out = _run(store, registry, explained=_cover(seen=MAILS[:1]))
    assert list(_signals(store).values()) == ["open"] and out.get("covered_by_review", 0) == 0, out
    assert ("unanswered_email", PERSON) in reasoned


def test_a_fact_with_no_source_event_is_never_explained(world, reasoned):
    store, registry = world
    with store.engine.begin() as c:
        c.execute(text("delete from graph_source_refs where org_id = :o and fact_version_id = 'm33u14_fv1'"),
                  {"o": ORG})
    out = _run(store, registry, explained=_cover())
    assert list(_signals(store).values()) == ["open"] and out.get("covered_by_review", 0) == 0, out


def test_another_files_review_never_stands_a_person_down(world, reasoned):
    """⛔ One introduction of two people is one thread and two files: a review that saw Ada's mails in
    ANOTHER file does not decide what is owed to her."""
    store, registry = world
    out = _run(store, registry, explained=Covers([FileCover(
        file_id="m33u14_other", fingerprint="ffp-other", seen=frozenset(MAILS),
        members=frozenset({"m33u14_other"}))]))
    assert list(_signals(store).values()) == ["open"] and out.get("covered_by_review", 0) == 0, out


def test_the_rule_reads_every_path_it_names():
    from genios_engine.packs.general_v1 import GENERAL_V1
    from genios_engine.reason.rules import rule_from_dict
    rules = {r["id"]: rule_from_dict(r) for r in GENERAL_V1["rules"]}
    assert runner._rule_paths(rules["unanswered_email"]) >= {"thread.ball_in_court", "thread.last_inbound"}
    assert "thread.ball_in_court" in runner._rule_paths(rules["champion_quiet"]), \
        "a condition's fact is read even when it is not an evidence field"
    assert runner._rule_paths(rules["commitment_overdue"]) >= {
        "commitment.due_at", "commitment.action", "commitment.owner"}, \
        "an evidence field is read even when no condition names it"


def _commitment(store, due_event: str = MAILS[0]) -> str:
    """A promise Ada's ask recorded — a node no one's counterparty — overdue since yesterday."""
    node = "m33u14_c1"
    with store.engine.begin() as conn:
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
            "values (:n, :o, 'commitment', 'Send Ada the pricing sheet', 'commitment:m33u14') "
            "on conflict do nothing"), {"n": node, "o": ORG})
        for i, (field, value) in enumerate((
                ("commitment.due_at", (NOW - timedelta(days=1)).isoformat()),
                ("commitment.action", "send Ada the pricing sheet"),
                ("commitment.text", "send Ada the pricing sheet"),   # every promise the pipeline writes has it
                ("commitment.owner", f"{ORG}@x.test"))):     # the org's own address: our promise
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, occurred_at) values "
                "(:fv, :f, :o, :n, :field, cast(:v as jsonb), 'string', 'active', :t)"),
                {"fv": f"m33u14_cfv{i}", "f": f"m33u14_cf{i}", "o": ORG, "n": node, "field": field,
                 "v": json.dumps(value), "t": NOW - timedelta(days=5)})
            conn.execute(text(
                "insert into graph_source_refs (source_ref_id, org_id, fact_version_id, event_id, source) "
                "values (:id, :o, :fv, :e, 'gmail')"),
                {"id": f"m33u14_csr{i}", "o": ORG, "fv": f"m33u14_cfv{i}", "e": due_event})
    return node


def test_a_node_no_one_owns_stands_down_for_any_review_that_saw_it(world, reasoned):
    """A promise is no one's counterparty: the review that saw the mail which made it explains it —
    even with no member of the file named — and without it the promise is reasoned as before."""
    store, registry = world
    node = _commitment(store)
    _run(store, registry, explained=None)
    assert ("commitment_overdue", node) in reasoned, "the premise: the promise is reasoned"
    reasoned.clear()
    out = _run(store, registry, explained=_cover(members=("m33u14_other",)),
               at=NOW + timedelta(hours=1))
    assert ("commitment_overdue", node) not in reasoned and out.get("covered_by_review", 0) >= 1, out
    assert ("unanswered_email", PERSON) in reasoned, "a person is never matched by events"


def _deal(store) -> None:
    """A deal of Acme's, its stage and amount each written by Ada's ask."""
    with store.engine.begin() as conn:
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
            "values ('m33u14_d1', :o, 'deal', 'Acme pilot', 'deal:m33u14') on conflict do nothing"),
            {"o": ORG})
        for i, (field, value) in enumerate((("deal.stage", "proposal"), ("deal.amount", 12000))):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, occurred_at) values "
                "(:fv, :f, :o, 'm33u14_d1', :field, cast(:v as jsonb), 'string', 'active', :t)"),
                {"fv": f"m33u14_dfv{i}", "f": f"m33u14_df{i}", "o": ORG, "field": field,
                 "v": json.dumps(value), "t": NOW - timedelta(days=20)})
            conn.execute(text(
                "insert into graph_source_refs (source_ref_id, org_id, fact_version_id, event_id, source) "
                "values (:id, :o, :fv, :e, 'gmail')"),
                {"id": f"m33u14_dsr{i}", "o": ORG, "fv": f"m33u14_dfv{i}", "e": MAILS[0]})


@pytest.fixture
def native(monkeypatch) -> list[str]:
    """Every subject the shadow native lane reasons — where the decider sits for it."""
    seen: list[str] = []
    original = runner.reason_native_capability

    def _spy(**kw):
        seen.append(kw["context"].node_id)
        return original(**kw)
    monkeypatch.setattr(runner, "reason_native_capability", _spy)
    return seen


def test_the_shadow_native_lane_asks_nothing_about_a_subject_the_review_judged(world, native):
    """`sales.deal_cooling` reasons every deal in shadow, the decider asked; a deal whose every stored
    fact came from mails the review saw is judged — and a deal is no one's counterparty."""
    store, registry = world
    _deal(store)
    runner.run(org_id=ORG, store=store, eval_time=NOW, registry=registry, pack_id="sales",
               explained=None)
    assert "m33u14_d1" in native, "the premise: the native lane reasons the deal"
    native.clear()
    out = runner.run(org_id=ORG, store=store, eval_time=NOW + timedelta(hours=1), registry=registry,
                     pack_id="sales", explained=_cover(members=("m33u14_other",)))["outcomes"]
    assert "m33u14_d1" not in native and out.get("covered_by_review", 0) >= 1, out
    with store.engine.connect() as c:
        rows = c.execute(text("select detail from signal_suppression_log where org_id = :o "
                              "and subject_node_id = 'm33u14_d1' and reason_code = 'covered_by_review'"),
                         {"o": ORG}).all()
    assert rows and rows[0].detail["native"] is True


def test_a_deal_holding_a_fact_with_no_source_event_is_reasoned_as_before(world, native):
    store, registry = world
    _deal(store)
    with store.engine.begin() as c:
        c.execute(text("delete from graph_source_refs where org_id = :o "
                       "   and fact_version_id = 'm33u14_dfv1'"), {"o": ORG})
    runner.run(org_id=ORG, store=store, eval_time=NOW, registry=registry, pack_id="sales",
               explained=_cover(members=("m33u14_other",)))
    assert "m33u14_d1" in native, "a fact nobody can trace to a mail was judged by no review"
