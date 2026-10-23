#!/usr/bin/env python3
"""Every production reading GeniOS-011 is blocked on, in one read-only pass, kept as one JSON.

    python scripts/g011_prod_readings.py --org org_... --show-sql        # read the SQL; opens nothing
    GENIOS_TARGET_DATABASE_URL=... GENIOS_ALLOW_PROD_WRITE=1 \
        python scripts/g011_prod_readings.py --org org_... [--out readings.json]

⛔ WHY THIS EXISTS (GeniOS-011 S01.U1). Production has not been read since the 823-commit merge
reached it (F6). Which producer makes Rohit's cards, which switches are on, where the funnel still
loses mail, how many cards a day, what `card_refusals` holds: all unknown, so "fewer and weirder
cards" (F2) cannot be put on a cause. 61 audit items wait on a read-only production read: 60 wrote
their SQL into `blocked_on`, each against its own spelling of the org, and `l3-replay-filed-noise`
described its count without writing it. Run one by one they are 61 copy-pastes and 61 chances to
run one against the wrong tenant. Here they are one command, one connection, one org, and one file
that S01.U4 reads to attribute the loss.

TWO LOCKS, AND THE SECOND ONE IS THE SERVER'S.
  1. `refuse_unless_read` refuses any statement whose first keyword is not SELECT, WITH or SHOW, and
     any text that is more than one statement. Every reading is checked BEFORE the connection is
     opened, so a planted write stops the pass before it touches the database.
  2. The connection's transaction is `read only` from its first statement (`scripts/_gate`). A
     write the keyword check cannot see — a `with x as (delete …) select …`, a `select … into` —
     is refused by Postgres itself.

ONE TRANSACTION, ONE SAVEPOINT PER READING. A failed statement aborts a Postgres transaction, and
production may lack a table a migration never created (whether 0243–0250 are applied is itself an
open item). So each reading runs in its own savepoint: one that fails is written into the JSON as
its error and the readings after it still run. Savepoints are transaction control, not writes, and
the read-only transaction allows them.

THE ORG IS A PARAMETER, NEVER TEXT. `--org` is required, and every per-tenant reading binds it as
`:org`. The audit's queries spelled the org four ways (`'org_e97e…'`, `'<ORG>'`, `:org`,
`'<rohit_org>'`); none survives here. Six readings are facts about the server and carry no org:
`server=True`, a closed set that the test names. Where an audit query read every tenant
(`l4_activation`, `org_channels`, `calibration_runs`, `graph_facts`), it is scoped to the org here.

WHERE THE AUDIT'S SQL WAS WRONG, CORRECTED HERE AND SAID:
  * `learning_object_evaluations` has no `unit` column; the unit lives on `learning_objects`
    (migrations/0045), so `recommendation_learning_evaluations` joins it.
  * `cross-billing-gates-silently-stop-the-org` found Rohit's other orgs by `name ilike
    '%swerashi%'`. Here a sibling org is one that shares the given org's email, which needs no name
    and prints no email.
  * `l3-replay-filed-noise` had a description and no SQL; `noise_events_in_a_file` is that count,
    written from `context/backfill.py`'s own noise test (`graph_observations.kind like
    'email_noise:%'`).

OUTPUT. One JSON, keyed by audit item key: `items[<key>][<reading>]` holds the SQL and its rows, or
its error. A reading several items ask for runs once. Exit 0 when every reading answered, 1 when
some failed (the JSON is still written), 3 when a statement was refused (nothing opened, nothing
written). `GENIOS_ALLOW_PROD_WRITE=1` is what `scripts/_db` asks before it opens production at all;
it is the deliberate act, not a permission to write — this pass cannot write.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import SQLAlchemyError                    # noqa: E402

from scripts._db import add_database_argument                 # noqa: E402
from scripts._db import resolve_database_url                  # noqa: E402
from scripts._gate import read_only_connection                # noqa: E402
from scripts._gate import sql                                 # noqa: E402

UNIT = "GeniOS-011 S01.U1"

#: The bind every per-tenant reading uses, and the only one any reading may use.
ORG_BIND = "org"

#: The first keywords a reading may start with. An allow-list, not a deny-list: `explain analyze`
#: runs the statement it explains, `do` runs a block, `call` runs a procedure — a list of what is
#: forbidden would miss the next one. A pattern rather than a set of bare words: the statement
#: census (`platform/table_coverage`, `platform/statement_plans`) reads a literal 'select' as a
#: statement, and these three words are not one.
READ_KEYWORD = re.compile(r"(?:select|with|show)\Z", re.IGNORECASE)

EXIT_OK = 0
EXIT_SOME_FAILED = 1
EXIT_REFUSED = 3


class RefusedStatement(ValueError):
    """A statement that is not one read. Raised before anything runs, never caught as a reading's
    error: a refused pass is a pass that did not happen."""


#: Comments and quoted text, matched so that what they contain is never read as SQL: a `;` inside
#: a literal is not a second statement, and `/* select */ update …` does not start with SELECT.
_NOT_CODE = re.compile(r"""
      (?P<line>--[^\n]*)
    | (?P<block>/\*.*?\*/)
    | '(?:[^']|'')*'
    | "(?:[^"]|"")*"
    | \$(?P<tag>[A-Za-z_][A-Za-z_0-9]*|)\$.*?\$(?P=tag)\$
