"""STEP-13b · the pass reads the engine for the files it reviews, and a deploy never uncovers a file.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_a_version_change_keeps_a_file_covered.py

Tree `yc2_w27_s13b` M37.C5.L-integration.V11.U03 (`reason/expert/sweep`). The engine is read for the files DUE for review
only — the Domain Expertise of their situations and kind, what the tenant's brains learned, the units in shadow, and the
company's record (read ONCE a pass) — and the receipt counts the reads, what they cut, the reads that could not be made
and the files whose engine moved. A deploy that moves the prompt, the dossier and the check together, and names the
engine and the record in the fingerprint, leaves every untouched file covered (s13b-F6): its review is checked again on
the dossier it saw, and the file is not reviewed again for it. A file whose engine moved is, covered by the review that
stands until the new one is written.
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.reason.expert import sweep as P
from tests.reason.expert.test_the_expert_pass import ORG, _files_of, _pass, world  # noqa: F401
from tests.reason.expert.test_a_version_change_rechecks_or_reviews_again import _age_the_checks, _rows

pytestmark = pytest.mark.pg

_VISIBILITY = json.dumps({"scope": "org", "principals": []})


def _rule(store, *, version=1, words="A spend over two lakh needs two approvers.", retire=()):
    """One Organization rule of the tenant's: read for every file, whatever its address."""
    with store.engine.begin() as c:
        for v in retire:
            c.execute(text("update learned_brain_entries set active=false where org_id=:o and version=:v"),
                      {"o": ORG, "v": v})
        c.execute(text(
            "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
            " visibility_scope, visibility, active, created_at) "
            "values (:o, 'organization', 'orgrule:spend', :v, :lid, cast(:val as jsonb), 'org', "
            " cast(:vis as jsonb), true, now())"),
            {"o": ORG, "v": version, "lid": f"orgrule:spend:v{version}",
             "val": json.dumps({"statement": words, "confidence_bp": 9000}), "vis": _VISIBILITY})


@pytest.fixture
def rule_world(world):
    store, now = world
    yield store, now
    with store.engine.begin() as c:
        c.execute(text("delete from learned_brain_entries where org_id=:o"), {"o": ORG})


def test_the_engine_is_read_for_the_files_reviewed_and_the_receipt_counts_it(rule_world):
    store, now = rule_world
    _rule(store)
    receipt, expert = _pass(store, now)
    assert receipt["reviewed"] == {"valid": 2}
    assert receipt["engine_reads"] == 2 and receipt["engine_unread"] == 0 and receipt["engine_cut"] == 0
    assert all("[org:" in prompt and "A spend over two lakh needs two approvers." in prompt for prompt in expert.prompts)
    assert all("WHAT THE ENGINE KNOWS ABOUT ITS SITUATIONS" in prompt for prompt in expert.prompts)


def test_a_file_not_due_is_not_read(rule_world):
    store, now = rule_world
    _pass(store, now)
    _rule(store)                           # nothing but the brains changed — that is the engine-moved trigger, below
    again, _ = _pass(store, now + timedelta(minutes=15), max_per_pass=0)
    assert again["engine_reads"] == 0, "carried files are not read"
    quiet, expert = _pass(store, now + timedelta(minutes=30), max_per_pass=0)
    assert quiet["engine_reads"] == 0 and expert.prompts == []


def test_a_file_whose_engine_moved_is_reviewed_again_and_covered_meanwhile(rule_world):
    store, now = rule_world
    _rule(store)
    first, _ = _pass(store, now)
    assert len(first["covered"]) == 2
    _rule(store, version=2, words="A spend over three lakh needs two approvers.", retire=(1,))
    carried, expert = _pass(store, now + timedelta(minutes=15), max_per_pass=0)
    assert expert.prompts == [] and carried["engine_moved"] == 2 and carried["carried"] == 2
    assert carried["covered"] == first["covered"], "the review that stands keeps covering it until the new one is written"
    again, expert = _pass(store, now + timedelta(minutes=30))
    assert len(expert.prompts) == 2 and again["engine_moved"] == 2 and again["reviewed"] == {"valid": 2}
    assert set(again["covered"].values()).isdisjoint(first["covered"].values())
    newest = [r for r in _rows(store).values() if r.fingerprint in again["covered"].values()]
    assert all([t["kind"] for t in r.triggers] == ["engine_moved"] for r in newest), [r.triggers for r in newest]
    assert all("learned-" in t["says"] for r in newest for t in r.triggers)


def test_the_unchanged_engine_is_no_trigger(rule_world):
    store, now = rule_world
    _rule(store)
    _pass(store, now)
    again, expert = _pass(store, now + timedelta(minutes=15))
    assert expert.prompts == [] and again["unchanged"] == 2 and again["engine_moved"] == 0


def test_the_company_record_is_read_once_a_pass(rule_world, monkeypatch):
    store, now = rule_world
    from genios_engine.context import company_record as CR
    calls = []
    real = CR.read_company_record
    monkeypatch.setattr(CR, "read_company_record", lambda *a, **k: calls.append(1) or real(*a, **k))
    _pass(store, now)
    assert len(calls) == 1, "two files reviewed, and the record read once"


