"""M45's acceptance: a faithful draft stands the check; every mutation of a line is caught (STEP-15).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 \\
        pytest tests/executive/test_the_brief_in_words.py -q
    … python scripts/golden_score.py --assert-recorded "speedrun008/YC-II W27/03-FINDINGS.md"

Tree `yc2_w27_s15` M45.C5.L-integration.V1.U02. M44's acceptance
(`tests/replays/test_the_morning_brief_is_judged.py`) proved the brief's CONTENT against the golden
set with no model; this is the same proof for its WORDS, now that M45 built one
(`executive/morning_writer.write_brief`). What this file holds against the golden set's own days:

  1. A FAITHFUL draft — `morning_template.words_for`'s own words, the ground truth every item's
     material is built from — stands the check whole: every line KEPT, nothing given back.
  2. Each of the check's own refusals, applied to one line of an otherwise-faithful draft, is
     caught ON THAT LINE ALONE — a name, a number or a date the item does not hold, "the founder",
     a connector named as the one to act (the same mechanism as an invented name: the check has no
     concept of "connector", only of a name the item's material does not hold) — every other line
     stands.
  3. An answer with the wrong COUNT of lines (an item added or dropped) is malformed, not checked
     line by line, and every line is given its template words; an answer with the right count but
     two lines SWAPPED (an item effectively moved to another's line) fails on both — each now holds
     the wrong item's words, which `invention_ok` cannot ground in either.
  4. Two lines failing escalates exactly once, to the Sonnet-class tier, never past it: Opus is not
     a value `reason/bundle/sites.tier_model` can even return. Failing twice more, the template
     stands.
  5. THE NEGATIVE CONTROL. The mutated text itself names what it should not — `Brief`/`Line`'s own
     contract does not forbid a `WRITER` line from holding it; only `morning_check.check_line`
     does. With the check skipped, the Brief contract alone would accept it.

THE BOARD THIS MOVES: nothing. `scripts/golden_score.py --assert-recorded` still matches
`03-FINDINGS.md` — measured on the merge (`65c6f702`) through M45.C5.L-integration.V0.U01
(`738201c7`): `morning_brief` is off by default for every golden tenant, so `write_brief`'s own
step-1 gate degrades every golden case's brief to the exact template `measure()` already read. M45
changes what an ARMED tenant's brief says; it does not touch which cards a case earns or what its
brief contains with the writer off, so the board this unit's own verify command re-measures is the
one M44 already recorded, unmoved.

Without a scratch database every test below skips, as the rest of this suite does — EXCEPT where
`GENIOS_GOLDEN_REQUIRED=1` (the `golden-pg` job), which turns the skip into a failure.
"""
from __future__ import annotations

import os
from collections.abc import Callable

import pytest

from genios_engine.contracts import morning_brief as B
from genios_engine.executive.morning_check import check_answer
from genios_engine.executive.morning_order import order
from genios_engine.executive.morning_template import words_for
from genios_engine.executive.morning_writer import write_brief
from genios_engine.platform.l4_activation import FEATURE_MORNING_BRIEF
from genios_engine.reason.bundle.sites import TIER_T1, TIER_T2
from tests.replays.founder_case import load_cases

pytestmark = [pytest.mark.pg, pytest.mark.golden]

CASES = load_cases()
#: The ten brief-only cases M44's acceptance closed (`06` D12d, minus F18/F53's own named gaps) —
#: the richest, most varied day material the golden set holds, and already the set this
#: programme's own acceptance work reuses rather than inventing a second representative sample.
REPRESENTATIVE = ("F08", "F14", "F20", "F21", "F22", "F23", "F30", "F45", "F54", "F55")
CASE_BY_ID = {c.case_id: c for c in CASES}

#: One day fetch per case per process — each costs a full sweep chain, and several tests below
#: want the same case's day.
_DAYS: dict[str, object] = {}


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL — the golden set "
                    "never skips in its own job")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _day(case_id: str):
    """`case_id`'s day, read on the scratch database with NO model spent (its cassette answers the
    chain) — the input `write_brief` is handed. Memoized: several tests below read the same case."""
    if case_id in _DAYS:
        return _DAYS[case_id]
    from tests.replays import cassettes
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM
    case = CASE_BY_ID[case_id]
    run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True, brief=False)
    from genios_engine.api import routes
    from genios_engine.executive.morning_day import read_day
    from genios_engine.platform.seats import OWNER_SEAT_ID
    engine = routes._graph.engine
    try:
        with engine.connect() as conn:
            day = read_day(conn, run.org_id, OWNER_SEAT_ID, now=case.sweeps[-1])
    finally:
        remove_tenant(engine, run.org_id)
    _DAYS[case_id] = day
    return day