""", re.S | re.X)
_FIRST_WORD = re.compile(r"[\s(]*([A-Za-z_]+)")


def _code_of(statement: str) -> str:
    """The statement with comments blanked and every quoted text reduced to an empty literal."""
    return _NOT_CODE.sub(
        lambda m: " " if (m.group("line") or m.group("block")) else "''", statement)


def refuse_unless_read(statement: str) -> str:
    """Return `statement` when it is ONE statement whose first keyword is SELECT, WITH or SHOW;
    raise `RefusedStatement` otherwise. The first lock — the read-only transaction is the second
    (module docstring)."""
    code = _code_of(statement)
    first = _FIRST_WORD.match(code)
    keyword = first.group(1) if first else ""
    if not READ_KEYWORD.match(keyword):
        raise RefusedStatement(
            f"first keyword is {keyword or '(none)'!r}, not SELECT, WITH or SHOW: "
            f"{statement.strip()[:120]!r}")
    if ";" in code.strip().rstrip(";"):
        raise RefusedStatement(f"more than one statement: {statement.strip()[:120]!r}")
    return statement


@dataclass(frozen=True)
class Reading:
    """One query. `server=True` marks a fact about the server (migrations, size, schema), which has
    no org to bind; every other reading binds `:org` and nothing else."""

    name: str
    sql: str
    server: bool = False


def _q(statement: str) -> str:
    """One line, single-spaced: the SQL as the JSON shows it. Safe only because no reading here
    holds a comment or a literal with a run of spaces — `test_g011_prod_readings` runs them all."""
    return " ".join(statement.split())


_READINGS = (
    # ── the pass itself, and what is deployed ──────────────────────────────────────────────────
    Reading("transaction_read_only", "show transaction_read_only", server=True),
    Reading("migrations_since_0191", _q("""
        select filename, applied_at from schema_migrations
         where filename >= '0191' order by filename"""), server=True),
    Reading("screen_followups_0250_columns", _q("""
        select column_name from information_schema.columns
         where table_schema = 'public' and table_name = 'screen_followups'
           and column_name in ('read_by', 'due_phrase') order by 1"""), server=True),
    Reading("database_size", _q("""
        select pg_database_size(current_database()) as bytes,
               pg_size_pretty(pg_database_size(current_database())) as size"""), server=True),
    Reading("largest_tables", _q("""
        select relname as table_name, pg_total_relation_size(relid) as bytes,
               pg_size_pretty(pg_total_relation_size(relid)) as size
          from pg_catalog.pg_statio_user_tables
         order by pg_total_relation_size(relid) desc limit 15"""), server=True),
    Reading("feedback_check_constraints", _q("""
        select conrelid::regclass::text as table_name, conname,
               pg_get_constraintdef(oid) as definition
          from pg_constraint
         where conrelid in ('card_feedback_verdicts'::regclass, 'card_feedback_revisions'::regclass)
           and contype = 'c' order by 1, 2"""), server=True),

    # ── the switches, L1 to L4 ─────────────────────────────────────────────────────────────────
    Reading("l1_semantic_activation", _q("""
        select enabled_at, enabled_by, disabled_at, disabled_by, notes
          from l1_semantic_activation where org_id = :org""")),
    Reading("l2_v2_activation", _q("""
        select analytic_enabled_at, analytic_disabled_at, patterns_enabled_at,
               patterns_disabled_at, enabled_by, notes, updated_at
          from l2_v2_activation where org_id = :org""")),
    Reading("l3_activation", _q("""
        select domain, enabled_at, enabled_by, disabled_at, disabled_by, variant_ids, updated_at
          from l3_activation where org_id = :org order by domain""")),
    Reading("l4_activation", _q("""
        select feature, enabled_at, enabled_by, disabled_at, disabled_by, notes, updated_at
          from l4_activation where org_id = :org order by feature""")),

    # ── the org: plan, billing, kill switches ──────────────────────────────────────────────────
    Reading("org_plan_state", _q("""
        select id, name, company, subscription_tier, plan_status, plan_started_at,
               plan_expires_at, grace_until, credit_period_start, credit_period_end, is_internal,
               activated_at, created_at
          from orgs
         where id = :org or email = (select email from orgs where id = :org)
         order by created_at""")),
    Reading("plan_expired_audit", _q("""
        select org_id, "timestamp" as at, metadata_jsonb from audit_log
         where action = 'plan_expired'
           and org_id in (select id from orgs
                           where id = :org or email = (select email from orgs where id = :org))
         order by 2""")),
    Reading("kill_switches", _q("""
        select key, enabled, updated_at from feature_flags
         where key in ('kill_switch_all', 'kill_switch:' || :org) order by key""")),
    Reading("delivery_holds", _q("""
        select seat_id, channel, delivery_enabled, hold_until, opted_out
          from delivery_preferences
         where org_id = :org
           and (delivery_enabled is false or hold_until is not null or opted_out is true)
         order by 1, 2""")),
    Reading("events_this_credit_period", _q("""
        select count(*) as n from source_events
         where org_id = :org
           and captured_at >= (select coalesce(credit_period_start, plan_started_at, created_at)
                                 from orgs where id = :org)""")),

    # ── L1 capture ─────────────────────────────────────────────────────────────────────────────
    Reading("source_events_since_deploy", _q("""
        select source, outcome, attention, count(*) as n from source_events
         where org_id = :org and captured_at >= '2026-10-18 00:00+00'
         group by 1, 2, 3 order by n desc""")),
    Reading("event_trace_s1_s2_since_deploy", _q("""
        select stage, action, reason_code, count(*) as n from event_trace
         where org_id = :org and at >= '2026-10-18 00:00+00' and stage in ('S1', 'S2')
         group by 1, 2, 3 order by n desc""")),
    Reading("readmitted_attention_since_deploy", _q("""
        select attention_reason, count(*) as n from source_events
         where org_id = :org and attention_reason like 'readmitted:%'
           and captured_at >= '2026-10-18 00:00+00'
         group by 1 order by n desc""")),
    Reading("gmail_events_by_outcome", _q("""
        select outcome, count(*) as n, min(occurred_at) as first_at, max(occurred_at) as last_at
          from source_events where org_id = :org and source = 'gmail'
         group by 1 order by n desc""")),
    Reading("resync_events", _q("""
        select count(*) as n from source_events
         where org_id = :org and dedup_key like '%#resync:%'""")),
    Reading("refused_attachments", _q("""
        select reason_code, status, refetch_failure_kind, count(*) as n from parked_events
         where org_id = :org and reason_code like 'DOC-%'
         group by 1, 2, 3 order by n desc""")),
    Reading("connections_capture_scope", _q("""
        select connection_id, source_type, seat_id, status, created_at,
               capture_scope ->> 'backfill_days' as backfill_days, capture_scope
          from connections where org_id = :org order by created_at""")),
    Reading("l1_sync_runs_since_deploy", _q("""
        select finished_at, source, mode, scanned, emitted, archived, parked, duplicate,
               cursor_exhausted, page_budget_spent, claimed_total, left(error, 200) as error
          from l1_sync_runs
         where org_id = :org and finished_at >= '2026-10-18 00:00+00'
         order by finished_at desc limit 60""")),
    Reading("l1_sync_runs_per_day", _q("""
        select (finished_at at time zone 'UTC')::date as day, count(*) as runs,
               sum(emitted) as emitted, count(*) filter (where error is not null) as errors
          from l1_sync_runs
         where org_id = :org and finished_at >= '2026-10-01 00:00+00'
         group by 1 order by 1""")),
    Reading("sync_jobs_per_day", _q("""
        select (created_at at time zone 'UTC')::date as day, count(*) as sync_jobs
          from sync_jobs where org_id = :org and created_at >= '2026-10-01 00:00+00'
         group by 1 order by 1""")),
    Reading("qualified_signals_by_type_state", _q("""
        select signal_type, state, count(*) as n from qualified_signals
         where org_id = :org group by 1, 2 order by n desc""")),
    Reading("evidence_needs_by_state", _q("""
        select state, count(*) as n from evidence_needs
         where org_id = :org group by 1 order by n desc""")),
    Reading("l2_evidence_needs_by_state", _q("""
        select state, count(*) as n from evidence_needs
         where org_id = :org and need_id like 'l2need:%' group by 1 order by n desc""")),
    Reading("l2_evidence_needs_latest", _q("""
        select need_id, state, created_at from evidence_needs
         where org_id = :org and need_id like 'l2need:%' order by created_at desc limit 20""")),
    Reading("signal_bundles_count", _q("""
        select count(*) as n, max(created_at) as latest from signal_bundles
         where org_id = :org""")),
    Reading("self_identities", _q("""
        select kind, value, declared_by, declared_at from org_self_identities
         where org_id = :org order by kind, value""")),
    Reading("subject_is_us_retirements", _q("""
        select count(*) as n, max(occurred_at) as latest from card_events
         where org_id = :org and cause = 'subject_is_us'""")),
    Reading("company_brief_lines_by_section", _q("""
        select section, status, proposed_by, count(*) as n from company_brief_lines
         where org_id = :org group by 1, 2, 3 order by 1, 2, 3""")),

    # ── L3 context ─────────────────────────────────────────────────────────────────────────────
    Reading("live_situation_multiplicity", _q("""
        select live, count(*) as anchors
          from (select anchor_node_id, count(*) as live from context_situations
                 where org_id = :org and status in ('active', 'partial')
                 group by anchor_node_id) per_anchor
         group by live order by live""")),
    Reading("live_situations_per_anchor", _q("""
        select anchor_node_id,
               count(*) filter (where status in ('active', 'partial')) as live,
               array_agg(distinct domain) as domains,
               array_agg(distinct situation_type) as types
          from context_situations where org_id = :org
         group by anchor_node_id
        having count(*) filter (where status in ('active', 'partial')) > 1
         order by live desc limit 30""")),
    Reading("situations_by_domain_type_status", _q("""
        select domain, situation_type, status, count(*) as n from context_situations
         where org_id = :org group by 1, 2, 3 order by n desc""")),
    Reading("thread_members_without_correlation", _q("""
        select count(*) as n from context_correlation_members m
         where m.org_id = :org and m.joined_via = 'thread'
           and not exists (select 1 from context_correlations c
                            where c.org_id = m.org_id and c.correlation_id = m.correlation_id)""")),
    Reading("events_only_in_missing_correlations", _q("""
        select count(*) as n
          from (select m.event_id from context_correlation_members m
                  left join context_correlations c
                    on c.org_id = m.org_id and c.correlation_id = m.correlation_id
                 where m.org_id = :org
                 group by m.event_id
                having bool_and(c.correlation_id is null)) orphaned""")),
    Reading("events_in_a_file_60d", _q("""
        select se.outcome, se.source, count(*) as events,
               count(*) filter (where exists (
                   select 1 from context_correlation_members m
                     join context_correlations c
                       on c.org_id = m.org_id and c.correlation_id = m.correlation_id
                    where m.org_id = se.org_id and m.event_id = se.event_id)) as in_a_file
          from source_events se
         where se.org_id = :org and se.occurred_at > now() - interval '60 days'
         group by 1, 2 order by events desc""")),
    Reading("l2_processing_runs_stuck", _q("""
        select status, left(last_error, 60) as last_error, count(*) as n
          from l2_processing_runs
         where org_id = :org and status in ('held', 'parked', 'failed')
         group by 1, 2 order by n desc""")),
    Reading("noise_events_in_a_file", _q("""
        select o.kind, count(distinct se.event_id) as events
          from source_events se
          join graph_observations o
            on o.org_id = se.org_id and o.created_by_event_id = se.event_id
         where se.org_id = :org and se.outcome = 'emitted' and o.kind like 'email_noise:%'
           and exists (select 1 from context_correlation_members m
                        where m.org_id = se.org_id and m.event_id = se.event_id)
         group by 1 order by events desc""")),
    Reading("fields_on_both_authority_scales", _q("""
        select field, count(*) as n from graph_facts
         where org_id = :org
         group by field
        having bool_or(authority_rank <= 6) and bool_or(authority_rank > 6)
         order by n desc""")),
    Reading("thread_objectives_by_month", _q("""
        select (date_trunc('month', created_at at time zone 'UTC'))::date as month,
               count(*) as n
          from graph_facts
         where org_id = :org and field = 'thread.objective' and valid_to is null
         group by 1 order by 1""")),

    # ── L2 qualification ───────────────────────────────────────────────────────────────────────
    Reading("expert_reviews_per_day_since_deploy", _q("""
        select (reviewed_at at time zone 'UTC')::date as day, model, status,
               checked ->> 'fate' as fate, count(*) as n
          from expert_reviews
         where org_id = :org and reviewed_at >= '2026-10-18 00:00+00'
         group by 1, 2, 3, 4 order by 1, 2, 3, 4""")),
    Reading("expert_reviews_per_day_30d", _q("""
        select (reviewed_at at time zone 'UTC')::date as day, status, count(*) as n
          from expert_reviews
         where org_id = :org and reviewed_at >= now() - interval '30 days'
         group by 1, 2 order by 1, 2""")),
    Reading("expert_fates_since_deploy", _q("""
        select checked ->> 'fate' as fate, checked ->> 'because' as because, count(*) as n
          from expert_reviews
         where org_id = :org and reviewed_at >= '2026-10-18 00:00+00' and status = 'valid'
         group by 1, 2 order by n desc""")),
    Reading("expert_failures_since_deploy", _q("""
        select status, left(reason, 120) as reason, count(*) as n from expert_reviews
         where org_id = :org and reviewed_at >= '2026-10-18 00:00+00' and status <> 'valid'
         group by 1, 2 order by n desc""")),
    Reading("l2_held_reasons", _q("""
        select checked ->> 'because' as because, count(*) as n from expert_reviews
         where org_id = :org and prompt_version like 'l2-%' and checked ->> 'fate' = 'held'
         group by 1 order by n desc""")),
    Reading("valid_reviews_with_live_situation_by_domain", _q("""
        select s.domain, count(distinct r.file_id) as files
          from expert_reviews r
          join context_situations s on s.org_id = r.org_id and s.anchor_node_id = r.file_id
         where r.org_id = :org and r.status = 'valid' and s.status in ('active', 'partial')
         group by 1 order by files desc""")),
    Reading("valid_reviews_without_situation", _q("""
        select count(distinct r.file_id) as files from expert_reviews r
         where r.org_id = :org and r.status = 'valid'
           and not exists (select 1 from context_situations s
                            where s.org_id = r.org_id and s.anchor_node_id = r.file_id)""")),
    Reading("reasoning_results_by_status_lane", _q("""
        select status, lane, count(*) as n, sum(cost_micro_usd) / 1e6 as usd
          from reasoning_results where org_id = :org
         group by 1, 2 order by n desc""")),
    Reading("reasoning_results_per_day", _q("""
        select (reasoned_at at time zone 'UTC')::date as day, status, count(*) as n
          from reasoning_results where org_id = :org
         group by 1, 2 order by 1, 2""")),
    Reading("reasoning_results_seed_subjects_7d", _q("""
        select (subject_ref like 'seed:%') as seed, status, lane, count(*) as n
          from reasoning_results
         where org_id = :org and reasoned_at > now() - interval '7 days'
         group by 1, 2, 3 order by n desc""")),
    Reading("l2_admissions_by_decision_op", _q("""
        select decision, op, count(*) as n from l2_admissions
         where org_id = :org group by 1, 2 order by n desc""")),
    Reading("signals_by_rule_since_deploy", _q("""
        select (created_at at time zone 'UTC')::date as day, rule_id, count(*) as n
          from signals
         where org_id = :org and created_at >= '2026-10-18 00:00+00'
         group by 1, 2 order by 1, n desc""")),
    Reading("situation_outcomes_since_deploy", _q("""
        select outcome, reason, count(*) as n from situation_outcomes
         where org_id = :org and last_seen_at >= '2026-10-18 00:00+00'
         group by 1, 2 order by n desc""")),
    Reading("llm_calls_per_day", _q("""
        select (created_at at time zone 'UTC')::date as day, count(*) as calls,
               count(*) filter (where not success) as failed,
               sum(input_tokens) as input_tokens, sum(output_tokens) as output_tokens
          from llm_costs
         where org_id = :org and created_at >= '2026-10-01 00:00+00'
         group by 1 order by 1""")),
    Reading("llm_calls_by_purpose_per_day", _q("""
        select (created_at at time zone 'UTC')::date as day, purpose, model, count(*) as calls,
               count(*) filter (where not success) as failed, sum(output_tokens) as output_tokens
          from llm_costs
         where org_id = :org and created_at >= '2026-10-10 00:00+00'
         group by 1, 2, 3 order by 1, 2, 3""")),

    # ── L4 executive ───────────────────────────────────────────────────────────────────────────
    Reading("r_site_calls_per_day", _q("""
        select (created_at at time zone 'UTC')::date as day, site, outcome, count(*) as n
          from l4_r_site_calls
         where org_id = :org and created_at >= '2026-10-10 00:00+00'
         group by 1, 2, 3 order by 1, 2, 3""")),
    Reading("execution_actions_gated", _q("""
        select count(*) filter (where requires_approval) as gated, count(*) as n
          from execution_actions where org_id = :org""")),
    Reading("authority_rules_count", _q("""
        select count(*) as n from authority_rules where org_id = :org""")),

    # ── L5 delivery ────────────────────────────────────────────────────────────────────────────
    Reading("cards_per_day", _q("""
        select (created_at at time zone 'UTC')::date as day, builder_version, output_lane,
               state, count(*) as n
          from cards
         where org_id = :org and created_at >= '2026-10-01 00:00+00'
         group by 1, 2, 3, 4 order by 1, 2, 3, 4""")),
    Reading("cards_per_day_by_template", _q("""
        select (created_at at time zone 'UTC')::date as day, output_lane, template_version,
               state, count(*) as n
          from cards
         where org_id = :org and created_at >= '2026-10-10 00:00+00'
         group by 1, 2, 3, 4 order by 1, 2, 3, 4""")),
    Reading("cards_by_lane_since_11_oct", _q("""
        select builder_version, output_lane, render_mode, state, count(*) as n from cards
         where org_id = :org and created_at >= '2026-10-11 00:00+00'
         group by 1, 2, 3, 4 order by n desc""")),
    Reading("cards_by_capability_since_deploy", _q("""
        select capability_key, builder_version, output_lane, count(*) as n from cards
         where org_id = :org and created_at >= '2026-10-18 00:00+00'
         group by 1, 2, 3 order by n desc""")),
    Reading("open_cards_by_builder_lane", _q("""
        select builder_version, output_lane, count(*) as n from cards
         where org_id = :org and state in ('queued', 'surfaced', 'snoozed')
         group by 1, 2 order by n desc""")),
    Reading("open_cards_per_subject_node", _q("""
        select s.subject_node_id, count(*) as n
          from cards k join signals s on s.signal_id = k.signal_id and s.org_id = k.org_id
         where k.org_id = :org
           and k.state in ('queued', 'surfaced', 'snoozed', 'claimed', 'delivered')
         group by 1 order by n desc limit 30""")),
    Reading("card_refusals_by_rule", _q("""
        select rule, writer, count(*) as n, max(refused_at) as latest from card_refusals
         where org_id = :org and refused_at >= '2026-10-11 00:00+00'
         group by 1, 2 order by n desc""")),
    Reading("card_refusals_per_day", _q("""
        select (refused_at at time zone 'UTC')::date as day, writer, rule, count(*) as n
          from card_refusals
         where org_id = :org and refused_at >= now() - interval '45 days'
         group by 1, 2, 3 order by 1, 2, 3""")),
    Reading("pipeline_counters_per_day", _q("""
        select (sweep_at at time zone 'UTC')::date as day, stage, sum(n) as n
          from pipeline_counters
         where org_id = :org and sweep_at >= now() - interval '30 days'
         group by 1, 2 order by 1, 2""")),
    Reading("funnel_cards_per_day", _q("""
        select (sweep_at at time zone 'UTC')::date as day,
               sum(n) filter (where stage = 'card_delivered') as funnel_cards
          from pipeline_counters
         where org_id = :org and sweep_at >= '2026-10-15 00:00+00'
         group by 1 order by 1""")),
    Reading("garbled_headline_cards", _q("""
        select card_id, builder_version, render_mode, capability_key, level, headline,
               recommended ->> 'what' as move, reject_code, reject_detail, created_at
          from cards
         where org_id = :org
           and (headline ilike '%calendar invite%' or headline ilike '%to body%')
         order by created_at desc limit 50""")),
    Reading("garbled_headline_card_events", _q("""
        select e.card_id, e.kind, e.cause, e.detail -> 'words' as words, e.occurred_at
          from card_events e
         where e.org_id = :org
           and e.card_id in (select card_id from cards
                              where org_id = :org
                                and (headline ilike '%calendar invite%'
                                     or headline ilike '%to body%'))
         order by e.card_id, e.occurred_at limit 200""")),
    Reading("card_feedback_events_since_1_oct", _q("""
        select type, detail ->> 'surface' as surface, detail ->> 'reason' as reason,
               count(*) as n
          from human_events
         where org_id = :org and type like 'card.%' and occurred_at >= '2026-10-01 00:00+00'
         group by 1, 2, 3 order by n desc""")),
    Reading("meeting_followup_cards", _q("""
        select count(*) as followup_cards,
               count(*) filter (where k.state in ('queued', 'surfaced', 'snoozed')) as open_cards,
               min(k.created_at) as first_at, max(k.created_at) as last_at
          from cards k join signals s on s.signal_id = k.signal_id and s.org_id = k.org_id
         where k.org_id = :org and s.capability_id = 'meeting.followup'""")),
    Reading("transcripts_by_status", _q("""
        select status, count(*) as n from transcripts
         where org_id = :org group by 1 order by n desc""")),
    Reading("org_channels", _q("""
        select channel, active, last_digest_date, updated_at from org_channels
         where org_id = :org order by channel""")),
    Reading("morning_briefs_latest", _q("""
        select seat_id, local_date, composed_at from morning_briefs
         where org_id = :org order by local_date desc limit 7""")),

    # ── L6 learning ────────────────────────────────────────────────────────────────────────────
    Reading("calibration_runs_latest", _q("""
        select run_id, status, completed_at, result -> 'would_mute' as would_mute,
               result -> 'would_nudge' as would_nudge, result -> 'rules_scored' as rules_scored
          from calibration_runs where org_id = :org
         order by completed_at desc nulls last limit 5""")),
    Reading("calibration_completed", _q("""
        select max(completed_at) as latest, count(*) as n from calibration_runs
         where org_id = :org and status = 'completed'""")),
    Reading("recommendation_learning_evaluations", _q("""
        select o.unit, e.result_state, e.sink_reason, count(*) as n
          from learning_object_evaluations e
          join learning_objects o on o.org_id = e.org_id and o.learning_id = e.learning_id
         where e.org_id = :org and o.unit = 'recommendation_learning'
         group by 1, 2, 3 order by n desc""")),

    # ── goals ──────────────────────────────────────────────────────────────────────────────────
    Reading("brief_goals_and_in_motion", _q("""
        select section, status, proposed_by, left(text, 120) as text, proposed_at, accepted_at
          from company_brief_lines
         where org_id = :org and section in ('goals', 'in_motion') order by proposed_at""")),
    Reading("brief_reviews_latest", _q("""
        select week_key, outcome, proposed, finished_at from company_brief_reviews
         where org_id = :org order by week_key desc limit 10""")),
    Reading("antler_facts", _q("""
        select field, left(value::text, 160) as value, occurred_at from graph_facts
         where org_id = :org and valid_to is null and value::text ilike '%antler%'
         order by occurred_at desc limit 20""")),
    Reading("antler_expert_reviews", _q("""
        select file_id, status, reviewed_at from expert_reviews
         where org_id = :org and (file_id ilike '%antler%' or review::text ilike '%antler%')
         order by reviewed_at desc limit 10""")),
    Reading("antler_reasoning_results", _q("""
        select subject_ref, status, lane, reasoned_at from reasoning_results
         where org_id = :org
           and (subject_ref ilike '%antler%' or result::text ilike '%antler%')
         order by reasoned_at desc limit 10""")),
)


def _index(readings: tuple[Reading, ...]) -> dict[str, Reading]:
    index: dict[str, Reading] = {}
    for reading in readings:
        if reading.name in index:
            raise ValueError(f"two readings are named {reading.name!r}")
        index[reading.name] = reading
    return index


#: Every reading, by name.
READINGS: dict[str, Reading] = _index(_READINGS)

#: Audit item key → the readings that answer its `blocked_on`. Every item of the GeniOS-011 audit
#: whose `blocked_on` is a SQL read is here — 60 keys (`l1-e2-need-fetchers-armed-off` is listed
#: twice in the audit and holds both its asks) — plus `l3-replay-filed-noise`, whose count was
#: described and never written: 61. Asks that SQL cannot answer (the host's env, the deploy log,
#: the Composio versions) are S01.U3's, not here. The first item runs first, so the proof that the
#: transaction is read only is the first thing read.
ITEMS: dict[str, tuple[str, ...]] = {
    # process
    "process-migrations-applied-unknown": ("transaction_read_only", "migrations_since_0191"),
    "process-switch-state-invisible": (
        "l1_semantic_activation", "l2_v2_activation", "l3_activation", "l4_activation"),
    "process-no-production-number-after-deploy": (
        "l4_activation", "r_site_calls_per_day", "expert_reviews_per_day_since_deploy"),
    "process-823-commit-big-bang-deploy": ("cards_per_day_by_template",),
    "process-no-daily-production-card-health": (
        "cards_per_day", "card_refusals_per_day", "expert_reviews_per_day_30d",
        "reasoning_results_per_day", "pipeline_counters_per_day"),
    # L1
    "l1-post-deploy-funnel-unmeasured": (
        "source_events_since_deploy", "event_trace_s1_s2_since_deploy",
        "qualified_signals_by_type_state", "l1_semantic_activation"),
    "l1-junk-verdict-readmitted-on-snippet": ("readmitted_attention_since_deploy",),
    "l1-e2-need-fetchers-armed-off": ("evidence_needs_by_state", "l2_evidence_needs_latest"),
    "l1-h4-refused-attachments-requeue": ("refused_attachments",),
    "l1-resync-and-history-window": ("connections_capture_scope", "resync_events"),
    "l1-company-brief-gate-dependence": ("company_brief_lines_by_section",),
    "l1-refusal-and-coverage-invisible": ("l1_sync_runs_since_deploy",),
    "l1-e1-bundles-read-only-in-shadow": ("l4_activation", "signal_bundles_count"),
    "l1-deleted-mail-needs-resync": ("gmail_events_by_outcome",),
    "l1-c3-d16-history-window-still-60-days": ("connections_capture_scope",),
    "l1-c2-second-mailbox": ("connections_capture_scope",),
    # L3
    "l3-one-subject-many-situations": ("live_situation_multiplicity", "live_situations_per_anchor"),
    "l3-thread-inherits-reading-correlations": (
        "thread_members_without_correlation", "events_only_in_missing_correlations"),
    "l3-events-outside-any-file": ("events_in_a_file_60d", "l2_processing_runs_stuck"),
    "l3-l2-admissions-shadow-status": ("l4_activation", "l2_admissions_by_decision_op"),
    "l3-domain-routing-fundraising": ("l3_activation", "situations_by_domain_type_status"),
    "l3-two-authority-scales": ("fields_on_both_authority_scales",),
    "l3-replay-filed-noise": ("noise_events_in_a_file",),
    # The audit's verify note adds the repair's own receipt: a card retired as `subject_is_us`
    # (`platform/card_lifecycle.SUBJECT_IS_US`) means `repair_self_identity --apply` has run.
    "l3-d14-d35-self-identity-declaration-and-repair": (
        "self_identities", "subject_is_us_retirements"),
    # L2
    "l2-card-paths-six-producers": (
        "l4_activation", "l3_activation", "cards_by_capability_since_deploy"),
    "l2-l3-binding-no-situation-no-card": (
        "valid_reviews_with_live_situation_by_domain", "valid_reviews_without_situation"),
    "l2-held-card-engineer-template": ("expert_fates_since_deploy",),
    "l2-fallback-to-formula-lanes": (
        "expert_failures_since_deploy", "reasoning_results_by_status_lane"),
    "l2-daily-cap-formula-first": ("signals_by_rule_since_deploy",),
    "l2-cards-precondition-not-enforced": ("l4_activation",),
    "l2-admission-g2-shadow": ("l2_admissions_by_decision_op",),
    "l2-judgment-holds-overdue-and-unknown": ("l2_held_reasons",),
    "l2-i2-first-switch-not-made": ("l4_activation", "reasoning_results_by_status_lane"),
    "l2-evidence-loop-not-armed": ("l2_evidence_needs_by_state",),
    "l2-founder-playbooks-gated-on-unread-review": ("situation_outcomes_since_deploy",),
    "l2-llm-decider-without-fallback-in-production": ("llm_calls_by_purpose_per_day",),
    "l2-a2-a3-per-type-cutover-not-built": ("l4_activation",),
    "l2-founder-office-and-expert-switches-prod-state": ("l3_activation", "l4_activation"),
    "cross-l2-subject-to-file-seam": ("reasoning_results_seed_subjects_7d",),
    # L4
    "l4-approver-and-org-data-writer": ("execution_actions_gated", "authority_rules_count"),
    # L5
    "l5-fewer-cards-refusals-unmeasured": (
        "cards_by_lane_since_11_oct", "card_refusals_by_rule", "cards_per_day"),
    "l5-subject-writer": ("garbled_headline_cards", "garbled_headline_card_events"),
    "l5-c6-person-level-context": ("open_cards_per_subject_node",),
    "l5-card-writer-c1-c2-c6-unbuilt": ("open_cards_per_subject_node",),
    "l5-wrong-without-reason": ("card_feedback_events_since_1_oct",),
    "l5-delivery-only-in-app": ("org_channels",),
    "l5-b3-email-delivery-channel-missing": ("org_channels",),
    "l5-meeting-followup-cards-fail-every-door": ("meeting_followup_cards", "transcripts_by_status"),
    "surfaces-question-and-team-cards-reach-only-the-cards-page": ("open_cards_by_builder_lane",),
    "surfaces-d9-morning-brief-composed-but-no-surface-reads-it": ("morning_briefs_latest",),
    "surfaces-0250-applied-unverified": ("migrations_since_0191", "screen_followups_0250_columns"),
    # L6
    "l6-calibration-shadow-unread": ("calibration_runs_latest",),
    "l6-adaptive-distinct-days-trap": ("recommendation_learning_evaluations",),
    "cross-eight-bugs-of-4-oct": ("feedback_check_constraints", "calibration_completed"),
    # goals
    "goals-g0-ground-partial": ("l4_activation", "l3_activation"),
    "goals-antler-cannot-appear-today": (
        "brief_goals_and_in_motion", "brief_reviews_latest", "antler_facts",
        "antler_expert_reviews", "antler_reasoning_results"),
    "goals-golden-brief-is-pre-curated": ("company_brief_lines_by_section",),
    "goals-thread-objective-history-missing": ("thread_objectives_by_month",),
    # across layers
    "cross-db-tier-never-budgeted": ("database_size", "largest_tables"),
    "cross-billing-gates-silently-stop-the-org": (
        "org_plan_state", "plan_expired_audit", "kill_switches", "delivery_holds",
        "events_this_credit_period", "l1_sync_runs_per_day", "sync_jobs_per_day",
        "cards_per_day", "llm_calls_per_day"),
    "cross-sync-now-runs-a-second-chain": (
        "funnel_cards_per_day", "cards_per_day", "sync_jobs_per_day"),
}


def _refuse_any(readings) -> None:
    """Check every reading before any runs; the refusal names the reading."""
    for reading in readings:
        try:
            refuse_unless_read(reading.sql)
        except RefusedStatement as refused:
            raise RefusedStatement(f"reading {reading.name!r}: {refused}") from None


def _said(exc: SQLAlchemyError) -> str:
    """The driver's own first line ("relation … does not exist", "cannot execute DELETE in a
    read-only transaction"), named by its type — what the reader of the JSON acts on."""
    cause = getattr(exc, "orig", None) or exc
    first = (str(cause).strip().splitlines() or [""])[0]
    return f"{type(cause).__name__}: {first}"


