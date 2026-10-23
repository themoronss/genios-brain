"""GeniOS-011 S16.U3 · the snapshot L2 reads has an as-of, its unknowns and its contradictions (real Postgres).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/l2/test_snapshot_as_of_and_unknowns.py -q

Audit item `l3-bounded-snapshot-incomplete` (Atlas v2, `GeniOS-008/00-ARCHITECTURE.md:107`, `02-MIGRATION-PLAN.md`
L3-3: "bounded query API: seeds, hops, max nodes, unknowns and contradictions; bitemporal as-of"):

  * `read_snapshot` built `ReadRequest(seeds, max_nodes)` with no instant, though 5985b6e1 gave the walk one — so
    the snapshot always read the live graph, whatever instant the L2 pass judged at. Now the instant is a REQUIRED
    keyword and the pass hands it its `now`;
  * the view held node ids, edges, revision and truncation, nothing L3 knows it does NOT know and nothing it knows
    is CONTESTED. Now it carries the typed absences on its nodes (`situation_absences`) and the open contradictions
    around them (`discrepancies`, L1's `signal_conflicts`), and block B of the L2 dossier prints them;
  * `ReadRequest.visibility` was declared and read by nothing (`graph_edges` has no visibility column): deleted,
    and the snapshot's own fact-backed reads keep the seed read's rule — no private fact decides what it shows.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context import bounded_read
from genios_engine.reason.l2.dossier import build_l2_dossier
from genios_engine.reason.l2.inputs import L1Conflict
from genios_engine.reason.l2.snapshot import Snapshot
from genios_engine.reason.l2.snapshot import SnapshotContradiction
from genios_engine.reason.l2.snapshot import SnapshotNode
from genios_engine.reason.l2.snapshot import SnapshotUnknown
from genios_engine.reason.l2.snapshot import read_snapshot
from tests.reason.l2.test_the_l2_pass_pg import NOW
from tests.reason.l2.test_the_l2_pass_pg import ORG as PASS_ORG
from tests.reason.l2.test_the_l2_pass_pg import _Client
from tests.reason.l2.test_the_l2_pass_pg import _seed
from tests.reason.l2.test_the_l2_pass_pg import store  # noqa: F401 — the L2 pass's own fixture

ORG = "org_g011_s16u3_snapshot"
T0 = datetime(2026, 9, 1, 9, tzinfo=timezone.utc)
LATER = T0 + timedelta(days=10)
_ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------------------------ the instant is required and handed in

def test_the_snapshot_cannot_be_read_without_an_instant():
    """A default would let the next caller forget it, which is how the walk's `as_of` went unused for three days."""
    param = inspect.signature(read_snapshot).parameters["as_of"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY and param.default is inspect.Parameter.empty


def test_an_empty_snapshot_still_says_its_instant():
    assert read_snapshot(None, ORG, (), as_of=T0).as_of == T0


def test_the_request_has_no_visibility_nothing_applies():
    """Declared, never read by `expand` or `sql_neighbours`, and `graph_edges` has nothing to apply it to."""
    assert "visibility" not in {f.name for f in dataclasses.fields(bounded_read.ReadRequest)}
    passed = []
    for path in (_ROOT / "genios_engine").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) \
                    == "ReadRequest" and any(k.arg == "visibility" for k in node.keywords):
                passed.append(str(path))
    assert not passed, passed


# ------------------------------------------------------------------ the database

@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres L2 tests skipped")
    from genios_engine.platform.db import get_engine
    eng = get_engine(url)
    with eng.begin() as c:
        _wipe(c)
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Snap', 's16u3@example.test')"), {"o": ORG})
        for node, kind, name in (("n_acme", "company", "Acme"), ("n_priya", "person", "Priya"),
                                 ("n_late", "person", "Late Comer"), ("n_far", "company", "Far Away")):
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, display_name) "
                           "values (:n, :o, :t, :d)"), {"n": node, "o": ORG, "t": kind, "d": name})
        for ev, to, recorded in (("e_priya", "n_priya", T0), ("e_late", "n_late", LATER)):
            c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, from_node_id, "
                           " to_node_id, valid_from, recorded_at) values (:ev, :ev, :o, 'works_at', :to, 'n_acme', "
                           " :rec, :rec)"), {"ev": ev, "o": ORG, "to": to, "rec": recorded})
    yield eng
    with eng.begin() as c:
        _wipe(c)


def _wipe(c):
    for table in ("graph_edges", "graph_nodes", "graph_facts", "discrepancies", "signal_conflicts",
                  "situation_absences", "coverage_epochs"):
        c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _snap(engine, as_of=LATER + timedelta(days=1)) -> Snapshot:
    with engine.connect() as c:
        return read_snapshot(c, ORG, ("n_acme",), as_of=as_of)


def _fact(c, fv, node, event, *, private=False):
    c.execute(text("insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, "
                   " created_by_event_id, visibility_scope) values (:fv, :fv, :o, :n, 'deal.value', '1', :e, :v)"),
              {"fv": fv, "o": ORG, "n": node, "e": event, "v": "private" if private else "org"})


