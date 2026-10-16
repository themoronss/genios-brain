"""STEP-13 · `06` D48 — a version change re-checks each standing review on the dossier it was reviewed on, and
reviews the file again only when the file moved.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_version_change_rechecks_or_reviews_again.py -q

Tree `yc2_w27_s13` M35.C3.L-integration.V1.U06 (the STEP-13 crosscheck's X11, X12, X13, X36; Rohit answered D48 on
12 Oct). Until here:

  * X13 — a re-check read TODAY's dossier, not the one the review was written against: a fact citing a line no
    longer printed dropped `unknown_evidence`. A dossier's digest moves with the clock (its head is "as of" the
    minute; its quiet days are today's), so no digest of today's dossier can say "the same dossier". The row now
    keeps the dossier it was written against (`0202`, `expert_reviews.dossier`), and a re-check reads THAT one;
  * X11 — a CHECK_VERSION bump uncovered every quiet file whose fingerprint had drifted (`unchecked`), decided per
    situation again, its `file_review` card never cleared; a PROMPT_VERSION bump re-reviewed nothing. Now a
    version change re-checks a standing review when the file is the one it saw (the fingerprint's inputs, who
    decides aside) and reviews the file again — inside the day's budget — when it moved; a file waiting for that
    review keeps its cover;
  * X12 — the file's decision was keyed on the review's fingerprint alone, so a re-check under a new check version
    that HELD a move the old check showed left the old card standing. It is keyed on (fingerprint, check version);
  * X36 — a re-check overwrote the check with no time. `checked_at` says when it ran.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.contracts.claim_check import CHECK_VERSION
from genios_engine.reason.expert import decide as D
from genios_engine.reason.expert import store as R
from genios_engine.reason.expert import sweep as P
from tests.reason.expert.test_the_expert_pass import ORG, _Expert, _files_of, _pass, world  # noqa: F401

pytestmark = pytest.mark.pg

OLD = "check.v1"


def _rows(store):
    with store.engine.connect() as c:
        return {r.fingerprint: r for r in c.execute(text(
            "select file_id, fingerprint, status, checked, checked_at, dossier, reviewed_at, triggers "
            "from expert_reviews where org_id = :o order by file_id, reviewed_at"), {"o": ORG})}


def _age_the_checks(store, version=OLD):
    """Every standing check as an older check version wrote it."""
    with store.engine.begin() as c:
        c.execute(text("update expert_reviews set checked = jsonb_set(checked, '{version}', to_jsonb(cast(:v as text))) "
                       "where org_id = :o and checked is not null"), {"o": ORG, "v": version})


def test_the_check_is_check_v3():
    """The check's behaviour changed in M35.C2.U09-U16 — so a review checked by check.v1 is checked again.
    ⛔ RESTATED by `yc2_w27_s14` M43.C2.L-logic.V1.U01: check.v3 — STEP-13's second fix wave and the gold card's
    alternative and stop rule changed it again; `OLD` (check.v1) is still an older version.
    ⛔ RESTATED by `yc2_w27_s16` M46.C4.L-logic.V3.U06: check.v4 — never silently; `OLD` is older still."""
    assert CHECK_VERSION == "check.v4"


def test_a_review_keeps_the_dossier_it_was_written_against_and_when_it_was_checked(world):
    store, now = world
    receipt, expert = _pass(store, now)
    rows = _rows(store)
    assert len(rows) == 2 and receipt["checked"] == {"shown": 2}
    for row in rows.values():
        assert row.checked_at == row.reviewed_at == now
        assert row.dossier["text"] in expert.prompts[0] + expert.prompts[1], "the dossier the expert was shown"
        assert row.dossier["evidence_ids"] and all(f"[{i}]" in row.dossier["text"]
                                                   for i in row.dossier["evidence_ids"])


def test_a_check_version_change_rechecks_on_the_reviewed_dossier_with_no_call(world):
    store, now = world
    first, _ = _pass(store, now)
    _age_the_checks(store)
    later = now + timedelta(minutes=15)
    again, expert = _pass(store, later)
    assert expert.prompts == [] and again["unchanged"] == 2 and again["rechecked"] == 2
    assert again["covered"] == first["covered"] and again["checked"] == {"shown": 2}
    for row in _rows(store).values():
        assert row.checked["version"] == CHECK_VERSION and row.checked_at == later


def test_a_recheck_reads_the_dossier_the_review_saw_never_todays(world):
    """X13: the review's one fact cites a line its own dossier printed and today's does not."""
    store, now = world
    _pass(store, now)
    kunal = _files_of(store)["evt_k_in"]
    with store.engine.begin() as c:
        c.execute(text(
            "update expert_reviews set "
            " dossier = jsonb_set(jsonb_set(dossier, '{text}', to_jsonb(dossier ->> 'text' || "
            "     E'\\n- [evt_only_then] a mail the file then held')), '{evidence_ids}', "
            "     (dossier -> 'evidence_ids') || '[\"evt_only_then\"]'::jsonb), "
            " review = jsonb_set(review, '{facts}', "
            "     '[{\"claim\": \"a mail the file then held\", \"evidence\": [\"evt_only_then\"]}]'::jsonb) "
            "where org_id = :o and file_id = :f"), {"o": ORG, "f": kunal})
    _age_the_checks(store)
    again, expert = _pass(store, now + timedelta(minutes=15))
    assert expert.prompts == [] and kunal in again["covered"], again
    [row] = [r for r in _rows(store).values() if r.file_id == kunal]
    assert row.checked["fate"] == "shown", "checked on today's dossier, the fact would cite an id it never prints"


def test_a_file_that_moved_is_reviewed_again_when_a_version_changes(world):
    """X11: eleven quiet days later no trigger fires and the fingerprint has drifted — the file moved. Before D48 its
    review was counted `unchecked` and the file uncovered; now it is reviewed again, the version named as why."""
    store, now = world
    first, _ = _pass(store, now)
    _age_the_checks(store)
    quiet, expert = _pass(store, now + timedelta(days=11))
    assert quiet["untouched"] == 2 and quiet["unchecked"] == 0 and len(expert.prompts) == 2
    assert quiet["reviewed"] == {R.VALID: 2} and quiet["version_moved"] == 2
    assert len(quiet["covered"]) == 2 and set(quiet["covered"].values()).isdisjoint(first["covered"].values())
    newest = [r for r in _rows(store).values() if r.fingerprint in quiet["covered"].values()]
    assert all(r.triggers == [{"kind": P.VERSION_MOVED, "says": f"the check moved: {OLD} → {CHECK_VERSION}"}]
               for r in newest), [r.triggers for r in newest]


def test_a_quiet_file_keeps_its_cover_while_its_review_waits(world):
    """The bump never uncovers a file: its re-review is carried (here, no file may be reviewed this pass) and the
    review that stood keeps covering it until one is written."""
    store, now = world
    first, _ = _pass(store, now)
    _age_the_checks(store)
    quiet, expert = _pass(store, now + timedelta(days=11), max_per_pass=0)
    assert expert.prompts == [] and quiet["carried"] == 2
    assert quiet["covered"] == first["covered"]


def test_a_prompt_version_change_alone_reviews_nothing_on_an_unmoved_file(world, monkeypatch):
    """The fingerprint names the prompt, so every fingerprint moves — but the file is the one its review saw: the
    review stands (its check is current), and nothing is asked of the model."""
    store, now = world
    first, _ = _pass(store, now)
    monkeypatch.setattr(P, "PROMPT_VERSION", "expert-review.v99")
    again, expert = _pass(store, now + timedelta(minutes=15))
    assert expert.prompts == [] and again["untouched"] == 2 and again["version_moved"] == 0
    assert again["covered"] == first["covered"]


def test_a_prompt_and_check_change_on_an_unmoved_file_rechecks_it(world, monkeypatch):
    store, now = world
    first, _ = _pass(store, now)
    _age_the_checks(store)
    monkeypatch.setattr(P, "PROMPT_VERSION", "expert-review.v99")
    again, expert = _pass(store, now + timedelta(minutes=15))
    assert expert.prompts == [] and again["rechecked"] == 2 and again["covered"] == first["covered"]
    assert all(r.checked["version"] == CHECK_VERSION for r in _rows(store).values())


def test_a_decision_is_keyed_on_its_review_and_its_check():
    assert D.decision_ref("ffp-1", "check.v2") == "ffp-1@check.v2"
    assert D.fingerprint_of("ffp-1@check.v2") == "ffp-1" and D.check_version_of("ffp-1@check.v2") == "check.v2"
    assert D.fingerprint_of("ffp-1") == "ffp-1" and D.check_version_of("ffp-1") is None, "a run before the key"
    assert D.fingerprint_of(None) is None



def test_a_prompt_version_change_on_a_moved_file_reviews_it_again(world, monkeypatch):
    """Its check is current, its prompt is not, and eleven quiet days moved it: reviewed again, the prompt named."""
    store, now = world
    _pass(store, now)
    monkeypatch.setattr(P, "PROMPT_VERSION", "expert-review.v99")
    quiet, expert = _pass(store, now + timedelta(days=11))
    assert len(expert.prompts) == 2 and quiet["version_moved"] == 2 and quiet["reviewed"] == {R.VALID: 2}
    newest = [r for r in _rows(store).values() if r.fingerprint in quiet["covered"].values()]
    assert {r.triggers[0]["says"] for r in newest} == {"the prompt moved: expert-review.v3 → expert-review.v99"}


def test_a_recheck_that_now_refuses_covers_nothing(world, monkeypatch):
    """Checked again on its own dossier and found standing on nothing, a quiet file's review covers nothing — the
    new check decides, never the one it replaced."""
    store, now = world
    _pass(store, now)
    kunal = _files_of(store)["evt_k_in"]
    with store.engine.begin() as c:
        c.execute(text("update expert_reviews set review = jsonb_set(review, '{facts}', "
                       "'[{\"claim\": \"they wrote\", \"evidence\": [\"evt_never_shown\"]}]'::jsonb) "
                       "where org_id = :o and file_id = :f"), {"o": ORG, "f": kunal})
    _age_the_checks(store)
    monkeypatch.setattr(P, "PROMPT_VERSION", "expert-review.v99")
    again, expert = _pass(store, now + timedelta(minutes=15))
    assert expert.prompts == [] and again["rechecked"] == 2 and kunal not in again["covered"]
    assert len(again["covered"]) == 1 and again["checked"] == {"refused": 1, "shown": 1}


def test_review_file_rechecks_a_standing_review_on_its_own_dossier(world):
    """The review run's own door (`review.review_file`): a standing valid row an older check wrote is checked again
    on the dossier the row kept, not the one it is handed."""
    from genios_engine.contracts.expert_review import DossierCatalogue
    from genios_engine.reason.expert import review as RV
    from genios_engine.reason.expert.dossier import Dossier
    store, now = world
    _pass(store, now)
    kunal = _files_of(store)["evt_k_in"]
    with store.engine.begin() as c:
        c.execute(text(
            "update expert_reviews set "
            " dossier = jsonb_set(jsonb_set(dossier, '{text}', to_jsonb(dossier ->> 'text' || "
            "     E'\\n- [evt_only_then] a mail the file then held')), '{evidence_ids}', "
            "     (dossier -> 'evidence_ids') || '[\"evt_only_then\"]'::jsonb), "
            " review = jsonb_set(review, '{facts}', "
            "     '[{\"claim\": \"a mail the file then held\", \"evidence\": [\"evt_only_then\"]}]'::jsonb) "
            "where org_id = :o and file_id = :f"), {"o": ORG, "f": kunal})
    _age_the_checks(store)
    [row] = [r for r in _rows(store).values() if r.file_id == kunal]
    today = Dossier(org_id=ORG, file_id=kunal, as_of=now, sections=(),
                    catalogue=DossierCatalogue(frozenset(), frozenset()), digest="sha256:today")
    result = RV.review_file(store.engine, org_id=ORG, dossier=today, fingerprint=row.fingerprint, inputs={},
                            triggers=(), gate=None, at=now + timedelta(minutes=5))
    assert (result.written, result.checked.fate, result.checked.version) == (False, "shown", CHECK_VERSION)


def test_the_file_is_the_one_its_review_saw_by_its_inputs_who_decides_aside():
    now = {"events": ["evt_1"], "quiet": ">=7", "who_decides": {"prompt_version": "v3"}}
    assert P._same_file({**now, "who_decides": {"prompt_version": "v2"}}, now)
    assert not P._same_file({**now, "quiet": ">=10"}, now)
    assert not P._same_file(None, now), "a row that kept no inputs saw a file nobody can compare"
