"""M11.C0.U01 · Which reasoning units are silent, and is the model the reason?

WHY THIS EXISTS. `speedrun008/YCW27/03-PROGRAM.md:92` calls one thing *"the live defect"*:

    "This is the live defect that leaves two of `core.risk`'s three plugins silent."

⛔ THAT CLAIM HAS NO SOURCE. Grepped the whole programme: it appears in that one sentence, with no
query, no measurement and no file:line behind it. M11.C1 was specified on top of it.

This programme has already shipped two confident findings that measurement destroyed:

  * L1 · `no_model_wired = 632` read as "relevance has no model in production". It was ONE lane that
    is model-free on purpose. Rule: **a count without its dimension is not a measurement.**
  * L3 · "nothing guards the graph revision". `reason/runner.py:570` is the guard, with six passing
    tests. Rule: **a guard lives with the reader, not the writer.**

So this script exists to make the third claim either a fact or a retraction, BEFORE code is written
against it.

⛔ THE DIMENSION THAT MATTERS HERE IS THE CLOCK, AND WITHOUT IT THIS REPORT WOULD LIE EXACTLY AS THE
L1 ONE DID. Since **2026-09-25 11:09 UTC** every model call in the product has been refused with
*"You have reached your specified API usage limits"* (L1 STEP-04, owner Rohit). A unit silent because
the model never answered and a unit silent because its source was dropped **look identical in a bare
status histogram**.

So every count below is split into two eras at that instant, and `--assert-measured` REFUSES to
report a verdict when the evidence lies only on the dead side of it. A measurement that cannot
distinguish its two explanations is not a measurement.

WHAT "SILENT" MEANS HERE, precisely. `reasoning_reasoner_results` holds one row per unit per run with
a closed `status`: `completed` · `skipped` · `failed` · `insufficient_context`. A unit is silent when
it was scheduled and did not `complete`. `skip_reason_code` says which kind of silence, and that
column is the difference between a defect and a design.

READ-ONLY BY CONSTRUCTION. One transaction, opened `read only`, so a statement that tried to write is
refused by Postgres rather than by a reviewer. `GENIOS_ALLOW_PROD_WRITE` is neither needed nor
accepted: that variable is named for writes because it was written for writes, and setting it to run
a report is the wrong shape of permission.

USAGE
    export GENIOS_DATABASE_URL="postgresql://..."        # or let it read .env
    .venv/bin/python scripts/l2_unit_silence.py [--org org_...] [--unit core.risk]
    .venv/bin/python scripts/l2_unit_silence.py --assert-measured    # S1's gate
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: The tenant every YCW27 baseline number was taken against.
_PILOT_ORG = "org_e97e86f858ad48b2bbf64b8a"

#: ⛔ THE INSTANT THE MODEL STOPPED ANSWERING. Last successful call, from L1 STEP-03's measurement.
#: Everything after this was produced with no model, and that includes every shadow-pass tally taken
#: since. It is a constant here rather than a query so this script says the same thing on a database
#: whose `llm_costs` has been trimmed by retention.
_OUTAGE_AT = datetime(2026, 9, 25, 11, 9, tzinfo=timezone.utc)

#: `completed` is the only status that means the unit spoke. The other three are kinds of silence,
#: and they are NOT interchangeable — see `_EXPECTED_SILENCE`.
_SPOKE = "completed"

#: ⛔ SILENCE THAT IS CORRECT, and this set is what stops a future reader "fixing" it.
#:
#: `skipped` + `dependency_not_scheduled` is `reason/plan.py:258` doing its job: the unit had NOTHING
#: left to read, so it was dropped and receipted. `plan.py:229` records at length why dropping it is
#: right and why the stricter rule was removed — it cost six units to one absent fact.
#:
#: `insufficient_context` is likewise a real answer: the unit ran and declined to assert. Counting it
#: as a defect is how a refusal that was correct gets engineered away.
#: BOTH branches of `_select`, because both are the same rule applied to the two kinds of input:
#: `dependency_not_scheduled` (plan.py:258) when every declared SOURCE went, and
#: `no_declared_input_available` (plan.py:266) when every declared FIELD is absent. Measured: the
#: second accounts for 3,102 of 26,396 result rows and the first for none — so a set holding only the
#: first would have called every one of those a defect.
_EXPECTED_SILENCE = frozenset({"dependency_not_scheduled", "no_declared_input_available"})

_BY_UNIT = """
    select r.reasoner_id,
           r.status,
           coalesce(r.skip_reason_code, '(none)') as skip_reason,
           case when r.created_at >= :outage then 'after' else 'before' end as era,
           count(*) as n
      from reasoning_reasoner_results r
     where r.org_id = :o
       -- Cast explicitly: Postgres cannot infer the type of a bare NULL parameter and refuses the
       -- whole statement with AmbiguousParameter. Found by running it.
       and (cast(:unit as text) is null or r.reasoner_id = cast(:unit as text))
     group by 1, 2, 3, 4
     order by r.reasoner_id, era, n desc
