-- L1.4.9-U1 · the extraction cache moves from Layer 2 to Layer 1, and gains the two columns
-- that say WHICH READING produced the row.
--
-- WHY A RENAME AT ALL. The table is unchanged in purpose and well-designed: it is what makes a
-- non-deterministic pipeline auditable, and it is what makes heavy L1 LLM affordable — the model
-- runs once per document version, ever. What changed is the layer that owns it. Extraction is a
-- CAPTURE act now (`genios_engine/capture/semantic/`), not a context-graph act, and a table
-- called `l2_*` that only Layer 1 writes is a name that lies to the next reader about where the
-- cost and the replay live. This migration relocates it; it invents nothing.
--
-- THE TWO NEW COLUMNS, and the fault each one closes:
--   profile_id  WHICH extraction profile ran (email | chat | transcript | document | crm_note |
--               structured). The same text read under the `document` profile is a DIFFERENT
--               extraction from the same text read under `email` — different prompt, different
--               emphasis, different tier. It is in the cache KEY for that reason (see
--               capture/semantic/cache.py), and it is also a stored column because a key is a
--               digest: without the column, "how much of this tenant's spend went on documents"
--               and "did the transcript profile regress last week" are both unanswerable, and
--               the only way to find out which prompt produced a stored row would be to guess.
--   tier        WHICH model tier the call was routed to (T1 | T2 | T3, L1.4.10). Deliberately
--               NOT a key component: the tier picks the model, and `model_snapshot` — the exact
--               dated model id — is already in the key. Putting the tier in as well would key on
--               the ROUTE rather than on the thing routed to, so a budget demotion that happened
--               to land on the same model would miss a cache it should have hit, and pay for it.
--               As a column it is what makes `tier_demoted` legible after the fact: persistent
--               demotion means the budget is wrong, not the router.
--
-- NO BACKFILL, and that is correct. Existing rows keep `profile_id`/`tier` null because nothing
-- knows what they were — the L2 lane never had a profile. Inventing 'email' for every historical
-- row would make a fabricated value indistinguishable from a recorded one in exactly the query
-- these columns exist to answer. Null means "written before profiles existed", which is true.
--
-- THE ROWS SURVIVE THE RENAME. This is a rename, not a re-create: `alter table ... rename to`
-- keeps every row, index, constraint and grant. That matters because those rows ARE the money
-- already spent — dropping and recreating would silently re-bill every tenant's whole backlog on
-- the next sync.
--
-- CALLERS UPDATED IN THE SAME CHANGE (the trap this migration sets if half-done): the erasure
-- loop in `api/account_routes.py::_wipe` executes `delete from {tbl}` for every name in
-- `_ORG_SCOPED_TABLES` with NO try/except, by design — so a stale name there does not leak rows,
-- it makes EVERY account deletion and every /reset raise `relation does not exist`. That list,
-- `context/graph_store.py` (cache_get/cache_set), `context/runner.py`, `api/routes.py` and four
-- scripts are updated alongside this file. `tests/capture/semantic/test_extraction_cache.py`
-- runs the real erasure loop against real PostgreSQL so the next rename cannot land half-done.
--
-- Migrations 0004 (create) and 0033 (org FK) are NOT edited — they are applied and immutable;
-- the ledger enforces it by checksum.

-- The rename, guarded so it is a no-op on a database that already carries the new name.
do $$
begin
    if to_regclass('public.l2_extraction_results') is not null
       and to_regclass('public.l1_extraction_results') is null then
        alter table l2_extraction_results rename to l1_extraction_results;
    end if;
end
$$;

-- Only reachable on a database where 0004 never ran. Same shape as 0004's, so a fresh schema
-- built from this file alone is the schema every other database has after the rename.
create table if not exists l1_extraction_results (
    processing_key text primary key,
    org_id         text not null,
    event_id       text not null,
    output         jsonb not null,
    input_tokens   int not null default 0,
    output_tokens  int not null default 0,
    model_snapshot text,
    created_at     timestamptz not null default now()
);

