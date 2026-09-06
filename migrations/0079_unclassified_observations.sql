-- L1.4.5 · the OPEN LANE — what the closed vocabulary had no word for, kept instead of dropped.
--
-- WHY A TABLE AT ALL. `ExtractionResult` names 34 kinds of thing. Everything a model notices
-- outside that set has, until now, died at the sink: not at the model, which described it fine,
-- but at the boundary that had nowhere to put it. That is a silent loss with no record that it
-- ever happened, and it is also the only route by which this system could ever learn a pattern
-- nobody anticipated. `context/extract/vocab.py` is the counter-example we already paid for —
-- free-form field names reaching 268 distinct values in ONE org, 192 of them used exactly once.
-- The answer is not "let the model name fields": it is a closed vocabulary PLUS a lane that
-- catches the rest, so the vocabulary grows from evidence and a human decides when it grows.
--
-- NO RULE MAY READ THIS TABLE. Rows here are unreviewed labels the model invented. A rule that
-- matched on one would change behaviour whenever the model's phrasing drifted, which is not a
-- rule. `tests/capture/semantic/test_open_lane.py` asserts it twice — nothing under
-- `genios_engine/packs/` or `genios_engine/reason/` imports `capture/semantic/open_lane.py`, and
-- neither tree so much as names this table in SQL.
--
-- COLUMNS BEYOND THE SPEC'S SKETCH (doc 04, L1.4.5-U1), each for a fault it prevents:
--   proposed_kind      CANONICAL (lowercase snake_case). The grouping key. Without it "Renewal
--                      Risk", "renewal risk" and "renewal_risk" are three candidates that each
--                      stay under the promotion threshold forever, and the discovery report
--                      proposes nothing while the pattern is right there three times over.
--   proposed_kind_raw  the model's own words, kept verbatim, never grouped on — the canonical
--                      form is lossy and the reviewer needs to read what was actually said.
--   span_verdict       WHICH grade L1.5.1 gave the stored receipt (verified / relocated / fuzzy
--                      / unverified / invalid_bounds). `verified` alone cannot distinguish a
--                      byte-exact quote from one found only after whitespace folding, and the
--                      difference is exactly what a reviewer weighs before naming a new kind.
--   promoted_by,       who decided and under which EXTRACTION_SCHEMA_VERSION. Promotion is a
--   promoted_schema_   human act with a code change attached (L1.4.5-U2); a `promoted_to` with
--   version            no author is an unattributable vocabulary change.
--
-- Unverified rows are KEPT, not dropped, matching the ALG-08 policy row for
-- `UnclassifiedObservation` (keep-and-flag, never delete). They are evidence about the
-- EXTRACTOR even when they are not evidence about the world. The discovery report counts only
-- verified rows toward promotion and reports the unverified ones beside them, so a prompt that
-- has started inventing quotes shows up as a column rather than as silence.
--
-- Retention: rolling 180 days unless `promoted_to` is set — a promoted row is the provenance of
-- a vocabulary member and outlives the window. Enforced by
-- `PostgresOpenLaneStore.purge_expired()` on the in-process heartbeat (`run_maintenance_sweep`),
-- not by a new Celery beat: the broker is quota-limited Upstash Redis.
--
-- Tenant erasure: added to `_ORG_SCOPED_TABLES` in `genios_engine/api/account_routes.py`. That
-- loop runs with no try/except by design, so a table missing from it leaks rows past an account
-- deletion; the org FK below is the second lock on the same door.

create table if not exists unclassified_observations (
    observation_id           text primary key,
    org_id                   text not null references orgs(id) on delete cascade,
    event_id                 text not null,
    proposed_kind            text not null,
    proposed_kind_raw        text not null,
    description              text not null,
    quote                    text not null,
    source_ref               text not null,
    start_offset             int  not null,
    end_offset               int  not null,
    confidence_bp            int  not null check (confidence_bp between 0 and 10000),
    verified                 boolean not null default false,
    span_verdict             text not null,
    created_at               timestamptz not null default now(),
    promoted_to              text,
    promoted_by              text,
    promoted_schema_version  text,
    reviewed_at              timestamptz,
    check (end_offset > start_offset)
);

-- The spec's index: one org's lane, newest first — the per-tenant review view.
create index if not exists unclassified_by_kind
    on unclassified_observations (org_id, proposed_kind, created_at desc);

-- The discovery report (L1.4.5-U3) is CROSS-ORG and only ever asks about the unpromoted rows in
-- a 30-day window, so it gets a partial index of its own rather than scanning every org's index.
create index if not exists unclassified_discovery
    on unclassified_observations (proposed_kind, created_at desc)
    where promoted_to is null;

-- Re-capture of one event (a replay, a re-extract) reads the rows it already wrote; the id is
-- content-addressed so that read is also what makes the insert idempotent.
create index if not exists unclassified_by_event
    on unclassified_observations (org_id, event_id, created_at desc);

comment on table unclassified_observations is
  'L1.4.5 open lane: observations the closed extraction vocabulary had no field for. Reviewed weekly, promoted only by a human, NEVER read by a rule (packs/ and reason/ are import- and SQL-fenced from it). 180-day retention unless promoted_to is set.';
comment on column unclassified_observations.proposed_kind is
  'Canonical lowercase snake_case form of the model label — the grouping key for the discovery report. Never a vocabulary member until a human promotes it.';
comment on column unclassified_observations.promoted_to is
  'The vocabulary member this kind became, set by L1.4.5-U2 when a human promoted it. Non-null rows are exempt from the 180-day purge.';
