"""STEP-16 · what you say brings the file back to the expert — `founder_corrected`, "you ask about it" given its door.

    .venv/bin/python -m pytest -q tests/reason/expert/test_a_correction_brings_the_file_back.py
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (the sweep, on Postgres)

Tree `yc2_w27_s16` M46.C4.L-logic.V4.U05 (`reason/expert/triggers`; `05` §5, S16-D2, S16-D3, `s16-F2`). A correction the
last review did not see — the file's own or its kind of work's, as the fingerprint names them — brings the file back;
a correction for the kind brings every file of the kind (nearest deadline first, under the day's cap and
`MAX_PER_PASS`: the sweep's own order). A `wrong` on a card of the file brings that file back, and only it; taking a
card does not (the work you do arrives as evidence). The brief's and the playbook's versions still ride along.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

from genios_engine.context.file_judgments import Verdict
from genios_engine.context.founder_corrections import Correction
from genios_engine.reason.expert import fingerprint as F
from genios_engine.reason.expert import triggers as T
from tests.reason.expert.test_the_dossier import NOW, _parts

MODEL, PROMPT = "claude-sonnet-5", "expert-review.v1"


def _inputs(parts):
    return F.fingerprint_inputs(parts, model=MODEL, prompt_version=PROMPT)


def _last(parts):
    return SimpleNamespace(inputs=json.loads(json.dumps(_inputs(parts))), reviewed_at=NOW - timedelta(hours=1))


def _corrected(parts, *ids, scope="file"):
    return dataclasses.replace(parts, corrections=tuple(Correction(
        correction_id=i, file_id="node_meridian", card_id=None, feedback_id=None, reason=None,
        words="news only on milestones", scope=scope, kind="investor" if scope == "kind" else None,
        brief_line_id=None, corrected_by="user_arjun", corrected_at=NOW, state="standing") for i in ids))


def _verdicts(parts, *verdicts):
    card = dataclasses.replace(parts.judgments.cards[0], verdicts=tuple(verdicts))
    return dataclasses.replace(parts, judgments=dataclasses.replace(parts.judgments, cards=(card,)))


def test_founder_corrected_is_a_trigger_of_its_own():
    assert T.FOUNDER_CORRECTED == "founder_corrected" and T.FOUNDER_CORRECTED in T.KINDS


@pytest.mark.parametrize("scope", ["file", "kind"])
def test_a_correction_the_last_review_did_not_see_brings_the_file_back(scope):
    before = _parts()
    now = _corrected(before, "fc_a", scope=scope)
    found = T.triggers_for(now, _inputs(now), last=_last(before))
    assert [(t.kind, t.says) for t in found] == [
        (T.FOUNDER_CORRECTED, "you corrected it since the last review: corr:fc_a")]


def test_a_correction_it_saw_brings_nothing_and_a_new_one_does():
    seen = _corrected(_parts(), "fc_a")
    assert T.triggers_for(seen, _inputs(seen), last=_last(seen)) == ()
    more = _corrected(_parts(), "fc_a", "fc_b")
    [found] = T.triggers_for(more, _inputs(more), last=_last(seen))
    assert found.says == "you corrected it since the last review: corr:fc_b"


def test_a_withdrawn_correction_brings_nothing():
    """A correction taken back leaves the dossier; nothing new was said."""
    seen = _corrected(_parts(), "fc_a")
    gone = _parts()
    assert T.triggers_for(gone, _inputs(gone), last=_last(seen)) == ()


def test_a_wrong_you_pressed_on_its_card_brings_the_file_back():
    before = _parts()
    now = _verdicts(before, *before.judgments.cards[0].verdicts, Verdict(cause="wrong", reason="not_relevant", at=NOW))
    [found] = T.triggers_for(now, _inputs(now), last=_last(before))
    assert (found.kind, found.says) == (T.FOUNDER_CORRECTED, "you called its card wrong: card:card_1 (not_relevant)")


def test_a_wrong_the_last_review_saw_brings_nothing():
    seen = _verdicts(_parts(), Verdict(cause="wrong", reason="not_relevant", at=NOW))
    assert T.triggers_for(seen, _inputs(seen), last=_last(seen)) == (), "the review that saw it judged it"


def test_taking_a_card_is_no_trigger():
    before = _verdicts(_parts())
    now = _verdicts(before, Verdict(cause="do_it_myself", reason=None, at=NOW))
    assert T.triggers_for(now, _inputs(now), last=_last(before)) == ()


def test_many_corrections_are_listed_then_counted():
    before = _parts()
    now = _corrected(before, *(f"fc_{i:02d}" for i in range(T.LISTED + 3)))
    [found] = T.triggers_for(now, _inputs(now), last=_last(before))
    assert found.says.endswith(" and 3 more") and found.says.count("corr:") == T.LISTED, "listed, then counted"


# =================================================================================================
# on Postgres — the sweep reviews a file again for what you said, and a kind correction every file of the kind
# =================================================================================================
def _brief_names_both_kinds(store, at):
    """Both files are investor work: an in-motion line names each fund's domain."""
    from genios_engine.platform import company_brief, company_brief_store
    with store.engine.begin() as c:
        for domain in ("meridianvc.test", "tamarindfund.test"):
            company_brief_store.add(c, org_id=EP.ORG, section="in_motion", words=f"Raise · {domain} — the seed round",
                                    domain=domain, kind="investor", decided_by="the founder", at=at)
    company_brief.invalidate(EP.ORG)


