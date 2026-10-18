"""M44's acceptance: the golden set judges the morning brief composed after each case's last sweep (STEP-15).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_the_morning_brief_is_judged.py -q
    … GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/genios_test python scripts/golden_score.py --assert-recorded "speedrun008/YC-II W27/03-FINDINGS.md"

Tree `yc2_w27_s15` M44.C5.L-integration.V2.U05. M44.C5.L-contract.V0.U01 let a case's brief be an expectation like
its cards; M44.C5.L-data.V1.U02 restated the twelve brief-only cases (`06` D12d) that a card could never express;
M44.C5.L-integration.V0.U03 made the runner compose the brief, with no model, after a case's last sweep;
M44.C5.L-integration.V1.U04 made the marking judge it. This file is where the four come together, and the four
things M44 promised:

  1. TEN of the twelve brief-only cases now PASS, on their brief alone: F08, F14, F20, F21, F22, F23, F30, F45,
     F54, F55. The other two stay blocked, each on a gap this step did not close: F18 at the gate (`06` D29 —
     the round's notice is archived `not_business`, so no file, no review, no words a brief could read, `03`
     s15-F6), and F53 on s15-D2 (a file decided on the shadow lane is not yet a brief line — that is
     `yc2_w27_s15` M45.C4.L-logic.V0.U01, not built by M44);
  2. every MUST-ABSTAIN case's brief names nothing its case forbids — the subjects a `max: 0` card expectation
     names, and every case's forbidden names and phrases, read over every line the brief composed, not only over
     cards (`tests/replays/marking._brief_checks`);
  3. the brief HIDES NO CARD: every open card a run's last sweep left (`CaseRun.cards`) is the card some line of
     the brief itself names (`BriefLineView.card_id`, read from the item's own `contracts.morning_brief.
     SOURCE_CARD` source — the same link a decision's and a question's line already carry, M44.C3.L-logic.V0.U02
     and `06` D60). Found while measuring this acceptance (`03` provisional s15-F17): `context/your_desk.py`
     read a file's raw open ask, not the expert's own judgment of it, and so told the founder a question was
     still owed when the review — and the engine's own cards — had already read its asker's reply and closed it
     (F38, a must-abstain case). Fixed in `executive/morning_day._resolved_nothing`: the desk excludes a file
     whose current judgment's effective mode (`reason/expert/decide.mode_of`) is `nothing`, read-only;
  4. the NEGATIVE CONTROL: a run that composes no brief at all (`run_case(..., brief=False)`) reads every
     brief-only case NOT_EXPRESSIBLE again — proving PASS #1 is the brief's own doing, not a chain that would
     have passed regardless.

THE BOARD THIS MOVES (measured on a fresh scratch database, `python scripts/golden_score.py`):

    before   founder golden set   must-detect  22/45 (12 not expressible)   must-abstain  13/13 (0 not exercised)   forbidden outputs  0
    after    founder golden set   must-detect  32/45 (0 not expressible)    must-abstain  13/13 (0 not exercised)   forbidden outputs  0
             atlas replays 01–07  passing  6/80   blocked  1/80   not expressible  73                                                  (unchanged)

Ten must-detect cases move from not expressible to pass (#1 above); two (F18, F53) move from not expressible to a
named, strict-xfail failure — `tests/replays/test_founder_cases.py`'s `_param` already turns a `blocked_on` case
into one. Must-abstain never moved past 13/13: the F38 regression this file's own first run measured (12/13) was
caught and fixed (#3) before it ever reached the board recorded in `03-FINDINGS.md` — restated in its five places
beside this unit's commit (`tests/replays/founder_case.py` needed no change: F18 and F53 already carried their
`blocked_on`; `test_the_gate_deletes_nothing.MOVED_AFTER` gained F08, F14, F20, F21, F22, F23, F30; the atlas specs
and the expert-off controls name no brief case and did not move; `03` §F.1).

RESTATED 16 OCT, on the merge of STEP-14 (03 s15-F19 to s15-F22). F53 PASSES now and leaves `BLOCKED`: its file's
shadow line has existed since `yc2_w27_s15` M45.C4.L-logic.V0.U01, and its expectation was restated to the section
the order seats it in (`today`; that unit's own contract: "F53's line restated and its blocked_on lifted") — the
eleventh brief-only case to pass; F18 is the one left blocked (`06` D29). STEP-14's F64, a new must-abstain case,
is judged by test 2 like every other, and its first run on the merge FAILED it: the changed section said
"Northlake: Introly wrote." about an introduction the expert had closed (s15-F20, fixed in `read_changes`). F22,
the same: it passed only on a clumsy question wording until STEP-14's plain ask no longer said "seed grant"
(s15-F19, the question line now carries what its file is about).

Without a scratch database every test below skips, as the rest of this suite does — EXCEPT where
`GENIOS_GOLDEN_REQUIRED=1` (the `golden-pg` job), which turns the skip into a failure.
"""
from __future__ import annotations

