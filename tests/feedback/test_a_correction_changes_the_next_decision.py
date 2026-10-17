"""STEP-16 · M46's acceptance — your correction changes the next decision, and never silently.

    .venv/bin/python -m pytest -q tests/feedback/test_a_correction_changes_the_next_decision.py
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (the door, the dossier and the delta on Postgres)

Tree `yc2_w27_s16` M46.C6.L-integration.V6.U02 (STEP-16 §6). End to end, on the dossier the expert is really shown
(`tests/reason/expert/check_world`) and through the real doors on Postgres:

  * a file is reviewed and its move stands; you correct it on its card — through the dashboard's door, with your
    words — and the dossier carries your verdict, its reason and your words;
  * the correction moves the file: the next sweep's trigger is `founder_corrected`;
  * a review that ignores it is HELD as one question naming your words — never silently; one that cites it and
    waits is shown, and the decision moved (mode and move); both stored decisions are read back with every model
    door poisoned, and the delta names the change;
  * a correction for the kind of work brings back every file of the kind; a bare `wrong` only its own file; a file
    of another kind, nothing.

Negative controls, each caught: the trigger off — nothing brings the file back; the check's rule off — the ignoring
review's move is shown; the dashboard door unwired — the dossier never sees the reason. A question called wrong is
retired and never asked again: `tests/deliver/test_calling_a_question_wrong.py` (U06), not repeated here.
"""
from __future__ import annotations

import dataclasses
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from genios_engine.context.file_judgments import PriorCard, Verdict
from genios_engine.context.founder_corrections import Correction
from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert import fingerprint as F
from genios_engine.reason.expert import triggers as T
from genios_engine.reason.expert import verify as V
from genios_engine.reason.expert.decide import mode_of
from tests.reason.expert import check_world as W

SAID_AT = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
WORDS = "Marco asked for news only on real milestones — don't push him."
MODEL, PROMPT = "claude-sonnet-5", "expert-review.v4"


def _correction(*, scope: str = "file", n: int = 1) -> Correction:
    return Correction(correction_id=f"fc_{n:024d}", file_id=W.FILE, card_id="card_1", feedback_id=None,
                      reason="not_relevant", words=WORDS, scope=scope, kind="investor" if scope == "kind" else None,
                      brief_line_id=None, corrected_by="user_arjun", corrected_at=SAID_AT, state="standing")


REF = f"corr:fc_{1:024d}"


def _parts(*, corrections=(), wrong: bool = False, file_id: str | None = None):
    parts = W.parts()
    if wrong:
        card = PriorCard(card_id="card_1", subject_node_id=W.FILE, headline="Send Marco the short deck",
                         level="prescriptive", state="acted", created_at=SAID_AT, resolved_at=None, events=(),
                         verdicts=(Verdict(cause="wrong", reason="not_relevant", at=SAID_AT),))
        parts = dataclasses.replace(parts, judgments=dataclasses.replace(parts.judgments, cards=(card,)))
    parts = dataclasses.replace(parts, corrections=tuple(corrections))
    return dataclasses.replace(parts, file_id=file_id) if file_id else parts


def _check(review: ExpertReview, parts) -> C.CheckedReview:
    dossier = D.build_dossier(parts)
    people = D.people_of(parts, us=W.US, our_names=W.OUR_NAMES)
    return V.check_review(review, dossier.text, people, evidence_ids=dossier.catalogue.evidence_ids)


def _waits_citing_it() -> ExpertReview:
    raw = W.answer()
    raw["inferences"] = [*raw["inferences"], {"claim": "Marco wants news only on real milestones, and none has landed",
                                               "based_on": [REF]}]
    raw.update(mode="wait", next_move=None, draft=None, alternative=None,
               wait_or_stop="wait for a real milestone before writing to Marco")
    return ExpertReview.from_mapping(raw)


def _triggered(before, now) -> list[str]:
    last = SimpleNamespace(inputs=F.fingerprint_inputs(before, prompt_version=PROMPT),
                           reviewed_at=W.NOW - timedelta(hours=1))
    return [t.kind for t in T.triggers_for(now, F.fingerprint_inputs(now, prompt_version=PROMPT),
                                           last=last)]


# =================================================================================================
# the decision moves — and an ignoring review is held, never silently
# =================================================================================================
def test_your_correction_changes_the_next_decision_mode_and_move():
    before = _check(W.review(), _parts())
    assert before.fate == C.SHOWN and mode_of(W.review(), before) == "act" and before.words.headline, \
        "the first review's move stands"
    corrected = _parts(corrections=(_correction(),))
    ignoring = _check(W.review(), corrected)
    assert ignoring.fate == C.HELD and ignoring.words.headline is None
    assert ignoring.question == f"You said “{WORDS}” on 19 Aug; does it still hold?"
    following = _check(_waits_citing_it(), corrected)
    assert following.fate == C.SHOWN, following.verdicts
    assert mode_of(_waits_citing_it(), following) == "wait" and _waits_citing_it().next_move is None
    assert following.words.headline != before.words.headline, "the decision moved: no move, a wait for the milestone"


def test_the_correction_brings_its_file_back():
    assert T.FOUNDER_CORRECTED in _triggered(_parts(), _parts(corrections=(_correction(),)))


