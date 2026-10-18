"""STEP-08 · the check: can a mail the old gate DELETED be landed again, and how?

Production holds 258 Gmail messages the pre-STEP-03 gate dropped: a `source_events` row with
`outcome = 'dropped'`, no payload, no prepared text. The golden set can reproduce exactly that
shape: run a case through today's chain (its noise mail is ARCHIVED, STEP-03), then rewrite those
rows to what production holds — `dropped`, payload and prepared text gone, no attention tier.

Then it measures, per case:
  1. a re-sync as it is today       — the same messages listed again land as `duplicate`;
  2. `unread.set_aside`              — frees nothing: it matches `outcome = 'emitted'` only;
  3. the orphan recovery hazard      — a dropped row set aside the way `set_aside` does, met by
                                       `recover_orphans` before its message lands again, comes
                                       back as `emitted` with no payload;
  4. the key freed, outcome kept     — the same messages listed again land through today's gate,
                                       with their content;
  5. the finish                      — every old row whose key the new capture took is
                                       `superseded`; nothing else changes.

No model spend: every model answer comes from the case's cassette. Run from the repo root:

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/<fresh db> .venv/bin/python <this file> out.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path.cwd()
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from tests.replays.cassettes import load  # noqa: E402
from tests.replays.engine_runner import (_connectors, _land, pin_scratch_database,  # noqa: E402
                                         pinned_world, production_switches, remove_tenant,
                                         run_case)
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import RecordedLLM  # noqa: E402

CASES = ("F01", "F02", "F03", "F09", "F16", "F32")
FREED = "#resync:"


def _rows(c, org):
    return c.execute(text(
        "select se.event_id, se.source_object_id, se.object_type, se.outcome, se.dedup_key, "
        "       se.attention, (select count(*) from raw_payloads p where p.org_id = se.org_id "
        "                        and p.event_id = se.event_id) as payloads, "
        "       (select count(*) from prepared_content q where q.org_id = se.org_id "
        "                        and q.event_id = se.event_id) as prepared "
        "  from source_events se where se.org_id = :o and se.source = 'gmail' "
        " order by se.source_object_id, se.captured_at"), {"o": org}).mappings().all()


def _relist(routes, case, org, llm, tag):
    """List the case's mail again through the production sync door, sweep by sweep, exactly as the
    run listed it — the junk filter is asked about the same page, so its recorded answer serves."""
    mailbox, _calendar = _connectors()
    outcomes = Counter()
    with production_switches(llm), pinned_world(f"golden:{case.case_id}:{tag}"):
        for sweep, at in enumerate(case.sweeps):
            mail = [o for o in case.objects_in(sweep) if o.source == "gmail"]
            if mail:
                landed = _land(routes, case, org, sweep, at, mailbox(mail), "gmail")
                outcomes.update(item.outcome for item in landed)
    return outcomes


def measure(case):
    from genios_engine.api import routes
    from genios_engine.capture.landing.unread import recover_orphans, set_aside

    llm = RecordedLLM(load(case))
    run = run_case(case, llm, keep=True)
    engine = routes._graph.engine
    org = run.org_id
    out = {"case": case.case_id, "title": case.title}
    try:
        with engine.begin() as c:
            archived = [r for r in _rows(c, org) if r["outcome"] == "archived"]
            out["archived_by_todays_gate"] = len(archived)
            ids = [r["event_id"] for r in archived]
            if not ids:
                out["note"] = "nothing archived — nothing the old gate would have deleted"
                return out
            # ── production's shape: dropped, content gone, no tier ──────────────────────────
            c.execute(text("update source_events set outcome = 'dropped', attention = null, "
                           "attention_reason = null where org_id = :o and event_id = any(:ids)"),
                      {"o": org, "ids": ids})
            for table in ("raw_payloads", "prepared_content"):
                c.execute(text(f"delete from {table} where org_id = :o and event_id = any(:ids)"),
                          {"o": org, "ids": ids})
        # 1 · a re-sync as it is today
        out["relist_today"] = dict(_relist(routes, case, org, llm, "relist"))
        # 2 · set_aside on a dropped row
        out["set_aside_frees"] = set_aside(engine, org, ids)
        # 3 · the orphan hazard, on ONE row, then put back exactly as it was
        probe = ids[0]
        with engine.begin() as c:
            c.execute(text("update source_events set outcome = 'superseded', "
                           "dedup_key = dedup_key || '#superseded:' || event_id "
                           "where org_id = :o and event_id = :e"), {"o": org, "e": probe})
        recovered = recover_orphans(engine, org)
        with engine.begin() as c:
            row = c.execute(text("select outcome, (select count(*) from raw_payloads p where "
                                 "p.org_id = se.org_id and p.event_id = se.event_id) as payloads "
                                 "from source_events se where org_id = :o and event_id = :e"),
                            {"o": org, "e": probe}).mappings().one()
            out["orphan_recovery"] = {"rows_recovered": recovered, "outcome_after": row["outcome"],
                                      "payloads_after": int(row["payloads"])}
            c.execute(text("update source_events set outcome = 'dropped' "
                           "where org_id = :o and event_id = :e"), {"o": org, "e": probe})
        # 4 · free the keys, keep the outcome
        with engine.begin() as c:
            freed = c.execute(text(
                "update source_events set dedup_key = dedup_key || :m || event_id "
                " where org_id = :o and event_id = any(:ids) and outcome = 'dropped' "
                "   and position(:m in dedup_key) = 0"),
                {"o": org, "ids": ids, "m": FREED}).rowcount
        out["keys_freed"] = freed
        out["relist_after_freeing"] = dict(_relist(routes, case, org, llm, "resync"))
        # 5 · the finish
        with engine.begin() as c:
            done = c.execute(text(
                "update source_events old set outcome = 'superseded' "
                " where old.org_id = :o and old.outcome = 'dropped' "
                "   and position(:m in old.dedup_key) > 0 "
                "   and exists (select 1 from source_events n where n.org_id = old.org_id "
                "                and n.dedup_key = split_part(old.dedup_key, :m, 1))"),
                {"o": org, "m": FREED}).rowcount
            rows = _rows(c, org)
        out["superseded_by_finish"] = done
        new = [r for r in rows if r["event_id"] not in ids and r["outcome"] != "superseded"]
        out["after"] = {
            "old_rows": dict(Counter(r["outcome"] for r in rows if r["event_id"] in ids)),
            "relanded": dict(Counter(f'{r["outcome"]}/{r["attention"]}' for r in new
                                     if r["source_object_id"] in
                                     {a["source_object_id"] for a in archived})),
            "relanded_without_payload": sum(
                1 for r in new if r["source_object_id"] in {a["source_object_id"] for a in archived}
                and r["payloads"] == 0),
        }
        # a second pass changes nothing
        out["relist_again"] = dict(_relist(routes, case, org, llm, "again"))
        out["model_misses"] = len(getattr(llm, "misses", ()) or ())
    finally:
        remove_tenant(engine, org)
    return out


def main() -> int:
    pin_scratch_database()
    cases = {c.case_id: c for c in load_cases()}
    results = []
    for cid in CASES:
        try:
            results.append(measure(cases[cid]))
        except BaseException as exc:      # a cassette miss is a BaseException — record it, go on
            results.append({"case": cid, "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
    Path(sys.argv[1]).write_text(json.dumps(results, indent=1, default=str) + "\n")
    for r in results:
        print(json.dumps(r, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