def _absence(c, sid, node, fact, kind, *, epoch=None, domain="sales"):
    absent = kind == "genuinely_absent"
    c.execute(text("insert into situation_absences (org_id, situation_id, expected_fact, subject_node_id, "
                   " absence_type, coverage_ready, coverage_basis, coverage_domain, coverage_epoch, "
                   " licenses_negative_inference, computed_at) values (:o, :s, :f, :n, :t, :r, :b, :d, :e, :l, :at)"),
              {"o": ORG, "s": sid, "f": fact, "n": node, "t": kind, "r": True if absent else None,
               "b": ["gmail"] if absent else [], "d": domain, "e": epoch, "l": absent, "at": T0})


def _discrepancy(c, did, node, *, status="open", created=T0, held_fv=None):
    c.execute(text("insert into discrepancies (id, org_id, subject_node_id, field, held, challenger, status, "
                   " created_at) values (:i, :o, :n, 'deal.value', cast(:h as jsonb), cast(:ch as jsonb), :s, :at)"),
              {"i": did, "o": ORG, "n": node, "s": status, "at": created,
               "h": json.dumps({"value": "40000 USD", "fact_version_id": held_fv}),
               "ch": json.dumps({"value": "45000 USD", "event_id": "evt_mail_9"})})


def _signal_conflict(c, cid, events, *, resolution="unresolved_surface_both", detected=T0):
    claims = [{"value": {"evidence": [{"quote": "the call is on Thursday"}]}},
              {"value": {"evidence": [{"quote": "moved to Monday"}]}}]
    c.execute(text("insert into signal_conflicts (conflict_id, org_id, signal_id, field, subject_key, claims, "
                   " resolution, event_ids, detected_at) values (:c, :o, 'sig_x', 'date.value', 'k', "
                   " cast(:cl as jsonb), :r, cast(:ev as jsonb), :at)"),
              {"c": cid, "o": ORG, "cl": json.dumps(claims), "r": resolution, "ev": json.dumps(list(events)),
               "at": detected})


# ------------------------------------------------------------------ as of an instant

@pytest.mark.pg
def test_the_snapshot_reads_the_graph_as_it_stood_at_its_instant(engine):
    before = _snap(engine, as_of=T0 + timedelta(days=1))
    assert {n.node_id for n in before.nodes} == {"n_acme", "n_priya"}, "an edge learned later is not yet known"
    assert before.as_of == T0 + timedelta(days=1)
    after = _snap(engine)
    assert {n.node_id for n in after.nodes} == {"n_acme", "n_priya", "n_late"}


@pytest.mark.pg
def test_the_l2_pass_reads_its_snapshot_at_its_own_now(store, monkeypatch):
    from genios_engine.reason.l2 import sweep as SW
    seen = []
    real = SW.read_snapshot

    def spy(*a, **k):
        seen.append(k.get("as_of"))
        return real(*a, **k)

    monkeypatch.setattr(SW, "read_snapshot", spy)
    _seed(store)
    SW.l2_pass(store=store, org_id=PASS_ORG, now=NOW, llm=_Client())
    assert seen == [NOW], seen


# ------------------------------------------------------------------ unknowns

@pytest.mark.pg
def test_the_typed_absences_on_its_nodes_are_in_the_view(engine):
    with engine.begin() as c:
        _absence(c, "sit_1", "n_acme", "deal.value", "genuinely_absent")
        _absence(c, "sit_2", "n_acme", "deal.value", "genuinely_absent")            # same gap, second situation
        _absence(c, "sit_1", "n_priya", "person.title", "unknowable")
        _absence(c, "sit_3", "n_far", "deal.owner", "genuinely_absent")             # a node outside the view
    unknowns = _snap(engine).unknowns
    assert unknowns == (
        SnapshotUnknown("n_acme", "deal.value", "genuinely_absent", licenses_negative_inference=True),
        SnapshotUnknown("n_priya", "person.title", "unknowable", licenses_negative_inference=False)), unknowns


@pytest.mark.pg
def test_an_absence_drawn_under_superseded_coverage_licenses_nothing(engine):
    with engine.begin() as c:
        c.execute(text("insert into coverage_epochs (org_id, domain, epoch, coverage_ready, fingerprint, opened_at) "
                       "values (:o, 'sales', 2, true, 'fp', :at)"), {"o": ORG, "at": T0})
        _absence(c, "sit_1", "n_acme", "deal.value", "genuinely_absent", epoch=1)
    [u] = _snap(engine).unknowns
    assert u.absence_type == "genuinely_absent" and u.stale_coverage and not u.licenses_negative_inference


# ------------------------------------------------------------------ contradictions

@pytest.mark.pg
def test_an_open_discrepancy_on_its_nodes_is_in_the_view_both_sides(engine):
    with engine.begin() as c:
        _discrepancy(c, "disc_open", "n_acme")
        _discrepancy(c, "disc_snoozed", "n_priya", status="snoozed")
        _discrepancy(c, "disc_settled", "n_acme", status="resolved")
        _discrepancy(c, "disc_far", "n_far")
    found = {(x.kind, x.ref, x.node_id) for x in _snap(engine).contradictions}
    assert found == {("discrepancy", "disc_open", "n_acme"), ("discrepancy", "disc_snoozed", "n_priya")}, found
    [one] = [x for x in _snap(engine).contradictions if x.ref == "disc_open"]
    assert one.field == "deal.value" and one.sides == ("40000 USD", "45000 USD")


