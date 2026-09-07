"""The ledger's own blind spot, and the machinery that closes it.

A Component map with no `Units` column promises nothing, and a promise of nothing can never be
under-delivered against — so a group that never states its scope reports greener than one that
does. Six of Layer 2's seven group docs are in that state, which is why the ledger read Layer 2's
gap as 2 while six groups sat between a quarter and two-thirds specified.

`PROMISE_SUPPLEMENTS` lets a plan state that promise in a file of its own. These tests drive that
path over synthetic plan fixtures — never over the real docs, whose numbers move — and each row
asserts an outcome that would change if the rule it names were removed.
"""
from __future__ import annotations

import json

import pytest

from scripts.unit_ledger import (PROMISE_SUPPLEMENTS, baseline_of, check, read_promise_ledger,
                                 scan, to_report)

GROUP_DOC_NO_UNITS_COLUMN = """# L2.9 — A Group That Never Stated Its Scope

## Component map

| # | Component | Status |
|---|---|---|
| L2.9.1 | First | OK |
| L2.9.2 | Second | MISSING |

# L2.9.1 · First

### L2.9.1-U1 · The one spec that was written

**WHAT** — something.

**ACCEPTANCE**
```
pytest -q
```
"""

GROUP_DOC_WITH_UNITS_COLUMN = """# L2.8 — A Group That Did State Its Scope

## Component map

| # | Component | Units | Status |
|---|---|---|---|
| L2.8.1 | Only | 2 | NEW |

# L2.8.1 · Only

### L2.8.1-U1 · Written

**ACCEPTANCE**
```
pytest -q
```
"""

SUPPLEMENT = """# Supplement

## 2. Promise ledger

| # | Component | Units | Note |
|---|---|---|---|
| L2.9.1 | First | 1 | already written in the group doc |
| L2.9.2 | Second | 2 | one written here, one still owed |
| L2.8.1 | Only | 9 | the group doc already said 2 — the map must win |

## L2.9.2 · Second

### L2.9.2-U1 · Supplied here

**WHAT** — the spec the group doc promised in prose and never wrote.

**ACCEPTANCE**
```
pytest -q
```
"""


@pytest.fixture()
def plan(tmp_path):
    """A two-group Layer 2 plan plus a supplement, laid out the way the real tree is."""
    layer_dir = tmp_path / "02-Layer-2-Plan"
    layer_dir.mkdir()
    (layer_dir / "08-Group-L2.8-Stated.md").write_text(GROUP_DOC_WITH_UNITS_COLUMN)
    (layer_dir / "09-Group-L2.9-Unstated.md").write_text(GROUP_DOC_NO_UNITS_COLUMN)
    supplement = tmp_path / "SUPPLEMENT.md"
    supplement.write_text(SUPPLEMENT)
    return tmp_path, supplement


def report_for(plan, *, with_supplement: bool):
    root, supplement = plan
    layers, anomalies = scan(root, supplements={2: supplement} if with_supplement else None)
    return to_report(layers, anomalies)


# ── the blind spot itself ────────────────────────────────────────────────────────────────

def test_a_group_with_no_units_column_reports_no_promise_and_no_gap(plan):
    """The defect, stated as a test: two components, one spec, and the ledger says 'fine'."""
    g = report_for(plan, with_supplement=False)["layers"]["L2"]["groups"]["L2.9"]
    assert g["components_declared"] == 2
    assert g["units_promised"] == 0          # nothing promised …
    assert g["units_written"] == 1
    assert g["gap"] == 0                     # … so nothing can be missing
    assert g["missing_unit_ids"] == []


def test_the_supplement_makes_the_unstated_promise_countable(plan):
    g = report_for(plan, with_supplement=True)["layers"]["L2"]["groups"]["L2.9"]
    assert g["units_promised"] == 3          # 1 + 2, from the promise ledger
    assert g["units_written"] == 2           # the group doc's one, plus the supplement's one
    assert g["gap"] == 1
    assert g["missing_unit_ids"] == ["L2.9.2-U2"]


# ── the two rules that keep a supplement from rewriting the plan ─────────────────────────

def test_a_stated_promise_is_never_overridden_by_a_supplement(plan):
    """The supplement claims 9 for L2.8.1; the group doc said 2. The doc wins."""
    report = report_for(plan, with_supplement=True)
    comp = report["layers"]["L2"]["groups"]["L2.8"]["components"]["L2.8.1"]
    assert comp["promised"] == 2
    assert comp["promise_source"] == "map"
    assert any("promises 2 in its Component map and 9" in a
               for a in report["scan_anomalies"])


