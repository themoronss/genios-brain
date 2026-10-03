"""The audit index is hand-written over generated pages, so its numbers are checked against them.

⛔ FOUND BY DRIFTING, 2026-10-03. `00-INDEX.md`'s summary table is written by hand; the eleven
package pages under it are **generated**. Adding `platform/table_coverage.py` moved that package's
line count, its unreceipted-table count and its declared-silence count — and the index kept saying
the old numbers, in the one table a reader looks at first.

⛔ *A total is a measurement, not an addition of other people's measurements* — and an index over
generated pages is exactly that addition. This asserts the two agree, so the index cannot quietly
describe a previous checkout.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_Y = Path(__file__).resolve().parents[2] / "speedrun008" / "YCW27"
_INDEX = _Y / "20-AUDIT-every-package" / "00-INDEX.md"
#: `context/`'s page lives beside its findings, not in the folder with the other ten.
_PAGES = {"context": _Y / "layer-3-context-graph" / "05-AUDIT-context-file-by-file.md"}

_ROW = re.compile(
    r"^\| [^|]*`(?P<pkg>\w+)`[^|]*\| (?P<files>\d+) \| (?P<lines>[\d,]+) \| "
    r"\*{0,2}(?P<writers>\d+)\*{0,2} \| \*{0,2}(?P<no_receipt>\d+)\*{0,2} \| "
    r"(?P<silences>\d+) ?✅? \|$", re.M)


def _rows() -> list[re.Match[str]]:
    rows = list(_ROW.finditer(_INDEX.read_text(encoding="utf-8")))
    assert len(rows) >= 11, (
        f"only {len(rows)} package rows parsed from the index — either the table changed shape or "
        "a row stopped matching, and an unparsed row is an unchecked row")
    return rows


def _page_numbers(package: str) -> dict[str, str]:
    path = _PAGES.get(package, _Y / "20-AUDIT-every-package" / f"{package}.md")
    assert path.exists(), f"the index links a page that does not exist: {path}"
    lines = path.read_text(encoding="utf-8").splitlines()

    def after(label: str) -> str:
        return next((ln.split()[-1] for ln in lines if ln.startswith(label)), "?")

    return {
        "files": after("files"),
        "lines": after("lines"),
        "writers": after("files that WRITE a table"),
        "no_receipt": next((ln.split()[-1] for ln in lines if "written, no receipt" in ln), "?"),
        "silences": after("declared silences"),
    }


@pytest.mark.parametrize("row", _rows(), ids=lambda m: m.group("pkg"))
def test_every_index_row_matches_its_generated_page(row):
    page = _page_numbers(row.group("pkg"))
    for field, value in page.items():
        assert row.group(field).replace(",", "") == value.replace(",", ""), (
            f"⛔ `{row.group('pkg')}`'s index row says {field}={row.group(field)} and its page says "
            f"{value}. The pages are generated and the index is written by hand, so the page wins: "
            f"regenerate with `python scripts/context_coverage_report.py {row.group('pkg')}` and "
            "correct the row")


def test_the_index_does_not_advertise_the_deleted_column():
    """⛔ The `no test names it` column was removed for being wrong 19 of 33 times. The index may
    EXPLAIN it — the explanation is the finding — but it may not carry it as data again."""
    text = _INDEX.read_text(encoding="utf-8")
    header = text.split("| package | files")[1].split("\n")[0]
    assert "no test names" not in header, "the deleted column is back in the table header"
    assert "DELETED" in text, "the index stopped explaining why the column is gone"


def test_every_page_the_index_links_exists():
    text = _INDEX.read_text(encoding="utf-8")
    missing = [target for target in re.findall(r"\]\((\.\.?/[^)]+\.md)\)", text)
               if not (_INDEX.parent / target).resolve().exists()]
    assert not missing, f"the index links pages that do not exist: {missing}"