@pytest.mark.pg
def test_a_contradiction_detected_after_the_instant_is_not_yet_known(engine):
    with engine.begin() as c:
        _discrepancy(c, "disc_late", "n_acme", created=LATER)
        _fact(c, "fv_1", "n_acme", "evt_a")
        _signal_conflict(c, "cfl_late", ("evt_a",), detected=LATER)
    assert _snap(engine, as_of=T0 + timedelta(days=1)).contradictions == ()
    assert {x.ref for x in _snap(engine).contradictions} == {"disc_late", "cfl_late"}


@pytest.mark.pg
def test_a_discrepancy_whose_held_fact_is_private_is_not_shown(engine):
    with engine.begin() as c:
        _fact(c, "fv_private", "n_acme", "evt_p", private=True)
        _discrepancy(c, "disc_private", "n_acme", held_fv="fv_private")
    assert _snap(engine).contradictions == ()


@pytest.mark.pg
def test_an_open_l1_conflict_on_the_events_behind_its_nodes_is_in_the_view(engine):
    with engine.begin() as c:
        _fact(c, "fv_1", "n_priya", "evt_a")
        _fact(c, "fv_2", "n_far", "evt_far")
        _fact(c, "fv_3", "n_acme", "evt_private", private=True)
        _signal_conflict(c, "cfl_open", ("evt_a", "evt_b"))
        _signal_conflict(c, "cfl_settled", ("evt_a",), resolution="resolved_by_authority")
        _signal_conflict(c, "cfl_far", ("evt_far",))
        _signal_conflict(c, "cfl_private", ("evt_private",))
    got = _snap(engine).contradictions
    assert [(x.kind, x.ref) for x in got] == [("signal_conflict", "cfl_open")], got
    assert got[0].sides == ("the call is on Thursday", "moved to Monday") and got[0].event_ids == ("evt_a", "evt_b")


# ------------------------------------------------------------------ the dossier prints them

def _subject(conflicts=()):
    from genios_engine.reason.l2.inputs import Subject
    return Subject(subject_ref="file:n_acme", file_id="n_acme", seed_key=None, bundle_ids=(), signals=(),
                   conflicts=tuple(conflicts))


_PLAIN = Snapshot(seeds=("n_acme",), nodes=(SnapshotNode("n_acme", "company", "Acme"),), edges=(), revision=7,
                  truncated=False, as_of=T0)


def _dossier(snapshot, subject=None):
    from genios_engine.contracts.reasoning_result import HistoricalContext
    return build_l2_dossier(org_id=ORG, subject=subject or _subject(), as_of=T0, snapshot=snapshot,
                            history=HistoricalContext(cases=()), tools=(), brief_block="b")


def test_block_b_prints_the_unknowns_and_the_contradictions_with_their_ids():
    snap = dataclasses.replace(_PLAIN, unknowns=(
        SnapshotUnknown("n_acme", "deal.value", "genuinely_absent", licenses_negative_inference=True),
        SnapshotUnknown("n_acme", "deal.owner", "unknowable", licenses_negative_inference=False)),
        contradictions=(SnapshotContradiction("discrepancy", "disc_1", "deal.value", ("40000 USD", "45000 USD"),
                                              node_id="n_acme"),
                        SnapshotContradiction("signal_conflict", "cfl_9", "date.value", ("Thursday", "Monday"),
                                              event_ids=("evt_a",))))
    d = _dossier(snap)
    block_b = d.text.split("# B · ")[1].split("\n# C · ")[0]
    assert "deal.value" in block_b and "ABSENT" in block_b and "NOT KNOWN" in block_b
    assert "“40000 USD” vs “45000 USD”" in block_b and "[disc_1]" in block_b
    assert "“Thursday” vs “Monday”" in block_b and "[cfl_9]" in block_b
    assert {"disc_1", "cfl_9", "node:n_acme"} <= d.catalogue.evidence_ids


def test_an_l1_conflict_already_on_the_subject_is_printed_once():
    snap = dataclasses.replace(_PLAIN, contradictions=(
        SnapshotContradiction("signal_conflict", "cfl_9", "date.value", ("Thursday", "Monday"),
                              event_ids=("evt_a",)),))
    d = _dossier(snap, _subject((L1Conflict("cfl_9", "date.value", ("Thursday", "Monday"), ("evt_a",)),)))
    assert d.text.count("[cfl_9]") == 1


def test_a_snapshot_with_neither_prints_as_it_did():
    """Most snapshots have none: their dossier — and so their prompt — must not move."""
    block_b = _dossier(_PLAIN).text.split("# B · ")[1].split("\n# C · ")[0]
    assert block_b.splitlines()[1:] == ["Read at graph@7, from 1 seed(s).",
                                        "- [node:n_acme] company · Acme · the subject"]
