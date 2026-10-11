"""STEP-12 M33 · a situation on one of the file's people, or on a node no one owns, stands down too.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_files_people_and_readings_stand_down.py -q

Tree `yc2_w27_s12` M33.C1.L-integration.V2.U13 (`reason/domain_shadow.py`), `03` F173. A file is often a
company, and its situations are anchored on the people who work there, the thread, the meeting's reading,
the dependency a mail stated — not on the company. Anchored on the file alone, the review stood none of
them down: each was decided beside the file's own decision, the decider asked, a second card raised.
Now what a review explains is `reason/expert/cover`'s rule: a situation on the file or one of its people
(the expert pass's `people`) is its own file's; one on a node no one owns is any covered file's whose
review saw all of it. The signals such a situation left open are replaced whatever their subject, and a
file with no situation of its own is filed under one it stood down.

The world is STEP-11's: the fund's file is its company, Banyan Seed Fund, and Arjun, who wrote, works
there. Its situation is moved onto Arjun — the shape a company's file takes when Layer 2 anchors the
work on the person.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _fund, _open_signals, _write, admitted, world)

pytestmark = pytest.mark.pg

FILE_FP = "ffp-fund-company-review-000"


def _on_arjun(store, org) -> tuple[str, str, set[str], set[str]]:
    """The fund's file (its company), Arjun (one of its people), the fund's situations — now anchored
    on Arjun — and every event behind them."""
    company, situations, events = _fund(store, org)
    with store.engine.begin() as c:
        arjun = c.execute(text("select node_id from graph_nodes where org_id = :o and valid_to is null "
                               "   and canonical_key = 'arjun@banyanseed.test'"), {"o": org}).scalar()
        assert arjun, "the premise: the person who wrote has a node"
        c.execute(text("update context_situations set anchor_node_id = :p where org_id = :o "
                       "   and situation_id = any(:s)"), {"o": org, "p": arjun, "s": list(situations)})
    return company, arjun, situations, events


def _compile(store, org, registry, *, covered, people, at=NOW):
    from genios_engine.reason import domain_shadow
    return domain_shadow.shadow_compile(
        store=store, org_id=org, eval_time=at, registry=registry, covered=covered, people=people,
        live_domains=frozenset({"founder_office"}))


def test_a_situation_on_one_of_the_files_people_stands_down(world):
    store, org, registry, reasoned = world
    company, arjun, situations, events = _on_arjun(store, org)
    _write(store, org, company, FILE_FP, events)
    counts = _compile(store, org, registry, covered={company: FILE_FP}, people={company: [arjun]})
    assert counts["covered_situations"] == len(situations) and arjun not in reasoned, counts
    assert counts.get("expert_emitted") == 1, counts
    [signal] = _open_signals(store, org, company)
    assert signal.rule_id == "file_review" and signal.situation_id in situations, \
        "a file with no situation of its own is filed under one it stood down"
    with store.engine.connect() as c:
        ends = {r.situation_id: (r.outcome, r.reason) for r in c.execute(text(
            "select situation_id, outcome, reason from situation_outcomes where org_id = :o"),
            {"o": org})}
        root = c.execute(text(
            "select x.root_node_id, x.root_node_type, m.manifest ->> 'root_entity_type' as declared "
            "  from reasoning_runs r "
            "  join reasoning_context_snapshots x on x.org_id = r.org_id "
            "       and x.context_snapshot_id = r.context_snapshot_id "
            "  join reasoning_capability_snapshots m on m.org_id = r.org_id "
            "       and m.capability_snapshot_id = r.capability_snapshot_id "
            " where r.org_id = :o and r.run_id = :r"), {"o": org, "r": signal.reasoning_run_id}).one()
    assert all(ends[s] == ("decided", "covered_by_review") for s in situations), ends
    assert tuple(root) == (company, "company", "company"), \
        "the file's decision is about the file, not the person whose situation it stood down"


def test_without_the_files_people_a_company_file_stands_none_of_them_down(world):
    """⛔ THE NEGATIVE CONTROL: the same review, the same company, no people handed — the fund's
    situations are Arjun's, not the company's, and are decided on today's path."""
    store, org, registry, reasoned = world
    company, arjun, situations, events = _on_arjun(store, org)
    _write(store, org, company, FILE_FP, events)
    counts = _compile(store, org, registry, covered={company: FILE_FP}, people=None)
    assert counts.get("covered_situations", 0) == 0 and arjun in reasoned, counts
    assert counts.get("covered_without_situation") == 1 and _open_signals(store, org, company) == []


def test_the_signals_its_people_left_open_are_replaced_whatever_their_subject(world):
    store, org, registry, _ = world
    company, arjun, situations, events = _on_arjun(store, org)
    before = _compile(store, org, registry, covered=None, people=None)        # today's path first
    left = [s for s in _open_signals(store, org, arjun) if s.situation_id in situations]
    assert left and before.get("emitted"), before
    _write(store, org, company, FILE_FP, events)
    counts = _compile(store, org, registry, covered={company: FILE_FP}, people={company: [arjun]},
                      at=NOW + timedelta(minutes=15))
    assert counts["covered_signals_replaced"] == len(left), counts
    assert [s.signal_id for s in _open_signals(store, org, arjun)
            if s.situation_id in situations] == []
    assert [s.rule_id for s in _open_signals(store, org, company)] == ["file_review"]


def _as_a_reading(monkeypatch):
    """Read the fund's situation's anchor as a meeting's reading — a node no one owns."""
    from genios_engine.reason import domain_shadow
    monkeypatch.setattr(domain_shadow, "_ACTIVE_SITUATIONS", domain_shadow._ACTIVE_SITUATIONS.replace(
        "n.node_type as anchor_type", "'reading:meeting'::text as anchor_type"))


def test_a_situation_on_a_node_no_one_owns_stands_down_for_any_review_that_saw_it(world, monkeypatch):
    """A thread, a meeting's reading, a stated dependency has no file of its own: the covered file whose
    review saw every event behind it explains it — no people named."""
    store, org, registry, reasoned = world
    company, arjun, situations, events = _on_arjun(store, org)
    _as_a_reading(monkeypatch)
    _write(store, org, company, FILE_FP, events)
    counts = _compile(store, org, registry, covered={company: FILE_FP}, people=None)
    assert counts["covered_situations"] == len(situations) and arjun not in reasoned, counts


def test_a_review_that_saw_part_of_it_explains_none_of_it(world, monkeypatch):
    store, org, registry, reasoned = world
    company, arjun, situations, events = _on_arjun(store, org)
    _as_a_reading(monkeypatch)
    _write(store, org, company, FILE_FP, ["evt_some_other_mail"])
    counts = _compile(store, org, registry, covered={company: FILE_FP}, people={company: [arjun]})
    assert counts.get("covered_situations", 0) == 0 and arjun in reasoned, counts