import os

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.marking import NOT_EXPRESSIBLE, PASS, brief_judged, judge, says

CASES = load_cases()
#: The twelve cases M44.C5.L-data.V1.U02 restated: a card can never express their answer (`06` D12d); each
#: carries `expected.brief.lines` the marking judges.
BRIEF_ONLY = tuple(c for c in CASES if c.brief is not None and c.brief.lines)
MUST_ABSTAIN = tuple(c for c in CASES if c.kind == "must_abstain")
#: The one of the twelve still blocked — it names the gap in `blocked_on`. (M44 left two: F53 left on 16 Oct.)
BLOCKED = frozenset({"F18"})


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL — the golden set never skips "
                    "in its own job")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


# =================================================================================================
# the twelve are the twelve `06` D12d names, and no more, no fewer
# =================================================================================================
def test_the_twelve_brief_only_cases_are_the_ones_d12d_names():
    assert {c.case_id for c in BRIEF_ONLY} == {
        "F08", "F14", "F18", "F20", "F21", "F22", "F23", "F30", "F45", "F53", "F54", "F55"}
    for case in BRIEF_ONLY:
        assert not case.expressible("cards"), f"{case.case_id}: brief-only, yet its cards are expressible"
    assert {c.case_id for c in BRIEF_ONLY if c.blocked_on} == BLOCKED
    assert {c.case_id for c in BRIEF_ONLY if not c.blocked_on} == {
        "F08", "F14", "F20", "F21", "F22", "F23", "F30", "F45", "F53", "F54", "F55"}


# =================================================================================================
# 1 · eleven of the twelve pass on their brief (ten at M44, F53 on the 16 Oct merge); F18 stays blocked, and says on what
# =================================================================================================
@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", BRIEF_ONLY, ids=lambda c: c.case_id)
def test_a_brief_only_case_passes_on_its_brief_or_stays_named_blocked(case):
    _scratch_db()
    run = cassettes.replayed(case)
    assert run.misses == (), f"{case.case_id}: cassette misses {run.misses}"
    mark = judge(case, run)
    if case.case_id in BLOCKED:
        assert case.blocked_on, f"{case.case_id}: in BLOCKED but names no gap"
        assert mark.verdict != PASS, (
            f"{case.case_id}: passes now — the gap named in blocked_on has closed; lift it, here and in "
            "BLOCKED above")
        return
    assert mark.verdict == PASS, (
        f"{case.case_id} ({case.title}) — {mark.verdict}" + (f", lost at {mark.lost_at}" if mark.lost_at else "")
        + f": {mark.reason}")
    assert brief_judged(case, run), (
        f"{case.case_id}: passed without its brief ever being judged — the brief expectation, or the run, "
        "is not doing what this test thinks it is")


# =================================================================================================
# 2 · every must-abstain case's brief names nothing its case forbids
# =================================================================================================
@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", MUST_ABSTAIN, ids=lambda c: c.case_id)
def test_a_must_abstain_brief_names_nothing_its_case_forbids(case):
    _scratch_db()
    run = cassettes.replayed(case)
    assert run.misses == (), f"{case.case_id}: cassette misses {run.misses}"
    if run.brief is None:
        return                     # nothing composed, nothing to check — `run_case`'s default composes one
    lines = run.brief
    forbidden_hits = sorted({(l.line_id, term) for l in lines
                             for term in (*case.forbidden_names, *case.forbidden_phrases) if says(l.text, term)})
    assert not forbidden_hits, f"{case.case_id}: the brief says {forbidden_hits}"
    never = tuple(t for c in case.cards if c.max == 0 for t in c.about)
    named = [(l.section, l.text) for l in lines if any(says(l.text, t) for t in never)] if never else []
    assert not named, f"{case.case_id}: the brief names {named}, which the case's `max: 0` card forbids"
    mark = judge(case, run)
    assert mark.verdict in (PASS, "not_exercised"), (
        f"{case.case_id} ({case.title}) — {mark.verdict}: {mark.reason}")


