"""STEP-01 · the golden label sheet: one question per real item, by sender and date only.

    pytest tests/test_golden_labels_sheet.py -q

`speedrun008/YC-II W27/golden-labels.md` is the founder set's answer key (STEP-01 §3.5, decision
D12): forty real items from Rohit's mailbox, each asked one question — *should this have reached
you?* — answered `yes`, `no` or `brief only`. Until Rohit answers a row, Claude's answer stands
and the row says so. The founder cases are built from these rows (`label_row`), and
`tests/replays/test_founder_cases.py` holds every case to its row's answer.

What this holds:

  * every row has a number, an item, Claude's answer, room for Rohit's, and who labelled it — and
    "labelled by" is `rohit` exactly when Rohit's column is filled (D12a);
  * the item is a sender and a date, nothing more (D12b): short, dated, no quoted text;
  * rows are numbered 1…N with no gap, so a case's `label_row` always names one row.
"""
from __future__ import annotations

import re
from pathlib import Path

SHEET = (Path(__file__).resolve().parents[1] / "speedrun008" / "YC-II W27" / "golden-labels.md")
ANSWERS = ("yes", "no", "brief only")
_ROW = re.compile(r"^\|\s*(\d+)\s*\|(.*)\|\s*$")
_DATE = re.compile(r"\b\d{1,2}(?:[–-]\d{1,2})?\s+(?:Aug|Sep|Oct)\b")


def rows() -> list[dict[str, str]]:
    """The sheet's label rows, as {number, item, claude, rohit, by}."""
    out = []
    for line in SHEET.read_text(encoding="utf-8").splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        assert len(cells) == 4, f"row {m.group(1)} has {len(cells)} cells after the number: {line}"
        item, claude, rohit, by = cells
        out.append({"number": int(m.group(1)), "item": item, "claude": claude.strip("`"),
                    "rohit": rohit.strip("`"), "by": by.strip("`")})
    return out


def answer(row: dict[str, str]) -> str:
    """The answer that counts: Rohit's where he gave one, otherwise Claude's."""
    return row["rohit"] or row["claude"]


def test_the_sheet_exists_and_is_not_empty():
    assert SHEET.is_file(), f"missing: {SHEET}"
    assert len(rows()) >= 40, "the founder set is about forty items (STEP-01 §4)"


def test_rows_are_numbered_without_a_gap():
    numbers = [r["number"] for r in rows()]
    assert numbers == list(range(1, len(numbers) + 1)), numbers


def test_every_answer_is_one_of_three():
    for r in rows():
        assert r["claude"] in ANSWERS, f"row {r['number']}: Claude's answer {r['claude']!r}"
        assert r["rohit"] in ("",) + ANSWERS, f"row {r['number']}: Rohit's answer {r['rohit']!r}"


def test_labelled_by_says_whose_answer_counts():
    for r in rows():
        expected = "rohit" if r["rohit"] else "claude"
        assert r["by"] == expected, (
            f"row {r['number']}: labelled by {r['by']!r}, but Rohit's column is "
            f"{'filled' if r['rohit'] else 'empty'}")


def test_an_item_is_a_sender_and_a_date_and_nothing_more():
    for r in rows():
        item = r["item"]
        assert "·" in item, f"row {r['number']}: write the item as `sender · date`: {item!r}"
        sender, dates = (part.strip() for part in item.split("·", 1))
        assert sender and _DATE.search(dates), f"row {r['number']}: no date in {item!r}"
        assert len(item) <= 110, f"row {r['number']}: an item is a sender and a date: {item!r}"
        assert '"' not in item and "“" not in item, (
            f"row {r['number']}: quoted text is content, which the sheet never carries")


def test_the_three_answers_are_all_in_use():
    """A sheet that says `yes` to everything is a wish list, not an exam."""
    used = {answer(r) for r in rows()}
    assert used == set(ANSWERS), used