def test_a_supplement_sourced_promise_is_labelled_as_such(plan):
    """A promise stated outside the plan is still a promise — and must be visibly outside it."""
    report = report_for(plan, with_supplement=True)
    groups = report["layers"]["L2"]["groups"]
    assert groups["L2.9"]["components"]["L2.9.2"]["promise_source"] == "supplement"
    assert groups["L2.9"]["units_promised_by_supplement"] == 3
    assert groups["L2.9"]["units_written_in_supplement"] == 1
    assert groups["L2.8"]["units_promised_by_supplement"] == 0


# ── parsing ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("heading", ["## Promise ledger", "# 2. Promise ledger",
                                     "### 4) PROMISE LEDGER — the counts"])
def test_promise_ledger_heading_variants(heading):
    lines = (f"{heading}\n\n| # | Component | Units |\n|---|---|---|\n"
             "| L2.9.1 | First | 3 |\n").splitlines()
    assert read_promise_ledger(lines) == {"L2.9.1": 3}


@pytest.mark.parametrize("body, expected", [
    pytest.param("| # | Component | Note |\n|---|---|---|\n| L2.9.1 | First | 3 |",
                 {}, id="no Units column -> no promise, never a guess from another column"),
    pytest.param("| # | Component | Units |\n|---|---|---|\n| L2.9.1 | First | many |",
                 {}, id="non-numeric Units cell is skipped, not coerced"),
    pytest.param("| # | Component | Units |\n|---|---|---|\n| **L2.9.1** | First | `2` |",
                 {"L2.9.1": 2}, id="markdown emphasis is decoration on the id and the count"),
    pytest.param("| # | Component | Units |\n|---|---|---|\n| not-an-id | First | 2 |",
                 {}, id="a row whose first cell is not a component id is skipped"),
    pytest.param("| # | Component | Units |\n|---|---|---|\n| L2.9.1 | First | 0 |",
                 {"L2.9.1": 0}, id="ZERO is a stated promise, distinct from an absent one"),
])
def test_promise_ledger_table_rows(body, expected):
    assert read_promise_ledger(f"## Promise ledger\n\n{body}\n".splitlines()) == expected


def test_no_promise_ledger_heading_means_no_promise():
    assert read_promise_ledger("# Nothing here\n\n| a | b |\n".splitlines()) == {}


# ── the ratchet ──────────────────────────────────────────────────────────────────────────

def test_deleting_the_promise_breaks_the_ratchet(plan, tmp_path, capsys):
    """The failure the frozen promise exists to catch.

    A gap is `promised - written`, so removing the promise closes it. Without the promise in the
    baseline, dropping the supplement would report success on a group that still owes a spec.
    """
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(baseline_of(report_for(plan, with_supplement=True))))

    assert check(report_for(plan, with_supplement=True), baseline) == 0
    assert check(report_for(plan, with_supplement=False), baseline) == 1
    assert "promise shrank 3 -> 0" in capsys.readouterr().out


def test_removing_a_written_spec_breaks_the_ratchet(plan, tmp_path, capsys):
    root, supplement = plan
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(baseline_of(report_for(plan, with_supplement=True))))

    supplement.write_text(SUPPLEMENT.replace("### L2.9.2-U1 · Supplied here", "### Gone"))
    assert check(report_for(plan, with_supplement=True), baseline) == 1
    out = capsys.readouterr().out
    assert "L2.9 gap grew 1 -> 2" in out
    assert "L2.9.2-U1" in out


def test_writing_the_missing_spec_shrinks_the_gap_and_passes(plan, tmp_path, capsys):
    """The ratchet must let the gap CLOSE freely — it only ever refuses growth."""
    root, supplement = plan
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(baseline_of(report_for(plan, with_supplement=True))))

    supplement.write_text(SUPPLEMENT + "\n### L2.9.2-U2 · Also supplied\n\n**ACCEPTANCE**\n"
                                       "```\npytest -q\n```\n")
    assert check(report_for(plan, with_supplement=True), baseline) == 0
    assert "closed since baseline (1): L2.9.2-U2" in capsys.readouterr().out


# ── the registration this repo actually ships ────────────────────────────────────────────

def test_the_registered_layer_2_supplement_exists_and_states_a_promise():
    """A supplement registered but absent would silently return Layer 2 to unstated."""
    path = PROMISE_SUPPLEMENTS[2]
    assert path.exists(), f"{path} is registered in PROMISE_SUPPLEMENTS and missing"
    promises = read_promise_ledger(path.read_text(encoding="utf-8").splitlines())
    assert len(promises) >= 40
    # Every Layer 2 group that has no `Units` column of its own is covered.
    assert {cid.rsplit(".", 1)[0] for cid in promises} >= {
        "L2.1", "L2.2", "L2.3", "L2.5", "L2.6", "L2.7"}
    # L2.4 states its own promise and must not be restated here.
    assert not any(cid.startswith("L2.4.") for cid in promises)