def _read(conn, reading: Reading, org: str) -> dict:
    """Run ONE reading in its own savepoint and keep its rows, or its error. The one place a
    statement reaches the connection, and it is checked first (`test_g011_prod_readings` holds
    that with the AST)."""
    statement = refuse_unless_read(reading.sql)
    params = {} if reading.server else {ORG_BIND: org}
    kept: dict = {"sql": statement}
    try:
        with conn.begin_nested():
            rows = [dict(row) for row in conn.execute(sql(statement), params).mappings()]
    except SQLAlchemyError as exc:
        kept["error"] = _said(exc)
        return kept
    kept["rows"] = rows
    kept["row_count"] = len(rows)
    return kept


def run(conn, org: str) -> dict[str, dict[str, dict]]:
    """Every item's readings on `conn`, keyed by item key. Each reading runs once, in item order,
    and every statement is checked before the first one runs."""
    _refuse_any(READINGS.values())
    done: dict[str, dict] = {}
    items: dict[str, dict[str, dict]] = {}
    for item, names in ITEMS.items():
        for name in names:
            if name not in done:
                done[name] = _read(conn, READINGS[name], org)
        items[item] = {name: done[name] for name in names}
    return items


def _plain(value):
    """JSON for what Postgres hands back: times as ISO text, whole numerics as ints."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return str(value)


def _show() -> None:
    for item, names in ITEMS.items():
        print(f"## {item}")
        for name in names:
            reading = READINGS[name]
            print(f"-- {name}{'  (server)' if reading.server else ''}")
            print(f"{reading.sql};")
        print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the org every per-tenant reading binds")
    ap.add_argument("--out", default=None,
                    help="the JSON to write (default g011-prod-readings-<org>-<UTC date>.json)")
    ap.add_argument("--show-sql", action="store_true",
                    help="print every reading's SQL by item and exit; opens no connection")
    args = ap.parse_args(argv)

    try:
        _refuse_any(READINGS.values())
    except RefusedStatement as refused:
        print(f"refused, nothing opened and nothing written: {refused}", file=sys.stderr)
        return EXIT_REFUSED
    if args.show_sql:
        _show()
        return EXIT_OK

    url = resolve_database_url(args, purpose="GeniOS-011 production readings (read-only)")
    from genios_engine.platform.db import get_engine
    conn = read_only_connection(get_engine(url))
    try:
        items = run(conn, args.org)
    finally:
        conn.close()

    readings = {name: kept for item in items.values() for name, kept in item.items()}
    failed = sorted(name for name, kept in readings.items() if "error" in kept)
    at = datetime.now(timezone.utc)
    out = Path(args.out or f"g011-prod-readings-{args.org}-{at:%Y%m%d}.json")
    out.write_text(json.dumps({
        "unit": UNIT,
        "org": args.org,
        "at": at.isoformat(timespec="seconds"),
        "summary": {"items": len(items), "readings": len(readings), "failed": len(failed)},
        "items": items,
    }, indent=2, ensure_ascii=False, default=_plain) + "\n", encoding="utf-8")

    for name in failed:
        print(f"FAILED  {name}: {readings[name]['error']}")
    print(f"wrote {out}: {len(items)} items, {len(readings)} readings, {len(failed)} failed")
    return EXIT_SOME_FAILED if failed else EXIT_OK


if __name__ == "__main__":        # pragma: no cover
    raise SystemExit(main())
