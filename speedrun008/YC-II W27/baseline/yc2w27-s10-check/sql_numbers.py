"""STEP-10 check, Task B.2: replay chosen golden cases (cassettes only), keep the tenant, run the SQL
that would compute STEP-10's promised numbers FROM WHAT IS STORED, print it, remove the tenant.

Run from the extracted tree at 79d0ff54:
  GENIOS_TEST_DATABASE_URL=.../s10_check_a <repo>/.venv/bin/python sql_numbers.py F14 F25 ...
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
from tests.replays.engine_runner import ORG_PREFIX, pin_scratch_database  # noqa: E402

pin_scratch_database()
from sqlalchemy import text  # noqa: E402

from tests.replays import cassettes  # noqa: E402
from tests.replays.engine_runner import remove_tenant, run_case  # noqa: E402
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import RecordedLLM  # noqa: E402

# ---- 1 · OUR reply time, and THEIRS, per counterparty, from source_events alone (mail) ----------
# A run = consecutive messages in one direction with one counterparty. Our latency = from the FIRST
# inbound of a run to our first outbound after it (the mirror of waiting._reply_gaps).
REPLY_TIMES = """
with msgs as (
  select e.event_id, e.occurred_at, lower(e.actor->>'email') as sender, e.recipients,
         (lower(e.actor->>'email') = any(cast(:ours as text[]))) as is_ours, e.outcome
    from source_events e
   where e.org_id = :o and e.source = 'gmail' and e.object_type = 'email_message'
),
pairs as (
  select m.event_id, m.occurred_at, m.is_ours, m.outcome,
         case when m.is_ours then lower(r.addr) else m.sender end as party
    from msgs m
    left join lateral unnest(m.recipients) as r(addr) on m.is_ours
   where (m.is_ours and r.addr is not null and not (lower(r.addr) = any(cast(:ours as text[]))))
      or (not m.is_ours)
),
runs as (
  select party, is_ours, occurred_at,
         lag(is_ours) over (partition by party order by occurred_at, event_id) as prev
    from pairs
),
starts as (select party, is_ours, occurred_at from runs where prev is distinct from is_ours),
nxt as (
  select party, is_ours, occurred_at,
         lead(occurred_at) over (partition by party order by occurred_at) as next_at
    from starts
)
select party,
       count(*) filter (where not is_ours and next_at is not null)                  as our_n,
       percentile_disc(0.5) within group (order by extract(epoch from (next_at - occurred_at)) / 86400.0)
         filter (where not is_ours and next_at is not null)                        as our_median_days,
       count(*) filter (where is_ours and next_at is not null)                      as their_n,
       percentile_disc(0.5) within group (order by extract(epoch from (next_at - occurred_at)) / 86400.0)
         filter (where is_ours and next_at is not null)                            as their_median_days,
       count(*) filter (where not is_ours and next_at is null)                      as inbound_unanswered_runs,
       count(*) filter (where is_ours and next_at is null)                          as outbound_unanswered_runs
  from nxt group by party order by party
"""

# ---- 2 · the same, from the GRAPH timeline waiting.py reads, split by node type ------------------
GRAPH_TIMELINE = """
select n.node_type, n.display_name, f.field, se.occurred_at
  from graph_source_refs r
  join graph_facts f on f.fact_version_id = r.fact_version_id and f.org_id = r.org_id
  join source_events se on se.event_id = r.event_id
  join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id and n.valid_to is null
 where r.org_id = :o and f.field in ('thread.last_outbound', 'thread.last_inbound')
 order by n.node_type, n.display_name, se.occurred_at
"""

# ---- 3 · a WAVE: outbound by us to >= 3 distinct outside addresses inside 36h; replied; bounced ---
WAVE = """
with sent as (
  select e.event_id, e.occurred_at, e.parent_object_id as thread, lower(r.addr) as rcpt
    from source_events e cross join lateral unnest(e.recipients) as r(addr)
   where e.org_id = :o and e.source = 'gmail' and e.object_type = 'email_message'
     and lower(e.actor->>'email') = any(cast(:ours as text[]))
     and not (lower(r.addr) = any(cast(:ours as text[])))
),
first_send as (select min(occurred_at) as t0 from sent),
wave as (select s.* from sent s, first_send f where s.occurred_at < f.t0 + interval '36 hours')
select (select count(distinct event_id) from wave)                                   as mails_sent,
       (select count(distinct rcpt) from wave)                                       as recipients,
       (select count(distinct w.rcpt) from wave w where exists (
          select 1 from source_events i where i.org_id = :o and i.source = 'gmail'
             and lower(i.actor->>'email') = w.rcpt and i.occurred_at > w.occurred_at)) as replied,
       (select count(distinct w.rcpt) from wave w where exists (
          select 1 from source_events b where b.org_id = :o and b.source = 'gmail'
             and b.parent_object_id = w.thread and b.occurred_at > w.occurred_at
             and lower(b.actor->>'email') ~ '(mailer-daemon|postmaster@|bounces?@)'))     as bounced_by_thread,
       (select count(*) from sent s, first_send f where s.occurred_at >= f.t0 + interval '36 hours') as later_sends,
       (select min(occurred_at) from wave) as first_sent,
       (select max(occurred_at) from wave) as last_sent