"""

#: ⛔ WHEN THE PER-UNIT TABLE ITSELF BEGINS. This is the query that overturned this script's first
#: verdict. `reasoning_runs` goes back to 19 Sep, but `reasoning_reasoner_results` starts on
#: 29 Sep 11:07 — FOUR DAYS AFTER the model outage began. So runs existing before the outage proves
#: nothing about the units, and a gate that checked runs (as this one first did) would pass while
#: every unit measurement it reported was taken with no model answering.
_RESULTS_SPAN = """
    select min(created_at) as first_seen, max(created_at) as last_seen, count(*) as n
      from reasoning_reasoner_results
     where org_id = :o
"""

#: How many runs there were at all, per era. Without this a unit with zero rows cannot be told apart
#: from a tenant with zero runs — and "silent" would be claimed about a system that never ran.
#: `started_at`, not `created_at` — `reasoning_runs` has no such column, and naming it made the whole
#: query fail with UndefinedColumn. `mode` rides along because a `shadow` run and a `live` run are
#: different facts, and a silence measured over shadow runs says nothing about production.
_RUNS = """
    select case when started_at >= :outage then 'after' else 'before' end as era,
           mode,
           count(*) as n
      from reasoning_runs
     where org_id = :o
     group by 1, 2
     order by 1, 2
"""

#: ⛔ The model's own record, so the reader can see which side of the outage they are standing on
#: rather than taking this script's constant on trust.
_LLM = """
    select case when created_at >= :outage then 'after' else 'before' end as era,
           purpose,
           sum(case when success then 1 else 0 end) as ok,
           sum(case when success then 0 else 1 end) as failed
      from llm_costs
     where org_id = :o
     group by 1, 2
     order by era, purpose