def test_an_engine_that_cannot_be_read_is_counted_and_the_file_is_still_reviewed(rule_world, monkeypatch):
    store, now = rule_world
    from genios_engine.reason.expert import file_engine as FE
    monkeypatch.setattr(FE.R, "engine_for", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    receipt, expert = _pass(store, now)
    assert receipt["reviewed"] == {"valid": 2} and receipt["engine_unread"] == 2 and receipt["engine_reads"] == 0
    assert all(f"Not read — {FE.UNREAD}." in prompt for prompt in expert.prompts)


def test_a_record_that_cannot_be_read_is_no_failed_pass(rule_world, monkeypatch):
    store, now = rule_world
    from genios_engine.context import company_record as CR
    monkeypatch.setattr(CR, "read_company_record", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    receipt, _ = _pass(store, now)
    assert receipt["reviewed"] == {"valid": 2}


def test_a_deploy_that_moves_every_version_and_names_the_engine_uncovers_no_file(rule_world):
    """s13b-F6: reviews written before this step (no `engine`, no `self`, older prompt, dossier and check) stay covered —
    checked again on the dossier they saw, the file not reviewed again for a deploy."""
    store, now = rule_world
    first, _ = _pass(store, now)
    _age_the_checks(store)
    with store.engine.begin() as c:
        c.execute(text("update expert_reviews set prompt_version = 'expert-review.v4', "
                       "inputs = (inputs - 'engine' - 'self') || "
                       "'{\"who_decides\": {\"model\": \"claude-sonnet-5\", \"prompt_version\": \"expert-review.v4\", "
                       "\"dossier_version\": \"dossier.v1\"}}'::jsonb, "
                       "fingerprint = 'ffp-before-' || file_id where org_id = :o"), {"o": ORG})
    again, expert = _pass(store, now + timedelta(minutes=15))
    assert expert.prompts == [], "a deploy is no reason to ask the model"
    assert again["untouched"] == 2 and again["unchecked"] == 0 and again["rechecked"] == 2
    assert set(again["covered"]) == set(first["covered"]) and again["checked"] == {"shown": 2}


def test_the_comparison_reads_an_input_a_review_never_named_as_none():
    then = {"events": ["a"], "who_decides": {"model": "m"}}
    now = {"events": ["a"], "engine": "none", "self": "none", "who_decides": {"ladder": "l"}}
    assert P._same_file(then, now)
    assert not P._same_file(then, {**now, "engine": {"route": "route-aaaa", "learned": "none", "units": "u"}})
    assert not P._same_file(then, {**now, "self": "evt_a"})
    assert not P._same_file(None, now)


def test_a_file_whose_facts_moved_too_is_not_covered_by_the_review_that_stood(rule_world):
    """Only an engine that moved is covered meanwhile: a file that has a new mail as well waits, uncovered, as ever."""
    store, now = rule_world
    from tests.context.workstream_world import process
    _rule(store)
    first, _ = _pass(store, now)
    _rule(store, version=2, words="A spend over three lakh needs two approvers.", retire=(1,))
    process(store, ORG, event_id="evt_k_new", sender="kunal@meridianvc.test", thread="t_k", at=now + timedelta(minutes=5))
    carried, _ = _pass(store, now + timedelta(minutes=15), max_per_pass=0)
    kunal = _files_of(store)["evt_k_in"]
    assert kunal not in carried["covered"] and len(carried["covered"]) == 1, carried["covered"]


def test_an_engine_that_moved_on_a_file_checked_by_an_older_check_rechecks_it_and_covers_it(rule_world):
    store, now = rule_world
    _rule(store)
    first, _ = _pass(store, now)
    _age_the_checks(store)
    _rule(store, version=2, words="A spend over three lakh needs two approvers.", retire=(1,))
    carried, expert = _pass(store, now + timedelta(minutes=15), max_per_pass=0)
    assert expert.prompts == [] and carried["rechecked"] == 2 and carried["covered"] == first["covered"]


def test_a_file_the_check_now_refuses_is_not_covered_by_an_engine_move(rule_world):
    store, now = rule_world
    _rule(store)
    first, _ = _pass(store, now)
    with store.engine.begin() as c:
        c.execute(text("update expert_reviews set checked = checked || "
                       "'{\"fate\": \"refused\", \"cited\": [], \"because\": \"nothing_stands\", \"question\": null}'::jsonb "
                       "where org_id = :o"), {"o": ORG})
    _rule(store, version=2, words="A spend over three lakh needs two approvers.", retire=(1,))
    carried, _ = _pass(store, now + timedelta(minutes=15), max_per_pass=0)
    assert carried["covered"] == {}


def test_what_the_engine_cut_is_counted(rule_world):
    store, now = rule_world
    for n in range(10):
        with store.engine.begin() as c:
            c.execute(text(
                "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
                " visibility_scope, visibility, active, created_at) values (:o, 'organization', :s, 1, :s, "
                " cast(:val as jsonb), 'org', cast(:vis as jsonb), true, now())"),
                {"o": ORG, "s": f"orgrule:r{n}", "val": json.dumps({"statement": f"Rule number {n}."}),
                 "vis": _VISIBILITY})
    receipt, _ = _pass(store, now)
    assert receipt["engine_reads"] == 2 and receipt["engine_cut"] == 4, "ten rules, eight shown, twice"


def test_the_one_record_and_the_tenants_corpora_are_what_every_file_is_read_with(rule_world, monkeypatch):
    store, now = rule_world
    from genios_engine.platform.l3_activation import activated_domains
    seen = []
    real = P.read_parts
    monkeypatch.setattr(P, "read_parts", lambda *a, **k: seen.append(k) or real(*a, **k))
    _pass(store, now)
    assert len(seen) == 2 + 2, "every file once for its fingerprint, and the two reviewed once more for the engine"
    assert {id(k["company_record"]) for k in seen if k["company_record"] is not None} and \
        len({id(k["company_record"]) for k in seen}) == 1, "the same record object, read once"
    assert all(k["domains_on"] == activated_domains(store.engine, ORG) for k in seen)
    assert [bool(k.get("engine")) for k in seen].count(True) == 2
