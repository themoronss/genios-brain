"""STEP-15 · the writer: R-8 writes the day, checked line by line; R-8E once if it fails.

    .venv/bin/python -m pytest -q tests/executive/test_the_brief_writer.py

Tree `yc2_w27_s15` M45.C2.L-logic.V1.U03. `executive/morning_writer.write_brief` puts the day's items
through `reason/llm_sites.run_site` on R-8 (Haiku-class), holds the answer to `morning_check`, and asks
R-8E (Sonnet-class) once — only on a real failure (malformed, or `MAX_GIVEN_BACK` lines given back),
the same bar both times. Failing twice, the template stands, in code's own words, and this file is
also where the frozen `Brief` contract's "the template brief spends nothing" rule meets a template
that really was asked for twice and failed both times — flagged in the module docstring, pinned here
by `test_a_failed_escalation_still_reports_zero_on_the_brief_itself`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_order as O
from genios_engine.executive import morning_template as T
from genios_engine.executive import morning_writer as W
from genios_engine.platform.l4_activation import FEATURE_MORNING_BRIEF
from genios_engine.reason.bundle.sites import SITE_BRIEF, SITE_BRIEF_ESCALATE, TIER_T1, TIER_T2

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
TZ = "UTC"
ARMED = frozenset({FEATURE_MORNING_BRIEF})
FOUNDER = ("Rohit Swerashi",)
PG_ORG = "org_scratch_tests"                    # seeded by tests/conftest.py; satisfies the FK


def _item(kind, about, *, words=(), numbers=(), dates=(), names=(), **over):
    return B.Item(item_id=B.item_id_for(kind, about), kind=kind, about=about,
                  subject=over.pop("subject", None),
                  material=B.Material(words=words, numbers=numbers, dates=dates, names=names),
                  sources=(B.Source(B.SOURCE_REVIEW, f"{about}@fp"),), **over)


def _decision(about, name, headline, reason):
    return _item(B.DECISION, about, subject=name,
                 words=(("name", name), ("headline", headline), ("reason", reason)))


DEC1 = _decision("node_bluepeak", "Bluepeak", "Introduce Meera Shah to the two pilot leads",
                 "Meera Shah's own deadline is this week")
DEC2 = _decision("node_cedarview", "Cedarview", "Reply to the pricing question",
                 "Cedarview asked three days ago")


def _flat_order(*items):
    """The SAME flattening `write_brief` does (`morning_order.order`, item_id breaks every tie) —
    a test must answer in this order, not the order it happened to list its fixtures in."""
    ordered = O.order(items, now=NOW, tz=TZ)
    return tuple(item for _section, held in ordered.sections for item in held)


# ── the fakes ─────────────────────────────────────────────────────────────────────────────────

@dataclass
class FakeResult:
    parsed: dict
    input_tokens: int = 900
    output_tokens: int = 100
    model: str = "claude-test-fake"
    ok: bool = True
    error: str | None = None
    truncated: bool = False


class FakeLLM:
    def __init__(self, *answers: FakeResult) -> None:
        self.answers = list(answers)
        self.calls: list[str] = []
        self.model = "claude-test-fake"

    def call(self, prompt: str, *, max_tokens: int = 1000) -> FakeResult:
        self.calls.append(prompt)
        if not self.answers:
            return FakeResult(parsed={}, ok=False, error="no answer queued")
        return self.answers.pop(0)


def _lines_answer(*texts: str) -> FakeResult:
    return FakeResult(parsed={"lines": list(texts)})


def _bad_answer() -> FakeResult:
    """Valid JSON, wrong shape — MALFORMED, the one thing `repair=syntax` may retry."""
    return FakeResult(parsed={"not_lines": []})


def _faithful(item: B.Item) -> str:
    """A line that holds against the item's own material — never invents."""
    m = item.material
    return f"{m.word('name')}: {m.word('headline')} — {m.word('reason')}."


def _inventive(item: B.Item) -> str:
    """A line that invents a name no item holds — always GIVEN_BACK."""
    return f"{item.material.word('name')}: ask Boardy Introductions to help."


def _answer(*pairs: tuple[B.Item, str]) -> FakeResult:
    """`(item, text)` pairs, answered in the order `write_brief` will actually flatten its items —
    never the order the test happened to list its fixtures in."""
    by_id = {item.item_id: text for item, text in pairs}
    flat = _flat_order(*(item for item, _ in pairs))
    return _lines_answer(*(by_id[item.item_id] for item in flat))


# ── nothing to write, or the switch is off: the template, for free ─────────────────────────────

def test_an_empty_day_is_the_template_no_model_touched():
    fake = FakeLLM(_lines_answer("never read"))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(), now=NOW, tz=TZ,
                          client_t1=fake, client_t2=fake, activated=ARMED)
    assert brief.written_by == B.TEMPLATE_BRIEF
    assert brief.cost_micro_usd == 0 and brief.model is None and brief.tier is None
    assert fake.calls == []


def test_not_activated_is_the_template_for_free():
    fake = FakeLLM(_lines_answer(_faithful(DEC1)))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1,), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake, client_t2=fake, activated=frozenset())
    assert brief.written_by == B.TEMPLATE_BRIEF
    assert fake.calls == []


