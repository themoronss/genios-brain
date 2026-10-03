#!/usr/bin/env python3
"""Generate the file-by-file coverage audit for one engine package.

⛔ WHY THIS IS A SCRIPT AND NOT A HAND-WRITTEN DOCUMENT. `context/` is 124 files. A paragraph per
file is wrong the day after it is written — `S9` paid for that three times in one programme (the
status counts, the test totals, the mover distribution). The audit is therefore MEASURED, and the
document it produces says how to regenerate itself.

    python scripts/context_coverage_report.py context > \
        speedrun008/YCW27/layer-3-context-graph/05-AUDIT-context-file-by-file.md

Same family as `pipeline_funnel_report.py` and `l2_refusal_report.py`: read-only, no database,
answers one question and prints it.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
from functools import lru_cache
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from genios_engine.platform import table_coverage as TC  # noqa: E402


def public_functions(tree: ast.Module) -> list[str]:
    return [n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")]


def declared_silences(package: str) -> dict[str, list[str]]:
    """``{module stem: [function, …]}`` from whatever declaration modules the package holds.

    ⛔ DISCOVERED, NOT DERIVED FROM THE PACKAGE NAME, AND THE FIRST VERSION WAS WRONG FOR FOUR
    PACKAGES. It imported `genios_engine.<package>.<package>_health` — but the modules are named
    for what they describe, not for their directory: `deliver/delivery_health.py`,
    `reason/reasoning_health.py`, `packs/pack_health.py`, and `executive/unreached.py`, which does
    not carry `health` at all. ⛔ So the column read **0 declared silences** for every one of them
    while their tables were full, in a report whose whole job is to say what is declared.

    *A name derived from a directory is a guess; a name found on disk is a measurement.*
    """
    import importlib

    out: dict[str, list[str]] = defaultdict(list)
    pkg_dir = ROOT / "genios_engine" / package
    modules = sorted({p.stem for p in pkg_dir.glob("*.py")
                      if p.stem.endswith("_health") or p.stem == "unreached"})
    for name in modules:
        try:
            mod = importlib.import_module(f"genios_engine.{package}.{name}")
        except Exception:                          # noqa: BLE001 - a module that will not import
            continue                               # is a finding for the suite, not for this report
        for table in ("UNREACHED", "PULL_ONLY", "KNOWN_UNWIRED", "UNCUT_OVER",
                      "REACHED_BY_DISPATCH"):
            for entry in getattr(mod, table, {}):
                stem, _, fn = entry.partition(".")
                out[stem].append(fn or stem)
    return out


def main() -> int:
    package = sys.argv[1] if len(sys.argv) > 1 else "context"
    pkg_dir = ROOT / "genios_engine" / package
    if not pkg_dir.is_dir():
        print(f"no such package: {package}", file=sys.stderr)
        return 2

    usage = TC.table_usage()
    receipted = TC.tables_with_a_receipt()
    silences = declared_silences(package)

    rows = []
    for path in sorted(pkg_dir.rglob("*.py")):
        rel = str(path.relative_to(pkg_dir))
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:                        # pragma: no cover - the tree parses
            continue
        key = f"{package}/{rel}"
        writes = sorted(t for t, v in usage.items()
                        if any(key in v.get(verb, ()) for verb in ("insert", "update"))
                        or any(f"genios_engine/{key}" in v.get(verb, ())
                               for verb in ("insert", "update")))
        reads = sorted(t for t, v in usage.items()
                       if f"genios_engine/{key}" in v.get("read", ()))
        rows.append({
            "file": rel, "lines": len(source.splitlines()),
            "public": len(public_functions(tree)),
            "declared": len(silences.get(path.stem, [])),
            "writes": writes, "reads": reads,
            "unreceipted": [t for t in writes if t not in receipted],
        })

    total_lines = sum(r["lines"] for r in rows)
    writers = [r for r in rows if r["writes"]]
    unreceipted = sorted({t for r in rows for t in r["unreceipted"]})

    print(f"# L3 · `{package}/` — the file-by-file coverage audit\n")
    print(f"⛔ **GENERATED, NOT WRITTEN.** Regenerate with:\n")
    print("```\npython scripts/context_coverage_report.py " + package + " > \\")
    print(f"    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-{package}-file-by-file.md\n```\n")
    print(f"Measured {date.today().isoformat()}. ⛔ Every number here is a measurement of one "
          "checkout; *a hardcoded count in a document is wrong the next day*, so the command above "
          "is the real answer and this file is its output.\n")
    print("```")
    print(f"files                       {len(rows)}")
    print(f"lines                       {total_lines:,}")
    print(f"files that WRITE a table    {len(writers)}")
    print(f"distinct tables written     {len({t for r in rows for t in r['writes']})}")
    print(f"⛔ written, no receipt       {len(unreceipted)}")
    print(f"declared silences           {sum(r['declared'] for r in rows)}")
    print("```\n")

    print("## ⛔ Tables this package writes that no receipt covers\n")
    print("| table | external readers | writers in this package |")
    print("|---|---|---|")
    for table, external in TC.written_without_a_receipt(package):
        ws = sorted(w.split("/")[-1] for w in TC.writers_of(table)
                    if f"/{package}/" in w)
        print(f"| `{table}` | {external} | {', '.join(f'`{w}`' for w in ws) or '—'} |")
    print()

    print("## ⛔ THE COLUMN THAT WAS HERE IS GONE, AND THAT IS A FINDING\n")
    print("This section used to list modules of 100+ lines that no test file names. ⛔⛔ **It was "
          "removed on 2026-10-03 after six repairs failed to make it honest**, and the removal is "
          "the most useful thing it produced.\n")
    print("Across three package audits it reported **33** entries. ⛔ Nineteen were false, and "
          "each false entry was a candidate finding that died on inspection:\n")
    print("```")
    print("a @router.get handler has no Python caller and no test imports its module   -> false")
    print("a table read through funnel.read_sweep: reached, path written nowhere       -> false")
    print("test_unit_roster.py parametrises ALL_UNITS: 23 units run, no class named    -> false x16")
    print("ConstraintReasoner = ConstraintUnit — an alias a ClassDef scan cannot see   -> false")
    print("```\n")
    print("⛔ And every repair over-corrected in the other direction, which is worse, because a "
          "false negative **hides** a live module:\n")
    print("```")
    print("counting a generic CAPABILITY constant rescued a module with NO test at all")
    print("counting __all__ as a definition made all 23 unit names look ambiguous, so the")
    print("    whole column collapsed to zero findings")
    print("⛔⛔ and the guard written FOR this column named two functions in its own docstring,")
    print("    which made the module it was asserting is untested read as named — the observer")
    print("    altering the thing it measured")
    print("```\n")
    print("> ⛔ **A column whose error rate is unknown in BOTH directions is a column nobody "
          "should act on.** Naming is not coverage, six attempts did not make it one, and the "
          "section produced **zero** surviving findings in three audits while costing nineteen "
          "false leads.\n")
    print("⛔ **What it did produce, kept as a real finding rather than a table row:** "
          "`api/identity_routes.py` has **five routes and 130 lines**, and no test file mentions "
          "it by any means — verified by hand, not by this column. That is on "
          "`21-PLAN-TO-PRODUCTION.md`.\n")
    print("⛔ **What replaced it: nothing.** The table above — *tables a package writes that no "
          "receipt covers* — held in all three audits and is what the audit is for.\n")
    print("## Every file\n")
    print("| file | lines | public | declared silences | writes | reads |")
    print("|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: -x["lines"]):
        w = ", ".join(f"`{t}`" for t in r["writes"]) or "—"
        rd = ", ".join(f"`{t}`" for t in r["reads"][:6])
        if len(r["reads"]) > 6:
            rd += f" +{len(r['reads']) - 6}"
        print(f"| `{r['file']}` | {r['lines']} | {r['public']} | "
              f"{r['declared'] or '—'} | {w} | {rd or '—'} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
