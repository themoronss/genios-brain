#!/usr/bin/env python3
r"""⛔ `axis_count` is published on every run and read by nobody — this is the reader.

READ-ONLY. One `set transaction read only` connection, no writes, no model calls.

WHY A READER AND NOT A FIELD. `reason/unit_health.py`'s header records the decision:

    "Having core.tradeoff publish which axis it lost would add a field to the output of ~100% of
     runs, and contracts/reasoning.py:845 states the consequence: every trace in reasoning_runs
     would fail replay verification against a run that computed the identical result. The
     established rule is conditional inclusion, and conditional inclusion does not help when the
     condition holds on every run. `axis_count` is ALREADY published on every run and read by
     nobody — so the fix is a reader, not a field."

⛔ WHAT IT FOUND, measured 2026-10-01 over 1,973 completed `core.tradeoff` runs:

    axis_count = 0     16 runs    margin_bp 0 · tension_bp 0 · contested_count 0 · no findings
    axis_count = 1    929 runs
    axis_count = 2  1,028 runs
    axis_count = 3      0 runs    ⛔ a THREE-axis comparator that has never compared three

`core.tradeoff` declares three axes — `speed_vs_certainty`, `risk_vs_reward`, `cost_vs_benefit` —
and `tradeoff.cost_vs_benefit` has fired **0 times**, because `AXIS_SOURCES` names
`benefit_source -> core.impact -> impact_bp` and `core.impact` is 100% silent (declared, mover
Harsh, a writer for `deal.status`). The chain is four deep and every link behaves correctly.

⛔ AND SIXTEEN RUNS COMPARED NOTHING AT ALL. Four zeros and an empty `reason_codes`. Those rows are
silent by `unit_health.is_silent`'s own definition, and the silence receipt is still RIGHT to pass:
16 of 1,973 is 0.8%, and `SILENT_THRESHOLD_PCT` is 90 — *"one silent completion out of a thousand
is noise; ninety per cent is a unit that does not work."* A share, not a count. So this probe
reports them rather than a receipt failing on them.

⛔ `axes_unavailable` IS NOT A SECOND SOURCE OF TRUTH, AND HAS NEVER BEEN WRITTEN. It was added in
S5.U02 and publishes only when non-zero, per the conditional-inclusion rule. Every stored row
predates it — `core.tradeoff`'s rows span 2026-09-29 to 2026-09-30 and S5 landed after — so it has
**0 occurrences in 1,973 rows** and will first appear on the next run. That is a field awaiting
exercise, not a field that failed, and this probe says which it is rather than leaving a reader to
guess.

EXIT CODE. 0 when every lost axis has a declared cause; 1 when a lost axis traces to a unit nobody
declared, which is the only state a human has to act on.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from typing import Mapping

from sqlalchemy import text

from genios_engine.platform.db import get_engine
from genios_engine.reason.reasoners.tradeoff_unit import AXES, AXIS_SIDES, AXIS_SOURCES
from genios_engine.reason.unit_health import DECLARED_NEVER_COMPLETED, DECLARED_SILENT

UNIT = "core.tradeoff"
#: Axes this unit declares, and the unit each side reads. Both DERIVED from the unit, never
#: retyped — the same rule `tradeoff_unit.source_units` follows and for the same reason.
#:
#: ⛔ The first version of this probe read `AXIS_SOURCES[*][0]` as the axis name. It is the SOURCE
#: KEY (`benefit_source`), so the probe reported "a 6-axis comparator that has never compared 6"
#: and "every axis has NEVER fired" — both false, and both looked exactly like findings. The axis
#: names live in `AXES`; the keys map to units through `AXIS_SOURCES`.
DECLARED_AXES = tuple(axis for axis, _, _ in AXES)
UNIT_FOR_KEY = {key: (unit_id, metric) for key, unit_id, metric in AXIS_SOURCES}


def classify_lost_axes(fired: Mapping[str, int], publishes: Mapping[tuple[str, str], int]) \
        -> tuple[dict[str, list[tuple[str, str, str]]],
                 dict[str, list[tuple[str, str]]],
                 dict[str, list[str]]]:
    """`(declared_cause, undeclared_cause, healthy_sides)` for every axis that never fired.

    ⛔ A PURE FUNCTION, AND THAT IS NOT TIDINESS — it is where this probe's one real bug lived.
    The first version asked, for each side of a non-firing axis, *"is this side's unit declared
    silent?"* and reported `core.cost` as an undeclared cause of `cost_vs_benefit`. `core.cost`
    publishes `effort_bp` on **1,973 of 1,973** completed runs. It is healthy, and it is absent
    from the declarations BECAUSE it is healthy.

    > **A declaration list answers "is this absence declared". It never answers "is there an
    > absence."** That has to be measured first.

    So: a side that publishes its metric is HEALTHY and is reported as such, so nobody is sent to
    fix a working unit. Only a side that publishes nothing is then checked against the
    declarations. Pure, so the rule can be tested without a database — the lesson
    `Domain Expertise/_tools/validate.registry_staleness` already states.
    """
    declared: dict[str, list[tuple[str, str, str]]] = {}
    undeclared: dict[str, list[tuple[str, str]]] = {}
    healthy: dict[str, list[str]] = {}
    for axis in DECLARED_AXES:
        if fired.get(axis):
            continue
        for key in AXIS_SIDES[axis]:
            unit_id, metric = UNIT_FOR_KEY[key]
            if publishes.get((unit_id, metric), 0) > 0:
                healthy.setdefault(axis, []).append(f"{unit_id}.{metric}")
                continue
            note = DECLARED_SILENT.get(unit_id) or DECLARED_NEVER_COMPLETED.get(unit_id)
            if note is not None:
                declared.setdefault(axis, []).append((unit_id, metric, note.mover))
            else:
                undeclared.setdefault(axis, []).append((unit_id, metric))
    return declared, undeclared, healthy


def main() -> int:
    url = os.environ.get("GENIOS_DATABASE_URL")
    if not url:
        print("GENIOS_DATABASE_URL is not set (.env is one level above the repo)", file=sys.stderr)
        return 2
    engine = get_engine(url)
    with engine.connect() as conn:
        conn.execute(text("set transaction read only"))

        total = conn.execute(text(
            "select count(*) from reasoning_reasoner_results "
            "where reasoner_id = :u and status = 'completed'"), {"u": UNIT}).scalar() or 0
        if not total:
            print(f"{UNIT} has no completed runs — nothing to read. "
                  f"That is the roster's question (ALARM A2), not this one.")
            return 0

        counts = dict(conn.execute(text(
            "select (output->'metrics'->>'axis_count')::int, count(*) "
            "from reasoning_reasoner_results where reasoner_id = :u and status = 'completed' "
            "  and output->'metrics' ? 'axis_count' group by 1 order by 1"), {"u": UNIT}).all())
        unavailable = conn.execute(text(
            "select count(*) from reasoning_reasoner_results where reasoner_id = :u "
            "  and status = 'completed' and output->'metrics' ? 'axes_unavailable'"),
            {"u": UNIT}).scalar() or 0
        fired = Counter()
        for (codes,) in conn.execute(text(
                "select output->'reason_codes' from reasoning_reasoner_results "
                "where reasoner_id = :u and status = 'completed'"), {"u": UNIT}).all():
            for code in codes or []:
                if str(code).startswith("tradeoff."):
                    fired[str(code).split(".", 1)[1]] += 1
        span = conn.execute(text(
            "select min(created_at), max(created_at) from reasoning_reasoner_results "
            "where reasoner_id = :u"), {"u": UNIT}).one()

        # ⛔ WHETHER A SIDE IS ABSENT IS A MEASUREMENT, NOT A LOOKUP IN A DECLARATION LIST.
        # The first version of this block asked "is this side's unit declared silent?" and
        # reported `core.cost` as an undeclared cause for `cost_vs_benefit`. `core.cost` publishes
        # `effort_bp` on 1,973 of 1,973 completed runs — it is healthy, and it is absent from the
        # declarations BECAUSE it is healthy. The declarations answer "is this absence declared",
        # never "is there an absence". So the metric is counted first, and only a side that really
        # publishes nothing is then checked against the declarations.
        publishes: dict[tuple[str, str], int] = {}
        for _, unit_id, metric in AXIS_SOURCES:
            publishes[(unit_id, metric)] = conn.execute(text(
                "select count(*) from reasoning_reasoner_results "
                "where reasoner_id = :u and status = 'completed' "
                "  and output->'metrics' ? :m"), {"u": unit_id, "m": metric}).scalar() or 0

    print("=" * 92)
    print(f"{UNIT} · {total} completed runs · {span[0]} -> {span[1]}")
    print(f"declares {len(DECLARED_AXES)} axes: {', '.join(DECLARED_AXES)}")
    print("=" * 92)

    print("\nHOW MANY AXES WERE ACTUALLY COMPARED")
    for n in range(len(DECLARED_AXES) + 1):
        k = counts.get(n, 0)
        bar = "#" * (50 * k // max(1, total))
        flag = ""
        if n == 0 and k:
            flag = "   <- compared NOTHING: four zeros, no findings"
        if n == len(DECLARED_AXES) and not k:
            flag = f"   <- ⛔ NEVER. A {n}-axis comparator that has never compared {n}"
        print(f"  axis_count = {n}  {k:>6} runs  {100*k//max(1,total):>3}%  {bar}{flag}")

    print("\nWHICH AXIS EVER FIRED")
    for axis in DECLARED_AXES:
        n = fired.get(axis, 0)
        print(f"  {axis:<22}{n:>7} firings  "
              + ("⛔ has NEVER fired" if not n else f"{100*n//max(1,total)}% of runs"))

    print("\n`axes_unavailable` (added in S5.U02, publishes only when non-zero)")
    print(f"  occurrences: {unavailable} of {total}"
          + ("   <- awaiting exercise: every stored row predates the field"
             if not unavailable else ""))

    print("\n" + "=" * 92)
    # For each axis that never fired, BOTH of its sides, and whether that side's unit is declared.
    # An axis needs both; naming only one would send a reader to fix half of it.
    silent_sources, undeclared, healthy = classify_lost_axes(fired, publishes)
    if silent_sources:
        print("⛔ AXES LOST TO A DECLARED CAUSE — correct behaviour, and the mover is named:")
        for axis, rows in sorted(silent_sources.items()):
            print(f"      {axis}")
            for unit_id, metric, mover in rows:
                print(f"          needs {unit_id}.{metric}")
                print(f"          mover: {mover}")
    if undeclared:
        print("\n⛔ AXES LOST TO AN UNDECLARED CAUSE — this is the state to act on:")
        for axis, rows in sorted(undeclared.items()):
            print(f"      {axis}")
            for unit_id, metric in rows:
                print(f"          needs {unit_id}.{metric}, and {unit_id} is declared nowhere")
        print("\n   Declare it in reason/unit_health with a reason and a mover, or find out what")
        print("   stopped it. A declared silence with no mover is an undeclared one with paperwork.")
    if healthy:
        print("\n   ...and the sides of those axes that ARE publishing, so nobody fixes a"
              " working unit:")
        for axis, sides in sorted(healthy.items()):
            print(f"      {axis:<22} {', '.join(sides)} — healthy")
    if not silent_sources and not undeclared:
        print("Every declared axis has fired at least once.")
    return 1 if undeclared else 0


if __name__ == "__main__":
    raise SystemExit(main())