def _ordered(case_id: str):
    """The case's day, flattened in the order `write_brief` would ask about it — items, sections,
    and `words_for`'s own FAITHFUL text for each: the ground truth every item's material holds,
    never invented."""
    day = _day(case_id)
    case = CASE_BY_ID[case_id]
    at, local = case.sweeps[-1], case.sweeps[-1].date()
    ordered = order(day.items, now=at, tz=day.tz)
    items, sections, texts = [], [], []
    for section, held in ordered.sections:
        for item in held:
            items.append(item)
            sections.append(section)
            texts.append(words_for(item, section, local_date=local))
    return items, sections, texts, day


def _founder(case_id: str) -> tuple[str, ...]:
    return (CASE_BY_ID[case_id].founder.name,)


# =================================================================================================
# 1 · a faithful draft — the template's own words — stands the check whole
# =================================================================================================

@pytest.mark.parametrize("case_id", REPRESENTATIVE)
def test_a_faithful_draft_is_kept_whole(case_id):
    _scratch_db()
    items, sections, texts, _day = _ordered(case_id)
    if not items:
        pytest.skip(f"{case_id}: an empty day proves nothing about the check")
    check = check_answer(items, texts, sections=sections, founder=_founder(case_id))
    assert not check.malformed
    given_back = [(l.item_id, l.reason) for l in check.lines if l.verdict != B.KEPT]
    assert not given_back, f"{case_id}: the template's own words were given back: {given_back}"


# =================================================================================================
# 2 · each mutation, on one otherwise-faithful line, is caught on that line alone
# =================================================================================================

#: Each entry mutates ONE faithful line; every other line of the case is untouched. The connector
#: mutation and the name mutation share a mechanism on purpose — `invention_ok` has no idea of
#: "connector", only of a name the item's material does not hold — and the comment says so rather
#: than hiding the overlap.
MUTATIONS: dict[str, Callable[[str], str]] = {
    "invents a name": lambda words: words + " Ask Boardy Introductions about it.",
    "invents a number": lambda words: words + " Within 47 days.",
    "invents a date": lambda words: words + " By 9 Oct 2099.",
    "says the founder": lambda words: words + " The founder should decide.",
    "names a connector as the one to act": lambda words: words + " Ask Tandem Referrals to reply.",
}


@pytest.mark.parametrize("case_id", REPRESENTATIVE)
@pytest.mark.parametrize("mutation", sorted(MUTATIONS), ids=sorted(MUTATIONS))
def test_a_mutated_line_is_given_back_alone(case_id, mutation):
    _scratch_db()
    items, sections, texts, _day = _ordered(case_id)
    if not items:
        pytest.skip(f"{case_id}: an empty day proves nothing about the check")
    mutate = MUTATIONS[mutation]
    for target in range(len(items)):
        mutated_text = mutate(texts[target])
        assert mutated_text != texts[target], f"{case_id}/{mutation}: the mutation is a no-op here"
        answer = list(texts)
        answer[target] = mutated_text
        check = check_answer(items, answer, sections=sections, founder=_founder(case_id))
        assert not check.malformed
        for n, line in enumerate(check.lines):
            if n == target:
                assert line.verdict == B.GIVEN_BACK, (
                    f"{case_id}/{mutation} on item {n}: the mutated line was KEPT — {mutated_text!r}")
                assert line.words == texts[n], f"{case_id}/{mutation}: given back, but not to its own template words"
            else:
                assert line.verdict == B.KEPT, (
                    f"{case_id}/{mutation} on item {target}: an UNTOUCHED line ({n}) was given back "
                    f"too — {line.reason}")
        break   # one target item per case is enough to prove the mechanism; every item is faithful


# =================================================================================================
# 3 · an item added or dropped is malformed; two lines swapped fail on both
# =================================================================================================

@pytest.mark.parametrize("case_id", REPRESENTATIVE)
def test_a_dropped_or_added_line_is_malformed_not_checked_line_by_line(case_id):
    _scratch_db()
    items, sections, texts, _day = _ordered(case_id)
    if len(items) < 1:
        pytest.skip(f"{case_id}: no items to drop or add to")
    dropped = check_answer(items, texts[:-1], sections=sections, founder=_founder(case_id))
    assert dropped.malformed and all(l.verdict == B.GIVEN_BACK for l in dropped.lines)
    added = check_answer(items, (*texts, "An extra line nobody asked for."), sections=sections,
                         founder=_founder(case_id))
    assert added.malformed and all(l.verdict == B.GIVEN_BACK for l in added.lines)