# ── a clean draft stands ─────────────────────────────────────────────────────────────────────

def test_a_clean_haiku_draft_is_written():
    fake1 = FakeLLM(_answer((DEC1, _faithful(DEC1)), (DEC2, _faithful(DEC2))))
    fake2 = FakeLLM()           # never touched
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1, DEC2), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=fake2, activated=ARMED)
    assert brief.written_by == B.WRITTEN
    assert brief.tier == TIER_T1 and brief.model == "claude-test-fake"
    assert brief.cost_micro_usd > 0
    assert "held" in brief.why
    assert all(l.by == B.WRITER and l.verdict == B.KEPT for l in brief.lines if l.kind == B.DECISION)
    assert len(fake1.calls) == 1 and fake2.calls == []


def test_the_one_line_is_never_the_models_words():
    fake1 = FakeLLM(_answer((DEC1, _faithful(DEC1)), (DEC2, _faithful(DEC2))))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1, DEC2), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=FakeLLM(), activated=ARMED)
    ordered = O.order((DEC1, DEC2), now=NOW, tz=TZ)
    assert brief.one_line == T.one_line(ordered)


# ── two given-back lines escalate once, to the Sonnet-class site ───────────────────────────────

def test_two_given_back_lines_escalate_to_sonnet():
    fake1 = FakeLLM(_answer((DEC1, _inventive(DEC1)), (DEC2, _inventive(DEC2))))
    fake2 = FakeLLM(_answer((DEC1, _faithful(DEC1)), (DEC2, _faithful(DEC2))))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1, DEC2), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=fake2, activated=ARMED)
    assert brief.written_by == B.ESCALATED
    assert brief.tier == TIER_T2
    assert "Haiku" in brief.why and "Sonnet" in brief.why
    assert all(l.verdict == B.KEPT for l in brief.lines if l.kind == B.DECISION)
    assert len(fake1.calls) == 1 and len(fake2.calls) == 1


def test_one_given_back_line_is_not_enough_to_escalate():
    fake1 = FakeLLM(_answer((DEC1, _inventive(DEC1)), (DEC2, _faithful(DEC2))))
    fake2 = FakeLLM()
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1, DEC2), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=fake2, activated=ARMED)
    assert brief.written_by == B.WRITTEN
    assert fake2.calls == []
    dec1_line = next(l for l in brief.lines if l.item_id == DEC1.item_id)
    assert dec1_line.verdict == B.GIVEN_BACK and dec1_line.words == T.words_for(DEC1, B.TODAY)


def test_malformed_past_its_one_repair_escalates_too():
    fake1 = FakeLLM(_bad_answer(), _bad_answer())      # the gate's one syntax retry, also bad
    fake2 = FakeLLM(_answer((DEC1, _faithful(DEC1)), (DEC2, _faithful(DEC2))))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1, DEC2), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=fake2, activated=ARMED)
    assert brief.written_by == B.ESCALATED
    assert len(fake1.calls) == 2            # the one repair, spent


# ── both fail: the template stands, honestly ─────────────────────────────────────────────────

def test_both_attempts_failing_falls_to_the_template():
    fake1 = FakeLLM(_answer((DEC1, _inventive(DEC1)), (DEC2, _inventive(DEC2))))
    fake2 = FakeLLM(_answer((DEC1, _inventive(DEC1)), (DEC2, _inventive(DEC2))))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1, DEC2), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=fake2, activated=ARMED)
    assert brief.written_by == B.TEMPLATE_BRIEF
    assert all(l.by == B.TEMPLATE for l in brief.lines)
    for word in ("Haiku", "Sonnet", "failed"):
        assert word in brief.why


def test_a_failed_escalation_still_reports_zero_on_the_brief_itself():
    """The frozen `Brief` contract's own rule, met literally even though two real consults were
    spent — see the module docstring's flagged gap."""
    fake1 = FakeLLM(_bad_answer(), _bad_answer())
    fake2 = FakeLLM(_bad_answer(), _bad_answer())
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1,), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=fake2, activated=ARMED)
    assert brief.written_by == B.TEMPLATE_BRIEF
    assert brief.cost_micro_usd == 0 and brief.model is None and brief.tier is None


# ── the cost is the honest total, through an escalation ─────────────────────────────────────────

def test_the_cost_sums_through_an_escalation():
    fake1 = FakeLLM(_answer((DEC1, _inventive(DEC1)), (DEC2, _inventive(DEC2))))
    fake2 = FakeLLM(_answer((DEC1, _faithful(DEC1)), (DEC2, _faithful(DEC2))))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(DEC1, DEC2), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=fake2, activated=ARMED)
    from genios_engine.reason.bundle.budget import cost_micro_usd
    # Recompute both calls' cost the same way the gate does, from the fakes' own token counts.
    expected = (cost_micro_usd(tier=TIER_T1, input_tokens=900, output_tokens=100)
               + cost_micro_usd(tier=TIER_T2, input_tokens=900, output_tokens=100))
    assert brief.cost_micro_usd == expected


