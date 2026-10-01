#!/usr/bin/env python3
r"""⛔ A unit that COMPLETED and computed NOTHING — the defect no test can see.

READ-ONLY. One `set transaction read only` connection, no writes, no model calls.

WHY THIS EXISTS. On 2026-10-01, with every unit test green and the full suite at 14,397 passed,
production said this:

    core.impact        1,973 completed   100% silent   no finding, no check, no non-zero metric
    core.opportunity   1,088 completed    94% silent

`core.impact` succeeds on every single run and computes nothing. Its status is `completed`, so
`l2_unit_silence.py` — which asks whether a unit SPEAKS — reports it as speaking. Its own module
docstring explains why it is right to be quiet: *"Silence is not zero. A dimension with no evidence
contributes no observation and publishes no metric … a fabricated zero silently lies."* **That
design is correct.** The defect is that nothing downstream can tell its honest silence from a
measurement.

⛔ WHAT IT COST, MEASURED. `core.tradeoff`'s `AXIS_SOURCES` names `benefit_source -> core.impact ->
impact_bp`. `core.impact` never publishes `impact_bp`, so `CostVersusBenefitPlugin` returns no
observation — **0 firings in 1,200 production rows**, while its sibling axes fired 1,163 and 597.
And `tests/reason/test_tradeoff_cost_axis.py::test_the_cost_versus_benefit_axis_produces_an_observation`
**passes**, on synthetic priors.

⛔ A GREEN TEST PROVING AN AXIS WORKS, OVER 1,200 ROWS WHERE IT HAS NEVER SPOKEN. That gap is what
this probe measures, and the unit test cannot: the test supplies the prior, and production does not.

⛔ AND THE CHAIN BEHIND IT. `core.impact`'s three plugins need a deal value or
`core.relationship.coverage_bp`. `core.relationship` has **never completed** — 708
`insufficient_context`, 221 `skipped: no_declared_input_available`. So the silence is inherited, two
units deep, and every link in it is behaving correctly.

⛔ WHY `findings` ALONE IS THE WRONG TEST, and the first version of this probe got it wrong.
Counting empty `findings` reports `core.constraint` (2,681 completions, 0 findings) and
`legacy.score_gate` (708, 0) as broken. Both are fine: their `output_kind` is `candidate_checks`,
and they emit CHECKS. A unit is silent only when it emitted no finding, no check, AND no non-zero
metric. *A crude slice that happens to fail looks exactly like a real finding.*
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text                                              # noqa: E402

from genios_engine.platform.db import get_engine                         # noqa: E402

# ⛔ THE DECLARATION, THE THRESHOLD AND THE SILENCE TEST ARE ALL IMPORTED.
#
# This probe defined all three itself when it was written. `platform/receipts.py` now needs the same
# three, and a second copy would be TWO DECLARATIONS OF ONE FACT — the shape this programme has found
# five times, most recently `unrouted_l2_types`, where a generated list and an independently computed
# one agreed by luck until somebody forgot to regenerate.
#
# `genios_engine/reason/unit_health.py` is the one declaration. This file reads it and keeps nothing.
from genios_engine.reason.unit_health import (                            # noqa: E402
    DECLARED_SILENT, SILENT_THRESHOLD_PCT, drifted, is_silent, undeclared_silent,
)


def _rows(conn):
    return conn.execute(text(
        "select reasoner_id, status, skip_reason_code, output "
        "from reasoning_reasoner_results")).all()


def main() -> int:
    url = os.environ.get("GENIOS_DATABASE_URL")
    if not url:
        print("GENIOS_DATABASE_URL is not set — nothing to measure.")
        return 2

    engine = get_engine(url)
    with engine.connect() as conn:
        # ⛔ READ ONLY, FIRST STATEMENT. This probe answers a question; it may never change the thing
        # it is asking about, and `GENIOS_ALLOW_PROD_WRITE` is named for writes because it was
        # written for writes.
        conn.execute(text("set transaction read only"))
        rows = _rows(conn)

    done, silent, never, skipped = Counter(), Counter(), Counter(), Counter()
    for unit, status, skip, output in rows:
        if status == "completed":
            done[unit] += 1
            if is_silent(output):
                silent[unit] += 1
        else:
            never[unit] += 1
            if skip:
                skipped[f"{unit}:{skip}"] += 1

    print("=" * 92)
    print("A UNIT THAT COMPLETED AND COMPUTED NOTHING")
    print("=" * 92)
    print(f"\n  {'unit':<26}{'completed':>10}{'silent':>8}{'share':>8}   verdict")
    print("  " + "-" * 74)

    offenders: dict[str, int] = {}
    for unit in sorted(done, key=lambda u: -(silent[u] / max(1, done[u]))):
        pct = 100 * silent[unit] // max(1, done[unit])
        if pct >= SILENT_THRESHOLD_PCT:
            offenders[unit] = pct
            verdict = "⛔ SAYS NOTHING, EVER"
        elif pct >= 50:
            verdict = "⚠  mostly silent"
        else:
            verdict = "speaks"
        print(f"  {unit:<26}{done[unit]:>10}{silent[unit]:>8}{pct:>7}%   {verdict}")

    print("\n  Units that have NEVER completed — a different defect, listed so the two are not mixed:")
    only_failed = sorted(set(never) - set(done))
    if not only_failed:
        print("      (none)")
    for unit in only_failed:
        reasons = {k.split(":", 1)[1]: v for k, v in skipped.items() if k.startswith(unit + ":")}
        print(f"      {unit:<26} n={never[unit]:<6} {reasons or '(no skip reason recorded)'}")

    print("\n" + "=" * 92)
    shares = {u: 100 * silent[u] // max(1, done[u]) for u in done}
    new = {u: shares[u] for u in undeclared_silent(shares)}
    speaking_again = drifted(shares)
    if new:
        print("⛔ NEW SILENT UNITS — not declared in reason/unit_health.DECLARED_SILENT.")
        print("   Each completes and computes nothing, and every reader downstream treats its")
        print("   absence as 'no signal here' rather than 'this unit had nothing to read'.\n")
        for unit, pct in sorted(new.items()):
            print(f"      {unit:<26} {pct}% silent")
        print("\n   To declare one, add it with a REASON, a MOVER, a SHARE and a DATE.")
        print("   A declared silence with no mover is an undeclared silence with paperwork.")
    if speaking_again:
        print("✅ DECLARED UNITS THAT NOW SPEAK — update the declaration with the new measurement:")
        for unit in speaking_again:
            was = DECLARED_SILENT[unit]
            print(f"      {unit:<26} was {was.share_pct}% on {was.measured_on}, "
                  f"now {shares.get(unit, 0)}%")
    if not new and not speaking_again:
        print("Silent set unchanged — exactly the declared units, and nothing else:")
        for unit, d in sorted(DECLARED_SILENT.items()):
            print(f"      {unit:<26} {shares.get(unit, 0)}% (declared {d.share_pct}% "
                  f"on {d.measured_on}) · mover: {d.mover}")
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
