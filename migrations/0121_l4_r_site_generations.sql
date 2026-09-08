-- Z4 / L4.5 · the per-SITE generation cache for R-1, R-3 and R-4.
--
-- WHY THIS IS NOT A COLUMN ON l4_reasoning_bundles (migration 0120). That table holds ONE narrative
-- per published decision, and these three sites do not fit that shape:
--
--   R-1  is keyed on a FACT DIGEST and has no decision at all — it runs BEFORE the units do, and
--        its output is evidence the deterministic half then reasons over. Doc 09 case 12 is the
--        requirement: "the same ambiguous claim interpreted differently across drains" is closed by
--        caching per claim VERSION, which is a key no decision row can carry.
--   R-3  is asked for on card expand (doc 11 §1: "on card expand only"), which for most decisions
--        never happens. A column on the bundle row would be null for the ~75% of cards nobody
--        opens, and a cache whose common state is null is a cache that answers the wrong question.
--   R-4  travels with the bundle today, and on demand beside R-3 when a card is expanded without a
--        bundle having been generated. One key covers both.
--
-- THE KEY IS THE CONTENT ADDRESS, NOT THE DECISION. `cache_key` is
-- semantic_hash(site, org, prompt_version, seed) — see `reason/llm_sites.cache_key`. The prompt
-- version is INSIDE it, so editing a prompt invalidates the cache instead of serving prose the new
-- prompt would never have produced (doc 09 case 10, closed at the key rather than by remembering to
-- purge), and the site id is inside it so two sites reading one decision never collide.
--
-- WHAT IS DELIBERATELY ABSENT. No TTL and no invalidation trigger. A generation is a function of the
-- key, the key covers everything the generation was made from, and an entry that can never be wrong
-- does not need an expiry — it needs a different key when the inputs change, which is what it has.
-- The row is small (one JSON fragment of a few hundred characters) and cascades with the org.

create table if not exists l4_r_site_generations (
    org_id     text        not null references orgs (id) on delete cascade,

    -- 'R-1' | 'R-3' | 'R-4'. Free text with the vocabulary enforced in reason/llm_sites.py, for the
    -- reason migration 0116 gives about features: a sixth site is a wave, not a schema event.
    site       text        not null,
    cache_key  text        not null,

    -- The VALIDATED payload — what the site's own parser accepted, never the raw generation. A
    -- rejected generation is a row in l4_r_site_calls and nothing here: the cache holds only prose
    -- that already passed, which is what makes serving it without re-validation correct.
    payload    jsonb       not null,

    -- 'llm:<model>@<version>' or 'template_fallback', the closed vocabulary
    -- contracts.reasoning.require_generation enforces. Stored beside the payload so a cache HIT
    -- reports the generation that produced the prose rather than the generation of the read.
    generation text        not null,

    created_at timestamptz not null default now(),

    primary key (org_id, site, cache_key)
);

-- "What has this tenant cached today, and is the cache actually being hit" — doc 11's acceptance
-- row is a cache hit rate above 60% on re-surfaced decisions, and that is measured over time.
create index if not exists l4_r_site_generations_org_created
    on l4_r_site_generations (org_id, created_at desc);

comment on table l4_r_site_generations is
  'Layer 4.5 · validated generations for the R-1/R-3/R-4 sites, keyed on the content address of the consult (site + org + prompt version + seed). A re-surfaced decision never regenerates; a prompt edit never serves stale prose, because the prompt version is inside the key.';
comment on column l4_r_site_generations.payload is
  'The parser-accepted payload only. A rejected generation is receipted in l4_r_site_calls and cached nowhere.';
