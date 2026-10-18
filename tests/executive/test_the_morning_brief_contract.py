"""STEP-15 · what a morning brief is — items, sections, lines and the brief, frozen and read back as stored.

    .venv/bin/python -m pytest -q tests/executive/test_the_morning_brief_contract.py

`genios_engine/contracts/morning_brief.py` (tree `yc2_w27_s15` M44.C1.L-contract.V0.U01; STEP-15 §8.4-§8.5). An
ITEM is one thing of the day — its kind (closed), what it is about, the material its words may use and its
sources; a LINE is an item's words in a section, whose words they are and what the check said; the BRIEF is
one seat's morning, in the sections' order, each section capped, inside 600 words. Pure: no I/O, no clock.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from genios_engine.contracts import morning_brief as B

pytestmark = pytest.mark.unit

AT = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)
DAY = date(2026, 9, 30)


def _item(kind=B.DECISION, about="node_bluepeak", **over):
    material = over.pop("material", B.Material(
        words=(("headline", "Introduce Meera Shah to the two pilot leads"),),
        numbers=(B.Number(name="your_reply_time", says="usually 1.5 days (n=6, person)", value=1.5, n=6,
                          calculator="context/workstream_numbers.your_reply_time", unit="days"),),
        dates=(("due", "2026-10-01"),), names=("Meera Shah", "Bluepeak")))
    sources = over.pop("sources", (B.Source(B.SOURCE_REVIEW, "node_bluepeak@ffp1"),))
    rich = {"mode": "act", "stakes": "high", "urgency": "high", "at": AT, "quiet_days": 15.1, "our_move": True,
            "book_score_bp": 9000, "card_id": "card_1", "lane": "live"} if kind == B.DECISION else {}
    return B.Item(item_id=B.item_id_for(kind, about), kind=kind, about=about,
                  subject=over.pop("subject", "Meera Shah"), material=material, sources=sources,
                  **{**rich, **over})


def _line(item, section=B.TODAY, words="Bluepeak — introduce Meera Shah to the two pilot leads.", **over):
    return B.Line(line_id=B.line_id_for("org_a", "seat_owner", DAY, section, item.item_id),
                  item_id=item.item_id, section=section, words=words, kind=item.kind,
                  subject=item.subject, sources=item.sources, **over)


def _brief(lines=None, items=None, **over):
    item = _item()
    items = (item,) if items is None else items
    lines = (_line(item),) if lines is None else lines
    fields = dict(org_id="org_a", seat_id="seat_owner", local_date=DAY, timezone="Asia/Kolkata", as_of=AT,
                  one_line="1 thing needs you.", lines=lines, items=items, written_by=B.TEMPLATE_BRIEF,
                  why="the template: no model is armed for this tenant", model=None, tier=None,
                  cost_micro_usd=0, cut=(), material_digest=B.digest_of(items))
    fields.update(over)
    return B.Brief(**fields)


# ── the vocabularies ──────────────────────────────────────────────────────────────────────────────
def test_the_vocabularies_are_closed_and_ordered():
    assert B.KINDS == ("decision", "question", "watched", "promise", "meeting", "no_follow_up", "desk",
                       "change")
    assert B.SECTIONS == ("today", "desk", "changed", "stuck", "asked", "promises", "meetings", "watching")
    assert set(B.CAPS) == set(B.SECTIONS) and B.CAPS[B.TODAY] == 5
    assert all(cap >= 1 for cap in B.CAPS.values())
    assert set(B.TITLES) == set(B.SECTIONS)
    assert B.WORD_BUDGET == 600 == 3 * B.WORDS_PER_MINUTE
    assert B.BY == ("template", "writer")
    assert B.LINE_VERDICTS == ("kept", "given_back")
    assert B.WRITTEN_BY == ("template", "written", "escalated")


# ── an item ───────────────────────────────────────────────────────────────────────────────────────
def test_an_item_carries_its_material_and_names_its_sources():
    item = _item()
    assert item.material.word("headline") == "Introduce Meera Shah to the two pilot leads"
    assert item.material.word("nothing") is None
    assert item.material.date("due") == "2026-10-01" and item.material.date("start") is None
    assert item.material.number("your_reply_time").n == 6
    assert item.material.number("missing") is None
    assert item.item_id == B.item_id_for(B.DECISION, "node_bluepeak") != B.item_id_for(B.QUESTION, "node_bluepeak")
    assert B.item_id_for(B.DECISION, "node_bluepeak").startswith("bi_")


@pytest.mark.parametrize("over, why", [
    ({"kind": "nudge"}, "kind"),
    ({"sources": ()}, "source"),
    ({"subject": "meera@bluepeak.test"}, "address"),
    ({"stakes": "huge"}, "stakes"),
    ({"urgency": "now"}, "urgency"),
    ({"lane": "dark"}, "lane"),
])
def test_an_item_that_is_not_one_is_refused(over, why):
    kind = over.pop("kind", B.DECISION)
    with pytest.raises(ValueError, match=why):
        _item(kind=kind, **over)


def test_a_source_and_a_number_are_closed():
    with pytest.raises(ValueError, match="source"):
        B.Source("rumour", "x")
    with pytest.raises(ValueError, match="ref"):
        B.Source(B.SOURCE_MAIL, " ")
    with pytest.raises(ValueError, match="calculator"):
        B.Number(name="n", says="3", value=3, n=3, calculator="")
    with pytest.raises(ValueError, match="says"):
        B.Number(name="n", says="", value=3, n=3, calculator="c")
    with pytest.raises(ValueError, match="n"):
        B.Number(name="n", says="3", value=3, n=-1, calculator="c")


def test_an_item_id_is_its_content():
    assert B.item_id_for(B.DESK, None) == B.item_id_for(B.DESK, None)
    assert B.item_id_for(B.PROMISE, "c1") != B.item_id_for(B.PROMISE, "c2")


# ── a line ────────────────────────────────────────────────────────────────────────────────────────
def test_a_line_says_whose_words_and_what_the_check_said():
    item = _item()
    template = _line(item)
    assert template.by == B.TEMPLATE and template.verdict is None and template.reason is None
    written = _line(item, by=B.WRITER, verdict=B.KEPT)
    assert written.by == B.WRITER
    back = _line(item, verdict=B.GIVEN_BACK, reason="name:Initech")
    assert back.by == B.TEMPLATE and back.reason == "name:Initech"


@pytest.mark.parametrize("over, why", [
    ({"section": "later"}, "section"),
    ({"words": "  "}, "words"),
    ({"by": "model"}, "by"),
    ({"by": B.WRITER}, "check"),                                   # a written line was checked
    ({"by": B.WRITER, "verdict": B.GIVEN_BACK, "reason": "x"}, "template"),
    ({"verdict": B.GIVEN_BACK}, "why"),                             # given back says why
    ({"verdict": B.KEPT}, "written"),                               # only a written line is kept
    ({"reason": "x"}, "reason"),                                    # a reason belongs to a given-back line
    ({"verdict": "fine"}, "verdict"),
])
def test_a_line_that_is_not_one_is_refused(over, why):
    item = _item()
    section = over.pop("section", B.TODAY)
    words = over.pop("words", "Bluepeak.")
    with pytest.raises(ValueError, match=why):
        _line(item, section=section, words=words, **over)


def test_a_line_id_is_its_place_in_the_day():
    a = B.line_id_for("org_a", "seat_owner", DAY, B.TODAY, "bi_1")
    assert a == B.line_id_for("org_a", "seat_owner", DAY, B.TODAY, "bi_1") and a.startswith("bl_")
    assert a != B.line_id_for("org_a", "seat_owner", date(2026, 10, 1), B.TODAY, "bi_1")
    assert a != B.line_id_for("org_a", "seat_owner", DAY, B.WATCHING, "bi_1")
    assert a != B.line_id_for("org_a", "seat_two", DAY, B.TODAY, "bi_1")
    assert a != B.line_id_for("org_b", "seat_owner", DAY, B.TODAY, "bi_1")


# ── the brief ─────────────────────────────────────────────────────────────────────────────────────
def test_a_brief_reads_back_as_it_was_stored():
    brief = _brief()
    again = B.Brief.from_mapping(brief.as_mapping())
    assert again == brief
    assert again.as_mapping() == brief.as_mapping()
    assert again.lines[0].sources == (B.Source(B.SOURCE_REVIEW, "node_bluepeak@ffp1"),)
    i = again.items[0]
    assert (i.mode, i.stakes, i.urgency, i.at, i.quiet_days, i.our_move, i.book_score_bp, i.card_id, i.lane) == \
        ("act", "high", "high", AT, 15.1, True, 9000, "card_1", "live")
    assert again.local_date == DAY and again.as_of == AT and again.timezone == "Asia/Kolkata"
    assert again.items[0].material.number("your_reply_time").says == "usually 1.5 days (n=6, person)"
    assert brief.words == B.count_words("1 thing needs you.") + B.count_words(brief.lines[0].words)
    assert brief.section(B.TODAY) == brief.lines and brief.section(B.WATCHING) == ()
    assert brief.version == B.BRIEF_VERSION


def test_an_empty_morning_has_no_line_outside_what_changed():
    change = _item(kind=B.CHANGE, about="node_x", subject="Hub71x")
    assert _brief(lines=(_line(change, section=B.CHANGED, words="Hub71x wrote."),), items=(change,)).empty
    assert not _brief().empty
    assert _brief(lines=(), items=()).empty


def test_the_lines_keep_the_sections_order_and_caps():
    items = tuple(_item(about=f"node_{i}") for i in range(6))
    six = tuple(_line(i, words=f"Line {n}.") for n, i in enumerate(items))
    with pytest.raises(ValueError, match="cap"):
        _brief(lines=six, items=items)
    watch = _item(kind=B.WATCHED, about="node_w")
    out_of_order = (_line(watch, section=B.WATCHING, words="w."), _line(items[0], words="t."))
    with pytest.raises(ValueError, match="order"):
        _brief(lines=out_of_order, items=(watch, items[0]))


def test_today_flexes_past_five_only_by_what_it_says():
    items = tuple(_item(about=f"node_{i}") for i in range(7))
    seven = tuple(_line(i, words=f"Line {n}.") for n, i in enumerate(items))
    brief = _brief(lines=seven, items=items, flexed=2)
    assert B.Brief.from_mapping(brief.as_mapping()).flexed == 2
    with pytest.raises(ValueError, match="cap"):
        _brief(lines=seven, items=items, flexed=1)
    with pytest.raises(ValueError, match="flexed by 0, and says 1"):
        _brief(flexed=1)                                    # one line today has not flexed
    with pytest.raises(ValueError, match="never negative"):
        _brief(flexed=-1)
    watch = tuple(_item(kind=B.WATCHED, about=f"w{i}") for i in range(5))
    with pytest.raises(ValueError, match="watching holds 4 lines, past its cap"):    # only today flexes
        _brief(lines=seven + tuple(_line(w, section=B.WATCHING, words="w.") for w in watch[:4]),
               items=items + watch[:4], flexed=2)


def test_a_brief_over_its_word_budget_is_refused():
    item = _item()
    long = " ".join(["word"] * (B.WORD_BUDGET + 1))
    with pytest.raises(ValueError, match="600"):
        _brief(lines=(_line(item, words=long),))


@pytest.mark.parametrize("over, why", [
    ({"written_by": "magic"}, "written"),
    ({"one_line": " "}, "one line"),
    ({"cost_micro_usd": -1}, "cost"),
    ({"cost_micro_usd": 5}, "template"),               # the template spends nothing
    ({"model": "claude-haiku-4-5"}, "template"),        # …and names no model
    ({"cut": (("later", 2),)}, "section"),
    ({"cut": ((B.TODAY, 0),)}, "cut"),
    ({"material_digest": "x"}, "digest"),
    ({"why": ""}, "why"),
])
def test_a_brief_that_is_not_one_is_refused(over, why):
    with pytest.raises(ValueError, match=why):
        _brief(**over)


def test_a_line_names_an_item_of_its_brief_once():
    item = _item()
    with pytest.raises(ValueError, match="item"):
        _brief(items=(_item(about="node_other"),), lines=(_line(item),))
    with pytest.raises(ValueError, match="once"):
        _brief(lines=(_line(item), _line(item, section=B.STUCK)))
    other = _item(about="node_other")
    twin = B.Line(line_id=_line(item).line_id, item_id=other.item_id, section=B.TODAY, words="Other.",
                  kind=other.kind, subject=other.subject, sources=other.sources)
    with pytest.raises(ValueError, match="line stands once"):
        _brief(lines=(_line(item), twin), items=(item, other))


def test_a_template_line_in_a_written_brief_and_a_writer_line_in_a_template_one():
    item = _item()
    written = _line(item, by=B.WRITER, verdict=B.KEPT)
    with pytest.raises(ValueError, match="template"):
        _brief(lines=(written,))
    ok = _brief(lines=(written,), written_by=B.WRITTEN, model="claude-haiku-4-5", tier="T1", cost_micro_usd=9000,
                why="written by T1 and checked")
    assert ok.lines[0].by == B.WRITER


def test_the_digest_is_the_days_material():
    a, b = _item(), _item(about="node_other")
    assert B.digest_of((a, b)) == B.digest_of((a, b)) != B.digest_of((a,))
    assert B.count_words(" one  two\nthree ") == 3 and B.count_words("") == 0
