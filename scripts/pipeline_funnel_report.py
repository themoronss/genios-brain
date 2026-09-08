"""Where a tenant's mail went, layer by layer and group by group — read, never re-run.

    python scripts/pipeline_funnel_report.py --org <org_id> --database-url postgresql://…

**WHY THIS EXISTS.** Every layer records what it decided, in its own table, and no surface joins
them. So the only way anybody could answer *"we synced 400 emails — what happened to them?"* was to
open five tables and count by hand, and the honest follow-up (*"why did 44 situations never reach
Layer 3?"*) had no answer at all. A pipeline whose drop reasons are queryable but never queried is
a pipeline nobody can improve.

Nothing here re-runs anything: `event_trace`, `parked_events`, `qualification_drops`,
`qualified_signals`, `situation_admission_decisions`, `reasoning_candidates` and `cards` were all
written as the sweep happened. The transaction is declared `read only` at the SERVER, so a
statement that tried to write would be refused by PostgreSQL rather than by review.

**HOW TO READ IT.** Every section is one layer, and inside it every group is one decision the layer
makes, with the count and — where the layer records one — the reason. A row that says `drop` with
no reason code is a bug in the layer, not in this report.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

BAR = "─" * 78


def _rows(conn, sql: str, org: str, **extra):
    from sqlalchemy import text
    try:
        return conn.execute(text(sql), {"o": org, **extra}).fetchall()
    except Exception as exc:      # noqa: BLE001 — a missing table is a gap, not a crash
        return [("(unavailable)", str(exc)[:60])]


def _section(title: str) -> None:
    print(f"\n{BAR}\n{title}\n{BAR}")


def _table(rows, headers: tuple[str, ...], total: int | None = None) -> None:
    if not rows:
        print("   (nothing)")
        return
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    print("   " + "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)))
    for r in rows:
        line = "  ".join(str(v).ljust(widths[i]) for i, v in enumerate(r))
        if total:
            count = next((v for v in r if isinstance(v, int)), None)
            share = f"   {count * 100 // total:>3}%" if count and total else ""
            line += share
        print("   " + line)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    add_database_argument(ap)
    ap.add_argument("--org", required=True)
    args = ap.parse_args()
    url = resolve_database_url(args, purpose=f"read the pipeline funnel for {args.org}")

    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    org = args.org
    with get_engine(url).connect() as c:
        c.execute(text("set transaction read only"))

        # ───────────────────────────────────────────────────────────── LAYER 1
        _section("LAYER 1 · CAPTURE — what arrived and what survived")
        captured = _rows(c, "select source, object_type, count(*) from source_events "
                            "where org_id=:o group by 1,2 order by 3 desc", org)
        print("\n  1a · what was pulled from the connected tools")
        _table(captured, ("source", "object", "count"))
        landed = sum(r[2] for r in captured if isinstance(r[2], int))

        print("\n  1b · the gate — every decision, with its reason code")
        _table(_rows(c, "select stage, action, coalesce(reason_code,'—') reason, count(*) "
                        "from event_trace where org_id=:o group by 1,2,3 "
                        "order by 4 desc", org),
               ("stage", "action", "reason", "events"), total=landed)

        print("\n  1c · the same decisions, GROUPED BY SOURCE — which tool loses what")
        _table(_rows(c, "select e.source, t.action, coalesce(t.reason_code,'—') reason, count(*) "
                        "from event_trace t join source_events e on e.event_id=t.event_id "
                        "and e.org_id=t.org_id where t.org_id=:o and t.action in "
                        "('drop','park','emit') group by 1,2,3 order by 1, 4 desc", org),
               ("source", "action", "reason", "events"))

        print("\n  1d · parked — held for review, not lost")
        _table(_rows(c, "select reason_code, status, count(*) from parked_events "
                        "where org_id=:o group by 1,2 order by 3 desc", org),
               ("code", "status", "count"))

        print("\n  1e · SIGNALS PUBLISHED — by type, with the importance spread")
        _table(_rows(c, "select signal_type, count(*), min(importance_bp), max(importance_bp), "
                        "count(*) filter (where evidence_refs @> '[{\"verified\": true}]') "
                        "from qualified_signals where org_id=:o group by 1 order by 2 desc", org),
               ("signal type", "count", "min bp", "max bp", "verified"))

        print("\n  1f · refused by the tenant's floor (kept, with the reason)")
        _table(_rows(c, "select signal_type, count(*), max(floor_bp) from qualification_drops "
                        "where org_id=:o group by 1 order by 2 desc", org),
               ("signal type", "dropped", "floor bp"))

        # ───────────────────────────────────────────────────────────── LAYER 2
        _section("LAYER 2 · CONTEXT — the graph, and which situations were admitted")
        print("\n  2a · the graph this built")
        _table(_rows(c, "select 'nodes', count(*) from graph_nodes where org_id=:o "
                        "union all select 'facts', count(*) from graph_facts where org_id=:o "
                        "union all select 'edges', count(*) from graph_edges where org_id=:o", org),
               ("thing", "count"))

        print("\n  2b · situations by type")
        _table(_rows(c, "select situation_type, status, count(*) from context_situations "
                        "where org_id=:o group by 1,2 order by 3 desc limit 15", org),
               ("situation type", "status", "count"))

        print("\n  2c · THE ADMISSION GATE — what reached Layer 3, and why the rest did not")
        admissions = _rows(c, "select outcome, count(*) from situation_admission_decisions "
                              "where org_id=:o group by 1 order by 2 desc", org)
        _table(admissions, ("outcome", "count"))
        print("\n       held for:")
        _table(_rows(c, "select array_to_string(array(select jsonb_array_elements_text("
                        "to_jsonb(reasons))), ' + ') r, count(*) "
                        "from situation_admission_decisions where org_id=:o and outcome='hold' "
                        "group by 1 order by 2 desc", org),
               ("reason", "count"))

        print("\n  2d · ADMISSION BY SITUATION TYPE — which KINDS of situation get through")
        _table(_rows(c, "select s.situation_type, "
                        "count(*) filter (where d.outcome='admit') admitted, "
                        "count(*) filter (where d.outcome='hold') held, "
                        "count(*) filter (where d.outcome='reject') rejected "
                        "from situation_admission_decisions d join context_situations s "
                        "on s.situation_id=d.situation_id and s.org_id=d.org_id "
                        "where d.org_id=:o group by 1 order by 2 desc, 3 desc", org),
               ("situation type", "admitted", "held", "rejected"))

        # ───────────────────────────────────────────────────────────── LAYER 3
        _section("LAYER 3 · EXPERTISE — which corpora compiled for this tenant")
        _table(_rows(c, "select domain, coalesce(enabled_by,'—'), "
                        "case when disabled_at is null then 'live' else 'off' end "
                        "from l3_activation where org_id=:o order by 1", org),
               ("domain", "switched on by", "state"))
        print("\n  3b · packages compiled")
        _table(_rows(c, "select count(*) packages, count(distinct situation_id) situations, "
                        "min(created_at)::date, max(created_at)::date "
                        "from expertise_packages where org_id=:o", org),
               ("packages", "situations", "first", "last"))
        print("\n  3c · WHAT IS INSIDE THE PACKAGES — the four brains, per package")
        _table(_rows(c, "select jsonb_array_length(payload->'capabilities') capabilities, "
                        "jsonb_array_length(payload->'behavior_patterns') behaviour, "
                        "jsonb_array_length(payload->'organization_rules') org_rules, "
                        "jsonb_array_length(payload->'adaptive_preferences') adaptive, "
                        "count(*) packages from expertise_packages where org_id=:o "
                        "group by 1,2,3,4 order by 5 desc limit 8", org),
               ("capabilities", "behaviour", "org rules", "adaptive", "packages"))

        print("\n  3d · packs this tenant runs")
        _table(_rows(c, "select pack_id, state, version from tenant_packs where org_id=:o", org),
               ("pack", "state", "version"))

        # ───────────────────────────────────────────────────────────── LAYER 4
        _section("LAYER 4 · REASONING — what was decided, and how it ranked")
        print("\n  4a · runs")
        _table(_rows(c, "select status, count(*) from reasoning_runs where org_id=:o "
                        "group by 1 order by 2 desc", org), ("status", "runs"))

        print("\n  4b · OUTCOME PER RUN — decided vs deferred, and on what confidence")
        _table(_rows(c, "select outcome_kind, count(*), min(confidence_bp), max(confidence_bp) "
                        "from reasoning_run_outputs where org_id=:o group by 1 order by 2 desc",
                     org),
               ("outcome", "runs", "min bp", "max bp"))

        print("\n  4c · candidates by disposition — the formula's own verdict")
        _table(_rows(c, "select disposition, count(*), min(final_utility_bp), "
                        "max(final_utility_bp), count(distinct final_utility_bp) "
                        "from reasoning_candidates where org_id=:o group by 1 order by 2 desc", org),
               ("disposition", "count", "min bp", "max bp", "distinct"))

        print("\n  4d · which play produced them")
        _table(_rows(c, "select play_id, count(*), max(final_utility_bp) "
                        "from reasoning_candidates where org_id=:o group by 1 "
                        "order by 2 desc limit 12", org),
               ("play", "candidates", "best bp"))

        print("\n  4e · signals emitted")
        _table(_rows(c, "select status, count(*) from signals where org_id=:o group by 1", org),
               ("status", "count"))

        # ───────────────────────────────────────────────────────────── DELIVERY
        _section("DELIVERY · the cards a human actually sees")
        _table(_rows(c, "select urgency_band, state, count(*), min(score), max(score) "
                        "from cards where org_id=:o group by 1,2 order by 3 desc", org),
               ("urgency", "state", "count", "min", "max"))
        print("\n  the cards themselves")
        for row in _rows(c, "select score, urgency_band, headline from cards where org_id=:o "
                            "order by score desc nulls last limit 12", org):
            print(f"   {str(row[0]):>4}  {str(row[1]):<9} {row[2]}")

        # ───────────────────────────────────────────────────────────── ONE LINE
        _section("THE FUNNEL, IN ONE LINE")
        one = _rows(c, """
            select (select count(*) from source_events where org_id=:o),
                   (select count(*) from event_trace where org_id=:o and action='emit'),
                   (select count(*) from qualified_signals where org_id=:o),
                   (select count(*) from context_situations where org_id=:o),
                   (select count(*) from situation_admission_decisions
                      where org_id=:o and outcome='admit'),
                   (select count(*) from reasoning_candidates where org_id=:o),
                   (select count(*) from cards where org_id=:o)""", org)
        if one and len(one[0]) == 7:
            e, em, q, s, a, cand, cards = one[0]
            print(f"\n   {e} captured  →  {em} emitted  →  {q} signals  →  {s} situations  "
                  f"→  {a} admitted  →  {cand} candidates  →  {cards} cards\n")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
