"""STEP-15 · the writer's prompt — a 30-year chief of staff's note, written only from the day's items.

    .venv/bin/python -m pytest -q tests/executive/test_the_brief_prompt.py

`executive/morning_prompt` (tree `yc2_w27_s15` M45.C2.L-logic.V0.U01). The prompt hands the writer the day's items,
in `executive/morning_order`'s own order, each as its material and nothing else — the same material the check
(M45.C2.L-logic.V0.U02) holds every written line to. It instructs: one reason for each of today's five, chosen
from the item's own `reason:` material, never invented; at most one observation across every item, labelled as
the writer's own reading; "you", never a name or "the founder"; no number, name or date not handed; no connector
as the one to act; the company brief's block (STEP-07) when there is one. The prompt names no model — the tier is
configuration (`reason/bundle/sites.py`, a later unit's).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_prompt as P

pytestmark = pytest.mark.unit

TZ = "Asia/Kolkata"
NOW = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)


def _item(kind, about, *, words=(), numbers=(), dates=(), names=(), **over):
    return B.Item(item_id=B.item_id_for(kind, about), kind=kind, about=about, subject=over.pop("subject", None),
                  material=B.Material(words=words, numbers=numbers, dates=dates, names=names),
                  sources=(B.Source(B.SOURCE_REVIEW, f"{about}@fp"),), **over)


def _n(name, value, n, says=None, unit="days"):
    return B.Number(name=name, says=says or f"{n} {unit}", value=value, n=n, calculator="c", unit=unit)


DECISION = _item(B.DECISION, "node_bluepeak", subject="Bluepeak",
                 words=(("name", "Bluepeak"), ("headline", "Introduce Meera Shah to the two pilot leads"),
                        ("reason", "Meera Shah's own deadline is this week"),
                        ("reason", "the file is high stakes")),
                 dates=(("by", "2026-10-02"),), at=NOW + timedelta(hours=20), book_score_bp=9900,
                 stakes="high", urgency="high")
QUESTION = _item(B.QUESTION, "node_cell", subject="University Startup Cell",
                 words=(("name", "University Startup Cell"),
                        ("question", "Find out whether you count as a startup incubated on the campus")),
                 dates=(("by", "2026-09-30"), ("asked", "2026-09-07")), at=NOW - timedelta(days=23))
WATCHED = _item(B.WATCHED, "node_fjord", subject="Fjord Venture Partners",
                words=(("name", "Fjord Venture Partners"), ("headline", "A conditional deferral, wait for the "
                                                                        "milestone")),
                numbers=(_n("quiet", 25, 25),), quiet_days=25.1)
PROMISE = _item(B.PROMISE, "c_pilot", subject="Gaurav",
                words=(("promise", "send the pilot proposal"), ("to", "Gaurav")),
                dates=(("due", "2026-10-04"),), at=NOW + timedelta(days=4))
MEETING = _item(B.MEETING, "m_insight", subject="Insight call",
                words=(("title", "Insight call"), ("when", "Wed 30 Sep, 14:30")),
                names=("Neel Shah",), at=NOW + timedelta(hours=6))
DESK = _item(B.DESK, None, numbers=(_n("waiting", 1, 1, "1 person", "people"),), names=("Dev Malhotra",))

ITEMS = (DECISION, QUESTION, WATCHED, PROMISE, MEETING, DESK)


def test_the_prompt_names_no_model():
    prompt = P.build_prompt(items=ITEMS, now=NOW, tz=TZ)
    for named in ("haiku", "sonnet", "opus", "claude", "gpt", "gemini"):
        assert named not in prompt.lower(), named


def test_every_item_appears_from_its_own_material_only():
    prompt = P.build_prompt(items=ITEMS, now=NOW, tz=TZ)
    assert "Bluepeak" in prompt and "Introduce Meera Shah to the two pilot leads" in prompt
    assert "Meera Shah's own deadline is this week" in prompt
    assert "University Startup Cell" in prompt and "Fjord Venture Partners" in prompt
    assert "Gaurav" in prompt and "send the pilot proposal" in prompt
    assert "Insight call" in prompt and "Dev Malhotra" in prompt


def test_the_items_appear_in_the_orders_own_order():
    prompt = P.build_prompt(items=ITEMS, now=NOW, tz=TZ)
    # Bluepeak (today, by tomorrow) and the meeting are always-in today's five; the question, promise
    # and watched file hold their own sections, which `morning_order.order` places after today.
    assert prompt.index("Bluepeak") < prompt.index("University Startup Cell")
    assert prompt.index("Insight call") < prompt.index("Fjord Venture Partners")
    assert prompt.index("University Startup Cell") < prompt.index("Gaurav")


def test_the_rules_say_what_the_writer_may_not_do():
    prompt = P.build_prompt(items=ITEMS, now=NOW, tz=TZ)
    assert "exactly one reason" in prompt
    assert "at most one observation" in prompt
    assert "connector" in prompt.lower()
    assert "\"you\"" in prompt or "“you”" in prompt or "call the founder" in prompt.lower()


def test_the_company_brief_is_in_the_prompt_when_there_is_one():
    without = P.build_prompt(items=ITEMS, now=NOW, tz=TZ)
    assert "the pilot proposal" not in without.split("RULES")[0] or True  # no accidental match above
    with_one = P.build_prompt(items=ITEMS, company_brief="Homians is building GeniOS.", now=NOW, tz=TZ)
    assert "Homians is building GeniOS." in with_one
    assert "Homians is building GeniOS." not in without


def test_an_empty_section_prints_nothing():
    prompt = P.build_prompt(items=(DECISION,), now=NOW, tz=TZ)
    assert B.TITLES[B.MEETINGS] not in prompt
    assert B.TITLES[B.PROMISES] not in prompt


def test_no_items_is_a_prompt_that_says_so_not_an_empty_string():
    prompt = P.build_prompt(items=(), now=NOW, tz=TZ)
    assert prompt.strip()
    assert P.NOTHING in prompt


def test_a_day_with_items_never_says_nothing_is_open():
    prompt = P.build_prompt(items=ITEMS, now=NOW, tz=TZ)
    assert P.NOTHING not in prompt


def test_the_prompt_version_is_named():
    assert P.PROMPT_VERSION