def _triggers(store):
    from sqlalchemy import text
    with store.engine.connect() as c:
        return {r.file_id: r.triggers for r in c.execute(text(
            "select distinct on (file_id) file_id, triggers from expert_reviews where org_id = :o "
            "order by file_id, reviewed_at desc"), {"o": EP.ORG})}


@pytest.mark.pg
def test_the_sweep_reviews_again_the_file_you_corrected_and_only_it(pass_world):
    from genios_engine.context import founder_corrections as C
    store, now = pass_world
    files = EP._files_of(store)
    kunal = files["evt_k_in"]
    EP._pass(store, now)
    with store.engine.begin() as c:
        kept = C.correct(c, org_id=EP.ORG, file_id=kunal, words="Kunal wants news only on milestones.",
                         scope=C.FILE, by="user_arjun", at=now + timedelta(minutes=5))
    receipt, expert = EP._pass(store, now + timedelta(minutes=15))
    assert receipt["reviewed"] == {"valid": 1} and receipt["unchanged"] == 1 and len(expert.prompts) == 1, receipt
    assert f"corr:{kept.correction_id}" in expert.prompts[0], "your words are in front of the expert"
    assert _triggers(store)[kunal] == [{"kind": T.FOUNDER_CORRECTED,
                                        "says": f"you corrected it since the last review: corr:{kept.correction_id}"}]


@pytest.mark.pg
def test_a_correction_for_the_kind_brings_every_file_of_the_kind_back(pass_world):
    from genios_engine.context import founder_corrections as C
    store, now = pass_world
    _brief_names_both_kinds(store, now - timedelta(days=1))
    files = EP._files_of(store)
    EP._pass(store, now)
    with store.engine.begin() as c:
        kept = C.correct(c, org_id=EP.ORG, file_id=files["evt_k_in"], words="Investors get nothing before a milestone.",
                         scope=C.KIND, kind="investor", by="user_arjun", at=now + timedelta(minutes=5))
    receipt, expert = EP._pass(store, now + timedelta(minutes=15))
    assert receipt["reviewed"] == {"valid": 2} and len(expert.prompts) == 2, receipt
    for file_id in (files["evt_k_in"], files["evt_a_in"]):
        assert {"kind": T.FOUNDER_CORRECTED,
                "says": f"you corrected it since the last review: corr:{kept.correction_id}"} in _triggers(store)[file_id]


from tests.reason.expert import test_the_expert_pass as EP  # noqa: E402
from tests.reason.expert.test_the_expert_pass import world as pass_world  # noqa: E402,F401 — fixture
