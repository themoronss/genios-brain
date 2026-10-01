-- 0188 · `pipeline_counters` — the five numbers that turn "we made 28 cards" into a diagnosis.
--
-- WHAT WAS WRONG. Grepped 2026-09-30 across `genios_engine/` and `migrations/`:
--
--     signals_detected      0 hits
--     situations_formed     0 hits
--     capability_resolved   0 hits
--     decision_emitted      0 hits
--     card_delivered        0 hits
--
-- So the product could say how many cards it produced and nothing else. "We produced 28 cards" and
-- "we produced 28 cards out of 4,000 signals and lost 3,900 at a step nobody can name" are the same
-- sentence today.
--
-- EVERY LAYER IN THIS PROGRAMME HAS FOUND AT LEAST ONE DEFECT A FUNNEL COUNT WOULD HAVE SURFACED
-- YEARS EARLIER: `l4_bundle` at 0 successes from 600 calls; a five-day total model outage, twice;
-- 467 situations held with nobody asking why; three modules built, tested, green and called by
-- nothing. Each one was found by hand, by reading the graph against the cards.
--
-- ⛔ ONE ROW PER STAGE, NEVER ONE WIDE ROW. A wide row needs every stage to have run before it can
-- be written, so a sweep that dies at stage three writes nothing at all — losing exactly the
-- measurement that would explain the death. Per-stage rows mean a partial funnel is still a funnel,
-- and "stages 1 and 2 wrote, 3 did not" is itself the diagnosis.
--
-- ⛔ AND A COUNT OF ZERO IS WRITTEN, NOT SKIPPED. A missing row and a real zero are different facts:
--
--     situations_formed = 0   the stage RAN and formed nothing
--     (no row)                nobody looked
--
-- This is the same distinction coverage draws between `None` and `0` one layer down, and this
-- programme has already been caught by it twice — `no_model_wired` in L1 and the graph-revision
-- guard in L3 were both "a count read without knowing what it was a count OF". `n` is therefore
-- NOT NULL, and a stage that ran writes its row whatever the number.
--
-- HOW IT IS BOUNDED. Five rows per sweep per tenant, and the primary key is the sweep — so a
-- re-run of the same sweep overwrites rather than appending a second opinion. That matters here:
-- `expertise_packages` put this database into read-only at 181 MB over 345 rows by appending per
-- sweep, and an unbounded counter table sampled every drain is the same shape.

create table if not exists pipeline_counters (
    org_id     text        not null references orgs (id) on delete cascade,

    --: The sweep this count belongs to. One id per pass, so five rows share it and the funnel for
    --: one pass is a single-key read.
    sweep_id   text        not null,

    --: One of the five, and the vocabulary is CLOSED by the check below. An open vocabulary makes
    --: "is the funnel complete?" unanswerable: a typo becomes a sixth stage nobody notices.
    stage      text        not null,

    --: ⛔ NOT NULL. Zero means the stage ran and counted nothing. No row means nobody looked.
    n          bigint      not null,

    --: The sweep's ONE instant, carried so a funnel can be read by time without joining.
    sweep_at   timestamptz not null,

    written_at timestamptz not null default now(),

    --: The sweep, not the clock — a re-run of one sweep overwrites its own row rather than
    --: appending a second, disagreeing observation of the same pass.
    primary key (org_id, sweep_id, stage),

    constraint pipeline_counters_stage_check
        check (stage in ('signals_detected', 'situations_formed', 'capability_resolved',
                         'decision_emitted', 'card_delivered')),

    --: A negative count is not a small count; it is a broken writer.
    constraint pipeline_counters_n_is_not_negative check (n >= 0)
);

-- The funnel read: this tenant's most recent sweeps, newest first.
create index if not exists pipeline_counters_by_sweep
    on pipeline_counters (org_id, sweep_at desc);

-- "Which stage is losing everything?" — one stage across time.
create index if not exists pipeline_counters_by_stage
    on pipeline_counters (org_id, stage, sweep_at desc);

comment on table pipeline_counters is
  'The five-stage funnel: signals_detected -> situations_formed -> capability_resolved -> '
  'decision_emitted -> card_delivered. One row per stage per sweep, written by the stage that owns '
  'it. A zero is written; a missing row means the stage did not run.';