"""


def _url() -> str:
    """The database, from the environment or from whichever `.env` actually holds it.

    ⛔ The `.env` on this checkout sits one level ABOVE the repo root, not inside it. A script that
    only looked at `_ROOT / ".env"` reported "no url" on a machine that had one — which reads as a
    missing secret and is really a missing directory. Both are checked, nearest first.
    """
    url = os.environ.get("GENIOS_DATABASE_URL")
    if url:
        return url
    for env in (_ROOT / ".env", _ROOT.parent / ".env"):
        if not env.exists():
            continue
        for line in env.read_text().splitlines():
            if line.startswith("GENIOS_DATABASE_URL="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    sys.exit("GENIOS_DATABASE_URL is not set, and no .env beside or above the repo carries one")


def _verdict(unit_rows: list[dict], *, clean_era: bool) -> tuple[str, str]:
    """(verdict, why) for one unit.

    ⛔ `clean_era` is whether ANY per-unit result row predates the model outage. When it is False, no
    unit's silence can be attributed — a unit silent because the model never answered and a unit
    silent because its source was dropped are the same rows. This script's first draft asked whether
    RUNS predated the outage, which is a different question with the opposite answer, and it produced
    a confident verdict on evidence that could not support one.

    That is the L1 `no_model_wired` mistake, reproduced by the very script written to avoid it.
    """
    rows = [r for r in unit_rows if r["era"] == "before"] if clean_era else list(unit_rows)
    spoke = sum(r["n"] for r in rows if r["status"] == _SPOKE)
    total = sum(r["n"] for r in rows)
    reasons = {r["skip_reason"] for r in rows if r["skip_reason"] != "(none)"}
    statuses = sorted({r["status"] for r in rows})

    if not total:
        return "NO ROWS", "this unit has never produced a result row"

    if spoke:
        share = f"{spoke} of {total} completed"
        if not clean_era:
            return "SPEAKS", f"{share} — but every row is outage-era, so the FAILURES are unattributable"
        return "SPEAKS", f"{share}, before the outage"

    # ⛔ EVERY row must be a by-design skip, not merely every REASON. The first version of this
    # check looked only at non-null `skip_reason_code`, so a unit with 53 by-design skips and 532
    # `insufficient_context` rows was labelled SILENT BY DESIGN — hiding the 532, which are the
    # interesting ones. `skipped` means the unit never ran; `insufficient_context` means it RAN and
    # declined to assert. Those are different facts and only the first can be "by design" here.
    by_design = sum(r["n"] for r in rows
                    if r["status"] == "skipped" and r["skip_reason"] in _EXPECTED_SILENCE)
    if by_design == total:
        return "SILENT BY DESIGN", (f"all {total} rows are `skipped` with {sorted(reasons)} — "
                                    f"`_select` receipting a unit that had nothing left to read, "
                                    f"which `plan.py:229` records as the correct rule")

    declined = sum(r["n"] for r in rows if r["status"] == "insufficient_context")
    detail = (f"0 of {total} completed; {by_design} skipped by design, {declined} "
              f"insufficient_context; statuses {statuses}")
    if not clean_era:
        return "UNATTRIBUTABLE", (f"{detail}. \u26d4 Every row is outage-era, so this cannot be told "
                                  f"apart from the model never answering")

    # \u2014 is lifted out of the f-string expression on purpose: a backslash inside the expression
    # part is a SyntaxError until Python 3.12 (PEP 701), and this repo runs 3.11 \u2014 so the file did
    # not parse at all, which broke every gate that AST-walks the source rather than imports it.
    reasons_text = sorted(reasons) or "\u2014"
    return "SILENT", f"{detail}, reasons {reasons_text}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--org", default=_PILOT_ORG)
    ap.add_argument("--unit", default=None, help="one reasoner id, e.g. core.risk")
    ap.add_argument("--assert-measured", action="store_true",
                    help="exit 1 unless at least one run predates the model outage — i.e. unless "
                         "the question is answerable at all. S1's gate.")
    args = ap.parse_args()

    from sqlalchemy import text

    # ⛔ THE APP'S OWN FACTORY, NOT `create_engine`. The project ships psycopg **v3** and SQLAlchemy
    # maps a bare `postgresql://` to psycopg2, which is not installed — so a hand-rolled engine dies
    # on ModuleNotFoundError against a database that is perfectly reachable.
    from genios_engine.platform.db import get_engine

    params = {"o": args.org, "outage": _OUTAGE_AT, "unit": args.unit}
    engine = get_engine(_url())
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("set transaction read only"))
        unit_rows = [dict(r) for r in conn.execute(text(_BY_UNIT), params).mappings()]
        run_rows = [dict(r) for r in conn.execute(text(_RUNS), params).mappings()]
        span = dict(conn.execute(text(_RESULTS_SPAN), params).mappings().first() or {})
        llm = [dict(r) for r in conn.execute(text(_LLM), params).mappings()]

    print(f"\norg: {args.org}")
    print(f"outage boundary: {_OUTAGE_AT.isoformat()}  (L1 STEP-04)\n")

    # ── which side of the outage is the evidence on? ───────────────────────────────────────────
    runs: dict[str, int] = {}
    for r in run_rows:
        runs[r["era"]] = runs.get(r["era"], 0) + r["n"]

    print("REASONING RUNS, by era and mode")
    for r in run_rows:
        print(f"  {r['era']:<7} mode={r['mode']:<12} n={r['n']}")
    print(f"  before the outage : {runs.get('before', 0)}")
    print(f"  after  the outage : {runs.get('after', 0)}")
    if not run_rows:
        print("  none at all — this tenant has never reasoned, so nothing below says anything "
              "about any unit.")

    # ⛔ THE MEASUREMENT WINDOW, stated before any verdict. A report that does not say when its
    # evidence begins cannot be checked, and this is the number that decides every verdict below.
    first_seen = span.get("first_seen")
    clean_era = bool(first_seen and first_seen < _OUTAGE_AT)
    print("\nPER-UNIT RESULT ROWS (reasoning_reasoner_results)")
    print(f"  {span.get('n') or 0} rows, {first_seen} .. {span.get('last_seen')}")
    if first_seen and not clean_era:
        gap = (first_seen - _OUTAGE_AT).days
        print(f"  \u26d4 THIS TABLE BEGINS {gap} DAY(S) AFTER THE OUTAGE STARTED.")
        print("     So `reasoning_runs` predating the outage proves NOTHING about any unit, and no")
        print("     unit's silence below can be told apart from the model never answering.")

    print("\nMODEL CALLS (llm_costs), by era — so you can check the boundary yourself")
    if not llm:
        print("  no rows")
    for r in llm:
        print(f"  {r['era']:<7} {r['purpose']:<24} ok={r['ok']:<6} failed={r['failed']}")

    # ── per unit ──────────────────────────────────────────────────────────────────────────────
    units: dict[str, list[dict]] = {}
    for row in unit_rows:
        units.setdefault(row["reasoner_id"], []).append(row)

    print(f"\nUNITS  (reasoning_reasoner_results)   {len(units)} distinct")
    if not units:
        print("  none — no unit has ever produced a result row for this org.")

    verdicts: dict[str, tuple[str, str]] = {}
    for unit_id in sorted(units):
        verdict, why = _verdict(units[unit_id], clean_era=clean_era)
        verdicts[unit_id] = (verdict, why)
        print(f"\n  {unit_id}  ->  {verdict}")
        print(f"      {why}")
        for row in units[unit_id]:
            print(f"      {row['era']:<7} {row['status']:<22} {row['skip_reason']:<28} "
                  f"n={row['n']}")

    # ── the claim under test ──────────────────────────────────────────────────────────────────
    print("\n" + "=" * 96)
    print("THE CLAIM UNDER TEST — 03-PROGRAM.md:92")
    print('  "the live defect that leaves two of `core.risk`\'s three plugins silent"')
    print("=" * 96)
    risk = {u: v for u, v in verdicts.items() if u.startswith("core.risk")}
    if risk and len(risk) != 3:
        print(f"  \u26d4 THE CLAIM NAMES THREE PLUGINS. {len(risk)} unit id(s) match `core.risk`: "
              f"{sorted(risk)}.")
        print("     There is no plugin layer under a reasoner id, so the sentence describes a")
        print("     structure this codebase does not have.")
    if not risk:
        print("  ⛔ NOT SUPPORTED — no unit id starting `core.risk` has any result row for this org.")
        print("     The claim names three plugins. Zero are present, so the sentence cannot be")
        print("     describing this tenant's data. WITHDRAW it, or name the tenant it came from.")
    else:
        silent = [u for u, (v, _) in risk.items() if v == "SILENT"]
        print(f"  units found: {len(risk)}   silent: {len(silent)}   {sorted(silent)}")
        if len(silent) != 2:
            print("  ⛔ NOT SUPPORTED as written — correct the count in 03-PROGRAM.md.")

    # ⛔ THE GATE ASKS ABOUT THE RESULT ROWS, NOT THE RUNS. Asking about runs is what this script did
    # first, and it answered "yes" on evidence that was entirely outage-era.
    print(f"\nANSWERABLE AT ALL: {'yes' if clean_era else 'NO'}")
    if not clean_era:
        print("  ⛔ Every per-unit result row postdates the model outage. A unit silent because the")
        print("     model never answered is indistinguishable from one silent because its source was")
        print("     dropped. This is the L1 `no_model_wired` mistake, and the gate refuses to repeat")
        print("     it. Re-run once the spend limit is raised and a sweep has completed.")

    if args.assert_measured and not clean_era:
        print("\nFAIL: --assert-measured — the question is not answerable from this data.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
