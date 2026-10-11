"""STEP-12 M33 · what a covered file's review explains — one rule for both lanes.

    .venv/bin/python -m pytest -q tests/reason/expert/test_what_a_review_explains.py

Tree `yc2_w27_s12` M33.C1.L-logic.V0.U10 (`reason/expert/cover.py`), `03` F173. A decision about a node
stands down for a covered file when the file's review saw every event behind it, and the node is the
file's own — its anchor or one of its people — or is no one's counterparty (a thread, a meeting's
reading, a stated dependency), when any covered file's review that saw it all explains it. A person, a
company or the tenant is matched by membership only: one introduction of two people is one thread and
two files, and one file's review never stands the other's down.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from genios_engine.reason.expert import cover as C
from genios_engine.reason.expert import store as R

pytestmark = pytest.mark.unit

#: Brandt Labs' file — a company — with Sofia in it; the intro and her reply judged.
BRANDT = C.FileCover(file_id="node_brandt", fingerprint="ffp-brandt", members=frozenset(
    {"node_brandt", "node_sofia"}), seen=frozenset({"evt_intro", "evt_sofia"}))
#: Kim's file — a person, her own — whose review saw the intro too, and a booked call.
KIM = C.FileCover(file_id="node_kim", fingerprint="ffp-kim", members=frozenset({"node_kim"}),
                  seen=frozenset({"evt_intro", "evt_kim", "evt_call"}))
COVERS = C.Covers([KIM, BRANDT])


def test_what_a_review_judged_is_its_events_and_its_booked_meetings():
    assert C.seen({"events": ["evt_a", "evt_b"], "booked": ["evt_c"], "asks": [["l", "k", "us"]]}) == \
        frozenset({"evt_a", "evt_b", "evt_c"})
    assert C.seen(None) == frozenset() and C.seen({"events": None}) == frozenset()


@pytest.mark.parametrize("node", ["node_brandt", "node_sofia"])
def test_the_files_anchor_and_its_people_are_explained_by_its_review(node):
    assert COVERS.explaining(node, "person", ["evt_sofia"]) is BRANDT
    assert COVERS.explaining(node, "company", ["evt_intro", "evt_sofia"]) is BRANDT


def test_an_event_the_review_never_saw_keeps_the_decision_on_its_own_path():
    assert BRANDT.explains(["evt_sofia"]) and not BRANDT.explains(["evt_sofia", "evt_later"])
    assert COVERS.explaining("node_sofia", "person", ["evt_sofia", "evt_later"]) is None


def test_nothing_behind_a_decision_explains_nothing():
    assert not BRANDT.explains([])
    assert COVERS.explaining("node_sofia", "person", []) is None
    assert COVERS.explaining("reading_meeting", "reading:meeting", []) is None


def test_a_person_is_explained_by_their_own_file_only():
    """⛔ One introduction of two people is one thread and two files: Kim's review saw the intro, and it
    must not stand down a decision about Sofia — only Brandt Labs' review may."""
    assert COVERS.explaining("node_sofia", "person", ["evt_intro"]) is BRANDT
    only_kim = C.Covers([KIM])
    assert only_kim.explaining("node_sofia", "person", ["evt_intro"]) is None
    assert only_kim.explaining("node_ravi", "person", ["evt_intro"]) is None
    assert only_kim.explaining("node_acme", "company", ["evt_kim"]) is None


def test_the_tenant_is_never_explained_by_a_file():
    assert COVERS.explaining("tenant_org", "tenant", ["evt_intro"]) is None


@pytest.mark.parametrize("node_type", ["thread", "reading:meeting", "meeting", "stated_dependency",
                                       "condition", "deal"])
def test_a_node_no_one_owns_is_explained_by_any_review_that_saw_it_all(node_type):
    assert COVERS.explaining("node_x", node_type, ["evt_call"]) is KIM
    assert COVERS.explaining("node_x", node_type, ["evt_intro", "evt_sofia"]) is BRANDT
    assert COVERS.explaining("node_x", node_type, ["evt_sofia", "evt_call"]) is None


def test_an_unknown_node_type_is_never_matched_by_its_events():
    assert COVERS.explaining("node_x", None, ["evt_call"]) is None


def test_a_member_is_never_matched_by_another_files_events():
    """A file's person whose own file's review did not see it all is NOT handed to another review."""
    assert COVERS.explaining("node_kim", "reading:meeting", ["evt_sofia"]) is None


def test_the_first_covering_file_is_chosen_in_a_stable_order():
    both = C.FileCover(file_id="node_aaa", fingerprint="ffp-a", members=frozenset({"node_aaa"}),
                       seen=frozenset({"evt_call"}))
    assert C.Covers([KIM, both]).explaining("node_x", "thread", ["evt_call"]) is both
    assert C.Covers([both, KIM]).explaining("node_x", "thread", ["evt_call"]) is both
    assert [c.file_id for c in C.Covers([KIM, both, BRANDT])] == ["node_aaa", "node_brandt", "node_kim"]
    assert len(C.Covers([KIM, BRANDT])) == 2 and len(C.Covers()) == 0


def _row(status=R.VALID, review=object(), inputs=None, file_id="node_brandt", fingerprint="ffp-brandt"):
    return SimpleNamespace(file_id=file_id, fingerprint=fingerprint, status=status, review=review,
                           inputs=inputs if inputs is not None else {"events": ["evt_sofia"],
                                                                     "booked": ["evt_call"]})


def test_a_stored_review_is_a_cover_of_its_file_and_its_people():
    cover = C.cover_of(_row(), people=["node_sofia"])
    assert cover == C.FileCover(file_id="node_brandt", fingerprint="ffp-brandt",
                                seen=frozenset({"evt_sofia", "evt_call"}),
                                members=frozenset({"node_brandt", "node_sofia"}))


def test_only_a_valid_review_covers(monkeypatch):
    rows = {("node_brandt", "ffp-brandt"): _row(),
            ("node_kim", "ffp-kim"): _row(status=R.REFUSED, review=None, file_id="node_kim",
                                          fingerprint="ffp-kim"),
            ("node_ash", "ffp-ash"): _row(review=None, file_id="node_ash", fingerprint="ffp-ash"),
            # A cut answer is never parsed into a review; were one ever carried, it still decides nothing.
            ("node_cut", "ffp-cut"): _row(status=R.TRUNCATED, file_id="node_cut", fingerprint="ffp-cut")}
    monkeypatch.setattr(R, "read_review", lambda conn, org, file_id, fp: rows.get((file_id, fp)))
    covers = C.covers_for(None, "org", {"node_brandt": "ffp-brandt", "node_kim": "ffp-kim",
                                        "node_ash": "ffp-ash", "node_cut": "ffp-cut",
                                        "node_gone": "ffp-gone"},
                          people={"node_brandt": ["node_sofia"]})
    assert [(c.file_id, sorted(c.members)) for c in covers] == [
        ("node_brandt", ["node_brandt", "node_sofia"])]
    assert len(C.covers_for(None, "org", {})) == 0