alter table l1_extraction_results add column if not exists profile_id text;
alter table l1_extraction_results add column if not exists tier text;

-- The tier vocabulary is closed and stated in the routing formula (doc 04, L1.4.10-U1), so the
-- database enforces it: a row claiming tier 'haiku' or 'T4' is a router bug, and the cheapest
-- place to find out is the insert that made it. `profile_id` deliberately gets NO such check —
-- that vocabulary grows by promotion (L1.4.5-U2), and a check constraint would make every
-- vocabulary change a schema migration, which is how a closed set becomes a frozen one.
do $$
begin
    if not exists (select 1 from pg_constraint
                    where conrelid = 'public.l1_extraction_results'::regclass
                      and conname = 'l1_extraction_results_tier_check') then
        alter table l1_extraction_results add constraint l1_extraction_results_tier_check
            check (tier is null or tier in ('T1', 'T2', 'T3'));
    end if;
end
$$;

-- The FK from 0033 and the index from 0004 followed the table through the rename, still wearing
-- `l2_` names. Renaming them too costs nothing and stops the next reader concluding there is a
-- second, older table somewhere that these belong to.
do $$
begin
    if exists (select 1 from pg_constraint
                where conrelid = 'public.l1_extraction_results'::regclass
                  and conname = 'l2_extraction_results_org_cascade_fk') then
        alter table l1_extraction_results
            rename constraint l2_extraction_results_org_cascade_fk
                           to l1_extraction_results_org_cascade_fk;
    end if;
end
$$;

-- The org cascade, made a property of THIS file rather than inherited.
--
-- On every existing database the FK arrived with 0033 and followed the table through the rename
-- above, so this block is a no-op. It matters for the `create table if not exists` branch — a
-- database where 0004 never ran would otherwise carry a cache table with an org_id and NO
-- cascade, which is an account-deletion hole that leaves a deleted tenant's extracted sentences
-- behind. `tests/test_account_erasure.py` replays every migration statically and requires the
-- cascade to be visible in the migration text, which is the same requirement stated as a test.
do $$
begin
    if not exists (select 1 from pg_constraint
                    where conrelid = 'public.l1_extraction_results'::regclass
                      and contype = 'f'
                      and conname like '%org%') then
        alter table l1_extraction_results add constraint l1_extraction_results_org_cascade_fk
            foreign key (org_id) references orgs (id) on delete cascade not valid;
    end if;
end
$$;

do $$
begin
    if to_regclass('public.extraction_by_event') is not null then
        alter index extraction_by_event rename to l1_extraction_by_event;
    end if;
    if to_regclass('public.l2_extraction_results_pkey') is not null then
        alter index l2_extraction_results_pkey rename to l1_extraction_results_pkey;
    end if;
end
$$;

create index if not exists l1_extraction_by_event
    on l1_extraction_results (org_id, event_id);

comment on table l1_extraction_results is
  'L1.4.9 extraction replay cache: one row per (org, prompt, schema, model, profile, vocabulary, content) extraction. Was l2_extraction_results. The model runs once per document version, ever; every component that changes the model INSTRUCTIONS is inside processing_key, because 260 cached extractions once survived a prompt fix and hid it.';
comment on column l1_extraction_results.processing_key is
  'sha256 over org_id : prompt_version : schema_version : model_snapshot : profile_id : vocab_fingerprint : content_hash. Built only by capture/semantic/cache.py::cache_key — never assembled at a call site.';
comment on column l1_extraction_results.profile_id is
  'Which extraction profile read this content (L1.4.2). A key component: the same text under the document profile is a different extraction from the same text under email. Null on rows written before profiles existed.';
comment on column l1_extraction_results.tier is
  'Which model tier the call was routed to (L1.4.10). NOT a key component — model_snapshot already pins the model the tier chose. Null on rows written before tiering existed.';