def test_a_kind_correction_brings_every_file_of_the_kind_back_and_a_bare_wrong_only_its_own():
    kind = (_correction(scope="kind"),)
    for other in (W.FILE, "node_second_fund"):
        assert T.FOUNDER_CORRECTED in _triggered(_parts(file_id=other), _parts(corrections=kind, file_id=other))
    assert T.FOUNDER_CORRECTED in _triggered(_parts(), _parts(wrong=True)), "a bare wrong: its own file"
    assert T.FOUNDER_CORRECTED not in _triggered(_parts(file_id="node_programme"),
                                                 _parts(file_id="node_programme")), "nothing reached it"


# ── the negative controls ─────────────────────────────────────────────────────────────────────────
def test_control_the_trigger_off_nothing_brings_the_file_back(monkeypatch):
    monkeypatch.setattr(T, "_corrected", lambda now, then: [])
    assert T.FOUNDER_CORRECTED not in _triggered(_parts(), _parts(corrections=(_correction(),)))


def test_control_the_checks_rule_off_the_ignoring_move_is_shown(monkeypatch):
    real = V.cited_anywhere
    monkeypatch.setattr(V, "cited_anywhere", lambda review: real(review) | {REF})
    assert _check(W.review(), _parts(corrections=(_correction(),))).fate == C.SHOWN, \
        "with the rule off nothing holds it: the rule is what makes it never silent"


# =================================================================================================
# on Postgres — the dashboard's door, the dossier, the delta
# =================================================================================================
from tests.deliver.test_a_card_verdict_reaches_every_reader import AT, decided  # noqa: E402,F401 — fixture
from tests.reason.expert.test_a_covered_file_decides_once import world  # noqa: E402,F401 — fixture
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: E402,F401 — fixture

DOOR_WORDS = "Arjun wants the numbers only after the partner meeting is booked."


def _press(store, org, card):
    from genios_engine.deliver import actions
    return actions.ingest_action(card_store=None, graph=store, org_id=org, card_id=card.card_id, actor="founder",
                                 action="wrong", reason="bad_timing", words=DOOR_WORDS, eval_time=AT,
                                 allow_any_assignee=True)


def _dossier(store, org, anchor):
    with store.engine.connect() as c:
        return D.build_dossier(D.read_parts(c, org, anchor, now=AT + timedelta(hours=1)))


@pytest.mark.pg
def test_through_the_dashboards_door_the_dossier_carries_your_verdict_and_your_words(decided):
    store, org, anchor, card = decided
    out = _press(store, org, card)
    assert out["ok"] is True and out.get("correction_id"), out
    said = _dossier(store, org, anchor).text
    assert "the founder's verdict: wrong — bad_timing" in said
    assert f"[corr:{out['correction_id']}] “{DOOR_WORDS}”" in said


@pytest.mark.pg
def test_control_the_dashboards_door_unwired_the_dossier_never_sees_the_reason(decided, monkeypatch):
    from genios_engine.deliver import verdicts
    store, org, anchor, card = decided
    monkeypatch.setattr(verdicts, "record", lambda *a, **k: None)
    _press(store, org, card)
    assert "the founder's verdict: wrong" not in _dossier(store, org, anchor).text, \
        "unwired, the reason never reaches the expert — the door is what carries it"


@pytest.mark.pg
def test_both_decisions_read_back_with_no_model_and_the_delta_names_the_change(decided, monkeypatch):
    from genios_engine.context import founder_corrections as FC
    from genios_engine.reason import llm_decision_maker, llm_interpretation, llm_sites
    from genios_engine.reason.expert import correction_delta as CD
    from genios_engine.reason.expert import store as R
    from tests.reason.expert.checks import as_written
    store, org, anchor, card = decided
    out = _press(store, org, card)

    def _asked(*_a, **_k):
        raise AssertionError("a model was asked")
    for module, name in ((llm_sites, "make_site_client"), (llm_decision_maker, "decide_with_llm"),
                         (llm_interpretation, "interpret_request")):
        monkeypatch.setattr(module, name, _asked)
    with store.engine.connect() as c:
        events = sorted(r[0] for r in c.execute(__import__("sqlalchemy").text(
            "select event_id from source_events where org_id = :o"), {"o": org}))
    from tests.reason.expert.test_a_covered_file_decides_once import _review
    after = ExpertReview.from_mapping({**_review(events[0]), "mode": "wait", "next_move": None, "draft": None,
                                       "alternative": None, "wait_or_stop": "wait for the partner meeting",
                                       "inferences": [{"claim": "he wants the numbers after the meeting is booked",
                                                       "based_on": [f"corr:{out['correction_id']}"]}]})
    with store.engine.begin() as c:
        R.write_review(c, org_id=org, file_id=anchor, fingerprint="ffp-fund-after-the-correction", model=MODEL,
                       prompt_version=PROMPT, dossier_digest="d" * 64, status=R.VALID, reason=None, review=after,
                       input_tokens=10, output_tokens=10, cost_micro_usd=1, at=AT + timedelta(hours=2),
                       inputs={"events": events, "corrections": [f"corr:{out['correction_id']}"]},
                       triggers=[{"kind": T.FOUNDER_CORRECTED, "says": "you corrected it"}], checked=as_written(after))
        correction = FC.by_id(c, org, out["correction_id"])
    with store.engine.connect() as c:
        [file] = CD.delta_for(c, org, correction).files
    assert (file.before.mode, file.after.mode, file.after.cited, file.changed) == ("act", "wait", True, True)