# =================================================================================================
# 3 · the brief hides no card: every open card a run's last sweep left is a card some line names
# =================================================================================================
@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_the_brief_hides_no_open_card(case):
    """`CaseRun.cards` is every card the founder could see after AT LEAST ONE sweep (`engine_runner._cards`) — a
    history, not today's queue: a card since given its template words back by a later sweep stands `expired`
    (`deliver/store.CardStore.HISTORY_STATES`), and the brief, read as of the last sweep, is not asked to name a
    card nobody could still act on (`03` F176 — a second, stale card where the review's advice changed, until
    STEP-14's living card). Only a card CURRENTLY open (`OPEN_STATES`) is checked here.

    A card is named by its own id (`BriefLineView.card_id`, a DECISION or QUESTION line's `SOURCE_CARD`) or, where
    the item that names the file carries no card source at all — your desk's waiting list (F55: Dev Malhotra is
    named by the desk line, which cites a calculator and a mailbox's receipt, never a card) — by its subject's own
    name appearing in some line (`says`): the file is not hidden, even where the brief's source trail for it is
    not the card."""
    from genios_engine.deliver.store import CardStore

    _scratch_db()
    run = cassettes.replayed(case)
    assert run.misses == (), f"{case.case_id}: cassette misses {run.misses}"
    open_cards = {c.card_id: c.subject for c in run.cards if c.state in CardStore.OPEN_STATES}
    if not open_cards:
        return                      # nothing open after the last sweep — nothing to hide
    lines = run.brief or ()
    named_by_id = {l.card_id for l in lines if l.card_id}
    missing = sorted(cid for cid, subject in open_cards.items()
                     if cid not in named_by_id and not (subject and any(says(l.text, subject) for l in lines)))
    assert not missing, (
        f"{case.case_id}: card(s) {missing} are open after the last sweep, and no line of the brief names them "
        f"by id or by their subject ({[open_cards[c] for c in missing]})")


# =================================================================================================
# 3b · a small move is a line in the brief and no card (s15-D3, M45.C4.L-integration.V0.U03)
# =================================================================================================
@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id, subject", [("F20", "TechBridge"), ("F23", "State Startup Mission")])
def test_a_small_move_is_a_line_in_the_brief_and_no_card(case_id, subject):
    """F20's meetup and F23's registration are `act` reviews appraised low stakes and low urgency that write to no one:
    decided, remembered, and no signal — so no card — while the brief still says them, in `today`. F61's two silent
    introductions are low/low too, but write to a person (a draft): they stay cards (03 s15-F24)."""
    _scratch_db()
    run = cassettes.replayed(next(c for c in CASES if c.case_id == case_id))
    assert run.cards == ()
    named = [l for l in (run.brief or ()) if says(l.text, subject)]
    (today,) = [l for l in named if l.section == "today"]          # (F23 also has its changed line: "… wrote")
    assert today.card_id is None and not any(l.card_id for l in named)


@pytest.mark.pg
@pytest.mark.golden
def test_a_move_that_writes_to_a_person_stays_a_card_though_it_is_small():
    _scratch_db()
    run = cassettes.replayed(next(c for c in CASES if c.case_id == "F61"))
    subjects = {c.subject for c in run.cards}
    assert any("Omkar" in (s or "") or "Redfern" in (s or "") for s in subjects)
    assert any("Tanvi" in (s or "") or "Copperleaf" in (s or "") for s in subjects)


# =================================================================================================
# 4 · the negative control: with no brief composed, every brief-only case is not expressible again
# =================================================================================================
@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", BRIEF_ONLY, ids=lambda c: c.case_id)
def test_with_no_brief_composed_a_brief_only_case_is_not_expressible_again(case):
    _scratch_db()
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import RecordedLLM

    run = run_case(case, RecordedLLM(cassettes.load(case)), brief=False)
    assert run.misses == (), f"{case.case_id}: cassette misses {run.misses}"
    assert run.brief is None, f"{case.case_id}: brief=False composed one anyway"
    mark = judge(case, run)
    assert mark.verdict == NOT_EXPRESSIBLE, (
        f"{case.case_id}: with no brief composed, marked {mark.verdict} ({mark.reason}) — the brief's PASS is "
        "not the brief's own doing if the case passes without one")
