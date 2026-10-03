"""The audit report has no naming heuristic, and this is why it must not get one again.

⛔⛔ `20-AUDIT-every-package/` once carried a column listing modules of 100+ lines that *no test
file names*. Across three package audits it reported **33** entries. ⛔ **Nineteen were false**, and
each false entry was a candidate finding that died on inspection:

```
a @router.get handler has no Python caller and no test imports its module   -> false
a table read through funnel.read_sweep: reached, its path written nowhere   -> false
test_unit_roster.py parametrises ALL_UNITS: 23 units run, no class named    -> false x16
ConstraintReasoner = ConstraintUnit — an alias a ClassDef scan cannot see   -> false
```

⛔ Six repairs followed — exported symbols, a collection hop, that hop made transitive, `__all__`,
a distinctiveness filter, and the corpus read from the AST — and **every one over-corrected in the
other direction**, which is worse, because a false negative *hides* a live module:

```
a generic CAPABILITY constant rescued a module with NO test for either public function
counting __all__ as a DEFINITION made all 23 unit names ambiguous: zero findings
⛔⛔ and the guard written FOR this column named two functions in its own DOCSTRING, which
   made the module it asserted was untested read as named — the observer altering the thing
   it measured, and the sixth time in one day that prose satisfied a text-level measurement
```

> ⛔ **A column whose error rate is unknown in BOTH directions is a column nobody should act on.**
> Naming is not coverage; six attempts did not make it one; and the section produced **zero**
> surviving findings in three audits while costing nineteen false leads. **It was deleted.**

⛔ What it did produce is kept as a real finding rather than a table row — verified by hand, not by
the heuristic: `api/identity_routes.py`, **five routes and 130 lines**, mentioned by no test by any
means. That is named in `21-PLAN-TO-PRODUCTION.md`.

⛔ What replaced it: **nothing.** The column that held in all three audits is *tables a package
writes that no receipt covers*, and that is what the audit is for.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "context_coverage_report.py"
_PLAN = _ROOT / "speedrun008" / "YCW27" / "21-PLAN-TO-PRODUCTION.md"


def _source() -> str:
    return _SCRIPT.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _report(package: str = "executive") -> str:
    """⛔ CACHED PER PACKAGE. Each call spawns a subprocess that imports the whole engine for
    `receipts`, and the tests below ask for three packages across six assertions — six engine
    imports inside one test module, 20s down to 5s. *A guard that spawns a process pays for the
    process every time it is asked.*

    ⛔ AND THE REASON I LOOKED WAS WRONG. I read a suite at 62%% as slow and blamed this file; the
    run finished in 11:45, its normal time. The guard really was six subprocesses and really is
    better cached — but the premise that it had slowed the suite was not measured, it was
    inferred from a progress percentage. *A number read off a progress bar is not a measurement.*"""
    out = subprocess.run([sys.executable, str(_SCRIPT), package],
                         capture_output=True, text=True, cwd=_ROOT)
    assert out.returncode == 0, out.stderr[-800:]
    return out.stdout


# ── the heuristic is gone, by name ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("helper", [
    "test_mentions", "_public_names", "_defined_names", "_distinctive",
    "_collections_by_member", "_code_identifiers", "_imported_modules",
])
def test_no_naming_heuristic_survives_in_the_generator(helper):
    """⛔ Each of these existed, each was a repair, and each left the column wrong in a new way.
    Dead code with a confident name is worse than none — a later reader re-enables it."""
    assert not re.search(rf"^(?:@lru_cache[^\n]*\n)?def {re.escape(helper)}\(", _source(), re.M), (
        f"`{helper}` is back in scripts/context_coverage_report.py. ⛔ Read this file's docstring "
        "before re-adding a naming heuristic: six of them were tried, all six were wrong in both "
        "directions, and the column produced zero surviving findings in three audits")


def test_the_report_no_longer_claims_to_know_what_is_untested():
    body = _report()
    assert "no test names it" not in body.split("THE COLUMN THAT WAS HERE IS GONE")[0], (
        "the summary block is advertising a naming count again")
    assert "THE COLUMN THAT WAS HERE IS GONE" in body


def test_the_report_explains_the_removal_rather_than_hiding_it():
    """⛔ A deleted measurement with no explanation is an invitation to rebuild it."""
    body = _report()
    for phrase in ("Nineteen were false", "error rate is unknown in BOTH directions",
                   "Naming is not coverage", "identity_routes.py"):
        assert phrase in body, f"the removal's reasoning lost: {phrase!r}"


# ── the column that held is still there ────────────────────────────────────────────────────────

def test_the_receipt_column_is_what_the_report_is_for():
    body = _report("platform")
    assert "Tables this package writes that no receipt covers" in body
    assert "written, no receipt" in body
    assert "| table | external readers | writers in this package |" in body


def test_the_per_file_table_has_no_tests_column():
    body = _report()
    assert "| file | lines | public | declared silences | writes | reads |" in body, (
        "the per-file table's header changed; a `tests` column there is the same heuristic in a "
        "smaller place")


# ── and the one real finding outlived the column that found it ─────────────────────────────────

def test_the_finding_the_column_produced_is_recorded_where_work_is_tracked():
    """⛔ The column's single real contribution must not vanish with it. Verified by hand:
    `api/identity_routes.py` has five routes and no test mentions it by any means."""
    plan = _PLAN.read_text(encoding="utf-8")
    assert "identity_routes" in plan, (
        "the one finding this column produced is not in the plan — deleting the column then "
        "deleted its only result")
    routes = (_ROOT / "genios_engine" / "api" / "identity_routes.py").read_text(encoding="utf-8")
    assert routes.count("@router.") >= 4, (
        "`identity_routes.py` no longer carries the routes the finding is about; re-read it")


# ── and it is fast enough to regenerate, which is the point of generating it ────────────────────

def test_the_report_is_fast_enough_to_re_run():
    """⛔ The heuristic's last version re-parsed a package once per module and took minutes.
    *A report too slow to re-run is a report nobody regenerates.*"""
    start = time.monotonic()
    _report("reason")
    assert time.monotonic() - start < 20, "the report has become slow again"
