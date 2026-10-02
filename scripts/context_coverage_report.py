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
import sys
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
    """``{module stem: [function, …]}`` from the package's own health module."""
    import importlib

    out: dict[str, list[str]] = defaultdict(list)
    for name in (f"{package}_health", "contract_health"):
        try:
            mod = importlib.import_module(f"genios_engine.{package}.{name}")
        except ModuleNotFoundError:
            continue
        for entry in getattr(mod, "UNREACHED", {}):
            stem, _, fn = entry.partition(".")
            out[stem].append(fn)
    return out


def test_mentions(package: str) -> dict[str, int]:
    """``{module path: how many test files name it}`` — the unit-test side of coverage.

    ⛔ KEYED ON THE DOTTED PATH, NOT THE BARE STEM, AND THE FIRST VERSION WAS WRONG. Matching
    `f"{package}.{stem}"` missed every subpackage: a test importing
    `genios_engine.context.analytic.cohort` contains `context.analytic.cohort`, never
    `context.cohort`. ⛔ That version reported **41** modules of 100+ lines as named by no test, in
    a package 306 test files import — a confident wrong number in the one column a reader would
    act on. *A resolver that answers for part of its input answers for none of it.*
    """
    pkg_dir = ROOT / "genios_engine" / package
    paths = sorted(pkg_dir.rglob("*.py"))
    dotted = {p: f"{package}." + str(p.relative_to(pkg_dir).with_suffix("")).replace("/", ".")
              for p in paths}
    counts: dict[str, int] = defaultdict(int)
    corpus = [path.read_text(encoding="utf-8", errors="replace")
              for path in (ROOT / "tests").rglob("*.py")]
    for path, module in dotted.items():
        parent, _, stem = module.rpartition(".")
        for text in corpus:
            if module in text or f"{parent} import {stem}" in text:
                counts[str(path.relative_to(pkg_dir))] += 1
    return counts


def main() -> int:
    package = sys.argv[1] if len(sys.argv) > 1 else "context"
    pkg_dir = ROOT / "genios_engine" / package
    if not pkg_dir.is_dir():
        print(f"no such package: {package}", file=sys.stderr)
        return 2

    usage = TC.table_usage()
    receipted = TC.tables_with_a_receipt()
    silences = declared_silences(package)
    mentions = test_mentions(package)

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
            "tests": mentions.get(rel, 0),
            "unreceipted": [t for t in writes if t not in receipted],
        })

    total_lines = sum(r["lines"] for r in rows)
    writers = [r for r in rows if r["writes"]]
    unreceipted = sorted({t for r in rows for t in r["unreceipted"]})
    untested = [r for r in rows if r["tests"] == 0 and r["lines"] >= 100]

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
    print(f"⛔ >=100 lines, no test names it  {len(untested)}")
    print("```\n")

    print("## ⛔ Tables this package writes that no receipt covers\n")
    print("| table | external readers | writers in this package |")
    print("|---|---|---|")
    for table, external in TC.written_without_a_receipt(package):
        ws = sorted(w.split("/")[-1] for w in TC.writers_of(table)
                    if f"/{package}/" in w)
        print(f"| `{table}` | {external} | {', '.join(f'`{w}`' for w in ws) or '—'} |")
    print()

    print("## ⛔ Files of 100+ lines that no test file names\n")
    print("⛔ **READ THE COLUMN LITERALLY.** This says no test file imports the module by its "
          "dotted path. It does **not** say the code is untested: both of the modules below are "
          "live and reached — `lifecycle/resolution.py` from `context/runner.py`, and "
          "`correlation_membership.declare_finding_events` from three production modules while "
          "`finding_events` is called directly by "
          "`tests/test_nothing_reads_a_name_that_cannot_exist.py` under a different import form. "
          "⛔ *A guard that measures naming cannot answer coverage* — what this column finds is a "
          "module with no test of its OWN, which is a different and smaller thing.\n")
    if untested:
        print("| file | lines | public fns | writes |")
        print("|---|---|---|---|")
        for r in sorted(untested, key=lambda x: -x["lines"]):
            print(f"| `{r['file']}` | {r['lines']} | {r['public']} | "
                  f"{', '.join(f'`{t}`' for t in r['writes']) or '—'} |")
    else:
        print("None — every module of 100+ lines is named by at least one test file.")
    print()

    print("## Every file\n")
    print("| file | lines | public | tests | declared silences | writes | reads |")
    print("|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: -x["lines"]):
        w = ", ".join(f"`{t}`" for t in r["writes"]) or "—"
        rd = ", ".join(f"`{t}`" for t in r["reads"][:6])
        if len(r["reads"]) > 6:
            rd += f" +{len(r['reads']) - 6}"
        print(f"| `{r['file']}` | {r['lines']} | {r['public']} | {r['tests']} | "
              f"{r['declared'] or '—'} | {w} | {rd or '—'} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
