"""STEP-12 M33 · the pass names each covered file's people — who is in the file a review answers.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_the_pass_names_each_covered_files_people.py -q

Tree `yc2_w27_s12` M33.C1.L-data.V1.U11 (`reason/expert/sweep.py`), `03` F173. Beside `covered` (file → the
fingerprint of the VALID review that answers it now), the receipt names each covered file's people
(`people`) — exactly the file's own (`context/workstreams.WorkFile.people`: the anchor when it is a
person, everyone who works at it when it is a company) — whichever way the file is covered: reviewed this
pass, unchanged, untouched. A file no valid review answers names no one. Either lane reads it to tell
what belongs to a file (`reason/expert/cover`) without reading the files again.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.context.workstreams import files_for
from tests.reason.expert.test_the_expert_pass import (  # noqa: F401 — a fixture
    ORG, _Expert, _files_of, _pass, world)

pytestmark = pytest.mark.pg


def _people(store, now) -> dict[str, list[str]]:
    with store.engine.connect() as c:
        return {f.file_id: sorted(f.people) for f in files_for(c, ORG, now=now).files}


def test_a_reviewed_file_names_its_own_people(world):
    store, now = world
    receipt, _ = _pass(store, now)
    people = _people(store, now)
    assert set(receipt["covered"]) == set(_files_of(store).values())
    assert receipt["people"] == {f: people[f] for f in receipt["covered"]}
    assert all(receipt["people"].values()), "a covered file with no one in it"


def test_an_unchanged_and_an_untouched_file_name_their_people_too(world):
    store, now = world
    _pass(store, now)
    unchanged, _ = _pass(store, now + timedelta(minutes=15))
    assert unchanged["unchanged"] == 2 and unchanged["reviewed"] == {}
    assert unchanged["people"] == {f: _people(store, now)[f] for f in unchanged["covered"]}
    untouched, _ = _pass(store, now + timedelta(days=11))
    assert untouched["untouched"] == 2 and untouched["reviewed"] == {}
    assert untouched["people"] == {f: _people(store, now)[f] for f in untouched["covered"]}
    assert len(untouched["people"]) == 2


def test_a_file_no_valid_review_answers_names_no_one(world):
    store, now = world

    class _Down(_Expert):
        def call(self, prompt, *, max_tokens=400):
            raise RuntimeError("connection reset")
    failed, _ = _pass(store, now, llm=_Down())
    assert failed["covered"] == {} and failed["people"] == {}


def test_a_tenant_the_pass_skips_names_no_one(world):
    from sqlalchemy import text
    store, now = world
    with store.engine.begin() as c:
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})
    receipt, _ = _pass(store, now)
    assert receipt == {"skipped": "expert_review_not_activated"}


def test_a_companys_file_names_everyone_who_works_there(world):
    """Two people of one fund write: the fund's file holds both, and the receipt names both."""
    from tests.context.workstream_world import process
    store, now = world
    process(store, ORG, event_id="evt_r_in", sender="ravi@meridianvc.test", thread="t_r",
            at=now - timedelta(days=3))
    receipt, _ = _pass(store, now)
    people = _people(store, now)
    crowded = [f for f in receipt["covered"] if len(people[f]) >= 2]
    assert crowded, people
    assert all(receipt["people"][f] == people[f] for f in receipt["covered"])