@pytest.mark.parametrize("case_id", REPRESENTATIVE)
def test_two_swapped_lines_fail_on_both(case_id):
    """Not every pair of lines can prove this: two items whose own worlds already overlap — Gaurav
    AT Stackfield, say — can swap and both still ground, because the OTHER item's own material
    already names what moved in. That is not a hole in the check; it is the check correctly
    reading content, never identity. So every different-subject pair is tried, in order, and the
    claim is that AT LEAST ONE of them demonstrates the catch — not that the first candidate must."""
    _scratch_db()
    items, sections, texts, _day = _ordered(case_id)
    pairs = [(i, j) for i in range(len(items)) for j in range(i + 1, len(items))
            if items[i].subject and items[j].subject and items[i].subject != items[j].subject
            and texts[i] != texts[j]]
    if not pairs:
        pytest.skip(f"{case_id}: no two items here have different, named subjects to swap")
    for i, j in pairs:
        swapped = list(texts)
        swapped[i], swapped[j] = swapped[j], swapped[i]
        check = check_answer(items, swapped, sections=sections, founder=_founder(case_id))
        assert not check.malformed                           # the COUNT is still right
        if check.lines[i].verdict == B.GIVEN_BACK and check.lines[j].verdict == B.GIVEN_BACK:
            return
    pytest.skip(f"{case_id}: every different-subject pair's words already ground in the other's "
                "own material — nothing here demonstrates a clean move")


# =================================================================================================
# 4 · two failed lines escalate once, to the Sonnet-class tier, never past it
# =================================================================================================

class _FakeResult:
    def __init__(self, parsed):
        self.parsed, self.raw = parsed, "{}"
        self.input_tokens, self.output_tokens = 400, 80
        self.model, self.ok, self.error, self.truncated = "fake", True, None, False


class _FakeLLM:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def call(self, prompt, *, max_tokens=4096, **_kw):
        self.calls.append(prompt)
        return self.answers.pop(0) if self.answers else _FakeResult({})


@pytest.mark.parametrize("case_id", REPRESENTATIVE)
def test_two_failed_lines_escalate_once_to_sonnet_never_past_it(case_id):
    _scratch_db()
    items, sections, texts, day = _ordered(case_id)
    if len(items) < 2:
        pytest.skip(f"{case_id}: fewer than two items — two cannot fail")
    invented = MUTATIONS["invents a name"]
    haiku_answer = [invented(t) for t in texts[:2]] + list(texts[2:])
    fake1 = _FakeLLM(_FakeResult({"lines": haiku_answer}))
    fake2 = _FakeLLM(_FakeResult({"lines": list(texts)}))
    case = CASE_BY_ID[case_id]
    brief = write_brief(None, org_id=f"org_s15_words_{case_id.lower()}", seat_id="seat_owner",
                        items=day.items, now=case.sweeps[-1], tz=day.tz, founder=_founder(case_id),
                        client_t1=fake1, client_t2=fake2, activated=frozenset({FEATURE_MORNING_BRIEF}))
    assert brief.written_by == B.ESCALATED
    assert brief.tier == TIER_T2
    assert brief.tier in (TIER_T1, TIER_T2), "no third tier exists to reach"
    assert len(fake1.calls) == 1 and len(fake2.calls) == 1, "T2 is asked exactly once"


# =================================================================================================
# 5 · the negative control: the Brief contract alone does not forbid what the check would refuse
# =================================================================================================

@pytest.mark.parametrize("case_id", REPRESENTATIVE)
@pytest.mark.parametrize("mutation", sorted(MUTATIONS), ids=sorted(MUTATIONS))
def test_with_the_check_skipped_the_contract_alone_accepts_the_mutation(case_id, mutation):
    """`Brief`/`Line.__post_init__` (M44.C1, frozen) enforces closed vocabularies, word budgets and
    cross-reference integrity — nothing about what WORDS a `WRITER` line may hold. Built directly,
    skipping `check_line` entirely, the mutated text stands: proof that `morning_check` is the thing
    doing the work this unit's other tests measure, not a redundant restatement of a rule the
    contract already enforced."""
    _scratch_db()
    items, sections, texts, _day = _ordered(case_id)
    if not items:
        pytest.skip(f"{case_id}: an empty day proves nothing about the check")
    mutated = MUTATIONS[mutation](texts[0])
    line = B.Line(line_id=B.line_id_for("org_x", "seat_x", CASE_BY_ID[case_id].sweeps[-1].date(),
                                        sections[0], items[0].item_id),
                 item_id=items[0].item_id, section=sections[0], words=mutated, kind=items[0].kind,
                 subject=items[0].subject, sources=items[0].sources, by=B.WRITER, verdict=B.KEPT)
    assert line.words == mutated, (
        f"{case_id}/{mutation}: the Brief contract alone refused this — it should not, by design; "
        "morning_check is the thing that does")