# ── a verbose draft is cut from the back, never raised ───────────────────────────────────────

def test_a_verbose_kept_draft_is_cut_not_raised():
    decisions = tuple(_decision(f"node_{n}", f"Company{n}", f"Decide on Company{n}'s renewal",
                               f"Company{n} asked recently") for n in range(5))
    filler = " ".join(["please follow up carefully and thoroughly"] * 40)   # ~240 words, no invention

    def _long(item: B.Item) -> str:
        return f"{item.material.word('name')}: {item.material.word('headline')} — {filler}."

    fake1 = FakeLLM(_answer(*((d, _long(d)) for d in decisions)))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=decisions, now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=FakeLLM(), activated=ARMED)
    assert brief.words <= B.WORD_BUDGET
    assert brief.cut            # something was cut from the back to make room


# ── two gates, two budgets — never one borrowing the other's ────────────────────────────────────

def test_each_sites_gate_carries_its_own_budget():
    """`_gate(SITE_BRIEF, ...)` must open R-8's own ledger, never R-8E's — the two numbers in
    `OWN_BUDGETS` happen to be equal, so only the `budget.site` itself tells them apart."""
    gate1 = W._gate(SITE_BRIEF, org_id="org_x", engine=None, client=None, activated=ARMED, now=NOW)
    gate2 = W._gate(SITE_BRIEF_ESCALATE, org_id="org_x", engine=None, client=None, activated=ARMED,
                   now=NOW)
    assert gate1.budget.site == SITE_BRIEF
    assert gate2.budget.site == SITE_BRIEF_ESCALATE


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from genios_engine.platform.db import get_engine
    eng = get_engine(url)

    def _clear():
        with eng.begin() as c:
            c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": PG_ORG})
            c.execute(text("delete from l4_r_site_generations where org_id = :o"), {"o": PG_ORG})
    _clear()
    yield eng
    _clear()


def _spent(eng, site: str, micro: int) -> None:
    from genios_engine.reason.bundle.sites import tier_for
    with eng.begin() as c:
        c.execute(text(
            "insert into l4_r_site_calls (org_id, site, outcome, tier, cache_key, cost_micro_usd, "
            "created_at) values (:o, :s, 'ran', :t, 'k', :m, :at)"),
            {"o": PG_ORG, "s": site, "t": tier_for(site), "m": micro, "at": NOW})


@pytest.mark.pg
def test_r8_runs_through_write_brief_on_its_own_unspent_budget_even_when_r8e_is_broke(engine):
    """End to end, through `write_brief` itself (not `_gate` in isolation): R-8E's whole day spent
    must not stop R-8 — the exact mix `_gate`'s own site parameter must get right on each of the
    two calls inside `write_brief`."""
    _spent(engine, SITE_BRIEF_ESCALATE, 250_000)       # R-8E's entire $0.25 day, gone
    fake1 = FakeLLM(_lines_answer(_faithful(DEC1)))
    brief = W.write_brief(engine, org_id=PG_ORG, seat_id="seat_x", items=(DEC1,), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=FakeLLM(), activated=ARMED)
    assert brief.written_by == B.WRITTEN
    assert len(fake1.calls) == 1


@pytest.mark.pg
def test_r8e_runs_through_write_brief_on_its_own_unspent_budget_even_when_r8_is_broke(engine):
    """The symmetric case: R-8's whole day spent must not stop the escalation to R-8E."""
    _spent(engine, SITE_BRIEF, 250_000)                 # R-8's entire $0.25 day, gone
    fake2 = FakeLLM(_lines_answer(_faithful(DEC1)))
    brief = W.write_brief(engine, org_id=PG_ORG, seat_id="seat_x", items=(DEC1,), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=FakeLLM(), client_t2=fake2, activated=ARMED)
    assert brief.written_by == B.ESCALATED
    assert len(fake2.calls) == 1


# ── the word budget leaves room for the one line, before `fit` cuts ─────────────────────────────

def test_the_fit_budget_reserves_room_for_the_one_line():
    """`ONE_LINE_RESERVE` (30 words) comes OUT of `WORD_BUDGET` before `fit` decides what survives
    — `morning_template.template_brief`'s own reservation, matched here. A single, otherwise-kept
    line long enough to clear 570 words but not 600 is cut only because the reserve is honoured."""
    from genios_engine.executive.morning_template import ONE_LINE_RESERVE
    assert B.WORD_BUDGET - ONE_LINE_RESERVE == 570
    solo = _decision("node_solo", "SoloCo", "Decide on SoloCo's renewal", "SoloCo asked recently")
    long_line = "SoloCo: " + " ".join(["please"] * 580)      # 581 words total, grounded
    assert 570 < B.count_words(long_line) <= 600
    fake1 = FakeLLM(_lines_answer(long_line))
    brief = W.write_brief(None, org_id="org_x", seat_id="seat_x", items=(solo,), now=NOW, tz=TZ,
                          founder=FOUNDER, client_t1=fake1, client_t2=FakeLLM(), activated=ARMED)
    assert not any(l.item_id == solo.item_id for l in brief.lines)
    assert brief.cut and brief.cut[0][0] == B.TODAY