"""

# ---- 4 · a BOUNCE tied to the original: same Gmail thread, earlier, sent by us -------------------
BOUNCE = """
select b.event_id as bounce_event, b.outcome as bounce_outcome, b.attention_reason,
       s.event_id as original_event, s.outcome as original_outcome, s.recipients as original_to,
       extract(epoch from (b.occurred_at - s.occurred_at)) as seconds_after
  from source_events b
  join source_events s on s.org_id = b.org_id and s.parent_object_id = b.parent_object_id
       and s.occurred_at <= b.occurred_at and lower(s.actor->>'email') = any(cast(:ours as text[]))
 where b.org_id = :o and lower(b.actor->>'email') ~ '(mailer-daemon|postmaster@|bounces?@)'
"""
BOUNCE_STORED = """
select (select count(*) from raw_payloads p where p.org_id = :o)                         as raw_payloads,
       (select count(*) from prepared_content p where p.org_id = :o)                     as prepared,
       (select count(*) from qualified_signals q where q.org_id = :o
           and q.signal_type = 'delivery_failure')                                       as delivery_failure_signals,
       (select count(*) from graph_observations g where g.org_id = :o
           and g.kind = 'delivery_failure')                                              as delivery_failure_obs
"""

# ---- 5 · a CONNECTOR's rate: intros made, contacts who replied, calls booked ----------------------
CONNECTOR = """
with intros as (
  select distinct lower(r.addr) as contact, e.occurred_at as introduced_at
    from source_events e cross join lateral unnest(e.recipients) as r(addr)
   where e.org_id = :o and e.source = 'gmail' and lower(e.actor->>'email') = :connector
     and not (lower(r.addr) = any(cast(:ours as text[]))) and lower(r.addr) <> :connector
)
select i.contact, i.introduced_at,
       exists (select 1 from source_events x where x.org_id = :o and x.source = 'gmail'
                 and lower(x.actor->>'email') = i.contact and x.occurred_at > i.introduced_at) as replied,
       exists (select 1 from source_events x where x.org_id = :o and x.source = 'gmail'
                 and lower(x.actor->>'email') = any(cast(:ours as text[]))
                 and i.contact = any(select lower(a) from unnest(x.recipients) a)
                 and x.occurred_at > i.introduced_at)                                     as we_wrote,
       exists (select 1 from source_events c where c.org_id = :o and c.source = 'gcal'
                 and i.contact = any(select lower(a) from unnest(c.recipients) a))         as call_on_calendar,
       exists (select 1 from graph_nodes n where n.org_id = :o and n.valid_to is null
                 and lower(n.canonical_key) = i.contact)                                  as person_in_memory
  from intros i order by i.introduced_at
"""


def rows(conn, sql, **kw):
    return [dict(r._mapping) for r in conn.execute(text(sql), kw).fetchall()]


def jsonable(v):
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def main(ids):
    from genios_engine.api import routes
    engine = routes._graph.engine
    cases = {c.case_id: c for c in load_cases()}
    out = {}
    for cid in ids:
        case = cases[cid]
        org = f"{ORG_PREFIX}{cid.lower()}"
        ours = sorted({a.lower() for a in case.founder.addresses})
        rec = {"ours": ours}
        try:
            run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
            rec["misses"] = len(run.misses)
            with engine.connect() as conn:
                rec["reply_times"] = rows(conn, REPLY_TIMES, o=org, ours=ours)
                tl = rows(conn, GRAPH_TIMELINE, o=org)
                rec["graph_timeline"] = [f'{r["node_type"]}:{r["display_name"]} {r["field"]} '
                                         f'{r["occurred_at"].isoformat()}' for r in tl]
                rec["wave"] = rows(conn, WAVE, o=org, ours=ours)
                rec["bounce"] = rows(conn, BOUNCE, o=org, ours=ours)
                rec["bounce_stored"] = rows(conn, BOUNCE_STORED, o=org)
                rec["connector"] = rows(conn, CONNECTOR, o=org, ours=ours,
                                        connector="hello@introly.test")
        except BaseException as e:   # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
        finally:
            remove_tenant(engine, org)
        out[cid] = jsonable(rec)
        print(cid, json.dumps(out[cid], default=str), flush=True)
    with engine.connect() as conn:
        left = conn.execute(text("select count(*) from orgs where id like :p"),
                            {"p": ORG_PREFIX + "%"}).scalar()
    print("GOLDEN_ORGS_LEFT", left, flush=True)
    path = os.environ.get("S10_SQL_OUT")
    if path:
        with open(path, "w") as fh:
            json.dump(out, fh, indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1:])
